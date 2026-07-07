# Changelog

## 1.1.0 — 2026-07-06

### Templates

- Rebuilt the card around self-contained blocks (title/logo identity, grouped
  ratings, metadata chips, plot, progress, clock, poster) and added five
  hand-designed templates that arrange them into genuinely different
  compositions: Spotlight, Split, Hero, Lower Third, and Big Clock.
- Template picker in settings with sketch thumbnails and instant live preview —
  changes preview in the demo frame without touching the Hub until saved.

### Customization

- Custom accent color picker alongside the four themes.
- Clock styles: 12/24-hour format and optional seconds.
- Block editor now moves and resizes whole blocks: position, width, and a new
  size control; every block can be shown or hidden independently.

### UI

- Release notes moved into a slide-over panel ("What's new") instead of a
  page-bottom section.
- Demo art is embedded in the card, so the settings preview always renders
  fully even before anything has played.

### Fixes

- New `PLEX_USERS` setting limits which Plex users trigger the marquee.
  Previously any session on the server — including shared and home users —
  would take over the Hub.
- Metadata strings are now HTML-escaped on the card, so titles or ratings
  containing &, <, or quotes render correctly.

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
