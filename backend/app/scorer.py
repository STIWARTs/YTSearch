"""
Main scoring pipeline.

Orchestrates all individual scorers and produces a final ranked list
of VideoResult objects.
"""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from app.models import VideoResult
from app.keyword_scorer import score_keywords, score_channel
from app.face_detector import score_thumbnail
from app.transcript_scorer import score_transcript

logger = logging.getLogger(__name__)

# Thread pool used to run blocking I/O (cv2, transcript download) concurrently
_executor = ThreadPoolExecutor(max_workers=8)


def _score_single(video: VideoResult) -> VideoResult:
    """Compute all score components for a single video (runs in thread)."""
    breakdown: dict[str, float | str] = {}

    # 1. Keyword scoring
    kw_delta, kw_reason = score_keywords(video.title, video.description)
    breakdown["keyword_score"] = kw_delta
    breakdown["keyword_reason"] = kw_reason

    # 2. Trusted channel bonus
    ch_delta, ch_reason = score_channel(video.channel_name)
    breakdown["channel_score"] = ch_delta
    breakdown["channel_reason"] = ch_reason

    # 3. Face detection penalty
    face_delta, face_reason = score_thumbnail(video.thumbnail_url)
    breakdown["face_score"] = face_delta
    breakdown["face_reason"] = face_reason

    # 4. Transcript analysis
    tr_delta, tr_reason = score_transcript(video.video_id)
    breakdown["transcript_score"] = tr_delta
    breakdown["transcript_reason"] = tr_reason

    total = kw_delta + ch_delta + face_delta + tr_delta
    video.score = round(total, 2)
    video.score_breakdown = breakdown
    return video


async def rank_videos(videos: list[VideoResult]) -> list[VideoResult]:
    """
    Run all scoring in parallel threads, then sort by descending score.
    """
    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(_executor, _score_single, video)
        for video in videos
    ]
    scored = await asyncio.gather(*tasks)
    return sorted(scored, key=lambda v: v.score, reverse=True)
