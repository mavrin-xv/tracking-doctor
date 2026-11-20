---
name: event-capture
description: Opens a site in a headless browser, walks a scripted journey (land, accept cookies, add to cart, buy, reload) and records every analytics and ad request that fires (GA4, Google Ads, Meta Pixel, PostHog, TikTok, LinkedIn, Microsoft UET), plus cookies and navigations, to a JSONL file the other tracking-doctor skills read. Can also convert a DevTools HAR export. Use when someone says "check what my pixels send", "is the purchase event firing", "capture the tracking on this page", "my numbers look wrong", or before any event audit, consent check or attribution check.
---

# Event capture

Everything in this pack starts from a record of what the browser really sent. Not the
dataLayer, not the tag manager preview: the requests. That is what the vendors receive.

## Setup

```bash
pip install playwright
python3 -m playwright install chromium
```

Without Playwright the script prints these two lines and exits 2. The HAR path below needs
nothing installed.

## 1. Write the journey

A steps file is a JSON list. Each step has a `step` name and one action:

```json
[
  {"step": "landing", "goto": "https://shop.example/?gclid=TEST&utm_source=test&utm_medium=cpc"},
  {"step": "consent-accept", "click": "#accept"},
  {"step": "add-to-cart", "click": "button.add"},
  {"step": "checkout", "click": "#pay"},
  {"step": "thanks-reload", "reload": true}
]
```

Actions: `goto`, `click`, `fill` (`["#email", "Test Buyer"]`), `reload`, `wait` (seconds).
Step names are what the plan, the consent check and the reports refer to, so keep them short
and stable. A full example is `examples/fabrikam-tea/steps.json`.

Rules for a useful journey:

- Start the first URL with a test click id and utm params. attribution-leaks needs them.
- Put the cookie banner click in its own step. consent-check splits the capture there.
- End with a reload of the thank-you page. Double purchases show up there.
- Run a second journey that clicks Reject, for consent-check.

## 2. Capture

```bash
python3 scripts/capture.py --steps steps.json --out capture.jsonl
python3 scripts/capture.py https://shop.example/ https://shop.example/pricing --out pages.jsonl
python3 scripts/capture.py --steps steps.json --serve site/ --out capture.jsonl   # local folder
```

By default tracking requests are answered locally with an empty 204 and never reach the vendors, so a
test run does not pollute live reports. Tag loaders still download so the tags run. Use
`--live` only when you want the hits in DebugView or Test Events.

Other options: `--wait 3` seconds after each step (raise it on slow pages, gtag batches),
`--headed` to watch, `--posthog-host` for a PostHog reverse proxy.

## 3. Or import a HAR

When the site needs a login or a real payment, record it by hand: DevTools, Network tab,
"Preserve log", walk the journey, then "Save all as HAR".

```bash
python3 scripts/capture.py --from-har session.har --out capture.jsonl
```

Steps become the HAR page ids (`page_1`, `page_2`). Rename them in your plan to match. HAR
files hold cookies and form data: never commit them.

## 4. Read it

```bash
python3 scripts/trackhits.py capture.jsonl
```

One line per hit: step, vendor, event, tag id, key params. Which URL patterns are verified and
which are guessed from what tags send today is in `references/vendor-patterns.md`.

## What the capture holds

One JSON object per line: `request` (url, method, body, step, time), `nav` (each page the
journey reached), `cookies` (names and domains only, after each step, never values) and
`error` (a step that failed).

Next: `event-audit` with a tracking plan.
