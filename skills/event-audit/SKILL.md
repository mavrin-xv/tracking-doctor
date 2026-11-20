---
name: event-audit
description: Compares a capture of what really fired against a tracking plan and lists every missing event, duplicate, missing param, purchase sent twice, purchase without an order id, value without currency, second forgotten tag, and email or phone leaking into a vendor. Works across GA4, Google Ads, Meta Pixel and PostHog in one pass. Use when someone asks "why does GA4 show more purchases than orders", "audit my events", "is my tracking plan implemented", "check the data layer", "revenue is doubled", or after event-capture.
---

# Event audit

The plan says what should fire. The capture says what did. The audit lists the difference, in
the order you should fix it.

## 1. Have a plan

`plan.csv` has one row per expected event per journey step: `step, vendor, event, required, count`.
The format, naming rules and the rows people forget are in `references/plan-format.md`.
Start from `templates/tracking-plan.csv`.

No plan yet? Run the audit without one. It still finds duplicates, double tags, purchases
twice, missing order ids and PII, and its INFO lines list everything that fired, which is a
first draft of the plan.

## 2. Run it

```bash
python3 scripts/audit.py capture.jsonl --plan plan.csv
python3 scripts/audit.py capture.jsonl
```

| Check | Meaning |
|---|---|
| A01 MISSING | planned event did not fire; a near name that did fire is shown (`Add To Cart` vs `add_to_cart`) |
| A02 DUPLICATE | fired more often than planned, or fired on a `count 0` row such as a reload |
| A03 PARAM | a required param is missing or empty |
| A04 ORDER_TWICE | the same order id reached one vendor twice |
| A05 NO_ORDER_ID | a purchase with no transaction id, oid or eid: no tool can dedupe it |
| A06 VALUE | value without currency, currency without value, value 0 or below |
| A07 DOUBLE_TAG | two tag ids for one vendor (WARN) |
| A08 PII | an email or phone in a URL or param sent to a vendor |
| A09 STEP_ERROR | a journey step failed, so its rows cannot be judged |
| A10 UNPLANNED | fired, not in the plan (INFO) |

Exit 1 on any FAIL.

## 3. Fix in this order

1. A09: a broken step hides everything after it. Fix the journey first.
2. A08: PII is a policy problem with the vendor, not only a data problem.
3. A02, A04, A07: doubles inflate revenue and teach bid strategies the wrong thing.
4. A05, A06: without ids and currency, dedup and value reports fail quietly.
5. A01, A03: missing events and params.

Causes and fixes per check: `references/fixes.md`. Capture again after each fix and keep the
before and after in `templates/test-log.md`.

## Worked example

`examples/fabrikam-tea/` has a small shop with nine planted problems. Run:

```bash
python3 scripts/audit.py ../../examples/fabrikam-tea/capture.jsonl --plan ../../examples/fabrikam-tea/plan.csv
```

It ends with 17 FAIL and 1 WARN: an old second GA4 tag, a case-split PostHog event, a purchase
without currency, a Meta purchase without eid, purchases on reload, and an email in the
thank-you URL.

Next: `consent-check` for what fires before the banner answer, `attribution-leaks` for lost
click ids.
