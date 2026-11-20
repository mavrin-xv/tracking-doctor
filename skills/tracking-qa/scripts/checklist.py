#!/usr/bin/env python3
"""Turn a tracking plan into a test checklist a person can tick off before a release.

  python checklist.py plan.csv > tracking-test.md
  python checklist.py plan.csv --site https://staging.shop.example --out tracking-test.md

Reads the same plan.csv as event-audit (step, vendor, event, required, count) and
writes one section per step: what to do, what must fire, where to look for it, plus
the fixed release checks (consent, reload, ad blocker, server events, counts).
Exit: 0 written, 2 bad input.
"""
import argparse
import csv
import sys
from collections import OrderedDict

WHERE = {
    "ga4": "GA4 DebugView (Admin, DebugView) with the debug_mode param or Tag Assistant",
    "meta": "Meta Events Manager, Test Events tab",
    "posthog": "PostHog Activity, filtered by your test distinct_id",
    "gads": "Tag Assistant, Google Ads conversion tag",
    "tiktok": "TikTok Events Manager, Test Events",
    "linkedin": "LinkedIn Campaign Manager, Insight Tag status",
    "uet": "Microsoft UET Tag Helper",
}

FIXED = """## Release checks (every release that touches pages, checkout or tags)

- [ ] Capture runs clean: `capture.py --steps steps.json` then `audit.py capture.jsonl --plan plan.csv` exits 0.
- [ ] Reload the thank-you page: no purchase event fires again (plan rows with count 0).
- [ ] Open the thank-you page from a second tab or the order email link: no second purchase.
- [ ] Consent, accept: tags fire after the click, Google hits carry gcs=G111.
- [ ] Consent, reject: no ad hits, no `_fbp` or `_gcl_*` cookies; `consent.py` exits 0 on both captures.
- [ ] Land with `?gclid=TEST&utm_source=test&utm_medium=test`: `leaks.py --capture` shows them carried.
- [ ] Ad blocker on: the order still saves, and the server-side events still go out.
- [ ] Server events: payloads pass `mp_check.py`; Meta CAPI event_id equals the browser eid.
- [ ] No email, phone or name in any URL or param that a vendor receives.
- [ ] Next day: `reconcile.py counts` shows every tool inside its usual band against the backend.
- [ ] Test orders are marked or refunded so they do not stay in revenue reports.
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan")
    ap.add_argument("--site", default="the staging site")
    ap.add_argument("--out")
    a = ap.parse_args()
    steps = OrderedDict()
    try:
        with open(a.plan, newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
                if r.get("event"):
                    steps.setdefault(r.get("step", ""), []).append(r)
    except FileNotFoundError:
        print(f"{a.plan}: not found", file=sys.stderr)
        sys.exit(2)
    if not steps:
        print(f"{a.plan}: no rows", file=sys.stderr)
        sys.exit(2)
    out = [f"# Tracking test: {a.site}", "",
           "Tester: ____  Date: ____  Build or release: ____", "",
           "Use a fresh private window per run. Note the test order id here: ____", ""]
    for i, (step, rows) in enumerate(steps.items(), 1):
        out.append(f"## {i}. {step}")
        out.append("")
        for r in rows:
            cnt = r.get("count") or "1"
            req = r.get("required", "").replace(";", ", ")
            where = WHERE.get(r.get("vendor", "").lower(), "the vendor's debug view")
            if cnt == "0":
                out.append(f"- [ ] {r['vendor']} `{r['event']}` does NOT fire here. Check in {where}.")
            else:
                times = "at least once" if cnt == "1+" else f"exactly {cnt}x"
                params = f", with {req}" if req else ""
                out.append(f"- [ ] {r['vendor']} `{r['event']}` fires {times}{params}. Check in {where}.")
        out.append("")
    out.append(FIXED)
    text = "\n".join(out)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(text)
        print(f"wrote {a.out} ({len(steps)} steps)")
    else:
        print(text)


if __name__ == "__main__":
    main()
