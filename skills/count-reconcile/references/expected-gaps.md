# Expected gaps between tools

No two tools agree, and they should not. The question is whether the gap is the usual one.

| Gap | Why it exists | What is normal |
|---|---|---|
| browser tools below the backend | ad blockers, consent denied, browsers that cap cookies, tags that load after the visitor leaves | depends on audience and consent rate; measure your own band over a clean month |
| GA4 below PostHog, or the reverse | blockers block different hosts; a proxy helps one tool and not the other | a stable ratio day to day matters more than the level |
| ad platform above the backend | the platform counts by click or view date, with view-through and modelled conversions | compare received events (Events Manager, Diagnostics), not attributed conversions |
| any tool above the backend on received events | a tag firing twice, reloads, test orders, a staging site sending to live | never normal; `reconcile.py` flags it as OVER |

## Working rules in reconcile.py

- OVER, above 105% of the backend: something counts twice. FAIL.
- ZERO on a day the backend has orders: the tag broke. FAIL.
- UNDER, below 70%: worth a look, often consent or blockers. WARN.
- JUMP, more than 15 points day to day: find the release or tag change on that day. WARN.

These are starting points. After a month, set `--under` and `--drift` to your own band.

## Order ids

Counts can match while the orders do not: one order missed, another counted twice, one test
order. `reconcile.py ids` lists each. Missing ids point to blocked visitors or a thank-you page
that some payment methods skip. Extra ids point to test or staging traffic.

For browser against server dedup on Meta (eventID equal to the CAPI event_id), use the
`meta-capi` skill from the ads-creative-lab pack if you have it. This pack only checks that the
eid exists.
