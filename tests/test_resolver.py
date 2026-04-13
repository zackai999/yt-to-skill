"""Tests for URL resolver — resolves single video, playlist, and channel URLs."""

from unittest.mock import MagicMock, patch

import pytest

from yt_to_skill.errors import NetworkError
from yt_to_skill.resolver import resolve_urls


# ---------------------------------------------------------------------------
# Single video URLs
# ---------------------------------------------------------------------------


def test_resolve_single_video_url():
    """resolve_urls with a standard watch URL returns [video_id]."""
    result = resolve_urls("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert result == ["dQw4w9WgXcQ"]


def test_resolve_short_url():
    """resolve_urls with a youtu.be URL returns [video_id]."""
    result = resolve_urls("https://youtu.be/dQw4w9WgXcQ")
    assert result == ["dQw4w9WgXcQ"]


# ---------------------------------------------------------------------------
# Playlist / channel URLs (mocked yt-dlp)
# ---------------------------------------------------------------------------


@patch("yt_to_skill.resolver.yt_dlp.YoutubeDL")
def test_resolve_playlist_url(MockYDL):
    """resolve_urls with a playlist URL returns list of video IDs."""
    fake_info = {
        "entries": [
            {"id": "vid001"},
            {"id": "vid002"},
            {"id": "vid003"},
        ]
    }
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.return_value = fake_info
    MockYDL.return_value = mock_ydl

    result = resolve_urls("https://www.youtube.com/playlist?list=PLxyz")
    assert result == ["vid001", "vid002", "vid003"]


@patch("yt_to_skill.resolver.yt_dlp.YoutubeDL")
def test_resolve_channel_url(MockYDL):
    """resolve_urls with a channel URL returns list of video IDs."""
    fake_info = {
        "entries": [
            {"id": "chanvid1"},
            {"id": "chanvid2"},
        ]
    }
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.return_value = fake_info
    MockYDL.return_value = mock_ydl

    result = resolve_urls("https://www.youtube.com/@TradingChannel/videos")
    assert result == ["chanvid1", "chanvid2"]


@patch("yt_to_skill.resolver.yt_dlp.YoutubeDL")
def test_resolve_playlist_filters_missing_ids(MockYDL, caplog):
    """Entries without 'id' key are filtered out; a warning is logged."""
    import logging

    fake_info = {
        "entries": [
            {"id": "goodvid"},
            {"title": "private video, no id"},
            {"id": "anothergood"},
        ]
    }
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.return_value = fake_info
    MockYDL.return_value = mock_ydl

    with caplog.at_level(logging.WARNING):
        result = resolve_urls("https://www.youtube.com/playlist?list=PLxyz")

    assert result == ["goodvid", "anothergood"]


@patch("yt_to_skill.resolver.yt_dlp.YoutubeDL")
def test_resolve_empty_playlist(MockYDL):
    """Playlist with no entries returns an empty list."""
    fake_info = {"entries": []}
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.return_value = fake_info
    MockYDL.return_value = mock_ydl

    result = resolve_urls("https://www.youtube.com/playlist?list=PLempty")
    assert result == []


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@patch("yt_to_skill.resolver.yt_dlp.YoutubeDL")
def test_resolve_network_error(MockYDL):
    """yt-dlp DownloadError is re-raised as NetworkError."""
    import yt_dlp.utils

    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.side_effect = yt_dlp.utils.DownloadError("connection refused")
    MockYDL.return_value = mock_ydl

    with pytest.raises(NetworkError):
        resolve_urls("https://www.youtube.com/playlist?list=PLfail")


@patch("yt_to_skill.resolver.yt_dlp.YoutubeDL")
def test_resolve_invalid_url(MockYDL):
    """Completely invalid URL raises NetworkError with actionable message."""
    mock_ydl = MagicMock()
    mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info.side_effect = Exception("Unsupported URL")
    MockYDL.return_value = mock_ydl

    with pytest.raises(NetworkError):
        resolve_urls("https://not-a-youtube-url.com/video")
