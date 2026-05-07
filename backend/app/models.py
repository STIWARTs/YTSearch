from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, HttpUrl


class VideoResult(BaseModel):
    video_id: str
    title: str
    description: str
    channel_name: str
    channel_id: str
    thumbnail_url: str
    published_at: str
    duration: Optional[str] = None
    view_count: Optional[int] = None
    # scoring
    score: float = 0.0
    score_breakdown: dict = {}


class SearchRequest(BaseModel):
    query: str
    max_results: int = 20


class SearchResponse(BaseModel):
    query: str
    expanded_queries: List[str]
    results: List[VideoResult]
    total_fetched: int
