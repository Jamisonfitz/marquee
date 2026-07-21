# Marquee

[![Build](https://github.com/Jamisonfitz/marquee/actions/workflows/container.yml/badge.svg)](https://github.com/Jamisonfitz/marquee/actions/workflows/container.yml)
[![Top language](https://img.shields.io/github/languages/top/Jamisonfitz/marquee)](https://github.com/Jamisonfitz/marquee)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Docker Pulls](https://img.shields.io/docker/pulls/jamisonfitz/marquee?logo=docker)](https://hub.docker.com/r/jamisonfitz/marquee)
[![Docker Image Version](https://img.shields.io/docker/v/jamisonfitz/marquee?sort=semver&logo=docker)](https://hub.docker.com/r/jamisonfitz/marquee/tags)
[![License](https://img.shields.io/github/license/Jamisonfitz/marquee)](LICENSE)

Marquee turns a Google Nest Hub into a clean now-playing display for Plex, Emby, or Jellyfin. It shows artwork, title, plot, genres, ratings, media details, progress, and a clock, then returns the Hub to ambient mode when playback stops.

![One app, many looks — templates × themes × fonts](docs/screenshots/variety.jpg)

*Same app, nine looks: six templates × eight themes × six fonts × any accent color.*

With your own library it looks like this — real posters, backdrops, and clear-logos straight from Plex:

| | |
|:---:|:---:|
| ![Street with a real library](docs/screenshots/live-street.jpg) | ![Spotlight with a real library](docs/screenshots/live-spotlight.jpg) |

## Templates

Six designed layouts, switchable live from the settings page:

| | |
|:---:|:---:|
| ![Spotlight](docs/screenshots/spotlight.jpg) **Spotlight** — poster beside the full metadata stack | ![Hero](docs/screenshots/hero.jpg) **Hero** — big centered title over the backdrop |
| ![Lower Third](docs/screenshots/lowerthird.jpg) **Lower Third** — broadcast-style chyron over full-bleed art | ![Big Clock](docs/screenshots/bigclock.jpg) **Big Clock** — ambient timepiece with a now-playing strip |
| ![Street](docs/screenshots/street.jpg) **Street** — a living night scene: your poster glowing in a bulb-lit marquee, the movie logo sprayed on brick, real weather on the wall | ![Split](docs/screenshots/split.jpg) **Split** — hard split: full-height art wall beside the info column |

Every template is built from the same set of blocks — title/logo identity, weather, grouped ratings, metadata chips, plot, progress, clock, poster — so themes, custom accent color, and fonts carry across all of them. Which blocks appear, and where, is set per template: add or remove any block from any template independently, and reposition them without affecting the others.

![Settings UI](docs/screenshots/settings.jpg)

## Features

- Live now-playing card — from Plex, Emby, or Jellyfin — with six designed
  templates: Spotlight, Split, Hero, Lower Third, Big Clock, and Street
  (animated marquee bulbs, real weather, and day/night, all included).
- Eight themes, one-tap Vibe presets, a custom accent color, five title
  fonts, 12/24-hour clock styles, and per-block show/hide toggles.
- Add or remove any block — clock, weather, title, plot, ratings, progress,
  poster — from any template independently, and reposition it without
  affecting the others. Nothing changes until you actually add or remove
  something; every template still ships with its original layout.
- Session filters: limit casting to your Plex users and your devices, live
  from the settings page — shared users no longer take over the display.
- A drag-and-slider editor for moving, sizing, justifying, and scaling each
  card block, with an instant demo preview featuring original fictional
  films (no copyrighted art). On phones, the template and vibe pickers
  collapse into one swipeable strip so the editor doesn't fight the screen
  for room.
- Persisted settings, health checks, and a Docker-first deployment path.
- Google Nest Hub casting with clean idle handoff back to ambient mode.

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
instead — same card, same settings page, same session filters and rotation.
Pick the backend either place; the settings page wins, env is the container
default (the same rule the cast device follows):

- **Settings page** — a *Media server* panel: one backend dropdown (Plex /
  Emby / Jellyfin), one server-address field, one key field. The dropdown
  picks which backend the two fields edit, and each backend keeps its own
  stored pair, so switching loses nothing. Nothing changes until you press
  **Save**; a saved change is picked up on the next poll (~5s), no container
  restart. Keys and tokens are stored server-side and never sent back to a
  browser — the page only shows *saved*; a blank field keeps the stored
  value, and Export/Import never includes them.
- **Env** — `MEDIA_BACKEND=emby` with `EMBY_HOST` (e.g.
  `http://localhost:8096`) and `EMBY_API_KEY` (Emby dashboard → Advanced →
  API Keys), or `MEDIA_BACKEND=jellyfin` with `JELLYFIN_HOST` and
  `JELLYFIN_API_KEY` (Jellyfin dashboard → API Keys). Jellyfin is an
  API-compatible fork of Emby and rides the same code path; either env pair
  works with either backend, and the pair matching the backend name wins
  when both are set. `PLEX_HOST`/`PLEX_TOKEN` are not required when the
  backend is emby or jellyfin.

Only `PAGE_URL` is required at startup: a container with no media-server
credentials boots to the settings page, where they can be entered.

The backends emit the same now-playing shape, so everything downstream —
templates, themes, toggles, `/now-playing.json` — behaves identically.
Verified against Emby 4.9 and Jellyfin 10.11.

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
- `BLOCK_TAGS` — comma-separated **do-not-cast** words, checked against each
  session's genres, tags, and content rating. A match means that session is
  never cast, so the marquee cannot overshare what someone is watching —
  e.g. `adult, xxx, 18+, nc-17, tv-ma`. Matching is case-insensitive; words
  of three or more characters match inside terms (`adult` also blocks
  "Adult Animation"), shorter words must match a term exactly (`r` blocks
  the R rating without blocking Horror). Works on all three backends; also
  editable on the settings page.

When more than one allowed session is playing, each takes the display in turn.
**Rotate between sessions** on the settings page sets how long each gets
(default 30 seconds; 0 pins the first, ordered by user then device). Sessions
are always sorted before one is picked, so the card never flips at random
because the server reordered its session list.
- `TMDB_API_KEY`
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

(Older versions **merged** the user/device env filters with the settings page
instead: the env list was invisible in the UI and clearing the field could
never lift it. If `PLEX_USERS=jamison` was set, the Users field showed up
*empty* while every session except `jamison`'s was silently ignored, and
clearing the field changed nothing.)

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
