#!/usr/bin/env python3
"""URL analyzer for the `down` skill.

Usage:
    python detect.py --url "<url>" [--json]

Emits a JSON object on stdout describing the URL kind, suggested download tool,
destination filename, and verification command. Exit code 0 always (except on
bad usage) — the caller inspects the JSON to decide the next step.

Design notes:
  * Read-only. Never touches the filesystem except for --help.
  * Zero third-party deps — stdlib only, works on Python 3.9+.
  * All heuristics are data-driven (PLATFORM_SITES, HOST_TOOL_MAP,
    EXT_TOOL_MAP). Adding a new site is one line in the map.
  * No network calls — the URL is classified from its shape alone.
    This is deliberate: a URL probe would leak credentials in Referer and
    might trip anti-bot systems before the caller even asked to install tools.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
import shlex
import sys
from pathlib import Path
from urllib.parse import urlparse

# --- Platform sites (yt-dlp handles these with its extractors) ----------------

# Hosts where a page URL (not a direct file) is a video/audio platform page.
# Matched by parsed hostname (case-insensitive, suffix match via endswith).
PLATFORM_SITES: dict[str, str] = {
    "youtube.com": "yt-dlp", "youtubekids.com": "yt-dlp",
    "youtu.be": "yt-dlp", "music.youtube.com": "yt-dlp",
    "twitter.com": "yt-dlp", "x.com": "yt-dlp",
    "bilibili.com": "yt-dlp", "b23.tv": "yt-dlp",
    "tiktok.com": "yt-dlp", "vm.tiktok.com": "yt-dlp",
    "vimeo.com": "yt-dlp", "dailymotion.com": "yt-dlp",
    "douyin.com": "yt-dlp", "weibo.com": "yt-dlp",
    "redditmedia.com": "yt-dlp", "reddit.com": "yt-dlp",
    "twitch.tv": "yt-dlp",
}

# --- Direct-file extensions (Content-Disposition or URL path suffix) ----------

VIDEO_EXT = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".ts", ".m4s"}
AUDIO_EXT = {".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wav", ".wma"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".heic", ".avif"}
ARCHIVE_EXT = {".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".iso"}
DOC_EXT = {".pdf", ".epub", ".txt", ".html", ".css", ".js", ".json", ".xml", ".csv", ".md"}
VIDEO_ALL = VIDEO_EXT | AUDIO_EXT

# --- Magnet / torrent URI schemes --------------------------------------------

TORRENT_EXT = {".torrent"}


def classify(url: str) -> dict:
    """Classify a URL and return the JSON payload dict."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.lower()

    # 1) URI schemes first — they're unambiguous.
    if parsed.scheme == "magnet":
        return _result(
            url, host="", kind="magnet", tool="aria2c",
            dest_name=_magnet_name(url), verify_cmd="file",
            install_hint=_aria2_hint(),
        )
    if path.endswith(".torrent"):
        return _result(
            url, host=host, kind="torrent", tool="aria2c",
            dest_name=_basename(path), verify_cmd="file",
            install_hint=_aria2_hint(),
        )

    # 2) Known platform sites → yt-dlp, regardless of extension.
    for plat, tool in PLATFORM_SITES.items():
        if host == plat or host.endswith("." + plat):
            ext = _first_ext(path)
            return _result(
                url, host=host, kind="platform_video", tool=tool,
                dest_name=_slugified_dest(url, ext or ".mp4"),
                verify_cmd=_ffprobe_cmd(),
                install_hint=_ytdlp_hint(),
            )

    # 3) Direct file link — decided by extension.
    ext = _first_ext(path)
    if ext:
        if ext in VIDEO_ALL:
            return _result(url, host, "direct_file", "curl",
                           _basename(path, default=f"download{ext}"),
                           _ffprobe_cmd())
        if ext in TORRENT_EXT:
            return _result(url, host, "torrent", "aria2c",
                           _basename(path), "file", _aria2_hint())
        # archives, docs, images, unknown — all just curl
        return _result(url, host, "direct_file", "curl",
                       _basename(path, default="download"),
                       "file")

    # 4) Fallback — host-based guess, then unknown.
    if host and any(host.endswith(d) for d in (".org", ".com", ".net", ".info", ".xyz", ".dev")):
        return _result(url, host, "unknown", "curl",
                       dest_name="download", verify_cmd="file")
    return _result(url, host, "unknown", "curl",
                   dest_name="download", verify_cmd="file")


