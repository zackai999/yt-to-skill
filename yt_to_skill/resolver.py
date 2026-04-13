"""URL resolver — resolves YouTube URLs to lists of video IDs.

Handles:
    - Single video URLs (watch?v=, youtu.be/, shorts/)
    - Playlist URLs (playlist?list=)
    - Channel URLs (@handle/videos, /c/channel/videos)

Usage:
    from yt_to_skill.resolver import resolve_urls

    video_ids = resolve_urls("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    # -> ["dQw4w9WgXcQ"]

    video_ids = resolve_urls("https://www.youtube.com/playlist?list=PLxxx")
    # -> ["vid001", "vid002", ...]
"""

from __future__ import annotations

import yt_dlp
from loguru import logger

from yt_to_skill.errors import NetworkError
from yt_to_skill.orchestrator import extract_video_id


def resolve_urls(url: str) -> list[str]:
    """Resolve a YouTube URL to a list of video IDs.

    For single-video URLs, returns a one-element list.
    For playlist/channel URLs, expands via yt-dlp and returns all video IDs.
    Entries without a valid 'id' key are filtered out with a warning log.

    Args:
        url: A YouTube video, playlist, or channel URL.

    Returns:
        List of video ID strings.

    Raises:
        NetworkError: If yt-dlp fails to extract playlist/channel info,
                      or if the URL is completely invalid/unreachable.
    """
    # Try single-video URL first (fast path — no network needed)
    try:
        video_id = extract_video_id(url)
        return [video_id]
    except ValueError:
        # Not a single-video URL — fall through to playlist/channel expansion
        pass

    # Playlist / channel expansion via yt-dlp
    ydl_opts = {
        "extract_flat": True,
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        raise NetworkError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise NetworkError(str(exc)) from exc

    entries = info.get("entries", []) if info else []

    video_ids: list[str] = []
    for entry in entries:
        entry_id = entry.get("id")
        if entry_id:
            video_ids.append(entry_id)
        else:
            title = entry.get("title", "<unknown>")
            logger.warning(
                "Skipping playlist entry without video ID: title={!r} (may be private or deleted)",
                title,
            )

    return video_ids
