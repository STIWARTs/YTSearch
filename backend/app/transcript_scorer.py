"""
Transcript analysis module.

Downloads auto-generated or manual captions for a video and scores the
transcript for animation signals vs. lecture signals.
"""
from __future__ import annotations

import logging
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled

logger = logging.getLogger(__name__)

ANIMATION_SIGNALS = [
    "visualize",
    "diagram",
    "observe",
    "simulation",
    "motion",
    "particle",
    "animate",
    "model",
    # "trajectory",
    # "wave",
    # "oscillate",
    # "vector",
]

LECTURE_SIGNALS = [
    # "hello students",
    # "welcome to class",
    # "take your notebook",
    # "subscribe",
    # "today we will learn",
    "write this down",
    "in this lecture",
    # "in this chapter",
]


def score_transcript(video_id: str) -> tuple[float, str]:
    """
    Returns (score_delta, reason).
    Positive delta = more animation-like.
    Negative delta = more lecture-like.
    Returns (0, 'no_transcript') if transcript is unavailable.
    """
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
    except (NoTranscriptFound, TranscriptsDisabled):
        return 0.0, "no_transcript"
    except Exception as exc:
        logger.warning("Transcript fetch failed for %s: %s", video_id, exc)
        return 0.0, "error"

    full_text = " ".join(entry["text"] for entry in transcript_list).lower()

    anim_hits = sum(1 for sig in ANIMATION_SIGNALS if sig in full_text)
    lect_hits = sum(1 for sig in LECTURE_SIGNALS if sig in full_text)

    score_delta = (anim_hits * 3.0) - (lect_hits * 5.0)
    reason = f"anim_hits={anim_hits}, lecture_hits={lect_hits}"
    return score_delta, reason
