#!/usr/bin/env python3
"""Unit tests for scripts/detect.py.

Stdlib only (unittest). No network. Run via:
    python -m unittest evals.test_detect -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Make scripts/ importable when run from repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from detect import classify  # noqa: E402


class TestDetect(unittest.TestCase):
    """Each test asserts the full JSON payload contract."""

    def _classify(self, url: str) -> dict:
        return classify(url)

    # --- platform_video ---

    def test_x_twitter_video(self):
        r = self._classify("https://x.com/HarrisDecodes/status/2107839872144900463/video/1")
        self.assertEqual(r["kind"], "platform_video")
        self.assertEqual(r["suggested_tool"], "yt-dlp")
        self.assertEqual(r["host"], "x.com")
        self.assertIn("2107839872144900463", r["dest_name"])
        self.assertTrue(r["dest_name"].endswith(".mp4"))
        self.assertIn("ffprobe", r["verify_cmd"])
        self.assertEqual(r["install_hint"]["name"], "yt-dlp")

    def test_twitter_short_domain(self):
        r = self._classify("https://twitter.com/foo/status/1234567890/video/1")
        self.assertEqual(r["kind"], "platform_video")
        self.assertEqual(r["suggested_tool"], "yt-dlp")
        self.assertIn("1234567890", r["dest_name"])

    def test_youtube_watch(self):
        r = self._classify("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertEqual(r["kind"], "platform_video")
        self.assertEqual(r["suggested_tool"], "yt-dlp")
        self.assertIn("dQw4w9WgXcQ", r["dest_name"])

    def test_youtube_short(self):
        r = self._classify("https://youtu.be/dQw4w9WgXcQ")
        self.assertEqual(r["kind"], "platform_video")
        self.assertIn("dQw4w9WgXcQ", r["dest_name"])

    def test_bilibili(self):
        r = self._classify("https://www.bilibili.com/video/BV1x411c7mD/")
        self.assertEqual(r["kind"], "platform_video")
        self.assertEqual(r["suggested_tool"], "yt-dlp")

    def test_douyin(self):
        r = self._classify("https://www.douyin.com/video/7365934524233212345")
        self.assertEqual(r["kind"], "platform_video")

    # --- direct_file ---

    def test_direct_mp4(self):
        r = self._classify("https://example.com/path/to/video.mp4")
        self.assertEqual(r["kind"], "direct_file")
        self.assertEqual(r["suggested_tool"], "curl")
        self.assertEqual(r["dest_name"], "video.mp4")
        self.assertIn("ffprobe", r["verify_cmd"])

    def test_direct_pdf(self):
        r = self._classify("https://example.com/report.pdf")
        self.assertEqual(r["kind"], "direct_file")
        self.assertEqual(r["suggested_tool"], "curl")
        self.assertEqual(r["dest_name"], "report.pdf")
        self.assertEqual(r["verify_cmd"], "file")

    def test_direct_archive(self):
        r = self._classify("https://cdn.example.com/files/backup.tar.gz")
        self.assertEqual(r["kind"], "direct_file")
        self.assertEqual(r["suggested_tool"], "curl")
        self.assertEqual(r["dest_name"], "backup.tar.gz")
        self.assertEqual(r["verify_cmd"], "file")

    def test_direct_image(self):
        r = self._classify("https://img.example.com/photo.jpg")
        self.assertEqual(r["kind"], "direct_file")
        self.assertEqual(r["suggested_tool"], "curl")
        self.assertEqual(r["dest_name"], "photo.jpg")

    # --- torrent ---

    def test_torrent_file_url(self):
        r = self._classify("https://tracker.example.com/movies/some-movie.torrent")
        self.assertEqual(r["kind"], "torrent")
        self.assertEqual(r["suggested_tool"], "aria2c")
        self.assertEqual(r["dest_name"], "some-movie.torrent")
        self.assertEqual(r["install_hint"]["name"], "aria2")

    # --- magnet ---

    def test_magnet_with_dn(self):
        r = self._classify("magnet:?xt=urn:btih:abc123def&dn=Test%20Movie")
        self.assertEqual(r["kind"], "magnet")
        self.assertEqual(r["suggested_tool"], "aria2c")
        self.assertEqual(r["dest_name"], "Test Movie")
        self.assertEqual(r["install_hint"]["name"], "aria2")

    def test_magnet_without_dn(self):
        r = self._classify("magnet:?xt=urn:btih:abc123def")
        self.assertEqual(r["kind"], "magnet")
        self.assertEqual(r["dest_name"], "magnet-download")

    # --- unknown ---

    def test_unknown_bare_page(self):
        r = self._classify("https://some-site.com/some/path")
        self.assertEqual(r["kind"], "unknown")
        self.assertEqual(r["suggested_tool"], "curl")

    def test_unknown_alfafile_short_link(self):
        # CGPersia-style resource aggregator: not in platform whitelist,
        # path is /file/SHORT_ID with no extension.
        r = self._classify("https://alfafile.net/file/AXAFy")
        self.assertEqual(r["kind"], "unknown")
        self.assertEqual(r["suggested_tool"], "curl")

    # --- edge cases ---

    def test_platform_site_wins_over_extension(self):
        # Even if a YouTube URL somehow had an extension, platform check comes first.
        r = self._classify("https://www.youtube.com/some/video.mp4")
        self.assertEqual(r["kind"], "platform_video")

    def test_json_is_serializable(self):
        # Sanity check: contract is a plain dict with JSON-serializable fields.
        r = self._classify("https://example.com/x.mp4")
        serialized = json.dumps(r, ensure_ascii=False)
        self.assertIsInstance(serialized, str)
        self.assertIn('"kind"', serialized)
        self.assertIn('"dest_name"', serialized)
        self.assertIn('"suggested_tool"', serialized)
        self.assertIn('"verify_cmd"', serialized)
        self.assertIn('"install_hint"', serialized)


if __name__ == "__main__":
    unittest.main(verbosity=2)
