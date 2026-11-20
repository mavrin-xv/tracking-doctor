# AGENTS.md

Notes for coding agents (Claude Code, Codex, Cursor, others) working on this repository.

## What this is

A skill pack that finds why analytics and ad pixels disagree with real orders. Seven skills in
`skills/`, each with SKILL.md, `references/` and `scripts/`. Scripts are Python 3.8+ standard
library only, except `capture.py`, which imports Playwright when it opens a browser. By
default no script sends data to any vendor: captures answer tracking requests locally, and only
`mp_check.py --debug` calls the GA4 debug endpoint, which stores nothing.

## Layout

- `skills/<name>/scripts/trackhits.py`: the shared request parser (vendor URL patterns, body
  decoding, hit fields). The same file sits in event-capture, event-audit, consent-check and
  attribution-leaks so each skill works alone after install. Edit the copy in `event-capture`,
  then copy it to the other three.
- `examples/fabrikam-tea/`: an invented shop with planted problems, its captures, exports and
  server payloads.
- `templates/`: tracking plan and test log. `docs/how-it-works.md`: data flow.

## Rules

- SKILL.md frontmatter has only `name` (same as the folder) and `description` (under 1024
  characters, says what and "Use when"). Bodies under 500 lines; detail goes to `references/`.
- A new vendor pattern goes into `PATTERNS` in `trackhits.py` with its verified flag, and a row
  in `skills/event-capture/references/vendor-patterns.md`.
- Captures store cookie names and domains, never cookie values. Keep it that way.
- Credentials come from environment variables only and are masked in output.
- Working rules (bands, limits we chose) are marked as such in SKILL.md and references. Vendor
  limits cite the vendor doc.
- Examples use invented businesses only and no real emails (`jane%40example.com` style).
- Run before you finish:

```bash
S=skills; E=examples/fabrikam-tea
for d in event-audit consent-check attribution-leaks; do
  cmp $S/event-capture/scripts/trackhits.py $S/$d/scripts/trackhits.py; done
python3 $S/event-audit/scripts/audit.py $E/capture.jsonl --plan $E/plan.csv
python3 $S/consent-check/scripts/consent.py $E/capture.jsonl --consent-step consent-accept --reject $E/capture-reject.jsonl --reject-step consent-reject
python3 $S/attribution-leaks/scripts/leaks.py --capture $E/capture.jsonl --sources $E/exports/ga4-sources.csv --domain fabrikam-tea.example
python3 $S/server-events/scripts/mp_check.py ga4 $E/server/ga4-mp-purchase.json
python3 $S/server-events/scripts/mp_check.py ga4 $E/server/ga4-mp-fixed.json
python3 $S/server-events/scripts/mp_check.py posthog $E/server/posthog-batch.json
python3 $S/count-reconcile/scripts/reconcile.py counts $E/exports/counts.csv
python3 $S/count-reconcile/scripts/reconcile.py ids $E/exports/orders.csv $E/exports/ga4-transactions.csv
python3 $S/tracking-qa/scripts/checklist.py $E/plan.csv > /dev/null
python3 $S/event-capture/scripts/capture.py --from-har $E/devtools-sample.har --out har.jsonl
```

Expected: `cmp` silent; audit exit 1 (17 FAIL, 1 WARN); consent exit 1 (6 FAIL); leaks exit 1
(11 FAIL, 1 WARN); mp_check purchase exit 1 (3 FAIL, 1 WARN), fixed exit 0, posthog exit 1
(2 FAIL, 1 WARN); reconcile counts exit 1 (ga4 ZERO, meta OVER), ids exit 1 (4 FAIL); checklist
exit 0; HAR import exit 0 (2 tracking requests, 3 hits). With Playwright installed, also run
the capture line in `examples/fabrikam-tea/README.md` and expect the same audit result.
