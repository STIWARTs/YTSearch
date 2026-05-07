"""
Query expansion module.

Generates multiple search variants from a user query so the YouTube API
returns a broader, richer set of educational animation candidates.
"""
from __future__ import annotations

VISUAL_SUFFIXES = [
    "animation",
    "simulation",
    "visual explanation",
    "3d visualization",
    "motion graphics",
    "explained visually",
]


def expand_query(base_query: str) -> list[str]:
    """Return the base query plus visually-oriented variants."""
    queries = [base_query]
    for suffix in VISUAL_SUFFIXES:
        queries.append(f"{base_query} {suffix}")
    return queries
