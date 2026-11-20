#!/usr/bin/env python3
"""Check what fires before and after the visitor answers the cookie banner.

Record two captures with event-capture: one where the visitor accepts, one where
they reject. Name the step that clicks the banner button.

  python consent.py capture.jsonl --consent-step consent-accept
  python consent.py capture.jsonl --consent-step consent-accept \\
      --reject capture-reject.jsonl --reject-step consent-reject --mode advanced

Mode (Google Consent Mode):
  basic     Google tags are blocked until consent: no GA4 or Ads hit before it.
  advanced  Google tags load and may send cookieless pings before consent, but
            only with gcs=G100 (both storages denied) and without setting _ga.
Other vendors (Meta, TikTok, LinkedIn, Microsoft, PostHog) have no such mode
here: any hit before consent, or after a reject, is a FAIL.

Checks:
  C01 BEFORE_CONSENT   ad or analytics hit before the banner answer
  C02 GCS_BEFORE       Google hit before consent says storage is granted (gcs not G100)
  C03 NO_GCS           Google hit without a gcs param (Consent Mode not set up)
  C04 COOKIE_BEFORE    tracking cookie set before the answer
  C05 NO_UPDATE        after accept, Google hits still say G100 (the update never reached the tag)
  C06 SILENT_AFTER     after accept, a vendor that should run sends nothing
  C07 AFTER_REJECT     ad hit, granted gcs or tracking cookie after reject
gcs reading: G1xy, x = ad_storage, y = analytics_storage, 1 granted, 0 denied
(from public write-ups, Google does not document it; see references/consent-signals.md).
Exit: 0 no FAIL, 1 at least one FAIL, 2 bad input.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trackhits  # noqa: E402

GOOGLE = {"ga4", "gads"}
ADS = {"meta", "tiktok", "linkedin", "uet", "gads"}
COOKIE = re.compile(r"^(_ga|_ga_.*|_gid|_gat.*|_gcl_.*|_fbp|_fbc|_ttp|_tt_.*|_uet.*|li_.*|lidc|bcookie|ph_.*_posthog|_hj.*|_clck|_clsk)$")


def split(records, step):
    order = trackhits.step_order(records)
    if step not in order:
        sys.exit(f"step {step!r} not in capture; steps are: {', '.join(map(str, order))}")
    i = order.index(step)
    return set(order[:i]), set(order[i:])


def cookies_in(records, steps):
    names = set()
    for r in records:
        if r.get("kind") == "cookies" and r.get("step") in steps:
            names.update(c["name"] for c in r["cookies"] if COOKIE.match(c["name"]))
    return names


def hits_in(records, steps):
    return [h for r in records if r.get("step") in steps for h in trackhits.parse_request(r) if not h.get("loader")]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("capture", help="capture where the visitor accepts")
    ap.add_argument("--consent-step", required=True, help="step name that clicks Accept")
    ap.add_argument("--reject", help="capture where the visitor rejects")
    ap.add_argument("--reject-step", help="step name that clicks Reject")
    ap.add_argument("--mode", choices=["basic", "advanced"], default="advanced")
    ap.add_argument("--expect", default="ga4,meta,posthog",
                    help="vendors that must send after accept (default ga4,meta,posthog)")
    a = ap.parse_args()
    rows = []

    def add(state, check, where, detail):
        rows.append((state, check, where, detail))

    recs = trackhits.load_records(a.capture)
    before, after = split(recs, a.consent_step)
    # the banner click itself can be read either way; only steps strictly before count as "before"
    pre = hits_in(recs, before)
    post = hits_in(recs, after)

    seen = set()
    for h in pre:
        key = (h["vendor"], h["event"])
        if key in seen:
            continue
        seen.add(key)
        where = f"{h['step']} / {h['vendor']} {h['event']}"
        if h["vendor"] in GOOGLE:
            if not h.get("gcs"):
                add("FAIL", "C03 NO_GCS", where, "no gcs param: Consent Mode is not running on this tag")
            elif a.mode == "basic":
                add("FAIL", "C01 BEFORE_CONSENT", where, f"Google hit before consent in basic mode (gcs={h['gcs']})")
            elif h["gcs"] != "G100":
                add("FAIL", "C02 GCS_BEFORE", where, f"gcs={h['gcs']} before consent; expected G100")
            else:
                add("PASS", "advanced ping", where, "cookieless ping with gcs=G100, allowed in advanced mode")
        else:
            add("FAIL", "C01 BEFORE_CONSENT", where, "fired before the visitor answered the banner")

    early = cookies_in(recs, before)
    google_cookies = {c for c in early if c.startswith(("_ga", "_gid", "_gat", "_gcl"))}
    for c in sorted(early):
        add("FAIL", "C04 COOKIE_BEFORE", c, "set before the banner answer"
            + (" (advanced mode must not set Google cookies either)" if c in google_cookies else ""))

    for h in post:
        if h["vendor"] in GOOGLE and h.get("gcs") == "G100":
            add("FAIL", "C05 NO_UPDATE", f"{h['step']} / {h['vendor']} {h['event']}",
                "still gcs=G100 after accept: the consent update does not reach the tag")
            break
    sent = {h["vendor"] for h in post}
    for v in [x.strip() for x in a.expect.split(",") if x.strip()]:
        if v not in sent:
            add("FAIL", "C06 SILENT_AFTER", v, "no hits after accept")
        else:
            add("PASS", "after accept", v, f"{sum(1 for h in post if h['vendor'] == v)} hits")

    if a.reject:
        if not a.reject_step:
            sys.exit("--reject needs --reject-step")
        rrecs = trackhits.load_records(a.reject)
        _, rafter = split(rrecs, a.reject_step)
        rseen = set()
        for h in hits_in(rrecs, rafter):
            where = f"reject: {h['step']} / {h['vendor']} {h['event']}"
            key = (h["vendor"], h["event"])
            if key in rseen:
                continue
            if h["vendor"] in ADS and h["vendor"] not in GOOGLE:
                rseen.add(key)
                add("FAIL", "C07 AFTER_REJECT", where, "ad hit after the visitor said no")
            elif h["vendor"] in GOOGLE and h.get("gcs") and h["gcs"] != "G100":
                rseen.add(key)
                add("FAIL", "C07 AFTER_REJECT", where, f"gcs={h['gcs']} after reject")
            elif h["vendor"] == "posthog":
                rseen.add(key)
                add("WARN", "C07 AFTER_REJECT", where, "PostHog event after reject; fine only if it runs cookieless by design")
        for c in sorted(cookies_in(rrecs, rafter)):
            add("FAIL", "C07 AFTER_REJECT", f"reject: cookie {c}", "tracking cookie present after reject")

    gcd = sorted({h["gcd"] for h in pre + post if h.get("gcd")})
    print(f"mode: {a.mode}; before consent: steps {', '.join(sorted(map(str, before))) or 'none'}")
    if gcd:
        print(f"gcd values seen (format not documented by Google, read with care): {', '.join(gcd)}")
    order = {"FAIL": 0, "WARN": 1, "PASS": 2}
    rows.sort(key=lambda r: order[r[0]])
    w = max([len(r[2]) for r in rows] + [10])
    for state, check, where, detail in rows:
        print(f"{state:<5} {check:<18} {where:<{w}}  {detail}")
    fails = sum(1 for r in rows if r[0] == "FAIL")
    print(f"\n{fails} FAIL, {sum(1 for r in rows if r[0] == 'WARN')} WARN")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
