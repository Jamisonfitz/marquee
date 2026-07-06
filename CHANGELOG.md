# Changelog

## 1.0.1 — 2026-07-06

### Reliability

- Fixed a crash loop on first start when `/config` is a host-owned bind mount
  (e.g. Unraid appdata, which arrives root-owned): the container now starts as
  root, chowns `/config` to the `marquee` user via an entrypoint, then drops
  privileges with `su-exec` before running the app. No more manual `chmod` on
  the appdata folder.

## 1.0.0 — 2026-07-05

### Features

- Initial Marquee release with Plex session polling, artwork, metadata, scores,
  progress, clock, poster/backdrop layouts, themes, and Google Nest Hub casting.
- Added one-click presets for minimal, clock-focused, poster wall, cinema, and
  dusk presentation styles.
- Added snap-grid move and width-resize controls in the live preview.
- Added persistent container settings under `/config`.

### Reliability

- Hardened container publishing so Docker Hub login is only used when
  credentials are present.
- Kept the cast workflow on current GitHub Actions releases.
- Added explicit Cast command error logging and retry behavior.

### Documentation

- Added a polished public README, screenshots, and version-history links.
- Removed internal Unraid/template setup language from the public docs.
- Kept the release notes visible in the settings panel for quick review.

### Notes

- Added explicit versioning and a clean container/Compose deployment path.
