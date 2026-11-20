#!/usr/bin/env python3
"""Shared parser: turns captured network requests into tracking hits.

A capture file is JSON lines. Each line is one record:
  {"kind": "request", "step": "...", "t": 1.23, "page": "...", "method": "GET",
   "url": "...", "body": "..." or null, "body_encoding": "utf8" | "base64"}
  {"kind": "nav", "step": "...", "t": 0.4, "url": "...", "from": "..." or null}
  {"kind": "cookies", "step": "...", "t": 2.0, "cookies": [{"name": "...", "domain": "..."}]}

parse_request() returns a list of hits (one request can carry several events):
  {"vendor", "event", "tag_id", "params", "order_id", "event_id", "gcs", "gcd",
   "value", "currency", "url", "step", "t", "page"}

The same file is copied into every skill that reads captures. Edit the copy in
skills/event-capture/scripts/, then copy it to the others.
Run directly to print the hits in a capture: python trackhits.py capture.jsonl
"""
import base64
import gzip
import json
import re
import sys
from urllib.parse import parse_qsl, unquote, urlsplit

# (vendor, kind, host regex, path regex). kind "hit" = an event beacon,
# "loader" = a tag library download (useful to see which tags load at all).
# "verified" tells how sure we are of the pattern; see references/vendor-patterns.md.
PATTERNS = [
    ("ga4", "hit", r"(^|\.)(google-analytics\.com|analytics\.google\.com)$", r"^/g/collect", "capture"),
    ("ga4-mp", "hit", r"(^|\.)google-analytics\.com$", r"^/(debug/)?mp/collect", "docs"),
    ("meta", "hit", r"(^|\.)facebook\.com$", r"^/tr/?$", "docs+capture"),
    ("gads", "hit", r"(^|\.)googleadservices\.com$", r"^/pagead/conversion/", "unverified"),
    ("gads", "hit", r"(^|\.)google\.[a-z.]+$", r"^/pagead/1p-conversion/", "unverified"),
    ("gads", "hit", r"(^|\.)(googletagmanager\.com|google\.[a-z.]+)$", r"^/ccm/collect", "unverified"),
    ("posthog", "hit", r"(^|\.)i\.posthog\.com$", r"^/(i/v0/e|e|batch|capture|track)/?$", "docs (i/v0/e, batch)"),
    ("tiktok", "hit", r"(^|\.)analytics\.tiktok\.com$", r"^/api/v2/pixel", "unverified"),
    ("linkedin", "hit", r"(^|\.)px\.ads\.linkedin\.com$", r"^/(collect|wa)", "unverified"),
    ("uet", "hit", r"(^|\.)bat\.bing\.com$", r"^/action/", "unverified"),
    ("gtm", "loader", r"(^|\.)googletagmanager\.com$", r"^/(gtm\.js|gtag/js)", "docs"),
    ("meta", "loader", r"(^|\.)connect\.facebook\.net$", r"/fbevents\.js$", "docs"),
    ("posthog", "loader", r"(^|\.)(i\.posthog\.com|assets\.i\.posthog\.com)$", r"/static/array", "docs"),
]
_COMPILED = [(v, k, re.compile(h, re.I), re.compile(p, re.I), s) for v, k, h, p, s in PATTERNS]

# Extra hosts that should be read as PostHog (a reverse proxy on your own domain).
EXTRA_POSTHOG_HOSTS = set()

PURCHASE_EVENTS = {"purchase", "Purchase", "order_completed", "conversion", "CompletePayment"}


def classify(url):
    """Return (vendor, kind) for a URL, or (None, None)."""
    u = urlsplit(url)
    host = (u.hostname or "").lower()
    if host in EXTRA_POSTHOG_HOSTS and re.match(r"^/(i/v0/e|e|batch|capture)/?$", u.path):
        return "posthog", "hit"
    for vendor, kind, h, p, _ in _COMPILED:
        if h.search(host) and p.search(u.path):
            return vendor, kind
    return None, None


def decode_body(rec):
    """Body as text, or "" when it cannot be read."""
    body = rec.get("body")
    if not body:
        return ""
    raw = body.encode("utf-8") if rec.get("body_encoding", "utf8") == "utf8" else base64.b64decode(body)
    if raw[:2] == b"\x1f\x8b":
        try:
            raw = gzip.decompress(raw)
        except OSError:
            return ""
    return raw.decode("utf-8", "replace")


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _hit(vendor, event, rec, **kw):
    h = {"vendor": vendor, "event": event, "tag_id": None, "params": {}, "order_id": None,
         "event_id": None, "gcs": None, "gcd": None, "value": None, "currency": None,
         "url": rec.get("url"), "step": rec.get("step"), "t": rec.get("t"), "page": rec.get("page")}
    h.update(kw)
    return h


