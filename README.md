# Marquee

[![Build](https://github.com/Jamisonfitz/marquee/actions/workflows/container.yml/badge.svg)](https://github.com/Jamisonfitz/marquee/actions/workflows/container.yml)
[![Top language](https://img.shields.io/github/languages/top/Jamisonfitz/marquee)](https://github.com/Jamisonfitz/marquee)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Docker Pulls](https://img.shields.io/docker/pulls/jamisonfitz/marquee?logo=docker)](https://hub.docker.com/r/jamisonfitz/marquee)
[![Docker Image Version](https://img.shields.io/docker/v/jamisonfitz/marquee?sort=semver&logo=docker)](https://hub.docker.com/r/jamisonfitz/marquee/tags)
[![License](https://img.shields.io/github/license/Jamisonfitz/marquee)](LICENSE)
[![Buy me a coffee](https://img.shields.io/badge/%E2%98%95%20Buy%20me%20a%20coffee-E5A83B?logoColor=white)](https://buymeacoffee.com/jamisonfitz)

Marquee turns a Google Nest Hub into a clean now-playing display for Plex, Emby, or Jellyfin. It shows artwork, title, plot, genres, ratings, media details, progress, and a clock, then returns the Hub to ambient mode when playback stops.

![One app, many looks — templates × themes × fonts](docs/screenshots/variety.jpg)

*Same app, many looks: seven templates, per-block colors and fonts, and every block movable — your setup will not look like anyone else&rsquo;s.*

With your own library it looks like this — real posters, backdrops, and clear-logos straight from Plex:

| | |
|:---:|:---:|
| ![Street with a real library](docs/screenshots/live-street.jpg) | ![Spotlight with a real library](docs/screenshots/live-spotlight.jpg) |

## Templates

Seven layouts, switchable live from the settings page:

| | |
|:---:|:---:|
| ![Spotlight](docs/screenshots/spotlight.jpg) **Spotlight** — poster beside the full metadata stack | ![Hero](docs/screenshots/hero.jpg) **Hero** — big centered title over the backdrop |
| ![Lower Third](docs/screenshots/lowerthird.jpg) **Lower Third** — broadcast-style chyron over full-bleed art | ![Big Clock](docs/screenshots/bigclock.jpg) **Big Clock** — ambient timepiece with a now-playing strip |
| ![Street](docs/screenshots/street.jpg) **Street** — a living night scene: your poster glowing in a bulb-lit marquee, the movie logo sprayed on brick, real weather on the wall | ![Split](docs/screenshots/split.jpg) **Split** — hard split: full-height art wall beside the info column |

Plus **Fanart** — a blank canvas where [fanart.tv](https://fanart.tv) artwork
for whatever's playing crossfades on a timer (backgrounds, posters, logos,
clear art, banners, or thumbs). It ships with no blocks; add only what you
want over the art. Needs a free fanart.tv API key (Connection tab, or
`FANART_API_KEY`).

Every template is built from the same set of blocks — backdrop, clock, weather,
title, metadata, plot, ratings, progress, poster — and every block carries its
own position, size, font, and color per template, so a nudge in Spotlight
never moves anything in Street.

## The settings page is the card

Settings v2 has no wall of options. The card fills the page; you edit what
you're looking at.

![Settings v2 — the card is the page](docs/screenshots/settings-design.jpg)

- **Tap anything.** Tap a block on the live preview — or its chip below — and
  the editor shows just that block's controls: font, color, position, width,
  size, plus whatever it owns (clock style and seconds, weather effects and
  intensity, which metadata pieces show, logo art vs text title). Tap the
  card's empty background to edit the backdrop.
- **The chips tell the truth.** One pill per block on the card: × takes it
  off, "+ Add" brings anything back. When a block is on your card but has
  nothing to show for the current title — no scores yet, an emptied metadata
  line — its chip goes dim and the editor says so, instead of letting you
  adjust an element that isn't on screen.
- **Bottle a look, share it, credit travels.** "Save preset" snapshots your
  whole layout onto the template carousel. "Share this look" copies it as a
  small setup file — credited to you — and anyone who imports it gets it on
  their carousel tagged with your name, one tap from applied. Locations and
  credentials never ride along.
- **A guided tour, once.** First run walks you through the six things that
  matter, spotlighting the real interface — then gets out of the way.
- **Phones are first-class.** The preview pins to the top at a size that
  leaves room to work, and the on-screen keyboard can never cover it.

| | |
|:---:|:---:|
| ![Contextual editor](docs/screenshots/settings-editor.jpg) | ![Guided tour](docs/screenshots/settings-tutorial.jpg) |

## Features

- Live now-playing card from Plex, Emby, or Jellyfin; casts to a Nest Hub
  and hands it back to ambient mode when playback stops.
- Seven templates, including Street (animated night scene with rain, snow,
  smoke-fog, and storms that follow your real weather, intensity 1–4) and
  Fanart (rotating fanart.tv art on a blank canvas).
- Every block — clock, weather, title, plot, ratings, progress, poster —
  addable, removable, and movable per template, each with its own font and
  color. Tap it on the live preview to edit it.
- Presets and "Share this look": snapshot a layout, or export it as a small
  credited file others import in one tap. Credentials never ride along.
- Session filters (users, devices, a "do not cast" word list) and rotation
  when multiple sessions play.
- A six-step guided tour on first run; settings persist in `/config`;
  `/healthz` for monitoring.

## What You Need

- Docker
- A Plex, Emby, or Jellyfin server on the same LAN
- A Google Nest Hub on the same LAN
- A Plex `X-Plex-Token` (or an Emby / Jellyfin API key)

Marquee is designed for a trusted LAN. It has no login and should not be port-forwarded.

## Quick Start

Edit the example IP addresses and token in `compose.yaml`, then run:

```sh
docker compose up -d --build
docker compose logs -f marquee
```

Open `http://SERVER-IP:8084/`. The card served to the Hub is `http://SERVER-IP:8084/image`.

If you prefer plain Docker:

```sh
docker build -t marquee:local .
docker run -d --name marquee --restart unless-stopped --network host \
  -e PAGE_URL=http://192.168.1.10:8084/image \
  -e PLEX_HOST=http://localhost:32400 \
  -e PLEX_TOKEN=replace-me \
  -v marquee-config:/config \
  marquee:local
```

Settings persist under `./data` in Compose mode or `/config` in the container.

## Configuration

Required environment variables:

- `PAGE_URL` — this server's LAN IP + `/image`. The Hub loads this URL, so
  `localhost` will not work here.
- `PLEX_HOST` — keep `http://localhost:32400` when Plex runs on the same
  machine; otherwise its LAN IP
- `PLEX_TOKEN`

### Choosing the media backend

Plex is the default. Marquee can poll an **Emby** or **Jellyfin** server
instead — same card, same settings, same filters. Pick it on the settings
page (*Media server* panel: backend dropdown + address + key; each backend
keeps its own stored pair, changes apply ~5s after Save, no restart), or via
env: `MEDIA_BACKEND=emby` with `EMBY_HOST`/`EMBY_API_KEY`, or
`MEDIA_BACKEND=jellyfin` with `JELLYFIN_HOST`/`JELLYFIN_API_KEY`.
Keys and tokens are write-only: stored server-side, never sent back to a
browser, never in Export. Only `PAGE_URL` is required at startup — a
container with no credentials boots to the settings page. Verified against
Emby 4.9 and Jellyfin 10.11.

Cast device: open the settings page and press **Scan** — Marquee discovers
Google Cast devices on your LAN and you pick your Hub from a dropdown.
(`HUB_IP` still works as an env fallback; discovery needs the container on
the same network/VLAN as the Hub, which host networking gives you.)

Optional settings:

- `PLEX_USERS` — comma-separated Plex usernames that trigger the marquee.
  Leave empty to react to everyone on the server, including shared and home
  users (the sessions API is server-wide).
- `PLEX_DEVICES` — comma-separated player/device names that trigger the
  marquee; empty allows any device. Both filters are also editable live on
  the settings page, which shows the exact names of active sessions.
- `BLOCK_TAGS` — comma-separated **do-not-cast** words checked against each
  session's genres, tags, and content rating (e.g. `adult, xxx, 18+, nc-17,
  tv-ma`); a match is never cast. Case-insensitive; words of 3+ characters
  match inside terms, shorter ones match exactly. Also on the settings page.

When more than one allowed session is playing, each takes the display in turn.
**Rotate between sessions** on the settings page sets how long each gets
(default 30 seconds; 0 pins the first, ordered by user then device). Sessions
are always sorted before one is picked, so the card never flips at random
because the server reordered its session list.
- `TMDB_API_KEY` — enables the credits-scene badge
- `FANART_API_KEY` — container default for the Fanart template's key
  (the settings page value wins)
- `POLL_SECONDS` default `5`
- `SERVE_PORT` default `8084`
- `REPO_DIR` — the container sets `/app` (the code's own default is `/repo`)
- `DATA_DIR` — the container sets `/config` (the code's own default is
  `REPO_DIR/output`)

### Env vars are defaults, not overrides

Some settings exist both as env vars and on the settings page. They all follow
one rule:

| Setting | Env var | Settings page | How they combine |
|---|---|---|---|
| Cast device | `HUB_IP` | Cast device picker | The settings page **wins**; the env var is the default when no device has been picked. |
| Users | `PLEX_USERS` | Plex users | Same rule: a typed list **replaces** the env var; a blank field inherits it. |
| Devices | `PLEX_DEVICES` | Devices | Same rule. |
| Do not cast | `BLOCK_TAGS` | Do not cast | Same rule. |

The settings page shows each inherited env value as a greyed placeholder —
`jamison (from PLEX_USERS)` — so a blank field reads as *inheriting this*
rather than *nothing is set*, and typing a value (then clearing it later)
behaves the way you'd expect. The placeholders come from `/env-defaults`,
which serves those values and nothing else — an allowlist, so nothing
credential-shaped can leak to a browser.

Health status is available at `/healthz` and includes the version.

## Plex Token

1. Sign in to Plex Web and open an item on your server.
2. Select **More (`…`) → Get Info → View XML**.
3. Copy the value after `X-Plex-Token=` from the browser address bar.
4. Test it at `http://PLEX-IP:32400/?X-Plex-Token=YOUR_TOKEN`.

See Plex's [token instructions](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/).
Never put a real token in Compose files, screenshots, issues, or commits.

For credits-scene badges, create a TMDb account, open **Account Settings → API**, request a key, and set `TMDB_API_KEY`.

## Tips

**Silence the cast chime.** Every time Marquee takes over the display, the
Nest Hub plays its connect sound. That chime comes from the device, not from
Marquee, and there's a switch for it: open the **Google Home** app → tap
your Hub → **Settings (gear) → Accessibility** → turn off **Play sounds on
start/end of casting**. One-time change; casting is silent afterwards.

## Community Forks & Related Projects

- [TRusselo's fork](https://github.com/TRusselo/marquee) — exploring Emby
  support, ESP32/ESPHome displays, Home Assistant integration, and vertical
  poster views. Independent project, not maintained or supported here, but
  worth a look if that's your stack.

## Development

```sh
docker build -t marquee:test .
docker run --rm marquee:test python cast/cast.py --selftest
docker logs -f marquee
```

The service uses [catt](https://github.com/skorokithakis/catt) to launch DashCast on the Hub. Ratings come from Plex metadata; optional credits-scene keywords come from TMDb.

### Cast behavior

Marquee checks that DashCast is active, casts the `/image` URL when playback starts, and releases the Hub when playback stops. Container tests cannot prove physical Hub behavior, so before publishing a release:

1. Open `PAGE_URL` from another LAN device.
2. Start a Plex movie or episode and confirm the Hub loads the card.
3. Pause and resume playback and confirm the progress state updates within one poll interval.
4. Stop playback and confirm the Hub returns to ambient mode.
5. Review `docker logs marquee`; there should be no `catt ... failed` message.

## Credits

Marquee stands on generous shoulders:

- **[TRusselo](https://github.com/TRusselo)** — the Emby & Jellyfin backends,
  session filters and rotation, the dead-card heartbeat, the content filter,
  and a steady stream of sharp fixes.
- **[catt](https://github.com/skorokithakis/catt)** by Stavros Korokithakis —
  the casting engine that actually puts the card on your Hub (BSD, bundled
  stock).
- The Street template's weather effects adapt open CodePen techniques by
  sheepjs, Ivan Odintsov, Braeden Craig, and Tiff Wong — full notes and
  sources in [CREDITS.md](CREDITS.md).

## Support

Marquee is free and stays that way. If it makes your living room a little
more cinematic, you can [buy me a coffee](https://buymeacoffee.com/jamisonfitz) ☕
