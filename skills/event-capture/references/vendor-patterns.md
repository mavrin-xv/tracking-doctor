# Vendor request patterns

What `trackhits.py` recognises, and how sure we are about each pattern. "Verified" means the
vendor documents it. "Seen" means it matches what tags send today, but the vendor does not
document the browser format, so it can change without notice. When a pattern stops matching,
the capture still keeps the raw request: fix the pattern, not the data.

| Vendor | Host | Path | Status | What we read |
|---|---|---|---|---|
| GA4 (gtag, GTM) | `*.google-analytics.com`, `*.analytics.google.com` | `/g/collect` | seen | `en` event, `tid` tag, `ep.*` text params, `epn.*` number params, `gcs`, `gcd`, `dl` page, `dr` referrer, `cu` currency. Several events can sit in the POST body, one per line |
| GA4 Measurement Protocol | `www.google-analytics.com`, `region1.google-analytics.com` | `/mp/collect`, `/debug/mp/collect` | verified | JSON body: `client_id`, `events[].name`, `events[].params` |
| Google Ads | `googleadservices.com` | `/pagead/conversion/<id>/` | seen | `label`, `value`, `currency_code`, `oid` (order id) |
| Google Ads | `www.google.com` | `/pagead/1p-conversion/<id>/`, `/ccm/collect` | seen | same as above; `/ccm/collect` also carries `en` and `tid` |
| Meta Pixel | `www.facebook.com` | `/tr`, `/tr/` | seen | `id` pixel, `ev` event, `eid` event id, `cd[...]` custom data |
| PostHog | `us.i.posthog.com`, `eu.i.posthog.com`, your proxy | `/i/v0/e/`, `/batch/` | verified | `api_key`, `event`, `distinct_id`, `uuid`, `properties` |
| PostHog | same | `/e/`, `/capture/` | seen | browser library format; the body may be gzip or base64 `data=` |
| TikTok Pixel | `analytics.tiktok.com` | `/api/v2/pixel*` | host only | JSON body `event`, `event_id` |
| LinkedIn Insight | `px.ads.linkedin.com` | `/collect`, `/wa/` | host only | `pid` partner id, `conversionId` |
| Microsoft UET | `bat.bing.com` | `/action/*` | host only | `ti` tag id, `evt`, `ea` |

Loaders (`gtm.js`, `gtag/js`, `fbevents.js`, the PostHog array script) are recorded as
"(tag loaded)". A loaded tag that sends nothing is a finding by itself.

## Reverse proxies

Many PostHog setups and some GA4 setups send through your own domain (`/ingest`, `t.shop.example`).
Pass `--posthog-host t.shop.example` to `capture.py`, or add the host to `EXTRA_POSTHOG_HOSTS`
in `trackhits.py`. A server-side GTM container on your own domain looks like GA4 `/g/collect`
on a first-party host: add that host to the GA4 pattern.

## Batching and tracking requests

gtag waits and batches. A capture that ends right after a click can miss the hit, so keep
`--wait` at 3 seconds or more, and longer on slow pages. `navigator.sendBeacon` and `fetch`
with `keepalive` are captured like any other request.

## Why read requests and not the dataLayer

The dataLayer shows what the page meant to send. The request shows what the vendor got. Tags
with wrong triggers, a consent block or a second container only show up in requests.
