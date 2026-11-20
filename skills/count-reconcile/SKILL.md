---
name: count-reconcile
description: Lines up the same event (purchases, leads, sign-ups) across GA4, PostHog, Meta and the backend by day, and flags tools that count above the backend, drop to zero, sit far below it, or jump after a release. Also matches order ids between the backend and a tool's export to list orders never tracked, orders tracked twice, and test or staging orders in live data. Use when someone says "GA4 and Shopify don't match", "Meta shows more purchases than we had", "which number is right", "conversions dropped overnight", or after any tracking fix.
---

# Count reconcile

The backend (your database, shop or CRM) is the truth for how many orders happened. Every
other tool is a sample of it. This skill tells you which gaps are normal and which are bugs.

## 1. Daily counts

Make `counts.csv` with `date, source, event, count`, one row per day, tool and event. Use
received events, not attributed conversions: Events Manager event counts, GA4 event count,
PostHog trends. Example: `examples/fabrikam-tea/exports/counts.csv`.

```bash
python3 scripts/reconcile.py counts counts.csv --truth backend
```

| Verdict | Rule (working rule, tune it) | Meaning |
|---|---|---|
| OVER | above 105% of the backend | counts twice: reloads, two tags, test orders |
| ZERO | 0 on a day the backend has orders | the tag broke |
| UNDER | below 70% | blockers, consent denied, a broken step (WARN) |
| JUMP | more than 15 points day to day | find the release on that day (WARN) |

`--over`, `--under`, `--drift` change the thresholds. After a clean month, set them to your
own band. Why tools differ and by how much: `references/expected-gaps.md`.

## 2. Order ids

```bash
python3 scripts/reconcile.py ids orders.csv ga4-transactions.csv
```

The files need an id column (`order_id`, `transaction_id`, `Transaction ID`, `oid` or `id`).
It lists MISSING_IN_TOOL, NOT_IN_BACKEND (test or staging orders), COUNTED_TWICE and
`(not set)` transaction ids. GA4 export: Reports, Monetization, Ecommerce purchases, dimension
Transaction ID.

Missing ids that share a payment method mean that method's return skips the thank-you page.

## Worked example

```bash
python3 scripts/reconcile.py counts ../../examples/fabrikam-tea/exports/counts.csv
python3 scripts/reconcile.py ids ../../examples/fabrikam-tea/exports/orders.csv ../../examples/fabrikam-tea/exports/ga4-transactions.csv
```

GA4 drops to zero on one day, Meta jumps to about 140% from 11 November (a second purchase
tag), PostHog stays in a stable band. The id match finds two orders never tracked, one test
order, one order counted twice and a `(not set)` row.

For Meta browser against server dedup by event_id, see the `meta-capi` skill in the
ads-creative-lab pack.

Next: `tracking-qa` so the fix stays fixed.
