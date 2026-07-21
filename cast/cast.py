#!/usr/bin/env python3
"""Marquee — a "now playing" marquee for Google Nest Hubs.
The whole app in one container: front end + back end.

Backend: polls the media server every POLL_SECONDS; while something plays it
downloads poster/backdrop/logo, writes now-playing.json, and casts the card to
the Hub; when idle it releases the Hub.

The media server is chosen on the settings page or by env (settings win,
env is the container default, plex when neither says otherwise):
  MEDIA_BACKEND=plex|emby|jellyfin -> get_session() -> current_session() /
  emby_current_session() (jellyfin shares the emby path — API-compatible fork)
Each backend's host and API key/token can also be entered on the settings
page (one host + key field pair, pointed at the backend the dropdown picks);
secrets are stored server-side and never served back to a browser.

Frontend (one HTTP server on :8084): serves the card page and art from
output/, the settings UI at /settings, /save, and /release-notes.

Env knobs: PAGE_URL, POLL_SECONDS, REPO_DIR, SERVE_PORT, DATA_DIR.
  Plex:     PLEX_HOST, PLEX_TOKEN
  Emby:     EMBY_HOST, EMBY_API_KEY
  Jellyfin: JELLYFIN_HOST, JELLYFIN_API_KEY (or the EMBY_ pair; shared backend)
Optional TMDB_API_KEY enables the credits-scene badge; optional PLEX_USERS /
PLEX_DEVICES limit which users and player devices trigger the marquee (also
editable live on the settings page); both backends honor both filters. The
cast device comes from the settings page (auto-discovered via catt scan) or
the HUB_IP env fallback.
"""
import json
import mimetypes
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "1.7.0"
HUB_IP = os.environ.get("HUB_IP", "")
PAGE_URL = os.environ.get("PAGE_URL", "")
PLEX = os.environ.get("PLEX_HOST", "").rstrip("/")
TOKEN = os.environ.get("PLEX_TOKEN", "")
POLL = int(os.environ.get("POLL_SECONDS", "5"))
REPO = os.environ.get("REPO_DIR", "/repo")
TMDB_KEY = os.environ.get("TMDB_API_KEY", "")
SERVE_PORT = int(os.environ.get("SERVE_PORT", "8084"))
def csv_set(value):
    return {v.strip().lower() for v in (value or "").split(",") if v.strip()}


# Comma-separated Plex usernames/device names that may trigger the marquee;
# empty = everyone / any device. The env var is the container-level default:
# whatever is typed on the settings page replaces it, exactly as HUB_IP
# behaves. The raw strings are kept so the settings page can show them as
# placeholders — an env filter nobody can see is an env filter that lies.
ENV_USERS = os.environ.get("PLEX_USERS", "")
ENV_DEVICES = os.environ.get("PLEX_DEVICES", "")
USERS = csv_set(ENV_USERS)
DEVICES = csv_set(ENV_DEVICES)


def filter_set(saved, env_default):
    """The allow-list actually in force: what the settings page says, or the
    container's env default when that field is blank.

    Overrides rather than merges. A union would let an env var filter sessions
    that the settings page shows no sign of, and could never be lifted from the
    UI — clearing the field would change nothing.
    """
    chosen = csv_set(saved)
    return chosen if chosen else csv_set(env_default)


# Only these env vars are ever shown to the settings page. An allowlist, not a
# denylist: a future PLEX_TOKEN-shaped variable must not leak by default.
ENV_HINT_KEYS = ("hubIp", "plexUsers", "plexDevices")


def env_defaults():
    """Container-level defaults the settings page shows as placeholders, so a
    blank field reads as "inheriting this" instead of "nothing is set"."""
    return {"hubIp": HUB_IP, "plexUsers": ENV_USERS, "plexDevices": ENV_DEVICES}

BACKENDS = ("plex", "emby", "jellyfin")
# MEDIA_BACKEND is the container-level default; the settings-page dropdown
# overrides it without a restart. Empty or unknown means plex.
ENV_BACKEND = os.environ.get("MEDIA_BACKEND", "").lower()
if ENV_BACKEND not in BACKENDS:
    ENV_BACKEND = "plex"


def uses_emby_backend(backend):
    """Jellyfin forked from Emby; the /Sessions, /Items and image APIs this app
    uses are identical (verified against Jellyfin 10.11), so both share the Emby
    session path and the same env-var seam."""
    return backend in ("emby", "jellyfin")


def media_backend(settings=None):
    """Backend picked in settings wins; MEDIA_BACKEND env is the fallback —
    the same rule hub_ip() follows. Resolved per poll, so a *saved* change
    applies on the next poll without a restart."""
    s = settings if settings is not None else load_settings()
    chosen = (s.get("mediaBackend") or "").lower()
    return chosen if chosen in BACKENDS else ENV_BACKEND


def get_session():
    """Current now-playing dict from the configured backend, or None."""
    return (emby_current_session() if uses_emby_backend(media_backend())
            else current_session())

OUTPUT = os.path.join(REPO, "output")
JSON_PATH = os.path.join(OUTPUT, "now-playing.json")
DATA_DIR = os.environ.get("DATA_DIR", OUTPUT)
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")

THEMES = ("amber", "ice", "crimson", "emerald",
          "campaign", "concrete", "trophy", "bsides")
TEMPLATES = ("spotlight", "split", "hero", "lowerthird", "bigclock", "street")
TITLE_FONTS = ("system", "bebas", "oswald", "playfair", "cinzel", "grotesk")
ACCENT_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
IP_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
DEFAULT_SETTINGS = {
    "hubIp": "",
    "template": "spotlight",
    "theme": "amber",
    "accent": "",
    "titleFont": "system",
    "bodyFont": "system",
    "posterSide": "right",
    "clockFormat": "12h",
    "clockSeconds": False,
    "showPlot": True, "showGenres": True, "showScores": True,
    "showMediaInfo": True, "showContentRating": True, "showRuntime": True,
    "showProgress": True, "showClock": True,
    "backdrop": True, "logo": True,
    "plexUsers": "", "plexDevices": "",
    "rotateSeconds": 30,
    "showWeather": False, "weatherZip": "", "weatherUnits": "f",
    "blockLayout": {},
    "mediaBackend": "",       # "" = inherit MEDIA_BACKEND env (plex when unset)
    "plexHost": "", "plexToken": "",
    "embyHost": "", "embyKey": "",
    "jellyfinHost": "", "jellyfinKey": "",
}

# Keys/tokens are write-only: stored in settings.json but never served back to
# a browser — /settings.json replaces each with a saved/not-saved hint.
SECRET_SETTINGS = ("plexToken", "embyKey", "jellyfinKey")


def served_settings(settings=None):
    """Settings as the browser may see them: each secret is swapped for a
    boolean <name>Set hint, so the page can say "saved" without knowing it.
    envBackend rides along so the page can show the container's default."""
    s = dict(settings if settings is not None else load_settings())
    for k in SECRET_SETTINGS:
        s[k + "Set"] = bool(s.pop(k, ""))
    s["envBackend"] = ENV_BACKEND
    return s

EDITABLE_BLOCKS = ("clock", "identity", "meta", "plot", "ratings",
                   "progress", "poster", "stinger")

_meta_cache = {}  # ratingKey -> extras dict


def plex_creds(settings=None):
    """(host, token) for Plex: the settings page wins, PLEX_HOST/PLEX_TOKEN
    env is the fallback — the same rule hub_ip() follows."""
    s = settings if settings is not None else load_settings()
    host = s.get("plexHost") or PLEX
    token = s.get("plexToken") or TOKEN
    return (host or "").rstrip("/"), token or ""


def plex_url(path):
    host, token = plex_creds()
    return f"{host}{path}{'&' if '?' in path else '?'}X-Plex-Token={token}"


def fetch_xml(path):
    with urllib.request.urlopen(plex_url(path), timeout=10) as r:
        return ET.fromstring(r.read())


def atomic_write(path, data, mode="w"):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
    with os.fdopen(fd, mode) as f:
        f.write(data)
    os.replace(tmp, path)
    os.chmod(path, 0o644)


def hub_ip():
    """Device picked in settings wins; HUB_IP env is the fallback."""
    return load_settings().get("hubIp") or HUB_IP


def catt(*args):
    result = subprocess.run(["catt", "-d", hub_ip(), *args],
                            capture_output=True, text=True, timeout=90)
    if result.returncode:
        detail = (result.stderr or result.stdout or "unknown catt error").strip()
        raise RuntimeError(f"catt {' '.join(args)} failed: {detail}")
    return result


