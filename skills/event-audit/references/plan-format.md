# Tracking plan format

`plan.csv` has one row per event you expect, per step of a test journey. The same file feeds
`audit.py`, `checklist.py` and your own review.

| Column | Meaning | Example |
|---|---|---|
| `step` | the step name in `steps.json` | `checkout` |
| `vendor` | `ga4`, `meta`, `gads`, `posthog`, `tiktok`, `linkedin`, `uet` | `ga4` |
| `event` | the exact name the vendor receives | `purchase` |
| `required` | params that must be present, `;` separated | `transaction_id;value;currency` |
| `count` | `1` exactly once, `1+` at least once, `0` must not fire | `1` |

Start from `templates/tracking-plan.csv`.

## Naming

- One style per vendor, and keep it. GA4 recommended events are snake_case (`add_to_cart`,
  `purchase`). Meta standard events are PascalCase (`AddToCart`, `Purchase`). PostHog takes
  anything, so pick object_action in snake_case (`order_completed`) and write it down.
- Names are case and space sensitive in every tool. `Add To Cart` and `add_to_cart` are two
  events and two report rows.
- Use the vendor's recommended or standard name when one exists. Reports, audiences and bid
  optimisation only understand those.

## Rows people forget

- `count 0` rows for the thank-you page reload and the order email link. Without them the
  audit cannot tell you that a refresh doubles revenue.
- The page view on the step right after the consent click, for each tool that waits for consent.
- `transaction_id` (GA4), `oid` (Google Ads), `eid` (Meta), a uuid or order id (PostHog) on
  every purchase row. Dedup in every tool depends on them.
