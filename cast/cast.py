#!/usr/bin/env python3
"""Marquee — a Plex "now playing" marquee for Google Nest Hubs.
The whole app in one container: front end + back end.

Backend: polls Plex every POLL_SECONDS; while something plays it downloads
poster/backdrop/logo, writes now-playing.json, and casts the card to the Hub;
when idle it releases the Hub.

Frontend (one HTTP server on :8084): serves the card page and art from
output/, the settings UI at /settings, /save, and /release-notes.

Env knobs: PAGE_URL, PLEX_HOST, PLEX_TOKEN, POLL_SECONDS, REPO_DIR,
SERVE_PORT, DATA_DIR. Optional TMDB_API_KEY enables the credits-scene badge;
optional PLEX_USERS / PLEX_DEVICES limit which Plex users and player devices
trigger the marquee (also editable live on the settings page). The cast
device comes from the settings page (auto-discovered via catt scan) or the
HUB_IP env fallback.
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
# empty = everyone / any device. Env is the seed; the settings page adds more.
USERS = csv_set(os.environ.get("PLEX_USERS", ""))
DEVICES = csv_set(os.environ.get("PLEX_DEVICES", ""))

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
}

EDITABLE_BLOCKS = ("clock", "identity", "meta", "plot", "ratings",
                   "progress", "poster", "stinger")

_meta_cache = {}  # ratingKey -> extras dict


def plex_url(path):
    return f"{PLEX}{path}{'&' if '?' in path else '?'}X-Plex-Token={TOKEN}"


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
    inner = urllib.parse.quote(f"{plex_path}?X-Plex-Token={TOKEN}", safe="")
    url = (f"{PLEX}/photo/:/transcode?width={w}&height={h}&minSize=1"
           f"&upscale=1&url={inner}&X-Plex-Token={TOKEN}")
    with urllib.request.urlopen(url, timeout=15) as r:
        atomic_write(os.path.join(OUTPUT, path), r.read(), "wb")


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
    users = USERS | csv_set(s.get("plexUsers"))
    devices = DEVICES | csv_set(s.get("plexDevices"))
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
            self._send(json.dumps(load_settings()), "application/json")
        elif path == "/devices":
            self._send(json.dumps(scan_devices("refresh" in self.path)),
                       "application/json")
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
            for k in ("plexUsers", "plexDevices", "weatherZip"):
                if not isinstance(merged[k], str):
                    merged[k] = ""
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
    missing = [name for name, value in (("PAGE_URL", PAGE_URL),
                                        ("PLEX_HOST", PLEX), ("PLEX_TOKEN", TOKEN))
               if not value]
    if missing:
        raise SystemExit("Missing required environment variables: " + ", ".join(missing))
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
            info = current_session()
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
                        print(f"plex playing ({info['title']}) -> casting", flush=True)
                        cast_card()
                    elif playing and not ok:
                        last = LAST_CARD_POLL["at"]
                        gone = f"{time.time() - last:.0f}s" if last else "ever"
                        print(f"hub claims to be showing but the card has not "
                              f"polled in {gone} -> re-casting", flush=True)
                        cast_card()
                    elif not playing and dash:
                        print("plex idle -> releasing hub", flush=True)
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


def selftest():
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
                                              "rotateSeconds": 30}
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
                                              "rotateSeconds": 0}
        globals()["time"].time = lambda: 99999.0
        assert current_session()["title"] == "Alien"

        # a device filter narrows the candidates; rotation orders what is left
        globals()["load_settings"] = lambda: {"plexUsers": "", "plexDevices": "apple tv",
                                              "rotateSeconds": 30}
        globals()["time"].time = lambda: 0.0
        assert current_session()["title"] == "Jaws"
    finally:
        globals()["time"].time = real_time
        globals()["fetch_xml"] = real_fetch
        globals()["parse_session"] = real_parse
        globals()["load_settings"] = real_load
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        loop()