_scan_cache = {"at": 0.0, "devices": []}


def parse_scan(text):
    """catt scan lines look like: '192.168.1.50 - Living Room - Google Nest Hub'."""
    devices = []
    for line in text.splitlines():
        m = re.match(r"\s*(\d{1,3}(?:\.\d{1,3}){3})\s+-\s+(.+?)\s+-\s+(.*)", line)
        if m:
            devices.append({"ip": m.group(1), "name": m.group(2),
                            "model": m.group(3).strip()})
    return devices


def scan_devices(refresh=False):
    """Google Cast devices announce over mDNS; catt scan collects them."""
    if refresh or time.time() - _scan_cache["at"] > 300:
        try:
            result = subprocess.run(["catt", "scan"], capture_output=True,
                                    text=True, timeout=45)
            _scan_cache.update(at=time.time(),
                               devices=parse_scan(result.stdout))
        except Exception as e:
            print(f"device scan failed: {e}", flush=True)
    return {"devices": _scan_cache["devices"], "current": hub_ip()}


def dashcast_active():
    return "DashCast" in catt("info").stdout


_wx_cache = {"at": 0.0, "zip": None, "loc": "", "data": {}}


def weather():
    """Current conditions via Open-Meteo (free, no API key). Location comes
    from the ZIP in settings (zippopotam.us geocode) or, when blank, from the
    server's public IP. Refreshes every 15 minutes."""
    zip_code = re.sub(r"[^0-9]", "", load_settings().get("weatherZip") or "")[:5]
    fresh = time.time() - _wx_cache["at"] < 900
    if fresh and _wx_cache["zip"] == zip_code and _wx_cache["data"]:
        return _wx_cache["data"]
    try:
        if _wx_cache["zip"] != zip_code or not _wx_cache["loc"]:
            if zip_code:
                with urllib.request.urlopen(
                        f"https://api.zippopotam.us/us/{zip_code}", timeout=10) as r:
                    p = json.load(r)["places"][0]
                    _wx_cache["loc"] = f"{p['latitude']},{p['longitude']}"
            else:
                with urllib.request.urlopen(
                        "http://ip-api.com/json/?fields=lat,lon", timeout=10) as r:
                    j = json.load(r)
                    _wx_cache["loc"] = f"{j['lat']},{j['lon']}"
            _wx_cache["zip"] = zip_code
        lat, lon = _wx_cache["loc"].split(",")
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}"
               f"&longitude={lon}&current=weather_code,is_day,temperature_2m")
        with urllib.request.urlopen(url, timeout=10) as r:
            cur = json.load(r)["current"]
        _wx_cache.update(at=time.time(), data={
            "code": cur["weather_code"], "isDay": cur["is_day"] == 1,
            "temp": cur["temperature_2m"]})
    except Exception as e:
        print(f"weather fetch failed: {e}", flush=True)
        _wx_cache["at"] = time.time()  # don't hammer on failure
    return _wx_cache["data"]


def tmdb_stinger(tmdb_id):
    """['during'|'after', ...] from TMDb keywords (aftercreditsstinger etc.)."""
    url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/keywords?api_key={TMDB_KEY}"
    with urllib.request.urlopen(url, timeout=10) as r:
        names = {k["name"] for k in json.load(r).get("keywords", [])}
    return [w for w, kw in (("during", "duringcreditsstinger"),
                            ("after", "aftercreditsstinger")) if kw in names]


def transcode_to(path, plex_path, w, h):
    host, token = plex_creds()
    inner = urllib.parse.quote(f"{plex_path}?X-Plex-Token={token}", safe="")
    url = (f"{host}/photo/:/transcode?width={w}&height={h}&minSize=1"
           f"&upscale=1&url={inner}&X-Plex-Token={token}")
    with urllib.request.urlopen(url, timeout=15) as r:
        atomic_write(os.path.join(OUTPUT, path), r.read(), "wb")


