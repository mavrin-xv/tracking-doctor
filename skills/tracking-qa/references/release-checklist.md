# Release checklist and CI

## When to run it

Every release that touches a template, the checkout, the consent banner, a tag container or a
plugin. Also once after any change in GTM, even "just a new tag".

## Manual pass (about 30 minutes)

1. Generate the list: `python3 scripts/checklist.py plan.csv --site staging --out test.md`.
2. Open a fresh private window and the debug views (GA4 DebugView, Meta Test Events, PostHog Activity).
3. Walk the steps, tick each line, write the test order id at the top.
4. Do the reload, second tab, consent reject and ad blocker lines.
5. Paste the script outputs into `templates/test-log.md`.

## Automated pass

```bash
python3 skills/event-capture/scripts/capture.py --steps steps.json --out capture.jsonl
python3 skills/event-audit/scripts/audit.py capture.jsonl --plan plan.csv
python3 skills/consent-check/scripts/consent.py capture.jsonl --consent-step consent-accept \
  --reject capture-reject.jsonl --reject-step consent-reject
```

Each script exits 1 on a FAIL, so a CI job goes red on a dropped or doubled event.

### CI snippet (GitHub Actions)

```yaml
jobs:
  tracking:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install playwright && python3 -m playwright install --with-deps chromium
      - run: python3 skills/event-capture/scripts/capture.py --steps tests/steps.json --out capture.jsonl
      - run: python3 skills/event-audit/scripts/audit.py capture.jsonl --plan tests/plan.csv
```

Point `tests/steps.json` at your staging URL. Tracking requests are answered locally by default, so CI
sends nothing to the vendors.

## Prove the gate works

Break one thing on purpose on staging (rename an event, remove `currency`) and run the job. It
must go red. A gate that has never failed has not been tested.

## After release

The next day, run `reconcile.py counts` against the backend, and refund or exclude test orders.
