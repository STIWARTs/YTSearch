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
from app.cache import get_cached, set_cached, purge_expired, cache_stats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    force=True,
)
logger = logging.getLogger(__name__)
app = FastAPI(
    title="YTSearch — Educational Animation Finder",
    description="Finds and ranks educational animation videos on YouTube using multi-signal scoring.",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "api_key_set": bool(settings.youtube_api_key)}


# ---------------------------------------------------------------------------
# Search (core logic, shared by POST + GET)
# ---------------------------------------------------------------------------

async def _run_search(query: str, max_results: int) -> SearchResponse:
    """Full search pipeline with cache read/write."""
    logger.info("--- Starting search for: '%s' ---", query)

    # 1. Cache check
    cached = await get_cached(query)
    if cached is not None:
        logger.info("Returning cached results for '%s'", query)
        # Re-slice in case max_results differs from what was originally cached
        response = SearchResponse(**cached)
        response.results = response.results[:max_results]
        return response

    # 2. Guard — API key must be present before hitting YouTube
    if not settings.youtube_api_key:
        raise HTTPException(
            status_code=503,
            detail="YOUTUBE_API_KEY is not configured on the server.",
        )

    # 3. Expand query → YouTube → score
    expanded = expand_query(query)
    logger.info("Query '%s' expanded to %d variants", query, len(expanded))

    search_result = await search_videos(expanded)
    logger.info(
        "Queries: attempted=%d succeeded=%d quota_errors=%d videos=%d",
        search_result.queries_attempted,
        search_result.queries_succeeded,
        search_result.quota_errors,
        len(search_result.videos),
    )

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

    # 4. Build full response (cache stores all results, not just the slice)
    full_response = SearchResponse(
        query=query,
        expanded_queries=expanded,
        results=ranked,
        total_fetched=len(raw_videos),
    )

    # 5. Persist to cache (fire-and-forget — don't block the response)
    await set_cached(query, full_response.model_dump())

    # 6. Slice for the caller
    full_response.results = ranked[:max_results]
    return full_response


# ---------------------------------------------------------------------------
# Search endpoints
# ---------------------------------------------------------------------------

@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    return await _run_search(request.query, request.max_results)


@app.get("/search", response_model=SearchResponse)
async def search_get(
    q: str = Query(..., description="Search query"),
    max_results: int = Query(20, ge=1, le=50),
) -> SearchResponse:
    """GET variant for easy browser/curl testing."""
    return await _run_search(q, max_results)


# ---------------------------------------------------------------------------
# Cache management endpoints
# ---------------------------------------------------------------------------

@app.get("/cache/stats")
async def get_cache_stats() -> dict:
    """Return cache statistics (entry count, ages, TTL, db path)."""
    return await cache_stats()


@app.delete("/cache/purge")
async def purge_cache() -> dict:
    """Delete all expired cache entries. Returns count removed."""
    removed = await purge_expired()
    return {"purged": removed}