def env_first(*names):
    """First non-empty env var among names; "" when none is set. An
    empty-but-present var counts as unset — a compose file that lists
    `JELLYFIN_HOST: ""` next to a filled EMBY_HOST must not shadow it."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return ""


# Jellyfin honors the same api_key query auth and endpoint shapes as Emby, so
# either env pair works with either backend; the pair matching the backend
# name wins when both are set. A host/key stored from the settings page wins
# over env — the same rule hub_ip() follows.
def emby_creds(backend=None, settings=None):
    """(host, key) for the emby-family backend in force."""
    s = settings if settings is not None else load_settings()
    if backend is None:
        backend = media_backend(s)
    if backend == "jellyfin":
        host = s.get("jellyfinHost") or env_first("JELLYFIN_HOST", "EMBY_HOST")
        key = s.get("jellyfinKey") or env_first("JELLYFIN_API_KEY", "EMBY_API_KEY")
    else:
        host = s.get("embyHost") or env_first("EMBY_HOST", "JELLYFIN_HOST")
        key = s.get("embyKey") or env_first("EMBY_API_KEY", "JELLYFIN_API_KEY")
    return (host or "").rstrip("/"), key or ""


def emby_url(path, creds=None):
    host, key = creds or emby_creds()
    base = host + path
    return f"{base}{'&' if '?' in base else '?'}api_key={key}"


def emby_fetch_json(path):
    with urllib.request.urlopen(emby_url(path), timeout=10) as r:
        return json.load(r)


def emby_image_url(host, key, item_id, kind, w=600, h=900):
    return (f"{host.rstrip('/')}/Items/{item_id}/Images/{kind}"
            f"?maxWidth={w}&maxHeight={h}&api_key={key}")


def emby_save_image(item_id, kind, out_name, w, h):
    host, key = emby_creds()
    url = emby_image_url(host, key, item_id, kind, w, h)
    with urllib.request.urlopen(url, timeout=15) as r:
        atomic_write(os.path.join(OUTPUT, out_name), r.read(), "wb")


def emby_download_art(item):
    """Save poster/backdrop/logo for an Emby item into output/."""
    out = {"poster": False, "backdrop": False, "logo": False}
    item_id = item.get("Id")
    tags = item.get("ImageTags") or {}
    if item.get("Type") == "Episode" and item.get("SeriesId"):
        poster_id = item["SeriesId"]
    else:
        poster_id = item_id
    try:
        if poster_id:
            emby_save_image(poster_id, "Primary", "poster.jpg", 600, 900)
            out["poster"] = True
    except Exception:
        pass
    backdrop_id = item.get("ParentBackdropItemId") or item.get("SeriesId") or item_id
    try:
        if backdrop_id:
            emby_save_image(backdrop_id, "Backdrop/0", "backdrop.jpg", 1280, 800)
            out["backdrop"] = True
    except Exception:
        pass
    logo_id = item.get("ParentLogoItemId") or item.get("SeriesId") or item_id
    try:
        if "Logo" in tags or logo_id:
            emby_save_image(logo_id, "Logo", "logo.png", 800, 310)
            out["logo"] = True
    except Exception:
        pass
    return out


def download_art(item, rating_key):
    """Save poster.jpg, backdrop.jpg, logo.png into output/."""
    out = {"poster": False, "backdrop": False, "logo": False}
    poster = item.get("grandparentThumb") or item.get("thumb")
    if poster:
        transcode_to("poster.jpg", poster, 600, 900)
        out["poster"] = True
    if item.get("art"):
        transcode_to("backdrop.jpg", item.get("art"), 1280, 800)
        out["backdrop"] = True
    try:
        with urllib.request.urlopen(
                plex_url(f"/library/metadata/{rating_key}/clearLogo"), timeout=15) as r:
            atomic_write(os.path.join(OUTPUT, "logo.png"), r.read(), "wb")
        out["logo"] = True
    except Exception:
        pass
    return out


def library_extras(rating_key, is_movie=False):
    """Genres, IMDb, stinger, art/logo from the full metadata record; cached per item."""
    if rating_key in _meta_cache:
        return _meta_cache[rating_key]
    x = {"genres": [], "imdb": None, "stinger": [],
         "poster": False, "backdrop": False, "logo": False}
    try:
        root = fetch_xml(f"/library/metadata/{rating_key}?includeRatings=1")
        item = root.find("./*")
        if item is not None:
            x["genres"] = [g.get("tag") for g in item.findall("Genre") if g.get("tag")]
            for r in item.findall("Rating"):
                if (r.get("image") or "").startswith("imdb://") and r.get("value"):
                    x["imdb"] = float(r.get("value"))
            if TMDB_KEY and is_movie:
                for g in item.findall("Guid"):
                    if (g.get("id") or "").startswith("tmdb://"):
                        x["stinger"] = tmdb_stinger(g.get("id")[7:])
                        break
            x.update(download_art(item, rating_key))
    except Exception as e:
        print(f"metadata fetch failed for {rating_key}: {e}", flush=True)
    _meta_cache.clear()  # only ever need the current item
    _meta_cache[rating_key] = x
    return x


def pretty_resolution(res):
    if not res:
        return None
    return {"4k": "4K", "sd": "SD"}.get(res.lower(), res + "p" if res.isdigit() else res.upper())


def emby_ticks_to_ms(ticks):
    return int(ticks) // 10000 if ticks is not None else None


def emby_resolution(width, height=None):
    """Label resolution by frame Width. Height is unreliable for
    letterboxed/scope films (a 1080p 2.76:1 movie is 1920x696, which by
    height would mislabel as "696p"). Width tracks the resolution tier."""
    w = int(width) if width else 0
    if w >= 3800:
        return "4K"
    if w >= 2500:
        return "1440p"
    if w >= 1800:
        return "1080p"
    if w >= 1200:
        return "720p"
    if w >= 700:
        return "480p"
    if height:  # width missing/odd -> fall back to height buckets
        return {2160: "4K", 1080: "1080p", 720: "720p", 480: "480p"}.get(
            int(height), f"{int(height)}p")
    return f"{w}px" if w else None


def parse_emby_session(session, extras):
    """One Emby /Sessions entry -> now-playing dict (same shape as Plex)."""
    item = session.get("NowPlayingItem") or {}
    play = session.get("PlayState") or {}
    is_episode = item.get("Type") == "Episode"
    info = {
        "playing": True,
        "type": (item.get("Type") or "").lower(),
        "key": item.get("Id"),
        "title": item.get("SeriesName") if is_episode else item.get("Name"),
        "year": item.get("ProductionYear"),
    }
    if is_episode and item.get("ParentIndexNumber") and item.get("IndexNumber"):
        info["subtitle"] = (f"S{item['ParentIndexNumber']} · "
                            f"E{item['IndexNumber']} · {item.get('Name')}")
    info["state"] = "paused" if play.get("IsPaused") else "playing"
    offset = emby_ticks_to_ms(play.get("PositionTicks"))
    duration = emby_ticks_to_ms(item.get("RunTimeTicks"))
    if offset is not None and duration:
        info["progress"] = {"offsetMs": offset, "durationMs": duration}
    if duration:
        m = duration // 60000
        info["runtime"] = f"{m // 60}h {m % 60:02d}m" if m >= 60 else f"{m}m"
    if item.get("Overview"):
        info["summary"] = item["Overview"]
    if item.get("OfficialRating"):
        info["contentRating"] = item["OfficialRating"]
    genres = [g for g in (item.get("Genres") or []) if g]
    if genres:
        info["genres"] = genres[:3]
    streams = item.get("MediaStreams") or []
    video = next((s for s in streams if s.get("Type") == "Video"), None)
    audio = next((s for s in streams if s.get("Type") == "Audio"), None)
    parts = [emby_resolution(video.get("Width"), video.get("Height")) if video else None,
             (video.get("Codec") or "").upper() or None if video else None,
             (audio.get("Codec") or "").upper() or None if audio else None]
    media = " · ".join(p for p in parts if p)
    if media:
        info["media"] = media
    scores = {}
    if item.get("CommunityRating"):
        scores["imdb"] = round(float(item["CommunityRating"]), 1)
    if item.get("CriticRating") is not None:
        scores["rtCritic"] = round(float(item["CriticRating"]))
        scores["rtCriticFresh"] = float(item["CriticRating"]) >= 60
    if scores:
        info["scores"] = scores
    x = extras(item)
    if x.get("stinger"):
        info["stinger"] = x["stinger"]
    info["poster"] = x.get("poster", False)
    info["backdrop"] = x.get("backdrop", False)
    info["logo"] = x.get("logo", False)
    return info


def parse_session(video, extras=library_extras):
    """Video element from /status/sessions -> now-playing dict."""
    a = video.get
    is_episode = a("type") == "episode"
    info = {
        "playing": True,
        "type": a("type"),
        "key": a("ratingKey"),
        "title": a("grandparentTitle") if is_episode else a("title"),
        "year": a("year"),
    }
    if is_episode and a("parentIndex") and a("index"):
        info["subtitle"] = f"S{a('parentIndex')} · E{a('index')} · {a('title')}"

    x = (extras(a("ratingKey"), a("type") == "movie") if a("ratingKey")
         else {"genres": [], "imdb": None, "stinger": [],
               "poster": False, "backdrop": False, "logo": False})

    player = video.find("Player")
    if player is not None and player.get("state"):
        info["state"] = player.get("state")
    if a("viewOffset") and a("duration"):
        info["progress"] = {"offsetMs": int(a("viewOffset")),
                            "durationMs": int(a("duration"))}
    if a("summary"):
        info["summary"] = a("summary")
    if x["genres"]:
        info["genres"] = x["genres"][:3]
    if x["stinger"]:
        info["stinger"] = x["stinger"]
    info["poster"] = x["poster"]
    info["backdrop"] = x["backdrop"]
    info["logo"] = x["logo"]
    if a("contentRating"):
        info["contentRating"] = a("contentRating")
    if a("duration"):
        m = int(a("duration")) // 60000
        info["runtime"] = f"{m // 60}h {m % 60:02d}m" if m >= 60 else f"{m}m"
    media = video.find("Media")
    if media is not None:
        parts = [pretty_resolution(media.get("videoResolution")),
                 (media.get("videoCodec") or "").upper() or None,
                 (media.get("audioCodec") or "").upper() or None]
        info["media"] = " · ".join(p for p in parts if p)
    scores = {}
    if "rottentomatoes" in (a("ratingImage") or "") and a("rating"):
        scores["rtCritic"] = round(float(a("rating")) * 10)
        scores["rtCriticFresh"] = "ripe" in a("ratingImage")
    if "rottentomatoes" in (a("audienceRatingImage") or "") and a("audienceRating"):
        scores["rtAudience"] = round(float(a("audienceRating")) * 10)
        scores["rtAudienceFresh"] = "upright" in a("audienceRatingImage")
    if x["imdb"]:
        scores["imdb"] = x["imdb"]
    if scores:
        info["scores"] = scores
    return info


def session_names(video):
    """(user, device) display names for a session; device falls back through
    Player title -> device -> product."""
    user = video.find("User")
    player = video.find("Player")
    u = (user.get("title") or "") if user is not None else ""
    d = ""
    if player is not None:
        d = player.get("title") or player.get("device") or player.get("product") or ""
    return u, d


def session_sort_key(user, device, title):
    """A total, case-insensitive order over sessions.

    /status/sessions has no defined order and Plex reorders it as sessions come
    and go, so "the first allowed session" is not a stable choice. Sorting first
    makes the pick deterministic: every poll, and every display, agrees.
    """
    return ((user or "").lower(), (device or "").lower(), (title or "").lower())


def clamp_rotate(value):
    """Rotation period in seconds: 0 disables, otherwise 5..3600."""
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return 30
    if seconds <= 0:
        return 0
    return max(5, min(3600, seconds))


def rotate_pick(items, seconds, now=None):
    """Which of several equally-allowed sessions drives the display right now.

    The choice is a pure function of the wall clock, so it needs no state and
    survives a restart mid-rotation. `seconds` <= 0 pins the first session.
    """
    if not items:
        return None
    if len(items) == 1 or seconds <= 0:
        return items[0]
    now = time.time() if now is None else now
    return items[int(now // seconds) % len(items)]


def session_allowed(video, users=None, devices=None):
    """True when the session's Plex user AND device pass the allow-lists
    (an empty list allows everyone / any device).

    /status/sessions is server-wide: with the owner token it includes every
    shared and home user, so without a filter the marquee reacts to anyone
    streaming from the library.
    """
    users = USERS if users is None else users
    devices = DEVICES if devices is None else devices
    u, d = session_names(video)
    if users and u.lower() not in users:
        return False
    if devices:
        player = video.find("Player")
        if player is None:
            return False
        names = {(player.get(k) or "").lower()
                 for k in ("title", "device", "product")} - {""}
        if not (names & devices):
            return False
    return True


LAST_SESSIONS = []  # every active session from the last poll, filtered or not

# The card page fetches /now-playing.json every POLL seconds. When it stops, the
# page is gone even if the Hub still reports the DashCast app as loaded.
# `at` is only ever set by a real request, so /healthz reports the truth; the
# grace window a freshly cast page gets is tracked separately rather than by
# faking a poll -- seeding `at` would make a card that never polled look alive.
LAST_CARD_POLL = {"at": 0.0}
CARD_GRACE = {"until": 0.0}
CARD_TIMEOUT = max(45, POLL * 6)


def card_alive(now, last_poll, timeout=CARD_TIMEOUT):
    """True when the card fetched now-playing.json recently enough."""
    return bool(last_poll) and (now - last_poll) < timeout


def card_ok(now, last_poll, grace_until, timeout=CARD_TIMEOUT):
    """Leave the Hub alone: the card is polling, or a freshly cast page is still
    inside the window we give it to load and check in."""
    return card_alive(now, last_poll, timeout) or now < grace_until


def cast_card():
    """Load the card on the Hub, and let it be silent for one timeout window."""
    sep = "&" if "?" in PAGE_URL else "?"
    catt("cast_site", f"{PAGE_URL}{sep}cb={int(time.time())}")
    CARD_GRACE["until"] = time.time() + CARD_TIMEOUT


def current_session():
    s = load_settings()
    host, token = plex_creds(s)
    if not (host and token):
        return None   # not configured yet — the settings page can fix it live
    users = filter_set(s.get("plexUsers"), ENV_USERS)
    devices = filter_set(s.get("plexDevices"), ENV_DEVICES)
    root = fetch_xml("/status/sessions")
    seen, allowed = [], []
    for video in root.findall("Video"):
        if video.get("type") not in ("movie", "episode"):
            continue
        u, d = session_names(video)
        title = video.get("title") or ""
        ok = session_allowed(video, users, devices)
        seen.append({"user": u, "device": d, "title": title, "allowed": ok})
        if ok:
            allowed.append((session_sort_key(u, d, title), video))
    LAST_SESSIONS[:] = seen
    # Sort before picking: the server's order is not stable, and without this
    # the card flips between two people's sessions on an arbitrary poll.
    allowed.sort(key=lambda pair: pair[0])
    picked = rotate_pick([video for _, video in allowed],
                         clamp_rotate(s.get("rotateSeconds")))
    return parse_session(picked) if picked is not None else None


def emby_session_names(s):
    """(user, device) display names for an Emby session; device falls back
    from DeviceName to Client, mirroring session_names() on the Plex path."""
    return (s.get("UserName") or "",
            s.get("DeviceName") or s.get("Client") or "")


def emby_session_allowed(s, users, devices):
    """True when the session's user AND device pass the allow-lists
    (an empty list allows everyone / any device)."""
    if users and (s.get("UserName") or "").lower() not in users:
        return False
    if devices:
        names = {(s.get(k) or "").lower()
                 for k in ("DeviceName", "Client")} - {""}
        if not (names & devices):
            return False
    return True


def emby_select_session(sessions, users, devices=frozenset()):
    """First session with a Movie/Episode NowPlayingItem whose user AND device
    pass the allow-lists (an empty list allows everyone / any device)."""
    for s in sessions:
        item = s.get("NowPlayingItem")
        if not item or item.get("Type") not in ("Movie", "Episode"):
            continue
        if not emby_session_allowed(s, users, devices):
            continue
        return s
    return None


_emby_meta_cache = {}    # item Id -> extras dict; current item only (mirrors _meta_cache)
_emby_enrich_cache = {}  # item Id -> enrichment fields; current item only


def emby_extras(item):
    """TMDB stinger + downloaded art for an Emby item; cached once per item.

    Without this, loop() would re-download poster/backdrop/logo and re-hit TMDB
    every POLL_SECONDS for the whole runtime — matching the Plex library_extras
    cache keeps it to one fetch per title.
    """
    key = item.get("Id")
    if key and key in _emby_meta_cache:
        return _emby_meta_cache[key]
    x = {"stinger": [], "poster": False, "backdrop": False, "logo": False}
    try:
        tmdb_id = (item.get("ProviderIds") or {}).get("Tmdb")
        if TMDB_KEY and item.get("Type") == "Movie" and tmdb_id:
            x["stinger"] = tmdb_stinger(tmdb_id)
    except Exception as e:
        print(f"emby stinger failed: {e}", flush=True)
    try:
        x.update(emby_download_art(item))
    except Exception as e:
        print(f"emby art failed: {e}", flush=True)
    if key:
        _emby_meta_cache.clear()  # only ever need the current item
        _emby_meta_cache[key] = x
    return x


def emby_enrich(item):
    """Fetch the fields /Sessions omits (genres, streams, ratings, overview)
    from /Items once per title, cached, and merge them in place."""
    key = item.get("Id")
    if not key:
        return
    if key not in _emby_enrich_cache:
        enriched = {}
        try:
            fields = ("Genres,MediaStreams,ProviderIds,Overview,"
                      "OfficialRating,CommunityRating,CriticRating")
            data = emby_fetch_json(f"/Items?Ids={key}&Fields={fields}")
            items = data.get("Items") if isinstance(data, dict) else None
            full = items[0] if items else {}
            for f in fields.split(","):
                if full.get(f) is None:
                    continue
                have = item.get(f)
                if isinstance(have, dict) and isinstance(full[f], dict):
                    # /Sessions can return a partial dict. A truthy-but-partial
                    # dict must still gain the missing keys; values already on
                    # the session win.
                    merged = {**full[f], **have}
                    if merged != have:
                        enriched[f] = merged
                elif not have:
                    enriched[f] = full[f]
        except Exception as e:
            print(f"emby enrich failed: {e}", flush=True)
        _emby_enrich_cache.clear()  # only ever need the current item
        _emby_enrich_cache[key] = enriched
    item.update(_emby_enrich_cache[key])


def emby_current_session():
    s = load_settings()
    host, key = emby_creds(settings=s)
    if not (host and key):
        return None   # not configured yet — the settings page can fix it live
    users = filter_set(s.get("plexUsers"), ENV_USERS)
    devices = filter_set(s.get("plexDevices"), ENV_DEVICES)
    sessions = emby_fetch_json("/Sessions")
    seen, allowed = [], []
    for session in sessions:
        item = session.get("NowPlayingItem")
        if not item or item.get("Type") not in ("Movie", "Episode"):
            continue
        u, d = emby_session_names(session)
        title = item.get("Name") or ""
        ok = emby_session_allowed(session, users, devices)
        seen.append({"user": u, "device": d, "title": title, "allowed": ok})
        if ok:
            allowed.append((session_sort_key(u, d, title), session))
    LAST_SESSIONS[:] = seen
    # Emby's /Sessions order tracks activity, so "the first allowed session"
    # flipped between two people's titles on an arbitrary poll. Sort, then let
    # the clock decide whose turn it is — same rotation as the Plex path.
    allowed.sort(key=lambda pair: pair[0])
    match = rotate_pick([session for _, session in allowed],
                        clamp_rotate(s.get("rotateSeconds")))
    if match is None:
        return None
    emby_enrich(match.get("NowPlayingItem") or {})
    return parse_emby_session(match, extras=emby_extras)


def load_settings():
    try:
        with open(SETTINGS_PATH) as f:
            saved = json.load(f)
        return {**DEFAULT_SETTINGS, **{k: v for k, v in saved.items() if k in DEFAULT_SETTINGS}}
    except Exception:
        return dict(DEFAULT_SETTINGS)


def clean_block_layout(value):
    """Keep layout overrides small, numeric, and limited to known card blocks."""
    if not isinstance(value, dict):
        return {}
    cleaned = {}
    for name, position in value.items():
        if name not in EDITABLE_BLOCKS or not isinstance(position, dict):
            continue
        item = {}
        for key, low, high in (("x", -100, 100), ("y", -100, 100),
                               ("width", 5, 100), ("scale", 0.3, 3)):
            number = position.get(key)
            if isinstance(number, (int, float)) and not isinstance(number, bool):
                item[key] = round(max(low, min(high, number)), 2)
        if position.get("align") in ("left", "center", "right"):
            item["align"] = position["align"]
        if position.get("font") in TITLE_FONTS:
            item["font"] = position["font"]
        if item:
            cleaned[name] = item
    return cleaned


class WebHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def _send(self, body, ctype="text/html; charset=utf-8", code=200):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path, code=200):
        try:
            with open(path, "rb") as f:
                ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
                self._send(f.read(), ctype, code)
        except Exception:
            self._send("not found", "text/plain", 404)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/settings.json":
            self._send(json.dumps(served_settings()), "application/json")
        elif path == "/devices":
            self._send(json.dumps(scan_devices("refresh" in self.path)),
                       "application/json")
        elif path == "/env-defaults":
            # Allowlisted container defaults, so the settings page can render a
            # blank field as "inheriting this" rather than "nothing is set".
            self._send(json.dumps(env_defaults()), "application/json")
        elif path == "/weather":
            self._send(json.dumps(weather()), "application/json")
        elif path == "/sessions":
            self._send(json.dumps({"sessions": LAST_SESSIONS}), "application/json")
        elif path == "/now-playing.json":
            # Served explicitly rather than through the static fallthrough so we
            # can timestamp the card's heartbeat -- see card_alive().
            LAST_CARD_POLL["at"] = time.time()
            self._send_file(JSON_PATH)
        elif path == "/healthz":
            last, now = LAST_CARD_POLL["at"], time.time()
            self._send(json.dumps({
                "ok": True, "version": VERSION,
                # Seconds since the card actually fetched now-playing.json; null
                # means it has never polled. A number past CARD_TIMEOUT is a Hub
                # showing a dead page.
                "cardPollAgo": round(now - last, 1) if last else None,
                "cardAlive": card_alive(now, last),
                # True while a freshly cast page is still allowed to be silent.
                "cardGrace": now < CARD_GRACE["until"],
            }), "application/json")
        elif path == "/release-notes":
            self._send_file(os.path.join(REPO, "CHANGELOG.md"))
        elif path in ("/", "/settings"):
            self._send_file(os.path.join(REPO, "cast", "settings.html"))
        elif path == "/image":
            self._send_file(os.path.join(OUTPUT, "index.html"))
        else:
            name = os.path.basename(urllib.parse.unquote(path))  # no traversal
            self._send_file(os.path.join(OUTPUT, name))

    def do_POST(self):
        if self.path.split("?")[0] != "/save":
            return self._send("not found", "text/plain", 404)
        try:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            merged = {**DEFAULT_SETTINGS,
                      **{k: v for k, v in body.items() if k in DEFAULT_SETTINGS}}
            if merged["posterSide"] not in ("left", "right"):
                merged["posterSide"] = "right"
            if merged["theme"] not in THEMES:
                merged["theme"] = "amber"
            if merged["template"] not in TEMPLATES:
                merged["template"] = "spotlight"
            if merged["clockFormat"] not in ("12h", "24h"):
                merged["clockFormat"] = "12h"
            if merged["titleFont"] not in TITLE_FONTS:
                merged["titleFont"] = "system"
            if merged["bodyFont"] not in TITLE_FONTS:
                merged["bodyFont"] = "system"
            merged["rotateSeconds"] = clamp_rotate(merged["rotateSeconds"])
            for k in ("plexUsers", "plexDevices", "weatherZip",
                      "plexHost", "embyHost", "jellyfinHost"):
                if not isinstance(merged[k], str):
                    merged[k] = ""
            for k in ("plexHost", "embyHost", "jellyfinHost"):
                merged[k] = merged[k].strip()
            if merged["mediaBackend"] not in ("",) + BACKENDS:
                merged["mediaBackend"] = ""
            # Keys/tokens are write-only: a blank field keeps the stored value
            # (the page never sees it, so it cannot echo it back).
            saved = load_settings()
            for k in SECRET_SETTINGS:
                typed = merged[k].strip() if isinstance(merged[k], str) else ""
                merged[k] = typed or saved.get(k, "")
            # Refuse to point the marquee at a backend that has no server
            # configured anywhere — a saved-but-dead backend fails silently.
            chosen = merged["mediaBackend"] or ENV_BACKEND
            if chosen == "plex":
                host, key = plex_creds(merged)
            else:
                host, key = emby_creds(chosen, merged)
            if not (host and key):
                what = "token" if chosen == "plex" else "API key"
                raise ValueError(
                    f"{chosen} backend: enter its server address and {what} "
                    "(or set them in the container)")
            merged["weatherZip"] = merged["weatherZip"].strip()[:10]
            if merged["weatherUnits"] not in ("f", "c"):
                merged["weatherUnits"] = "f"
            merged["showWeather"] = bool(merged["showWeather"])
            merged["clockSeconds"] = bool(merged["clockSeconds"])
            if not (isinstance(merged["accent"], str)
                    and (merged["accent"] == "" or ACCENT_RE.match(merged["accent"]))):
                merged["accent"] = ""
            if not (isinstance(merged["hubIp"], str)
                    and (merged["hubIp"] == "" or IP_RE.match(merged["hubIp"]))):
                merged["hubIp"] = ""
            merged["blockLayout"] = clean_block_layout(merged["blockLayout"])
            atomic_write(SETTINGS_PATH, json.dumps(merged))
            self._send(json.dumps({"ok": True}), "application/json")
        except Exception as e:
            self._send(json.dumps({"ok": False, "error": str(e)}), "application/json", 400)


def serve_web():
    ThreadingHTTPServer(("", SERVE_PORT), WebHandler).serve_forever()


def loop():
    os.makedirs(DATA_DIR, exist_ok=True)
    # Only PAGE_URL is fatal: every media-server credential can be entered on
    # the settings page, so a missing one warns and keeps serving — a running
    # settings page beats a crash loop.
    if not PAGE_URL:
        raise SystemExit("Missing required environment variables: PAGE_URL")
    backend = media_backend()
    ready = all(plex_creds()) if backend == "plex" else all(emby_creds(backend))
    if not ready:
        names = {"plex": "PLEX_HOST/PLEX_TOKEN",
                 "emby": "EMBY_HOST/EMBY_API_KEY",
                 "jellyfin": "JELLYFIN_HOST/JELLYFIN_API_KEY"}[backend]
        print(f"{backend}: no server configured yet — set {names}, or enter "
              "them on the settings page", flush=True)
    if not os.path.exists(SETTINGS_PATH):
        atomic_write(SETTINGS_PATH, json.dumps(DEFAULT_SETTINGS))
    threading.Thread(target=serve_web, daemon=True).start()
    print(f"Marquee {VERSION} ready on :{SERVE_PORT} (card: /image, settings: /)",
          flush=True)
    # A card cast before this restart gets one window to check in, so restarting
    # the container does not needlessly re-cast a perfectly good page. This must
    # not touch LAST_CARD_POLL, or /healthz would report it as alive.
    CARD_GRACE["until"] = time.time() + CARD_TIMEOUT
    # Poll sessions fast (5s) so json/poster/hub flip together on play/stop;
    # talk to the hub only on transitions, plus a slow reconcile pass.
    last_playing, tick = None, 0
    while True:
        try:
            backend = media_backend()
            info = get_session()
            atomic_write(JSON_PATH, json.dumps(info or {"playing": False}))
            playing = bool(info)
            if playing != last_playing or tick % 6 == 0:
                if not hub_ip():
                    if playing and playing != last_playing:
                        print("no cast device configured — pick one on the "
                              "settings page or set HUB_IP", flush=True)
                else:
                    dash = dashcast_active()
                    # `dash` only means the DashCast app is loaded. A Hub whose
                    # page died keeps reporting it, so without the card's own
                    # heartbeat the loop sits here forever in front of a blank
                    # screen, casting nothing and logging nothing.
                    ok = card_ok(time.time(), LAST_CARD_POLL["at"],
                                 CARD_GRACE["until"])
                    if playing and not dash:
                        print(f"{backend} playing ({info['title']}) -> casting", flush=True)
                        cast_card()
                    elif playing and not ok:
                        last = LAST_CARD_POLL["at"]
                        gone = f"{time.time() - last:.0f}s" if last else "ever"
                        print(f"hub claims to be showing but the card has not "
                              f"polled in {gone} -> re-casting", flush=True)
                        cast_card()
                    elif not playing and dash:
                        print(f"{backend} idle -> releasing hub", flush=True)
                        catt("stop")
            last_playing = playing
            tick += 1
        except Exception as e:
            print(f"loop error: {e}", flush=True)
        time.sleep(POLL)


SAMPLE_SESSION = """<Video type="movie" title="The Devil Wears Prada 2" year="2026"
  summary="Miranda returns." contentRating="PG-13" duration="7141120" ratingKey="79372"
  rating="7.7" ratingImage="rottentomatoes://image.rating.ripe"
  audienceRating="8.4" audienceRatingImage="rottentomatoes://image.rating.upright"
  viewOffset="3600000">
  <Media videoResolution="1080" videoCodec="h264" audioCodec="eac3"/>
  <Player state="paused"/></Video>"""

SAMPLE_EXTRAS = {"genres": ["Comedy", "Drama"], "imdb": 7.2, "stinger": ["after"],
                 "poster": True, "backdrop": True, "logo": True}

SAMPLE_EMBY_SESSION = {
    "UserName": "Alice",
    "NowPlayingItem": {
        "Name": "The Devil Wears Prada 2", "Type": "Movie",
        "ProductionYear": 2026, "RunTimeTicks": 71411200000,
        "Overview": "Miranda returns.", "OfficialRating": "PG-13",
        "Genres": ["Comedy", "Drama"], "Id": "79372",
        "ProviderIds": {"Tmdb": "12345"},
        "CommunityRating": 7.2, "CriticRating": 77,
        "MediaStreams": [
            {"Type": "Video", "Codec": "h264", "Height": 1080, "Width": 1920},
            {"Type": "Audio", "Codec": "eac3"},
        ],
    },
    "PlayState": {"PositionTicks": 36000000000, "IsPaused": True},
}
SAMPLE_EMBY_EXTRAS = {"stinger": ["after"],
                      "poster": True, "backdrop": True, "logo": True}


def selftest():
    assert ENV_BACKEND in BACKENDS
    assert get_session is not None  # dispatcher exists, chosen per poll
    # Jellyfin rides the Emby session path; Plex does not.
    assert uses_emby_backend("emby") and uses_emby_backend("jellyfin")
    assert not uses_emby_backend("plex")
    # the settings dropdown overrides the env default; junk falls back
    assert media_backend({"mediaBackend": "emby"}) == "emby"
    assert media_backend({"mediaBackend": "JELLYFIN"}) == "jellyfin"
    assert media_backend({"mediaBackend": ""}) == ENV_BACKEND
    assert media_backend({"mediaBackend": "bogus"}) == ENV_BACKEND
    assert media_backend({}) == ENV_BACKEND

    # keys/tokens are write-only: /settings.json swaps each for a boolean hint
    served = served_settings({**DEFAULT_SETTINGS, "plexToken": "tok-secret",
                              "embyKey": "key-secret", "jellyfinKey": ""})
    for k in SECRET_SETTINGS:
        assert k not in served, k
    assert served["plexTokenSet"] is True and served["embyKeySet"] is True
    assert served["jellyfinKeySet"] is False
    assert "secret" not in json.dumps(served)
    assert served["envBackend"] == ENV_BACKEND   # page shows the env default

    # plex creds: settings page wins, env is the fallback
    _saved_plex = {k: os.environ.get(k) for k in ("PLEX_HOST", "PLEX_TOKEN")}
    try:
        os.environ.update(PLEX_HOST="http://p:32400", PLEX_TOKEN="pt")
        # module-level PLEX/TOKEN were read at import; test the settings side
        assert plex_creds({"plexHost": "http://s:32400/",
                           "plexToken": "st"}) == ("http://s:32400", "st")
        assert plex_creds({"plexHost": "", "plexToken": "st"})[1] == "st"
    finally:
        for k, v in _saved_plex.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    # per-backend creds: settings win; the env pair matching the backend name
    # wins over the alias pair when both are set
    blank = {"mediaBackend": "", "embyHost": "", "embyKey": "",
             "jellyfinHost": "", "jellyfinKey": ""}
    assert emby_creds("emby", {**blank, "embyHost": "http://s:1/",
                               "embyKey": "sk"}) == ("http://s:1", "sk")
    _envkeys = ("EMBY_HOST", "EMBY_API_KEY", "JELLYFIN_HOST", "JELLYFIN_API_KEY")
    _saved_env = {k: os.environ.get(k) for k in _envkeys}
    try:
        os.environ.update(EMBY_HOST="http://e:1", EMBY_API_KEY="ek",
                          JELLYFIN_HOST="http://j:2", JELLYFIN_API_KEY="jk")
        assert emby_creds("emby", blank) == ("http://e:1", "ek")
        assert emby_creds("jellyfin", blank) == ("http://j:2", "jk")
        os.environ["JELLYFIN_HOST"] = ""      # alias fallback when its own
        os.environ["JELLYFIN_API_KEY"] = ""   # pair is absent
        assert emby_creds("jellyfin", blank) == ("http://e:1", "ek")
        # settings beat env
        assert emby_creds("emby", {**blank, "embyHost": "http://s:1",
                                   "embyKey": "sk"}) == ("http://s:1", "sk")
    finally:
        for k, v in _saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    info = parse_session(ET.fromstring(SAMPLE_SESSION), extras=lambda k, m: SAMPLE_EXTRAS)
    assert info["title"] == "The Devil Wears Prada 2"
    assert info["key"] == "79372"
    assert info["runtime"] == "1h 59m"
    assert info["media"] == "1080p · H264 · EAC3"
    assert info["scores"] == {"rtCritic": 77, "rtCriticFresh": True,
                              "rtAudience": 84, "rtAudienceFresh": True, "imdb": 7.2}
    assert info["genres"] == ["Comedy", "Drama"]
    assert info["progress"] == {"offsetMs": 3600000, "durationMs": 7141120}
    assert info["state"] == "paused"
    assert info["stinger"] == ["after"]
    assert info["poster"] and info["backdrop"] and info["logo"]
    ep = ET.fromstring(SAMPLE_SESSION)
    ep.set("type", "episode")
    ep.set("grandparentTitle", "Severance")
    ep.set("parentIndex", "2")
    ep.set("index", "5")
    info = parse_session(ep, extras=lambda k, m: dict(SAMPLE_EXTRAS, stinger=[]))
    assert info["title"] == "Severance"
    assert info["subtitle"] == "S2 · E5 · The Devil Wears Prada 2"
    merged = {**DEFAULT_SETTINGS, **{"posterSide": "left", "bogus": 1, "showPlot": False}}
    assert "bogus" not in DEFAULT_SETTINGS and merged["posterSide"] == "left" \
        and merged["showPlot"] is False and merged["showClock"] is True \
        and merged["template"] == "spotlight"
    layout = clean_block_layout({"identity": {"x": 12.345, "y": -200, "width": 140,
                                              "scale": 9, "height": 50,
                                              "align": "center", "font": "bebas"},
                                 "plot": {"align": "diagonal", "font": "comic-sans"},
                                 "unknown": {"x": 1}})
    assert layout == {"identity": {"x": 12.35, "y": -100, "width": 100,
                                   "scale": 3, "align": "center", "font": "bebas"}}
    assert ACCENT_RE.match("#A1b2C3") and not ACCENT_RE.match("red") \
        and not ACCENT_RE.match("#12345")
    v = ET.fromstring(SAMPLE_SESSION)
    assert session_allowed(v, set(), set()) and not session_allowed(v, {"alice"}, set())
    v.append(ET.Element("User", {"id": "1", "title": "Alice"}))
    assert session_allowed(v, {"alice"}, set()) and not session_allowed(v, {"bob"}, set())
    assert not session_allowed(v, set(), {"office phone"})  # Player has no names yet
    player = v.find("Player")
    player.set("title", "Office Phone")
    player.set("device", "Pixel 9")
    player.set("product", "Plex for Android")
    assert session_allowed(v, {"alice"}, {"office phone"})
    assert session_allowed(v, set(), {"pixel 9"})
    assert not session_allowed(v, {"alice"}, {"living room tv"})
    assert csv_set(" Alice, ,Office Phone ") == {"alice", "office phone"}
    scan = parse_scan("Scanning Chromecasts...\n"
                      "192.168.1.50 - Living Room - Google Inc. Google Nest Hub\n"
                      "not a device line")
    assert scan == [{"ip": "192.168.1.50", "name": "Living Room",
                     "model": "Google Inc. Google Nest Hub"}]
    assert IP_RE.match("10.0.0.2") and not IP_RE.match("nest.local")

    # The settings page overrides the env var; it does not merge with it. A
    # union let PLEX_USERS filter sessions the UI showed no sign of, and no
    # amount of editing the field could lift it.
    assert filter_set("alice, Bob", "jamison") == {"alice", "bob"}
    assert filter_set("", "jamison") == {"jamison"}       # blank -> inherit env
    assert filter_set("   ", "jamison") == {"jamison"}    # whitespace is blank
    assert filter_set("alice", "") == {"alice"}
    assert filter_set("", "") == set()                    # nobody filtered
    assert "jamison" not in filter_set("alice", "jamison")  # env is replaced

    # The env hints the settings page may see are an allowlist. Nothing that
    # looks like a credential may ever join them.
    hints = env_defaults()
    assert set(hints) == set(ENV_HINT_KEYS), set(hints)
    for secret in ("PLEX_TOKEN", "TMDB_API_KEY", "token", "key"):
        assert not any(secret.lower() in k.lower() for k in hints), secret
    assert all(isinstance(v, str) for v in hints.values())

    # dashcast_active() only proves the DashCast *app* is loaded, not that our
    # card is drawing. A Hub whose page died keeps reporting DashCast forever,
    # so the loop never re-casts and the screen stays blank. The card fetches
    # /now-playing.json every POLL seconds; silence means it is gone.
    assert card_alive(100.0, 99.0, 45)
    assert card_alive(100.0, 56.0, 45)          # just inside the window
    assert not card_alive(100.0, 54.0, 45)      # just outside
    assert not card_alive(100.0, 0.0, 45)       # never polled at all
    # "never polled" stays dead even when the clock is younger than the
    # timeout, which a bare subtraction would misread as alive.
    assert not card_alive(10.0, 0.0, 45)

    # A freshly cast page is allowed to be silent for one window, but that must
    # never make a card which has not polled *look* alive on /healthz.
    assert card_ok(100.0, 0.0, grace_until=140.0, timeout=45)    # silent, in grace
    assert not card_alive(100.0, 0.0, 45)                        # ...but not alive
    assert not card_ok(100.0, 0.0, grace_until=0.0, timeout=45)  # grace expired
    assert card_ok(100.0, 99.0, grace_until=0.0, timeout=45)     # polling, no grace
    assert card_ok(1000.0, 999.0, grace_until=1.0, timeout=45)   # poll outlives grace

    # Several people can stream at once. /status/sessions has no defined order,
    # so picking "the first allowed session" made the card flip between them on
    # any poll where the server reordered. Sort, then rotate on a clock bucket.
    rows = [("Bob", "Apple TV", "Jaws"),
            ("alice", "Pixel 9", "Alien"),
            ("Bob", "apple tv", "Aliens")]
    assert sorted(rows, key=lambda r: session_sort_key(*r)) == [
        ("alice", "Pixel 9", "Alien"),
        ("Bob", "apple tv", "Aliens"),
        ("Bob", "Apple TV", "Jaws")]           # case-insensitive, total order

    items = ["a", "b", "c"]
    assert rotate_pick([], 30, now=0) is None
    assert rotate_pick(["solo"], 30, now=999) == "solo"
    # rotation is a pure function of the clock, so every display agrees
    assert rotate_pick(items, 30, now=0) == "a"
    assert rotate_pick(items, 30, now=29.9) == "a"    # stable within a bucket
    assert rotate_pick(items, 30, now=30) == "b"
    assert rotate_pick(items, 30, now=61) == "c"
    assert rotate_pick(items, 30, now=90) == "a"      # wraps
    # rotateSeconds = 0 disables rotation: the first session pins
    assert rotate_pick(items, 0, now=12345) == "a"
    assert rotate_pick(items, -5, now=12345) == "a"

    assert clamp_rotate(30) == 30 and clamp_rotate(0) == 0
    assert clamp_rotate("45") == 45                   # settings arrive as text
    assert clamp_rotate("nonsense") == 30 and clamp_rotate(None) == 30
    assert clamp_rotate(2) == 5 and clamp_rotate(99999) == 3600   # bounds

    # current_session() must not care what order the server lists sessions in.
    two = ('<MediaContainer>'
           '<Video type="movie" title="Alien" ratingKey="1">'
           '<User title="alice"/><Player title="Pixel 9"/></Video>'
           '<Video type="movie" title="Jaws" ratingKey="2">'
           '<User title="Bob"/><Player title="Apple TV"/></Video>'
           '</MediaContainer>')
    flipped = ('<MediaContainer>'
               '<Video type="movie" title="Jaws" ratingKey="2">'
               '<User title="Bob"/><Player title="Apple TV"/></Video>'
               '<Video type="movie" title="Alien" ratingKey="1">'
               '<User title="alice"/><Player title="Pixel 9"/></Video>'
               '</MediaContainer>')
    real_fetch, real_parse, real_load = fetch_xml, parse_session, load_settings
    real_time = time.time
    try:
        globals()["parse_session"] = lambda v: {"title": v.get("title")}
        globals()["load_settings"] = lambda: {"plexUsers": "", "plexDevices": "",
                                              "rotateSeconds": 30,
                                              "plexHost": "http://t:1",
                                              "plexToken": "tk"}
        picks = {}
        for label, xml in (("normal", two), ("flipped", flipped)):
            globals()["fetch_xml"] = lambda _p, _x=xml: ET.fromstring(_x)
            for bucket, when in (("t0", 0.0), ("t1", 30.0), ("t2", 60.0)):
                globals()["time"].time = lambda _w=when: _w
                picks[(label, bucket)] = current_session()["title"]
        # Server order must not change the choice...
        for bucket in ("t0", "t1", "t2"):
            assert picks[("normal", bucket)] == picks[("flipped", bucket)], \
                (bucket, picks)
        # ...and the clock, not the server, decides whose turn it is.
        assert picks[("normal", "t0")] == "Alien"      # alice sorts first
        assert picks[("normal", "t1")] == "Jaws"
        assert picks[("normal", "t2")] == "Alien"      # wraps
        assert len(LAST_SESSIONS) == 2                 # both still reported

        # rotateSeconds = 0 pins the first sorted session forever
        globals()["load_settings"] = lambda: {"plexUsers": "", "plexDevices": "",
                                              "rotateSeconds": 0,
                                              "plexHost": "http://t:1",
                                              "plexToken": "tk"}
        globals()["time"].time = lambda: 99999.0
        assert current_session()["title"] == "Alien"

        # a device filter narrows the candidates; rotation orders what is left
        globals()["load_settings"] = lambda: {"plexUsers": "", "plexDevices": "apple tv",
                                              "rotateSeconds": 30,
                                              "plexHost": "http://t:1",
                                              "plexToken": "tk"}
        globals()["time"].time = lambda: 0.0
        assert current_session()["title"] == "Jaws"
    finally:
        globals()["time"].time = real_time
        globals()["fetch_xml"] = real_fetch
        globals()["parse_session"] = real_parse
        globals()["load_settings"] = real_load

    einfo = parse_emby_session(SAMPLE_EMBY_SESSION, extras=lambda item: SAMPLE_EMBY_EXTRAS)
    assert einfo["type"] == "movie"
    assert einfo["title"] == "The Devil Wears Prada 2"
    assert einfo["key"] == "79372"
    assert einfo["year"] == 2026
    assert einfo["state"] == "paused"
    assert einfo["runtime"] == "1h 59m"
    assert einfo["media"] == "1080p · H264 · EAC3"
    assert einfo["progress"] == {"offsetMs": 3600000, "durationMs": 7141120}
    assert einfo["summary"] == "Miranda returns."
    assert einfo["contentRating"] == "PG-13"
    assert einfo["genres"] == ["Comedy", "Drama"]
    assert einfo["scores"] == {"imdb": 7.2, "rtCritic": 77, "rtCriticFresh": True}
    assert einfo["stinger"] == ["after"]
    assert einfo["poster"] and einfo["backdrop"] and einfo["logo"]
    # both backends hand the card the same dict: same keys, no extras
    minfo = parse_session(ET.fromstring(SAMPLE_SESSION), extras=lambda k, m: SAMPLE_EXTRAS)
    assert set(einfo) == set(minfo), set(einfo) ^ set(minfo)
    # episode shape
    eep = json.loads(json.dumps(SAMPLE_EMBY_SESSION))
    eep["NowPlayingItem"].update(Type="Episode", SeriesName="Severance",
                                 ParentIndexNumber=2, IndexNumber=5, Name="The Rundown")
    einfo = parse_emby_session(eep, extras=lambda item: dict(SAMPLE_EMBY_EXTRAS, stinger=[]))
    assert einfo["title"] == "Severance"
    assert einfo["subtitle"] == "S2 · E5 · The Rundown"
    # resolution is labeled by Width, not Height (scope/letterboxed films)
    assert emby_resolution(1920, 1080) == "1080p"
    assert emby_resolution(1920, 696) == "1080p"   # 2.76:1 scope film
    assert emby_resolution(3840, 1600) == "4K"     # 2.40:1 UHD
    assert emby_resolution(1280, 720) == "720p"
    assert emby_resolution(None, 1080) == "1080p"  # width missing -> height fallback
    assert emby_resolution(None, None) is None
    scope = json.loads(json.dumps(SAMPLE_EMBY_SESSION))
    scope["NowPlayingItem"]["MediaStreams"] = [
        {"Type": "Video", "Codec": "h264", "Height": 696, "Width": 1920},
        {"Type": "Audio", "Codec": "aac"}]
    sinfo = parse_emby_session(scope, extras=lambda item: SAMPLE_EMBY_EXTRAS)
    assert sinfo["media"] == "1080p · H264 · AAC"
    assert emby_image_url("http://emby:8096", "KEY", "79372", "Primary") == (
        "http://emby:8096/Items/79372/Images/Primary"
        "?maxWidth=600&maxHeight=900&api_key=KEY")
    assert emby_image_url("http://emby:8096/", "KEY", "79372", "Backdrop/0",
                          600, 400) == (
        "http://emby:8096/Items/79372/Images/Backdrop/0"
        "?maxWidth=600&maxHeight=400&api_key=KEY")
    # env aliases: empty-but-present must not shadow a filled fallback
    os.environ["MARQUEE_TEST_PRIMARY"] = ""
    os.environ["MARQUEE_TEST_FALLBACK"] = "http://emby:8096"
    try:
        assert env_first("MARQUEE_TEST_PRIMARY", "MARQUEE_TEST_FALLBACK") == \
            "http://emby:8096"
        os.environ["MARQUEE_TEST_PRIMARY"] = "http://jf:8098"
        assert env_first("MARQUEE_TEST_PRIMARY", "MARQUEE_TEST_FALLBACK") == \
            "http://jf:8098"                       # primary wins when set
        assert env_first("MARQUEE_TEST_MISSING") == ""   # absent -> ""
    finally:
        del os.environ["MARQUEE_TEST_PRIMARY"], os.environ["MARQUEE_TEST_FALLBACK"]
    sessions = [
        {"UserName": "Bob"},  # no NowPlayingItem -> skipped
        {"UserName": "Alice", "NowPlayingItem": {"Type": "Photo"}},  # wrong type
        {"UserName": "Alice", "NowPlayingItem": {"Type": "Movie", "Id": "9"},
         "PlayState": {}},
    ]
    assert emby_select_session(sessions, set()) is sessions[2]
    assert emby_select_session(sessions, {"alice"}) is sessions[2]
    assert emby_select_session(sessions, {"bob"}) is None

    # device filters, matching the Plex path
    esessions = [
        {"UserName": "Alice", "DeviceName": "Chrome", "Client": "Emby Web",
         "NowPlayingItem": {"Type": "Movie", "Id": "1"}, "PlayState": {}},
        {"UserName": "Alice", "DeviceName": "Living Room TV",
         "Client": "Emby Theater",
         "NowPlayingItem": {"Type": "Movie", "Id": "2"}, "PlayState": {}},
    ]
    def pick(u, d):
        got = emby_select_session(esessions, u, d)
        return got and got["NowPlayingItem"]["Id"]
    assert pick(set(), set()) == "1"          # no filters -> first playable
    assert pick(set(), {"living room tv"}) == "2"   # by DeviceName
    assert pick(set(), {"emby theater"}) == "2"     # or by Client
    assert pick({"alice"}, {"chrome"}) == "1"       # user AND device must pass
    assert pick({"bob"}, {"chrome"}) is None
    assert pick(set(), {"nope"}) is None

    # the settings page reads device names off LAST_SESSIONS, so Emby must
    # report them the way Plex does: DeviceName, falling back to Client
    assert emby_session_names(esessions[1]) == ("Alice", "Living Room TV")
    assert emby_session_names({"UserName": "Al", "Client": "Emby Web"}) == \
        ("Al", "Emby Web")
    assert emby_session_names({}) == ("", "")

    # Emby rotates too: /Sessions is ordered by activity, so without a sort the
    # card flips between two people's titles on an arbitrary poll.
    def emby_two(order):
        return [
            {"UserName": "Bob", "DeviceName": "Apple TV",
             "NowPlayingItem": {"Type": "Movie", "Id": "1", "Name": "Jaws"},
             "PlayState": {}},
            {"UserName": "alice", "DeviceName": "Pixel 9",
             "NowPlayingItem": {"Type": "Movie", "Id": "2", "Name": "Alien"},
             "PlayState": {}},
        ][::order]

    real_efetch, real_eload, real_enrich = emby_fetch_json, load_settings, emby_enrich
    real_eparse, real_etime = parse_emby_session, time.time
    try:
        globals()["emby_enrich"] = lambda item: item
        globals()["parse_emby_session"] = lambda s, extras=None: {
            "title": (s.get("NowPlayingItem") or {}).get("Name")}
        globals()["load_settings"] = lambda: {
            "plexUsers": "", "plexDevices": "", "rotateSeconds": 30,
            "embyHost": "http://test:1", "embyKey": "k"}
        picks = {}
        for label, order in (("normal", 1), ("flipped", -1)):
            globals()["emby_fetch_json"] = lambda _p, _o=order: emby_two(_o)
            for bucket, when in (("t0", 0.0), ("t1", 30.0)):
                globals()["time"].time = lambda _w=when: _w
                picks[(label, bucket)] = emby_current_session()["title"]
        # server order must not change the choice, and the clock must
        for bucket in ("t0", "t1"):
            assert picks[("normal", bucket)] == picks[("flipped", bucket)], picks
        assert picks[("normal", "t0")] == "Alien"      # alice sorts before Bob
        assert picks[("normal", "t1")] == "Jaws"
        assert len(LAST_SESSIONS) == 2                 # both still reported
    finally:
        globals()["time"].time = real_etime
        globals()["emby_fetch_json"] = real_efetch
        globals()["load_settings"] = real_eload
        globals()["emby_enrich"] = real_enrich
        globals()["parse_emby_session"] = real_eparse

    # The Emby path honors filter_set the same way Plex does: a settings-page
    # user list REPLACES the env var, it does not union with it. With
    # PLEX_USERS=bob in the container and "alice" typed on the page, only
    # alice's session may cast — a union would wrongly let Bob through too.
    real_users, real_env_users = USERS, ENV_USERS
    try:
        globals()["USERS"], globals()["ENV_USERS"] = {"bob"}, "bob"
        globals()["emby_enrich"] = lambda item: item
        globals()["parse_emby_session"] = lambda s, extras=None: {
            "title": (s.get("NowPlayingItem") or {}).get("Name")}
        globals()["emby_fetch_json"] = lambda _p: emby_two(1)
        globals()["load_settings"] = lambda: {
            "plexUsers": "alice", "plexDevices": "", "rotateSeconds": 0,
            "embyHost": "http://test:1", "embyKey": "k"}
        globals()["time"].time = lambda: 0.0
        assert emby_current_session()["title"] == "Alien"   # bob is not unioned in
        allowed = {row["user"]: row["allowed"] for row in LAST_SESSIONS}
        assert allowed == {"alice": True, "Bob": False}, allowed
    finally:
        globals()["USERS"], globals()["ENV_USERS"] = real_users, real_env_users
        globals()["time"].time = real_etime
        globals()["emby_fetch_json"] = real_efetch
        globals()["load_settings"] = real_eload
        globals()["emby_enrich"] = real_enrich
        globals()["parse_emby_session"] = real_eparse

    # enrich: /Sessions omits fields /Items has; fetched once, session wins
    captured = {}
    def fake_fetch(path):
        captured["path"] = path
        return {"Items": [{
            "Genres": ["Horror"],
            "MediaStreams": [{"Type": "Video", "Codec": "h264", "Width": 1920}],
            "ProviderIds": {"Tmdb": "123", "Imdb": "tt-full"}}]}
    _orig_fetch = globals()["emby_fetch_json"]
    globals()["emby_fetch_json"] = fake_fetch
    try:
        _emby_enrich_cache.clear()
        it = {"Id": "999"}
        emby_enrich(it)
        assert it["Genres"] == ["Horror"]
        assert "Genres" in captured["path"] and "MediaStreams" in captured["path"]
        # a truthy-but-partial dict from /Sessions must still gain missing keys,
        # and values already on the session must win over the fetched ones
        _emby_enrich_cache.clear()
        partial = {"Id": "998", "ProviderIds": {"Imdb": "tt-session"}}
        emby_enrich(partial)
        assert partial["ProviderIds"]["Tmdb"] == "123"          # merged in
        assert partial["ProviderIds"]["Imdb"] == "tt-session"   # session wins
    finally:
        globals()["emby_fetch_json"] = _orig_fetch
        _emby_enrich_cache.clear()
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        loop()
