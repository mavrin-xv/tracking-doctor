---
name: consent-check
description: Checks what analytics and ad tags do before and after the visitor answers the cookie banner, from two captures (accept and reject). Flags pixels that fire before consent, Google hits whose gcs signal says granted too early, Consent Mode that never updates, tracking cookies set before the answer or after a reject, and tools that stay silent after accept. Supports Google Consent Mode basic and advanced. Use when someone asks "does my cookie banner work", "is the pixel firing before consent", "consent mode v2 check", "why did conversions drop after the banner", or before a privacy review.
---

# Consent check

A banner can look right and still let the pixel fire on page load. Or it can block so well
that nothing fires after Accept either, and conversions drop by half. This check reads both
sides from real captures.

## 1. Two captures

With event-capture, record two journeys from fresh profiles that differ only in the banner
click. Example: `examples/fabrikam-tea/steps.json` (Accept) and
`examples/fabrikam-tea/steps-reject.json` (Reject). The banner click must be its own step.

## 2. Know your mode

- **basic**: Google tags wait for consent. Nothing from Google before Accept.
- **advanced**: Google tags load and send cookieless pings with `gcs=G100`, and set no cookies.

Ask the site owner or read the tag setup. If nobody knows, run with `--mode basic` first.
Other vendors get one rule: nothing before Accept, nothing after Reject.

## 3. Run it

```bash
python3 scripts/consent.py capture.jsonl --consent-step consent-accept \
  --reject capture-reject.jsonl --reject-step consent-reject --mode advanced
```

| Check | Meaning |
|---|---|
| C01 BEFORE_CONSENT | an ad or analytics hit before the banner answer |
| C02 GCS_BEFORE | a Google hit before consent says storage is granted |
| C03 NO_GCS | a Google hit with no gcs param: Consent Mode is not running |
| C04 COOKIE_BEFORE | `_ga`, `_gcl_*`, `_fbp`, `_ttp` and similar set before the answer |
| C05 NO_UPDATE | after Accept, Google still says denied: the update never reached the tag |
| C06 SILENT_AFTER | a vendor in `--expect` sends nothing after Accept |
| C07 AFTER_REJECT | an ad hit, granted gcs or tracking cookie after Reject |

`--expect ga4,meta,posthog` sets which vendors must run after Accept. Exit 1 on any FAIL.

## Reading the result

- C01 or C04 on Meta: the pixel base code sits in the theme outside the consent manager, or
  `fbq('init')` runs before it. Move it behind the consent trigger.
- C05: the banner fires its own event but nothing calls `gtag('consent', 'update', ...)`.
- C06 after Accept and a conversion drop: the consent trigger in GTM never fires. Very common
  after a banner vendor change.
- `gcs` and `gcd` are not documented by Google. What we know and how sure we are:
  `references/consent-signals.md`.

This checks what fires. It does not say what your banner must contain under any law.

Next: `attribution-leaks`, since consent rules also change which sessions keep a source.
