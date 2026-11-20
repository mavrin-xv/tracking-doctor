# Contributing

Thanks for helping. Small, tested changes are the easiest to merge.

## Good first contributions

- Request patterns for more vendors (Pinterest, Snap, Reddit, X, HubSpot, Segment), each with a
  sample request and its verified flag.
- First-party hosts for server-side GTM containers, read as GA4.
- A Firefox and WebKit run of `capture.py` with notes on what differs.
- A reader for GA4 BigQuery exports in `reconcile.py`.
- A `gcd` decoder, with a source for each part of the format.

## How

1. Open an issue first for anything that changes a verdict rule or a threshold.
2. Keep scripts stdlib-only (Playwright only in `capture.py`), and keep default captures from
   sending anything to vendors.
3. Change `trackhits.py` in `skills/event-capture/scripts/`, copy it to the other three skills.
4. Run the commands in `AGENTS.md` and paste their output in the PR.
5. Plain English. No hype words, no invented numbers. If a number is in the docs, say where it
   came from, and mark working rules as working rules.

## Credit

If your change is based on someone else's method or repo, add it to the Credits section of the
README with the URL and license.
