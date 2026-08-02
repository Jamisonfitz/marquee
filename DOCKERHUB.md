# Marquee

**Your media server's now-playing, as a cinematic marquee on a Google Nest Hub.**

Marquee watches Plex, Emby, or Jellyfin and casts a designed now-playing card
to your Hub the moment something plays — artwork, clear-logo, plot, ratings,
progress, a clock, even live local weather on the animated Street scene. When
playback stops, the Hub goes back to being a photo frame. Self-hosted, one
container, no accounts, no cloud.

## Why people like it

- **Six designed templates** — Spotlight, Split, Hero, Lower Third, Big Clock,
  and Street: a living night scene with marquee bulbs, sprayed logos, and
  rain, snow, or fog that follows your real local weather.
- **The settings page is the card.** Tap any block on the live preview and its
  controls appear — font, color, position, size, and that block's own
  settings. No wall of toggles; chips under the preview tell you exactly
  what's on the card (and go dim when a block has nothing to show).
- **Make it yours, then share it.** Every block carries its own color and font
  per template. Save presets onto the template carousel, or export a look as a
  small credited setup file a friend can import in one tap.
- **Plays fair with your household** — user and device filters, session
  rotation, and a "do not cast" content filter so the marquee never overshares.
- **Original demo art** — the preview runs on fictional demo films, so nothing
  copyrighted ships in the image.

## Quick start

```sh
docker run -d --name marquee --restart unless-stopped --network host \
  -e PAGE_URL=http://YOUR-SERVER-IP:8084/image \
  -e PLEX_HOST=http://localhost:32400 \
  -e PLEX_TOKEN=replace-me \
  -e HUB_IP=YOUR-HUB-IP \
  -v marquee-config:/config \
  jamisonfitz/marquee:latest
```

Open `http://YOUR-SERVER-IP:8084/` for settings (a guided tour runs on first
visit). Emby/Jellyfin: pick the backend on the Connection tab, or set
`MEDIA_BACKEND` / `EMBY_HOST` / `EMBY_KEY` env vars.

Designed for a trusted LAN — no login, don't port-forward it.

**Docs, templates gallery, and source:**
https://github.com/Jamisonfitz/marquee

Free forever. If it makes your living room a little more cinematic:
https://buymeacoffee.com/jamisonfitz ☕
