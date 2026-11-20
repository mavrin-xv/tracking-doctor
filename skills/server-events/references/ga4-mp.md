# GA4 Measurement Protocol

Source: developers.google.com/analytics/devguides/collection/protocol/ga4 (reference,
validation and limits pages).

## Request

```
POST https://www.google-analytics.com/mp/collect?measurement_id=G-XXXX&api_secret=SECRET
POST https://region1.google-analytics.com/mp/collect?...     EU collection
POST .../debug/mp/collect?...                                validation only, writes nothing
```

Body: `client_id` (web) or `app_instance_id` plus `firebase_app_id` (app), and `events[]` with
`name` and `params`. Optional: `user_id`, `user_properties`, `timestamp_micros`.

## Limits checked by mp_check.py

- 25 events per request, 25 params per event
- event and param names up to 40 characters, param values up to 100 (500 on GA4 360)
- 25 user properties, name up to 24 characters, value up to 36
- `timestamp_micros` up to 72 hours back
- body up to 130 kB
- reserved event names (session_start, first_visit, user_engagement, error, ad_click and
  others) and reserved prefixes (`_`, `firebase_`, `ga_`, `google_`, `gtag.`)

## Things that bite

- `/mp/collect` answers 2xx even for a broken payload. Only `/debug/mp/collect` tells you,
  with `{"validationMessages": [...]}`; an empty list means valid. Always debug first.
- The debug endpoint checks format, not meaning. A purchase with the wrong currency passes.
- `client_id` must be the one from the visitor's `_ga` cookie (the part after `GA1.1.`), or
  the server event becomes a new user with no source.
- Put `session_id` (from the `_ga_<container>` cookie) and `engagement_time_msec` in event
  params. Without `session_id` the event is not tied to a session, and session reports show it
  without a source. That last part is a working rule from practice, not a Google statement.
- Server events do not inherit consent from the page. Send only for visitors who allowed it,
  or follow Google's guidance on consent fields for the Measurement Protocol.
