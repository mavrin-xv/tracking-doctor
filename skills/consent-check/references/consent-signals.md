# Consent signals

## Google Consent Mode v2

There are four signals: `ad_storage`, `analytics_storage`, `ad_user_data`, `ad_personalization`.
Google's docs say to set the default state before any `config` or `event` command and to update
it when the visitor answers (developers.google.com/tag-platform/security/guides/consent).

Two setups:

- **Basic**: Google tags do not load until the visitor accepts. Nothing from Google fires before.
- **Advanced**: tags load with everything denied and send cookieless pings. These pings carry
  `gcs=G100` and must not set `_ga` or `_gcl_*` cookies.

Tell the check which one your site claims to run with `--mode`. It fails on anything that does
not match the claim.

## Reading gcs and gcd (not documented by Google)

This comes from public write-ups, not from Google docs, so treat it as a hint:

- `gcs=G1xy`: x is ad_storage, y is analytics_storage, `1` granted, `0` denied. `G100` means
  both denied, `G111` both granted, `G1--` no consent default set at all.
- `gcd` encodes all four v2 signals and whether each came from a default or an update. The
  format is longer and changes. `consent.py` prints the values it saw and does not judge them.

## Other vendors

Meta, TikTok, LinkedIn, Microsoft UET and PostHog have no equivalent mode here. The check
applies one rule: no hit and no tracking cookie before the visitor accepts, and none after a
reject. Meta has `fbq('consent', 'revoke')`; if you use it, the pixel must still send nothing
before grant. PostHog can run cookieless (`persistence: 'memory'`), which shows as a WARN after
reject, and you decide whether that is your design.

## What a test needs

- Two captures from fresh profiles: one accept, one reject.
- A step that only clicks the banner button, so "before" and "after" have a clear line.
- A run where the banner is ignored, if your banner lets people browse without answering.

This is a technical check of what fires. It is not legal advice about what your banner must
say or which law applies.
