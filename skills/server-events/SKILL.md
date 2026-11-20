---
name: server-events
description: Lints server-side analytics payloads before they go out (GA4 Measurement Protocol and PostHog capture), and validates GA4 ones against Google's debug endpoint, which writes no data. Catches the errors that get a 2xx answer and are dropped anyway: missing client_id or distinct_id, reserved names, over-limit params, old timestamps, purchase without transaction_id or currency, no session_id. Use when someone builds or debugs server-side tracking, says "measurement protocol events don't show up", "server events have no source", "PostHog returns 200 but nothing appears", or "send purchases from the backend".
---

# Server events

Server-side events fill the gap that blockers and consent leave in browser tracking. They also
fail quietly. GA4 `/mp/collect` and PostHog answer 200 to payloads they then throw away.

## 1. Save the payload

Write the exact JSON body your server would send to a file. Examples:
`examples/fabrikam-tea/server/ga4-mp-purchase.json` (broken),
`examples/fabrikam-tea/server/ga4-mp-fixed.json` (clean),
`examples/fabrikam-tea/server/posthog-batch.json` (broken).

## 2. Lint

```bash
python3 scripts/mp_check.py ga4 payload.json
python3 scripts/mp_check.py posthog payload.json
```

No network. GA4 limits checked: 25 events per request, 25 params, names up to 40 characters,
values up to 100, user properties, reserved names and prefixes, 72-hour timestamps, 130 kB.
PostHog: api_key, event, distinct_id, 200-character id limit, ISO timestamps. "No session_id"
and "no uuid" are WARN; the rest are FAIL.

## 3. Validate GA4 with Google

```bash
export GA4_MEASUREMENT_ID=G-XXXX
export GA4_API_SECRET=...        # Admin, Data streams, Measurement Protocol API secrets
python3 scripts/mp_check.py ga4 payload.json --debug            # --region eu for EU collection
```

This posts to `/debug/mp/collect`, which validates and stores nothing. The secret comes only
from the environment and is masked in output. PostHog has no validation endpoint: after the
lint, send one test event and look for it in Activity.

Exit: 0 clean, 1 any FAIL or validation message, 2 setup problem.

## Rules that keep server events useful

- Reuse the browser's ids. GA4 `client_id` from the `_ga` cookie and `session_id` from the
  `_ga_<container>` cookie; PostHog `distinct_id` from the browser library. New ids create
  sourceless strangers.
- Send the same order id the browser sends, so tools that dedupe can match.
- Respect consent: send only for visitors who allowed it.
- Meta CAPI is not covered here. The `meta-capi` skill in the ads-creative-lab pack builds and
  checks CAPI payloads and browser against server dedup.

Details: `references/ga4-mp.md`, `references/posthog-capture.md`.

Next: `count-reconcile` to see whether server events closed the gap.
