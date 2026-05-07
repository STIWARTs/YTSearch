"""
FastAPI application — entry point.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.models import SearchRequest, SearchResponse
from app.query_expander import expand_query
from app.youtube_client import search_videos
from app.scorer import rank_videos

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="YTSearch — Educational Animation Finder",
    description="Finds and ranks educational animation videos on YouTube using multi-signal scoring.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "api_key_set": bool(settings.youtube_api_key)}


@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    if not settings.youtube_api_key:
        raise HTTPException(
            status_code=503,
            detail="YOUTUBE_API_KEY is not configured on the server.",
        )

    expanded = expand_query(request.query)
    logger.info("Query '%s' expanded to %d variants", request.query, len(expanded))

    search_result = await search_videos(expanded)
    logger.info(
        "Queries: attempted=%d succeeded=%d quota_errors=%d videos=%d",
        search_result.queries_attempted,
        search_result.queries_succeeded,
        search_result.quota_errors,
        len(search_result.videos),
    )

    # All queries failed with quota/auth errors — surface a clear error
    if search_result.queries_succeeded == 0 and search_result.quota_errors > 0:
        raise HTTPException(
            status_code=503,
            detail=(
                "YouTube API quota exhausted or key unauthorized. "
                "Daily quota resets at midnight Pacific Time. "
                f"({search_result.quota_errors}/{search_result.queries_attempted} queries hit 403/429)"
            ),
        )

    raw_videos = search_result.videos
    logger.info("Fetched %d unique videos", len(raw_videos))

    ranked = await rank_videos(raw_videos)
    top = ranked[: request.max_results]

    return SearchResponse(
        query=request.query,
        expanded_queries=expanded,
        results=top,
        total_fetched=len(raw_videos),
    )


@app.get("/search")
async def search_get(
    q: str = Query(..., description="Search query"),
    max_results: int = Query(20, ge=1, le=50),
) -> SearchResponse:
    """GET variant for easy browser/curl testing."""
    return await search(SearchRequest(query=q, max_results=max_results))
