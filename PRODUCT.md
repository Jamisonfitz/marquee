# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

1. **Self-hosters discovering Marquee** (owner-confirmed primary, 2026-08-01: "community
   project that grows" — when choices conflict, the new user wins). Unraid/Docker people
   arriving from Community Applications, GitHub, or Reddit; they judge in the first five
   minutes: does it cast, does it look good, do the settings make sense.
2. The household watching the Hub — the card is read at couch distance on a 7″ screen
   while something plays; nobody interacts with it.
3. Contributors (TRusselo precedent: backends, filters, heartbeat) and setup-sharers —
   the `marquee-setup` file format with author credit exists to grow this group.
4. The owner (Jamison) — daily driver on his own Tower/Nest Hub.

## Product Purpose

Marquee turns a Google Nest Hub into a cinematic now-playing display for Plex, Emby, or
Jellyfin: a designed card (six templates, per-block layout/color/font, live weather on the
Street scene) casts when something plays and hands the Hub back to ambient mode when it
stops. Success = a growing community project: CA installs, stars, contributors, people
trading credited setup files.

## Positioning

Not a dashboard, not a scraper overlay — a *designed marquee*. The mechanisms a neighbor
project can't truthfully copy: direct-manipulation settings where the card itself is the
page (tap a block, edit that block), truth-accounting chips that never lie about what's
rendered, per-template per-block ownership (position/size/font/color), original fictional
demo films so nothing copyrighted ships, and credited shareable setups.

## Operating Context

- One Docker container on a trusted LAN (no login; never port-forwarded). Casts via
  bundled `catt` to a Hub found by scan or HUB_IP.
- Two surfaces: `/` the settings page (Operate; phone + desktop, first-run tour) and
  `/image` the card (viewed on the Hub; 1280×800 16:10, also the settings preview iframe).
- Settings are drafts until Save; the Hub polls and picks changes up in ~5s. Env vars are
  container defaults; the settings page wins.
- Release pipeline: PR → merge → tag `v*` → CI builds Docker Hub images; Unraid template;
  What's new tab renders CHANGELOG.md as release cards.

## Capabilities and Constraints

- Single-file surfaces by design: `cast/settings.html`, `output/index.html`,
  `cast/cast.py` (stdlib-only Python server). No frontend framework, no build step;
  Google Fonts load with graceful offline fallback. Tables like TEMPLATE_DEFAULT_BLOCKS
  are deliberately triplicated across the three files — change all or none.
- Server `/save` is a strict allowlist with validators/clamps; sliders must mirror
  `clean_block_position` ranges (x/y ±100, width 5–100, scale 0.3–3). Secrets are
  write-only. Old exports must always import (migrations run on load and import).
- postMessage protocol between settings and card (`marquee-cfg/-select/-selection/-set/
  -snap/-layout/-blocks/-demo-next`) is the contract; chrome may change, protocol keeps.
- Demo content must remain original fiction (Rat King III, Participation Trophy…) —
  never real posters in the app; README/marketing screenshots may use real library art.

## Brand Commitments

- Name: Marquee; wordmark "MARQUEE settings"; Docker Hub `jamisonfitz/marquee`.
- The current identity (night ground, amber #E5A83B, Bebas Neue letterboard, bulb rails)
  is **open to evolution** (owner-confirmed 2026-08-01) — incumbent evidence, not binding.
- Voice: plain, warm, explain-the-why. Release notes and What's new are feature prose,
  never dumped changelog text. Support link: buymeacoffee.com/jamisonfitz (optional, quiet).
- Credit is a value: contributors and borrowed techniques are named (About tab,
  CREDITS.md); shared setups carry their author's name.

## Evidence on Hand

- Live installs: prod + dev rigs on Tower; CA-approved Unraid template.
- Real contributor history (TRusselo PRs #16–#25), issue traffic (#9 ESP32/Jellyfin asks).
- Screenshot pipeline (puppeteer + alpine-chrome rigs) and `--selftest`; docs/screenshots
  gallery incl. real-library shots (owner-approved exception).
- No testimonials, install counts, or benchmarks recorded — do not invent any.

## Product Principles

1. The card is the settings — edit what you're looking at; nothing more than one tap
   from the thing it changes.
2. Never lie to the user: chips reflect what's actually rendered; dead controls look dead;
   drafts say "save to apply."
3. New-user first five minutes beats power-user depth when they conflict.
4. Ship credit with the work — contributors, techniques, and shared setups all carry names.
5. Migrations are forever: an old save or export never breaks, never 400s.

## Accessibility & Inclusion

**Across-the-room legibility is a hard floor** (owner-confirmed): card text must read
from couch distance on a 7″ Hub — template and type changes are judged at that distance,
not at desk zoom. Existing behaviors to preserve: prefers-reduced-motion honored on both
surfaces; amber focus-visible rings; ≥44px touch targets on phone settings.
