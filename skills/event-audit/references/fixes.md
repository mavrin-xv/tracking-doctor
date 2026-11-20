# Fixes by finding

| Finding | Usual cause | Fix |
|---|---|---|
| A01 MISSING | the trigger never fires, a wrong event name, a tag blocked by consent or by an ad blocker in your test browser | read the near-name hint first, then the trigger in GTM Preview, then test in a clean profile |
| A02 DUPLICATE | two containers, or a hardcoded gtag next to GTM; a trigger on both click and page view; a single-page app sending page_view on each route and on history change | list the tag ids (A07) and remove one source; for single-page apps pick one page view source |
| A02 on a `count 0` row | purchase fires on every load of the thank-you page | fire only when the backend says the order is new (a flag the server sets once), or dedupe by order id in the tag |
| A03 PARAM | the dataLayer key differs from what the tag maps; the value is read before the page sets it | map the variable in GTM; push the ecommerce object before the event |
| A04 ORDER_TWICE | reload, back button, a second tab, the email link | same as A02 on a reload row. GA4 drops some repeats by transaction_id; other tools do not |
| A05 NO_ORDER_ID | the tag was built without it | GA4 `transaction_id`, Google Ads `transaction_id` (sent as `oid`), Meta `eventID` (sent as `eid`) equal to the CAPI `event_id` |
| A06 VALUE | value as text with a currency sign, value 0, currency missing | send a number and an ISO 4217 code on every event that has a value |
| A07 DOUBLE_TAG | an old property left in the theme, an agency container, a plugin | find which file or container sends it, then remove it or move it to a test property |
| A08 PII | email in the thank-you URL, form fields read into params | take it out of the URL; never put a raw email or phone in params. Hashed fields for Meta and Google go only through their user data fields |
| A09 STEP_ERROR | a selector changed, a page timed out | fix `steps.json`; the audit cannot judge a step that did not run |
| A10 UNPLANNED | auto events (user_engagement, scroll), plugins | add them to the plan or ignore them; INFO only |

After each fix, capture again and run the audit. Keep the before and after output in the test
log (`templates/test-log.md`).
