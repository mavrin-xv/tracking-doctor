# Leak fixes

| Leak | Where it comes from | Fix |
|---|---|---|
| L01 click id lost | a redirect (http to https, www, locale, a link shortener) or a JS router that rebuilds the URL without the query | keep the full query through every redirect (server rules, and `location.replace(target + location.search)` in JS); test with `?gclid=TEST` |
| L02 utm lost | same as L01; also forms that post to a new page without the query | same fix; store the utm values in a first-party cookie on landing if the journey crosses pages that drop them |
| L03 payment referral | the buyer returns from PayPal, Stripe or Klarna, and the return starts a new session from that site | GA4 Admin, Data streams, Configure tag settings, List unwanted referrals: add the gateway domains |
| L04 self referral | a page without the tag (a checkout on a subdomain, a help center), or cross-domain without the linker | tag every page; set up cross-domain measurement for every domain in the journey; add your own domains to the unwanted list |
| L05 case split | `Facebook`, `facebook` and `FB` typed by hand in different campaigns | one lowercase source list and one medium list; build links with a tool that enforces them |
| L06 unknown medium | a medium that no default channel rule matches (`paid-social-test`, `newsletter`) | use mediums from the default channel group rules (cpc, email, social, display, referral, affiliate) |
| L07 (not set) and Unassigned | GA4 says Unassigned when no channel rule matches (support.google.com/analytics/answer/9756891); server events without session_id and stripped click ids add to it | fix L01 to L06 first, then server events (the server-events skill) |

The channel rules in `leaks.py` are a simplified copy. Google changes them, so check the GA4
help page "[GA4] Default channel group" before you act on an L06.

## Testing a leak fix

1. Capture with a test URL: `capture.py "https://shop.example/?gclid=TEST&utm_source=test&utm_medium=cpc"`.
2. `leaks.py --capture capture.jsonl` must show every param carried.
3. A day later, export Session source / medium and run `leaks.py --sources` again.
