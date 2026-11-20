# Fabrikam Tea: a shop with broken tracking

An invented tea shop. `site/` is four static pages with fake tags (`site/fake-tags.js`) that
build real GA4, Google Ads, Meta and PostHog request URLs. The captures were recorded with
tracking requests answered locally, so nothing reached any vendor.

## Planted problems

| # | Problem | Where | Found by |
|---|---|---|---|
| 1 | a second, forgotten GA4 tag `G-OLDTAG001` doubles page views | `fake-tags.js` | event-audit A02, A07 |
| 2 | Meta PageView fires before the banner answer, and after Reject | `fake-tags.js` | consent-check C01, C07 |
| 3 | the `_fbp` cookie is set before consent | `fake-tags.js` | consent-check C04, C07 |
| 4 | PostHog gets `Add To Cart` where the plan says `add_to_cart` | `fake-tags.js` | event-audit A01 |
| 5 | GA4 purchase has no currency | `fake-tags.js` | event-audit A03, A06 |
| 6 | Meta Purchase has no `eid`, so CAPI cannot dedupe it | `fake-tags.js` | event-audit A03, A05 |
| 7 | every purchase fires again on a thank-you page reload | `thanks.html` | event-audit A02, A04 |
| 8 | the buyer email is in the thank-you URL and reaches three vendors | `shop.html` | event-audit A08 |
| 9 | the landing page redirect drops gclid and utm params | `landing.html` | attribution-leaks L01, L02 |

Exports (`exports/`) add the problems you only see in reports: payment and self referrals, a
case split, unknown mediums, a GA4 outage day, a Meta double count from 11 November, and order
ids missing, doubled or from a test order. `server/` holds one broken and one clean GA4
Measurement Protocol payload and one broken PostHog batch.

## Run it

From the repo root:

```bash
S=skills; E=examples/fabrikam-tea
python3 $S/event-capture/scripts/capture.py --steps $E/steps.json --serve $E/site --out $E/capture.jsonl
python3 $S/event-audit/scripts/audit.py $E/capture.jsonl --plan $E/plan.csv
python3 $S/consent-check/scripts/consent.py $E/capture.jsonl --consent-step consent-accept --reject $E/capture-reject.jsonl --reject-step consent-reject
python3 $S/attribution-leaks/scripts/leaks.py --capture $E/capture.jsonl --sources $E/exports/ga4-sources.csv --domain fabrikam-tea.example
python3 $S/server-events/scripts/mp_check.py ga4 $E/server/ga4-mp-purchase.json
python3 $S/count-reconcile/scripts/reconcile.py counts $E/exports/counts.csv
python3 $S/count-reconcile/scripts/reconcile.py ids $E/exports/orders.csv $E/exports/ga4-transactions.csv
python3 $S/tracking-qa/scripts/checklist.py $E/plan.csv --out $E/tracking-test.md
```

The first line needs Playwright and rewrites `capture.jsonl`. The rest run on the files here.
`devtools-sample.har` is a tiny HAR to try `capture.py --from-har`.
