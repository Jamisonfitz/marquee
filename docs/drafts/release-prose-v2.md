# Release bodies — applied to GitHub 2026-08-02

Kept in the repo as the source of truth for the published release text.
Voice rule: concise — features added or removed, what's in it for you.

---

## v2.0.0 — Settings v2

**The settings page is the card now.** The live preview fills the page; tap
any block — or the background — and only that block's controls appear: font,
per-block color (new), position, size, and its own settings.

- **Presets** — snapshot your look onto the template carousel.
- **Block chips** — one pill per block: tap to edit, × to remove, "+ Add"
  brings anything back.
- **A six-step guided tour**, once, for new installs.
- **Phones done right** — the preview pins to the top; the keyboard can
  never cover it.

Removed: the vibes/theme rows (per-block color replaces them; saved themes
keep tinting until you recolor), card-wide fonts, and poster side. Every old
save and export still imports cleanly.

---

## v2.1.0 — honest chips, shareable looks

- **Share your look.** Export your setup as a small credited file; importing
  lands it on the carousel as a preset "by you", one tap from applied.
  Credentials and location never ride along.
- **Honest chips.** A block with nothing to show for the current title goes
  dim and dashed, and the editor says so.
- **Credits + support.** Contributors, catt, and the weather-technique
  artists are named in About — plus an optional Buy Me a Coffee button.
- What's new renders as release cards instead of a changelog dump.

---

## v2.2.0 — the Fanart template

- **New: Fanart template.** fanart.tv artwork for whatever's playing
  crossfades on a timer — backgrounds by default, or posters, logos, clear
  art, banners, thumbs. Starts empty; add only the blocks you want over the
  art. Free fanart.tv API key goes on the Connection tab (write-only, like
  every key; `FANART_API_KEY` works too).
- **New: fog is real smoke** — rising particles (technique by dburrell), and
  a frame-rate bug foggy weather always carried is gone.
- **New: try any weather** from the editor — rain, snow, storm, fog, cloudy,
  day/night. Preview only, never saved.
- **Fixed: adding a block always shows it.** Several template/block combos
  (Metadata on Big Clock, Plot on Hero…) silently never rendered.
