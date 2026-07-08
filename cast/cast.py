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

VERSION = "1.4.0"
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
    "posterSide": "right",
    "clockFormat": "12h",
    "clockSeconds": False,
    "showPlot": True, "showGenres": True, "showScores": True,
    "showMediaInfo": True, "showContentRating": True, "showRuntime": True,
    "showProgress": True, "showClock": True,
    "backdrop": True, "logo": True,
    "plexUsers": "", "plexDevices": "",
    "blockLayout": {},
}

EDITABLE_BLOCKS = ("clock", "identity", "meta", "plot", "ratings",
                   "progress", "poster")

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


def current_session():
    s = load_settings()
    users = USERS | csv_set(s.get("plexUsers"))
    devices = DEVICES | csv_set(s.get("plexDevices"))
    root = fetch_xml("/status/sessions")
    seen, match = [], None
    for video in root.findall("Video"):
        if video.get("type") not in ("movie", "episode"):
            continue
        u, d = session_names(video)
        ok = session_allowed(video, users, devices)
        seen.append({"user": u, "device": d,
                     "title": video.get("title") or "", "allowed": ok})
        if ok and match is None:
            match = parse_session(video)
    LAST_SESSIONS[:] = seen
    return match


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
        elif path == "/sessions":
            self._send(json.dumps({"sessions": LAST_SESSIONS}), "application/json")
        elif path == "/healthz":
            self._send(json.dumps({"ok": True, "version": VERSION}), "application/json")
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
            for k in ("plexUsers", "plexDevices"):
                if not isinstance(merged[k], str):
                    merged[k] = ""
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
                    if playing and not dash:
                        print(f"plex playing ({info['title']}) -> casting", flush=True)
                        sep = "&" if "?" in PAGE_URL else "?"
                        catt("cast_site", f"{PAGE_URL}{sep}cb={int(time.time())}")
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
                                              "align": "center"},
                                 "plot": {"align": "diagonal"},
                                 "unknown": {"x": 1}})
    assert layout == {"identity": {"x": 12.35, "y": -100, "width": 100,
                                   "scale": 3, "align": "center"}}
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
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        loop()
