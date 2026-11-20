#!/usr/bin/env python3
"""Lint server-side analytics payloads before they go out, and validate GA4 ones
against Google's debug endpoint.

  python mp_check.py ga4 payload.json                 lint only, no network
  python mp_check.py ga4 payload.json --debug         POST to /debug/mp/collect (writes no data)
  python mp_check.py posthog payload.json             lint a PostHog capture or batch body

GA4 needs GA4_MEASUREMENT_ID and GA4_API_SECRET in the environment for --debug.
Add --region eu to use region1.google-analytics.com. The secret is never printed.

GA4 limits checked (Measurement Protocol reference, see references/ga4-mp.md):
  25 events per request, 25 params per event, event and param names up to 40
  characters, param values up to 100, 25 user properties (name 24, value 36),
  reserved names and prefixes, timestamp_micros at most 72 hours old, body under
  130 kB, client_id or app_instance_id present.
Working rule, not a Google limit: events without session_id in params are not tied
to a session, so session-scoped reports show them without a source.

PostHog: api_key, event and distinct_id present (PostHog answers 200 and drops
events without them), distinct_id up to 200 characters, a uuid on events you may
resend, timestamp in ISO 8601.
Exit: 0 no FAIL (WARN allowed) and debug endpoint empty, 1 FAIL, 2 bad input or setup.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

RESERVED_EVENTS = {"ad_activeview", "ad_click", "ad_exposure", "ad_impression", "ad_query", "ad_reward",
                   "adunit_exposure", "app_background", "app_clear_data", "app_exception", "app_install",
                   "app_remove", "app_store_refund", "app_update", "app_upgrade", "dynamic_link_app_open",
                   "dynamic_link_app_update", "dynamic_link_first_open", "error", "first_open", "first_visit",
                   "in_app_purchase", "notification_dismiss", "notification_foreground", "notification_open",
                   "notification_receive", "notification_send", "os_update", "session_start", "user_engagement"}
RESERVED_PARAM_PREFIX = ("_", "firebase_", "ga_", "google_", "gtag.")
RESERVED_UP_PREFIX = ("_", "firebase_", "ga_", "google_")
RESERVED_UP = {"first_open_time", "first_visit_time", "last_deep_link_referrer", "user_id", "first_open_after_install"}
NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def lint_ga4(p, raw_len):
    out = []
    if raw_len > 130 * 1024:
        out.append(f"body is {raw_len} bytes, over 130 kB")
    if not (p.get("client_id") or p.get("app_instance_id")):
        out.append("no client_id (web) or app_instance_id (app): the hit cannot be tied to a user")
    events = p.get("events") or []
    if not events:
        out.append("no events")
    if len(events) > 25:
        out.append(f"{len(events)} events, limit 25 per request")
    now = time.time() * 1e6
    for label, ts in [("request", p.get("timestamp_micros"))] + [(f"event {i}", e.get("timestamp_micros")) for i, e in enumerate(events)]:
        if ts is not None and now - float(ts) > 72 * 3600 * 1e6:
            out.append(f"{label}: timestamp_micros older than 72 hours")
    ups = p.get("user_properties") or {}
    if len(ups) > 25:
        out.append(f"{len(ups)} user properties, limit 25")
    for k, v in ups.items():
        val = v.get("value") if isinstance(v, dict) else v
        if len(k) > 24:
            out.append(f"user property {k!r}: name over 24 characters")
        if k in RESERVED_UP or k.startswith(RESERVED_UP_PREFIX):
            out.append(f"user property {k!r}: reserved name or prefix")
        if val is not None and len(str(val)) > 36:
            out.append(f"user property {k!r}: value over 36 characters")
    for i, e in enumerate(events):
        n = e.get("name", "")
        tag = f"event {i} {n!r}"
        if not NAME.match(n or ""):
            out.append(f"{tag}: name must start with a letter and use only letters, digits and _")
        if len(n) > 40:
            out.append(f"{tag}: name over 40 characters")
        if n in RESERVED_EVENTS:
            out.append(f"{tag}: reserved event name")
        params = e.get("params") or {}
        if len(params) > 25:
            out.append(f"{tag}: {len(params)} params, limit 25")
        for k, v in params.items():
            if len(k) > 40:
                out.append(f"{tag}: param {k!r} name over 40 characters")
            if k.startswith(RESERVED_PARAM_PREFIX):
                out.append(f"{tag}: param {k!r} uses a reserved prefix")
            if isinstance(v, str) and len(v) > 100:
                out.append(f"{tag}: param {k!r} value over 100 characters")
        if "session_id" not in params:
            out.append(f"{tag}: no session_id in params (working rule: it will show without a session source)")
        if n == "purchase":
            if not params.get("transaction_id"):
                out.append(f"{tag}: purchase without transaction_id")
            if "value" in params and not params.get("currency"):
                out.append(f"{tag}: value without currency")
    return out


def lint_posthog(p):
    out = []
    events = p.get("batch") if isinstance(p, dict) and "batch" in p else [p]
    key = p.get("api_key") if isinstance(p, dict) else None
    for i, e in enumerate(events):
        tag = f"event {i} {e.get('event')!r}"
        if not (e.get("api_key") or key or (e.get("properties") or {}).get("token")):
            out.append(f"{tag}: no api_key")
        if not e.get("event"):
            out.append(f"{tag}: no event name (PostHog returns 200 and drops it)")
        did = e.get("distinct_id") or (e.get("properties") or {}).get("distinct_id")
        if not did:
            out.append(f"{tag}: no distinct_id (PostHog returns 200 and drops it)")
        elif len(str(did)) > 200:
            out.append(f"{tag}: distinct_id over 200 characters")
        if not e.get("uuid"):
            out.append(f"{tag}: no uuid; a retry can create a second copy")
        ts = e.get("timestamp")
        if ts:
            try:
                datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            except ValueError:
                out.append(f"{tag}: timestamp {ts!r} is not ISO 8601")
    return out


def debug_ga4(body, region, endpoint=None):
    mid, secret = os.environ.get("GA4_MEASUREMENT_ID"), os.environ.get("GA4_API_SECRET")
    if not (mid and secret):
        print("set GA4_MEASUREMENT_ID and GA4_API_SECRET in the environment for --debug", file=sys.stderr)
        sys.exit(2)
    host = "region1.google-analytics.com" if region == "eu" else "www.google-analytics.com"
    base = endpoint or f"https://{host}/debug/mp/collect"
    url = f"{base}?measurement_id={mid}&api_secret={secret}"
    print(f"POST {base}?measurement_id={mid}&api_secret=***")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            res = json.loads(r.read().decode("utf-8") or "{}")
    except (urllib.error.URLError, ValueError) as e:
        print(f"debug endpoint call failed: {e}", file=sys.stderr)
        sys.exit(2)
    msgs = res.get("validationMessages", [])
    for m in msgs:
        print(f"  {m.get('validationCode')}: {m.get('fieldPath')}: {m.get('description')}")
    print("debug endpoint: no validation messages" if not msgs else f"debug endpoint: {len(msgs)} messages")
    return len(msgs)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=["ga4", "posthog"])
    ap.add_argument("payload", help="JSON body as you would send it")
    ap.add_argument("--debug", action="store_true", help="GA4 only: send to the debug endpoint")
    ap.add_argument("--region", choices=["global", "eu"], default="global")
    ap.add_argument("--endpoint", help="override the debug URL (a proxy, or a local mock for tests)")
    a = ap.parse_args()
    raw = open(a.payload, "rb").read()
    try:
        p = json.loads(raw.decode("utf-8-sig"))
    except ValueError as e:
        sys.exit(f"{a.payload}: not JSON ({e})")
    problems = lint_ga4(p, len(raw)) if a.kind == "ga4" else lint_posthog(p)
    warn = [x for x in problems if "no session_id" in x or "no uuid" in x]
    fail = [x for x in problems if x not in warn]
    for x in fail:
        print(f"FAIL  {x}")
    for x in warn:
        print(f"WARN  {x}")
    print(f"{len(fail)} FAIL, {len(warn)} WARN in {a.payload}")
    bad = len(fail)
    if a.debug:
        if a.kind != "ga4":
            sys.exit("--debug is for GA4 only; PostHog has no validation endpoint")
        bad += debug_ga4(raw, a.region, a.endpoint)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
