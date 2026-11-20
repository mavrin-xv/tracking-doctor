---
name: tracking-qa
description: Turns a tracking plan into a release test checklist (what to do, what must fire, where to see it in GA4 DebugView, Meta Test Events, PostHog Activity) plus fixed checks for reloads, consent, ad blockers, click ids, server events and next-day counts, and gives a CI job that fails on a dropped or doubled event. Use when someone says "test tracking before release", "make a QA checklist for analytics", "the redesign broke our pixels", "add tracking tests to CI", or after fixing anything with the other tracking-doctor skills.
---

# Tracking QA

Tracking breaks in releases that never mention tracking: a new theme, a checkout change, a
banner vendor swap. A short test on every release is cheaper than a month of wrong data.

## 1. Generate the checklist

```bash
python3 scripts/checklist.py plan.csv --site https://staging.shop.example --out tracking-test.md
```

One section per journey step with a checkbox per expected event, the required params, and
where to verify it. The release checks at the end cover reloads, a second tab, accept and
reject, ad blocker on, test click ids, server payloads, PII and next-day counts. Example output:
`examples/fabrikam-tea/tracking-test.md`.

## 2. Run it

By hand: a fresh private window, the debug views open, tick each line, write the test order id
at the top, paste script outputs into `templates/test-log.md`.

Automated: event-capture, then event-audit and consent-check. Each exits 1 on a FAIL, so they
work as a CI gate. A GitHub Actions job is in `references/release-checklist.md`.

## 3. Prove the gate

Break one thing on staging on purpose (rename an event, drop `currency`) and confirm the job
goes red. Then restore it. A gate that has never failed proves nothing.

## When to run

- Every release that touches templates, checkout, the banner, GTM or plugins.
- After each fix from the other skills.
- The day after a release: `reconcile.py counts` against the backend.

## Rules

- Test orders get a marker (a test coupon, a note) and are refunded or excluded, or they stay
  in revenue reports.
- Default captures do not send to vendors. Use `--live` only when checking debug views.
- Keep `plan.csv` in the repo next to the code that fires the events, and change both in one
  pull request.
