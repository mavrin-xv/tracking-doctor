---
name: attribution-leaks
description: Finds where visits lose their source. From a capture it checks whether gclid, fbclid, msclkid, ttclid and utm params survive redirects and reach the tags. From a GA4 source / medium export it flags payment gateways and your own domain as referrals, UTM values split by case, mediums no default channel rule matches, and the share of (not set) and Unassigned. Use when someone asks "why is so much traffic Unassigned", "paypal shows up as a referral", "Google Ads conversions are not attributed", "direct traffic is too high", or "check my UTMs".
---

# Attribution leaks

A conversion with no source is a conversion your ad platforms and reports cannot credit. Most
leaks are not in the tags: they are in redirects, payment returns and hand-typed UTMs.

## 1. From a capture

Start the event-capture journey with a test URL that has click ids and utm params, then:

```bash
python3 scripts/leaks.py --capture capture.jsonl
```

- L01 CLICK_ID_LOST: the landing URL had `gclid` (or `gbraid`, `wbraid`, `fbclid`, `msclkid`,
  `ttclid`, `li_fat_id`) and no tracking hit carried it. The page path in the output shows the
  redirect that dropped it.
- L02 UTM_LOST: the same for `utm_*`.

## 2. From a GA4 export

GA4, Reports, Acquisition, Traffic acquisition, dimension "Session source / medium", 30 days,
download CSV. Then:

```bash
python3 scripts/leaks.py --sources ga4-sources.csv --domain shop.example
```

| Check | Meaning |
|---|---|
| L03 PAYMENT_REFERRAL | paypal.com, stripe.com, klarna.com and others show up as referral |
| L04 SELF_REFERRAL | your own domain shows up as referral |
| L05 CASE_SPLIT | `facebook / cpc` and `Facebook / cpc` in separate rows |
| L06 UNKNOWN_MEDIUM | a medium no default channel rule matches, so it lands in Unassigned |
| L07 NOT_SET | share of (not set) and Unassigned, WARN above `--not-set-max` (5% by default, a working rule) |

Both inputs at once also works. Exit 1 on any FAIL.

## Fix

Fixes per check, including where unwanted referrals live in GA4: `references/leak-fixes.md`.
The channel rules in the script are a simplified copy of GA4's; Google changes them, so check
the help page before acting on an L06.

For building links with clean UTMs from the start, the `tracking-plan` skill in the
marketing-analytics-hub pack has a link builder and linter.

## Worked example

```bash
python3 scripts/leaks.py --capture ../../examples/fabrikam-tea/capture.jsonl \
  --sources ../../examples/fabrikam-tea/exports/ga4-sources.csv --domain fabrikam-tea.example
```

The landing page drops the whole query in a JS redirect, so gclid and three utm params are lost.
The export adds two payment referrals, two self-referrals, a case split and two unknown mediums.

Next: `count-reconcile` to measure how much the leaks cost.
