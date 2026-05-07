"""
YouTube Data API v3 client.

Fetches up to 50 unique videos per expanded query set, returning raw
metadata needed for the scoring pipeline.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx

from app.config import settings
from app.models import VideoResult

logger = logging.getLogger(__name__)

_BASE = "https://www.googleapis.com/youtube/v3"


@dataclass
class SearchResult:
    videos: list[VideoResult] = field(default_factory=list)
    quota_errors: int = 0
    queries_attempted: int = 0
    queries_succeeded: int = 0


async def search_videos(queries: list[str], per_query: int = 15) -> SearchResult:
    """
    Search YouTube for each expanded query and return deduplicated results.
    Caps at ~50 total unique videos regardless of how many queries are run.
    Returns a SearchResult with error counters so the caller can decide whether
    to surface a quota error to the user.
    """
    seen_ids: set[str] = set()
    result = SearchResult()

    async with httpx.AsyncClient(timeout=15) as client:
        for query in queries:
            if len(result.videos) >= 50:
                break

            result.queries_attempted += 1

            params = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": per_query,
                "key": settings.youtube_api_key,
            }

            try:
                resp = await client.get(f"{_BASE}/search", params=params)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                logger.warning(
                    "Search query '%s' failed with HTTP %s — skipping",
                    query,
                    status,
                )
                if status in (403, 429):
                    result.quota_errors += 1
                continue
            except httpx.RequestError as exc:
                logger.warning("Network error for query '%s': %s — skipping", query, exc)
                continue

            data = resp.json()

            # Check for API-level error embedded in 200 response (some quota errors come this way)
            if "error" in data:
                err_code = data["error"].get("code", 0)
                logger.warning("API error in response for '%s': %s", query, data["error"])
                if err_code in (403, 429):
                    result.quota_errors += 1
                continue

            video_ids = [
                item["id"]["videoId"]
                for item in data.get("items", [])
                if item["id"].get("videoId") and item["id"]["videoId"] not in seen_ids
            ]

            if not video_ids:
                result.queries_succeeded += 1
                continue

            # Fetch statistics + contentDetails in one batch call
            detail_params = {
                "part": "snippet,statistics,contentDetails",
                "id": ",".join(video_ids),
                "key": settings.youtube_api_key,
            }
            try:
                detail_resp = await client.get(f"{_BASE}/videos", params=detail_params)
                detail_resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                logger.warning(
                    "Video details batch failed with HTTP %s — skipping %d videos",
                    status,
                    len(video_ids),
                )
                if status in (403, 429):
                    result.quota_errors += 1
                continue

            detail_data = detail_resp.json()
            result.queries_succeeded += 1

            for item in detail_data.get("items", []):
                vid_id = item["id"]
                if vid_id in seen_ids:
                    continue
                seen_ids.add(vid_id)

                snippet = item["snippet"]
                stats = item.get("statistics", {})
                content = item.get("contentDetails", {})

                result.videos.append(
                    VideoResult(
                        video_id=vid_id,
                        title=snippet.get("title", ""),
                        description=snippet.get("description", ""),
                        channel_name=snippet.get("channelTitle", ""),
                        channel_id=snippet.get("channelId", ""),
                        thumbnail_url=(
                            snippet.get("thumbnails", {})
                            .get("high", {})
                            .get("url", "")
                        ),
                        published_at=snippet.get("publishedAt", ""),
                        duration=content.get("duration"),
                        view_count=int(stats["viewCount"])
                        if stats.get("viewCount")
                        else None,
                    )
                )

    return result
