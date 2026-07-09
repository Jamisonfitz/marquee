# Changelog

## 1.4.0 — 2026-07-08

### Session filters

- New "Who triggers the marquee" section in settings: limit casting to
  specific Plex **users** and **devices**, editable live — no container
  restart. Empty fields keep the old behavior (everyone, any device), so a
  shared user's stream — or your own phone away from home — no longer takes
  over the Hub.
- An "Active sessions" check shows exactly who is playing what on which
  device, with the exact names to copy into the filters, and flags sessions
  the current filters exclude.
- `PLEX_DEVICES` env var joins `PLEX_USERS` as a container-level fallback;
  both merge with the settings-page lists.

### Demo reel

- The single demo movie is now a four-film reel of original fictional
  comedies — *Shaking Hands & Kissing Babies* (campaign-poster style),
  *Rat King III: Still Gnawing* (graffiti stencil), *Participation Trophy*
  (sticker bomb), and *B-Sides* (vinyl sleeve). Each has hand-built vector
  poster, backdrop, and logo art; the preview picks one at random per load,
  and pure demo mode (`/image?demo`) rotates every 20 seconds.
  `?demo=N` pins a film. Roughly 70KB lighter than the old embedded art.
- Fifth film: *Justafaze* — a graffiti-nerd documentary where the quotes are
  part of the tag ("it's ironic because it's not"). Weighted rotation makes it
  the rare pull — films carry a `weight`, and Justafaze shows a third as
  often as the rest.

### Street template & vibes

- New **Street** template: a living night scene — brick wall, pay phone,
  and your poster hanging in a bulb-lit **NOW PLAYING** marquee frame. The
  clear-logo (or title) reads as spray-painted onto the brick, grain and all.
  The lighting is alive: marquee bulbs twinkle on their own phases, the sign
  bulbs chase, the neon flickers now and then, the street-lamp pool breathes,
  and the marquee trim re-lights in your theme's accent. Honors
  prefers-reduced-motion.
- Four new themes named for the demo reel: **Campaign** (navy & red tape),
  **Concrete** (back-alley gold), **Trophy** (gold-star yellow), and
  **B-Sides** (dollar-bin orange).
- **Vibes**: one-tap presets bundling theme + font + template — Campaign
  Trail, Back Alley, Gold Star, Dollar Bin, Simulation ("we're all just
  programming ourselves"), and Third Act ("the universe is on its final
  reel"). Tap one, tweak, save.

### Faze mode (the personal cut)

- `?justafaze=1982` on the card URL unlocks a personal edition of Street:
  the writer himself is out on the sidewalk spray-painting whatever's
  playing — the clear-logo on the wall is his work in progress — while the
  marquee (holding the live Plex poster) hangs at a slight tilt. Smoke
  creeps from a manhole, heavier in fog.
- Live local weather, no API key: the container asks Open-Meteo (location
  auto-detected once from the server IP, cached 15 min, `/weather`
  endpoint) and the card renders rain, snow, fog, or overcast to match
  what's outside. Real day/night too — daylight raises the wall and rests
  the bulbs. `?wx=rain|snow|fog|cloud` and `?day=1|0` force conditions.
- Justafaze is est. 1982 now, as it always was.

### Preview & accent

- Changing the title font now previews instantly even when a clear-logo is
  shown: the card swaps in the text title for a few seconds so you can see
  the font.
- A custom accent color now tints as deeply as the built-in themes: metadata
  chip borders and the progress track pick it up too.
- The Big Clock template's clock now glows in the accent color.

## 1.3.0 — 2026-07-07

### Layout & type

- Every block can now be justified left, center, or right from the editor.
- Title fonts: Bebas Neue, Oswald, Playfair Display, Cinzel, and Space
  Grotesk (free Google fonts, system fallback when offline).
- Themes go deeper: each theme now tints panels, chips, and progress tracks,
  and the accent glows through the title and progress bar.

### Feel

- Saves reach the Hub in ~2 seconds — the card polls settings on a fast
  loop instead of waiting for the next now-playing cycle.
- Template picker cards show real screenshots of each layout.
- The demo movie now includes a title logo, so the clear-logo look
  (pulled from Plex metadata on real playback) is visible in the preview.

## 1.2.0 — 2026-07-07

### Device discovery

- The settings page now finds Google Cast devices on your LAN (mDNS via
  `catt scan`) — press Scan and pick your Hub from a dropdown instead of
  typing an IP. `HUB_IP` remains as an env fallback and is no longer
  required, so the container starts fine before a device is chosen.

### Cleanup

- Removed one-time repo bootstrap scripts.
- `PLEX_HOST` defaults to `http://localhost:32400`; field descriptions now
  explain why `PAGE_URL` must be a LAN IP the Hub can reach.

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