def _ga4(rec, q, body):
    lines = [ln for ln in body.splitlines() if ln.strip()] or [""]
    hits = []
    for ln in lines:
        p = dict(q)
        p.update(dict(parse_qsl(ln, keep_blank_values=True)))
        params = {}
        for k, v in p.items():
            if k.startswith("ep.") or k.startswith("epn."):
                params[k.split(".", 1)[1]] = v
        hits.append(_hit("ga4", p.get("en"), rec, tag_id=p.get("tid"), params=params,
                         order_id=params.get("transaction_id") or None, gcs=p.get("gcs"), gcd=p.get("gcd"),
                         value=_num(params.get("value")), currency=p.get("cu") or params.get("currency"),
                         raw=p))
    return hits


def _meta(rec, q, body):
    p = dict(q)
    if body and "=" in body and not body.lstrip().startswith("{"):
        p.update(dict(parse_qsl(body, keep_blank_values=True)))
    cd = {k[3:-1]: v for k, v in p.items() if k.startswith("cd[") and k.endswith("]")}
    return [_hit("meta", p.get("ev"), rec, tag_id=p.get("id"), params=cd, event_id=p.get("eid") or None,
                 order_id=cd.get("order_id"), value=_num(cd.get("value")), currency=cd.get("currency"), raw=p)]


def _posthog_events(body):
    txt = body.strip()
    if txt.startswith("data="):
        txt = unquote(txt[5:])
    if txt and not txt.startswith(("{", "[")):
        try:
            txt = base64.b64decode(txt + "=" * (-len(txt) % 4)).decode("utf-8", "replace")
        except (ValueError, UnicodeDecodeError):
            return []
    try:
        data = json.loads(txt)
    except ValueError:
        return []
    key = data.get("api_key") if isinstance(data, dict) else None
    if isinstance(data, dict) and "batch" in data:
        data = data["batch"]
    events = data if isinstance(data, list) else [data]
    for ev in events:
        if isinstance(ev, dict) and key and not ev.get("api_key"):
            ev["api_key"] = key
    return events


def _posthog(rec, q, body):
    hits = []
    for ev in _posthog_events(body):
        if not isinstance(ev, dict):
            continue
        props = ev.get("properties") or {}
        hits.append(_hit("posthog", ev.get("event"), rec, tag_id=ev.get("api_key") or props.get("token"),
                         params=props, event_id=ev.get("uuid"), order_id=props.get("order_id"),
                         value=_num(props.get("value") or props.get("revenue")), currency=props.get("currency"),
                         distinct_id=ev.get("distinct_id") or props.get("distinct_id")))
    return hits


def _gads(rec, q, body):
    path = urlsplit(rec["url"]).path.strip("/").split("/")
    tag = q.get("tid") or (path[2] if len(path) > 2 else None)
    # /ccm/collect carries en= (page_view, conversion); conversion pixels have no event name
    return [_hit("gads", q.get("en") or "conversion", rec, tag_id=tag, params=dict(q), order_id=q.get("oid") or None,
                 value=_num(q.get("value")), currency=q.get("currency_code"), label=q.get("label"),
                 gcs=q.get("gcs"), gcd=q.get("gcd"))]


def _generic(vendor, rec, q, body):
    p = dict(q)
    event = p.get("evt") or p.get("ea") or p.get("event") or p.get("conversionId")
    if body.strip().startswith("{"):
        try:
            data = json.loads(body)
            event = event or data.get("event")
            p.update({k: v for k, v in data.items() if isinstance(v, (str, int, float))})
        except ValueError:
            pass
    return [_hit(vendor, event, rec, tag_id=p.get("ti") or p.get("pid") or p.get("pixel_code"), params=p)]


def parse_request(rec):
    if rec.get("kind", "request") != "request":
        return []
    vendor, kind = classify(rec.get("url", ""))
    if not vendor:
        return []
    if kind == "loader":
        return [_hit(vendor, "(tag loaded)", rec, loader=True)]
    q = dict(parse_qsl(urlsplit(rec["url"]).query, keep_blank_values=True))
    body = decode_body(rec)
    if vendor == "ga4":
        return _ga4(rec, q, body)
    if vendor == "meta":
        return _meta(rec, q, body)
    if vendor == "posthog":
        return _posthog(rec, q, body)
    if vendor == "gads":
        return _gads(rec, q, body)
    if vendor == "ga4-mp":
        return [_hit("ga4-mp", e.get("name"), rec, params=e.get("params", {}))
                for e in (json.loads(body).get("events", []) if body.strip().startswith("{") else [])]
    return _generic(vendor, rec, q, body)


def load_records(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                sys.exit(f"{path}:{n}: not a JSON line")
    return out


def load_hits(path, include_loaders=False):
    hits = []
    for rec in load_records(path):
        for h in parse_request(rec):
            if include_loaders or not h.get("loader"):
                hits.append(h)
    return hits


def step_order(records):
    order = []
    for r in records:
        s = r.get("step")
        if s not in order:
            order.append(s)
    return order


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0 if len(sys.argv) == 2 else 2)
    for h in load_hits(sys.argv[1], include_loaders=True):
        extra = " ".join(f"{k}={h[k]}" for k in ("order_id", "event_id", "value", "currency", "gcs") if h.get(k))
        print(f"{h['step'] or '-':<16} {h['vendor']:<8} {str(h['event']):<22} {h['tag_id'] or '-':<14} {extra}")
