# Changelog

## Unreleased

### Env vars are defaults you can see, not overrides you can't

`PLEX_USERS` / `PLEX_DEVICES` used to **merge** with the settings page instead
of being replaced by it. The env list was invisible — the Users field showed
empty while every other session was silently ignored — and unliftable: the
page could only add names to what the env var already allowed, so clearing the
field changed nothing. `HUB_IP` alone behaved correctly.

Now all three follow `HUB_IP`'s rule: a typed value replaces the env var, a
blank field inherits it. The inherited value is shown as a greyed placeholder —
`jamison (from PLEX_USERS)` — via a new `/env-defaults` route that serves
exactly those three values and nothing else, an allowlist so nothing
credential-shaped can leak to a browser by default. `selftest` pins the
override semantics (blank inherits, typed replaces, the env is never unioned
back in) and the allowlist (no token/key-shaped name may ever join the hints).

### Emby and Jellyfin join Plex

Marquee can now watch an Emby or Jellyfin server instead of Plex. Set
`MEDIA_BACKEND=emby` (with `EMBY_HOST` / `EMBY_API_KEY`) or
`MEDIA_BACKEND=jellyfin` (with `JELLYFIN_HOST` / `JELLYFIN_API_KEY`); Plex
stays the default and the Plex path is untouched.

Both backends produce the same now-playing dict, so every template, theme,
toggle, and the session filters and rotation work identically — the selftest
asserts the two parsers emit the same keys. Emby's `/Sessions` omits some of
the fields the card wants (genres, media streams, ratings, overview), so the
backend fetches them from `/Items` once per title and caches them, exactly as
the Plex path caches its metadata lookups. Artwork (poster, backdrop, logo)
comes from the item image endpoints at the same sizes the Plex transcoder
delivers.

Jellyfin forked from Emby in 2018 and the handful of APIs Marquee uses —
`api_key` query auth, `/Sessions`, `/Items`, `/Items/{id}/Images/*` — are
byte-compatible, so Jellyfin rides the Emby code path unchanged. The
`JELLYFIN_*` env names are aliases for the `EMBY_*` pair, accepted so a
compose file can say what it means. Verified end to end against live Emby and
Jellyfin (10.11) servers, through to the card rendering on a real Nest Hub.

### Switch backends from the settings page

A new **Media server** panel picks the backend: one dropdown (Plex / Emby /
Jellyfin), one server-address field, one key field. The dropdown decides
which backend the two fields edit; each backend keeps its own stored pair,
so switching between servers loses nothing. Like every other setting,
nothing changes until **Save**; the choice is then resolved every poll, so a
saved change takes effect within ~5 seconds — no container restart. The
settings page wins and env is the container-level default, exactly the rule
the cast device field has always followed; with nothing set anywhere, the
backend is plex, as it has always been.

Keys and tokens are write-only secrets: stored server-side, never served
back to a browser. `/settings.json` replaces each with a saved/not-saved
hint, the page shows *saved — blank keeps it*, and Export/Import never
carries them. Saving a backend that has no server configured anywhere is
rejected with a clear error rather than stored — a backend that fails
silently on the next poll would just be a blank display with no explanation.

With that, only `PAGE_URL` is required at startup. A container with no
media-server credentials at all no longer exits; it warns and serves the
settings page, where the server address and key finish the job. Every
credential env var still works exactly as before — it is simply no longer
the only way in.

## 1.8.0 — 2026-07-19

### The block editor grows up

- **Font per block**: a Block font picker next to Selected block. The clock,
  progress bar, plot — any block — can now carry its own face; Theme default
  keeps the card-wide fonts. Title & logo blocks apply it to the text title
  too.
- **Snap to grid**: get a block close, hit the button, and its top-left corner
  lands on the nearest line of the grid you already see while editing
  (every 2.5% of the screen).
- **Justify tells the truth**: Left/Center/Right now aligns the logo image and
  the plain-text title the same way, in every template. Before, templates that
  center the title block (Hero, Big Clock) kept centering the *logo* while the
  text obeyed your choice — so a movie without a clear-logo drew its title
  off-center from where the logo had been.
- The editor also no longer writes `align: left` into your layout the first
  time you touch a slider — that silent write was how most off-center titles
  happened. No Justify button lights up until you actually pick one.

### Phones stopped fighting you

The preview, the block controls, and Save now ride together in one fixed
bottom sheet. Scrolling the settings page can't graze a slider and skew a
block, Save is always next to what you're previewing, and tapping a block in
the preview unfolds the editor right above it. On desktop nothing moved —
the editor just gained the same Snap button and font picker, and folds away
if you want it gone.

## 1.7.0 — 2026-07-14

### The Hub no longer sits on a blank screen

Marquee decided whether to cast by asking the Hub whether the DashCast app was
loaded. That answers the wrong question: a Hub whose card page has died — it
crashed, reloaded into nothing, or was left holding a stale page — keeps
reporting DashCast forever. Marquee concluded the card was already up and did
nothing, silently, while the display showed nothing. There was no error, and
nothing in the log.

The card fetches `/now-playing.json` every `POLL_SECONDS`, so the server already
knew whether the page was alive; it just wasn't looking. That fetch is now
timestamped, and a card silent for longer than 45 seconds is treated as gone and
re-cast. A page cast moments ago gets one window to load before it counts.

`/healthz` reports `cardPollAgo`, `cardAlive`, and `cardGrace`, so a display
showing a dead page is now visible from outside the container — which matters,
because per-request logging is suppressed.

### More than one person is watching

When two people stream at once, the card used to flip between their titles at
random. `/status/sessions` has no defined order, Plex reorders it as sessions
come and go, and Marquee took whichever session happened to be listed first —
re-deciding every poll.

Sessions are now sorted by user, then device, then title, so the choice is
stable. When more than one allowed session is playing, each takes the display
in turn: a new **Rotate between sessions** setting, 30 seconds by default. Set
it to 0 to pin the first one instead.

Rotation is a pure function of the clock, so nothing needs to be remembered
across a restart, and two displays watching the same server show the same
session at the same time. Your user and device filters still decide who is
eligible — rotation only orders whoever is left, so filtering to yourself with
two devices rotates rather than flickering.

## 1.6.0 — 2026-07-09

### Share your look

- **Export / Import**: two buttons next to Save. Export copies your whole
  setup as text; Import pastes someone else's and applies it (your cast
  device stays yours). Post your look, let people steal it.

### Mobile

- The settings page works properly on phones now — no more sideways
  overflow — and the **live preview rides the bottom of the screen**, so
  stepping vibes, flipping toggles, and changing fonts is always visible
  while you scroll the controls.

### Type

- **Card font** joins Title font: pick a face for everything else — plot,
  metadata, clock. Per-element size still lives on the block editor's
  Size slider.

### Odds & ends

- Street's pay phone is retired.
- `?demo=N` pins a demo film again (and holds through the rotation timer).
- README leads with a variety collage and real-library screenshots.

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
