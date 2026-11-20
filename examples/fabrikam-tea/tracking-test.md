# Tracking test: the staging site

Tester: ____  Date: ____  Build or release: ____

Use a fresh private window per run. Note the test order id here: ____

## 1. landing

- [ ] ga4 `page_view` fires exactly 1x. Check in GA4 DebugView (Admin, DebugView) with the debug_mode param or Tag Assistant.
- [ ] meta `PageView` fires exactly 1x. Check in Meta Events Manager, Test Events tab.

## 2. consent-accept

- [ ] posthog `$pageview` fires exactly 1x. Check in PostHog Activity, filtered by your test distinct_id.

## 3. add-to-cart

- [ ] ga4 `add_to_cart` fires exactly 1x, with value, currency. Check in GA4 DebugView (Admin, DebugView) with the debug_mode param or Tag Assistant.
- [ ] meta `AddToCart` fires exactly 1x, with value, currency. Check in Meta Events Manager, Test Events tab.
- [ ] posthog `add_to_cart` fires exactly 1x, with value. Check in PostHog Activity, filtered by your test distinct_id.

## 4. checkout

- [ ] ga4 `purchase` fires exactly 1x, with transaction_id, value, currency. Check in GA4 DebugView (Admin, DebugView) with the debug_mode param or Tag Assistant.
- [ ] meta `Purchase` fires exactly 1x, with value, currency, eid. Check in Meta Events Manager, Test Events tab.
- [ ] gads `conversion` fires exactly 1x, with oid, value, currency_code. Check in Tag Assistant, Google Ads conversion tag.
- [ ] posthog `order_completed` fires exactly 1x, with order_id, value, currency. Check in PostHog Activity, filtered by your test distinct_id.

## 5. thanks-reload

- [ ] ga4 `purchase` does NOT fire here. Check in GA4 DebugView (Admin, DebugView) with the debug_mode param or Tag Assistant.
- [ ] meta `Purchase` does NOT fire here. Check in Meta Events Manager, Test Events tab.
- [ ] gads `conversion` does NOT fire here. Check in Tag Assistant, Google Ads conversion tag.
- [ ] posthog `order_completed` does NOT fire here. Check in PostHog Activity, filtered by your test distinct_id.

## Release checks (every release that touches pages, checkout or tags)

- [ ] Capture runs clean: `capture.py --steps steps.json` then `audit.py capture.jsonl --plan plan.csv` exits 0.
- [ ] Reload the thank-you page: no purchase event fires again (plan rows with count 0).
- [ ] Open the thank-you page from a second tab or the order email link: no second purchase.
- [ ] Consent, accept: tags fire after the click, Google hits carry gcs=G111.
- [ ] Consent, reject: no ad hits, no `_fbp` or `_gcl_*` cookies; `consent.py` exits 0 on both captures.
- [ ] Land with `?gclid=TEST&utm_source=test&utm_medium=test`: `leaks.py --capture` shows them carried.
- [ ] Ad blocker on: the order still saves, and the server-side events still go out.
- [ ] Server events: payloads pass `mp_check.py`; Meta CAPI event_id equals the browser eid.
- [ ] No email, phone or name in any URL or param that a vendor receives.
- [ ] Next day: `reconcile.py counts` shows every tool inside its usual band against the backend.
- [ ] Test orders are marked or refunded so they do not stay in revenue reports.
