# PostHog capture API

Source: posthog.com/docs/api/capture.

```
POST https://us.i.posthog.com/i/v0/e/      one event
POST https://eu.i.posthog.com/batch/       {"api_key": "...", "batch": [ ... ]}
```

Each event has `event`, `distinct_id`, `properties`, and optionally `timestamp` (ISO 8601) and
`uuid`. The project api key is public by design: it can only write events.

## Things that bite

- A missing `event` or `distinct_id` still gets a 200 answer, and the event is dropped. Lint
  before you trust a green response.
- `distinct_id` is limited to 200 characters. Use the id the browser uses (read it with
  `posthog.get_distinct_id()` and pass it to the server) or call identify, or the server event
  lands on a stranger.
- `uuid` helps PostHog drop repeats, but that dedup is eventual and not guaranteed. Do not rely
  on it to clean up after a retry loop.
- Batch bodies can be up to 20 MB.
- If you send through your own proxy, point the browser and the server at the same project.
