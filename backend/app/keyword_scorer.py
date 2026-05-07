"""
Keyword scorer and trusted-channel booster.

Analyses title + description for animation/lecture signals and applies a
bonus for videos from known high-quality educational channels.
"""
from __future__ import annotations

GOOD_KEYWORDS: list[str] = [
    "animation",
    "simulation",
    "visualized",
    "diagram",
    "3d",
    "motion graphics",
    "explained visually",
    "visual",
    "animated",
    "physics simulation",
    "interactive",
]

BAD_KEYWORDS: list[str] = [
    "lecture",
    "neet",
    "jee",
    "classroom",
    "facecam",
    "live class",
    "teacher explains",
    "class 11",
    "class 12",
    "cbse",
    "board exam",
    "ncert",
    "study material",
]

TRUSTED_CHANNELS: list[str] = [
    "kurzgesagt",
    "minutephysics",
    "crashcourse",
    "veritasium",
    "3blue1brown",
    "vsauce",
    "scishow",
    "ted-ed",
    "ted ed",
    "mark rober",
    "smarter every day",
    "numberphile",
    "tibees",
    "physics girl",
    "looking glass universe",
]


def score_keywords(title: str, description: str) -> tuple[float, str]:
    """Score title+description against good/bad keyword lists."""
    text = (title + " " + description).lower()

    good_hits = [kw for kw in GOOD_KEYWORDS if kw in text]
    bad_hits = [kw for kw in BAD_KEYWORDS if kw in text]

    delta = (len(good_hits) * 5.0) - (len(bad_hits) * 8.0)
    reason = f"good={good_hits}, bad={bad_hits}"
    return delta, reason


def score_channel(channel_name: str) -> tuple[float, str]:
    """Return a trust bonus for channels on the whitelist."""
    name_lower = channel_name.lower()
    for trusted in TRUSTED_CHANNELS:
        if trusted in name_lower:
            return 30.0, f"trusted_channel={channel_name}"
    return 0.0, "not_trusted"
