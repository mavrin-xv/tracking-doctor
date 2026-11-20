# How it works

## Data flow

```
 steps.json ──► capture.py ──► capture.jsonl ──┬─► audit.py      (+ plan.csv)
 or a HAR file   (Playwright,    requests,      ├─► consent.py    (+ reject capture)
                  vendors         navigations,  └─► leaks.py      (+ GA4 source export)
                  answered        cookie names
                  locally)

 server payload.json ─────────────────────────────► mp_check.py  (+ debug endpoint)
 counts.csv, orders.csv, tool export ─────────────► reconcile.py
 plan.csv ────────────────────────────────────────► checklist.py ──► test checklist
```

`trackhits.py` turns raw requests into hits: vendor, event, tag id, params, order id, event
id, consent signals, value and currency. It is the only file that knows vendor URL formats.
The same copy sits in event-capture, event-audit, consent-check and attribution-leaks so each
skill works alone after install.

## Why requests, not the dataLayer

A dataLayer push is an intent. A request is what the vendor received. Double containers,
blocked tags, consent that never updates and redirects that drop click ids only show up in
requests. The method follows the analytics testing approach in petrkindlmann/qa-skills:
intercept the tracking request, parse both the query and the body, compare against a plan kept outside
the code, and report every violation, not the first one.

## Why tracking requests are answered locally

A test run that sends to live properties adds fake page views and purchases to real reports.
`capture.py` lets tag scripts load, then answers each tracking request with an empty 204 inside the
browser. The tags behave as if the vendor answered. `--live` turns this off for DebugView or
Test Events checks.

## Verdicts

Every script prints one line per finding with PASS, WARN, FAIL or INFO, and exits 1 on any
FAIL and 2 on bad input. Thresholds marked as working rules (reconcile bands, the (not set)
share) are starting points to tune, not vendor limits. Vendor limits (GA4 Measurement Protocol
sizes, PostHog id length) come from the vendor docs listed in the README credits.

## What is guessed

Browser tracking request formats (`/g/collect` params, Meta `/tr` params, `gcs`) are not documented by
the vendors. `skills/event-capture/references/vendor-patterns.md` marks each pattern as
verified, seen or host only. When a vendor changes a format, the capture still keeps the raw
request, so the fix is in `trackhits.py` only.