# --- Helpers -----------------------------------------------------------------


def _result(url: str, host: str, kind: str, tool: str,
            dest_name: str, verify_cmd: str, install_hint: dict | None = None) -> dict:
    return {
        "url": url,
        "host": host,
        "kind": kind,
        "suggested_tool": tool,
        "dest_name": dest_name,
        "verify_cmd": verify_cmd,
        "install_hint": install_hint or {},
    }


def _basename(path: str, default: str | None = None) -> str:
    name = Path(path).name
    if not name or name == "/":
        return default or "download"
    # URL-decode common escapes
    for enc in ("%20", "%2F", "%2f"):
        name = name.replace(enc, " ")
    return name.strip() or (default or "download")


def _first_ext(path: str) -> str | None:
    name = Path(path).name.lower()
    if "." not in name:
        return None
    _, _, ext = name.rpartition(".")
    if len(ext) > 6 or ext.isdigit():  # not a real extension
        return None
    return "." + ext


def _slugified_dest(url: str, ext: str) -> str:
    """For platform videos, build a descriptive filename from the URL."""
    parsed = urlparse(url)
    host = (parsed.hostname or "media").replace(".", "_")
    qs = parsed.query

    # YouTube: video id is in ?v=<id>
    if "youtube" in host or host.endswith("youtu.be"):
        from urllib.parse import parse_qs
        v = parse_qs(qs).get("v", [None])[0]
        if v:
            return f"{host}_{v}{ext}"
        # youtu.be/<id> short form
        m = re.search(r"youtu\.be/([A-Za-z0-9_-]{6,})$", parsed.path)
        if m:
            return f"youtube_{m.group(1)}{ext}"

    # Twitter/X/Bilibili/etc.: pull a status/post id from the path
    m = re.search(r"/(?:status|video|watch|v)(?:/)?(\d+)", parsed.path)
    if m:
        return f"{host}_{m.group(1)}{ext}"
    m = re.search(r"([A-Za-z0-9_-]{6,12})$", parsed.path.rstrip("/"))
    if m:
        return f"{host}_{m.group(1)}{ext}"
    return f"{host}download{ext}"


def _magnet_name(magnet: str) -> str:
    m = re.search(r"dn=([^&]+)", magnet)
    if m:
        from urllib.parse import unquote_plus
        return unquote_plus(m.group(1))
    return "magnet-download"


def _ffprobe_cmd() -> str:
    return ("ffprobe -v error -show_entries "
            "format=duration,size -show_entries stream=codec_type,codec_name,width,height "
            "-of default=nw=1 \"<file>\"")


def _aria2_hint() -> dict:
    # Windows: winget; others: platform package manager. Caller must ASK user first.
    return {
        "name": "aria2",
        "purpose": "torrent/magnet downloads (curl/yt-dlp cannot do this)",
        "install_windows": "winget install -e --id aria2.aria2",
        "install_linux": "apt install -y aria2  (or dnf install -y aria2)",
        "install_macos": "brew install aria2",
        "size_mb": 4,
        "license": "Apache-2.0",
    }


def _ytdlp_hint() -> dict:
    return {
        "name": "yt-dlp",
        "purpose": "platform video/audio downloads (YouTube, X/Twitter, Bilibili, ...)",
        "install": "uv tool install yt-dlp",
        "size_mb": 3,
        "license": "Unlicense",
    }


# --- CLI ---------------------------------------------------------------------


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Analyze a URL for the `down` skill.")
    p.add_argument("--url", required=True, help="URL to analyze")
    p.add_argument("--json", action="store_true", help="Emit JSON (default; kept for clarity)")
    args = p.parse_args(argv)

    result = classify(args.url)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
