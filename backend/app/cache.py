"""
SQLite-backed async cache for scored search results.

Cache key  : lowercase-stripped query string
Cache value: full SearchResponse JSON blob
TTL        : configurable via CACHE_TTL_HOURS env var (default 24 h)

Schema
------
CREATE TABLE search_cache (
    query       TEXT PRIMARY KEY,
    response    TEXT NOT NULL,       -- JSON
    cached_at   REAL NOT NULL        -- unix timestamp (time.time())
);
"""
from __future__ import annotations

import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from app.config import settings

logger = logging.getLogger(__name__)

# DB file lives next to the backend package, not inside app/
_DB_PATH = Path(__file__).parent.parent / "cache.db"

# How long a cached entry stays valid (seconds)
_TTL = getattr(settings, "cache_ttl_hours", 24) * 3600


def _normalize(query: str) -> str:
    """Canonical cache key: strip + casefold."""
    return query.strip().casefold()


@asynccontextmanager
async def _get_conn():
    async with aiosqlite.connect(_DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS search_cache (
                query     TEXT PRIMARY KEY,
                response  TEXT NOT NULL,
                cached_at REAL NOT NULL
            )
            """
        )
        await conn.commit()
        yield conn


async def get_cached(query: str) -> dict | None:
    """
    Return the cached SearchResponse dict for *query*, or None if absent/expired.
    """
    key = _normalize(query)
    try:
        async with _get_conn() as conn:
            async with conn.execute(
                "SELECT response, cached_at FROM search_cache WHERE query = ?", (key,)
            ) as cur:
                row = await cur.fetchone()

        if row is None:
            return None

        age = time.time() - row["cached_at"]
        if age > _TTL:
            logger.info("Cache EXPIRED for '%s' (age=%.0fs)", query, age)
            await delete_cached(query)
            return None

        logger.info("Cache HIT for '%s' (age=%.0fs)", query, age)
        return json.loads(row["response"])

    except Exception:
        logger.exception("Cache read error for '%s'", query)
        return None


async def set_cached(query: str, response_dict: dict) -> None:
    """Persist *response_dict* (SearchResponse.model_dump()) for *query*."""
    key = _normalize(query)
    payload = json.dumps(response_dict, default=str)
    try:
        async with _get_conn() as conn:
            await conn.execute(
                """
                INSERT INTO search_cache (query, response, cached_at)
                VALUES (?, ?, ?)
                ON CONFLICT(query) DO UPDATE SET
                    response  = excluded.response,
                    cached_at = excluded.cached_at
                """,
                (key, payload, time.time()),
            )
            await conn.commit()
        logger.info("Cache SET for '%s'", query)
    except Exception:
        logger.exception("Cache write error for '%s'", query)


async def delete_cached(query: str) -> None:
    """Remove a single expired/stale entry."""
    key = _normalize(query)
    try:
        async with _get_conn() as conn:
            await conn.execute("DELETE FROM search_cache WHERE query = ?", (key,))
            await conn.commit()
    except Exception:
        logger.exception("Cache delete error for '%s'", query)


async def purge_expired() -> int:
    """Delete all rows older than TTL. Returns number of rows removed."""
    cutoff = time.time() - _TTL
    try:
        async with _get_conn() as conn:
            cur = await conn.execute(
                "DELETE FROM search_cache WHERE cached_at < ?", (cutoff,)
            )
            await conn.commit()
            removed = cur.rowcount
        if removed:
            logger.info("Cache purge: removed %d expired entries", removed)
        return removed
    except Exception:
        logger.exception("Cache purge error")
        return 0


async def cache_stats() -> dict:
    """Return row count and oldest/newest timestamps for the /cache/stats endpoint."""
    try:
        async with _get_conn() as conn:
            async with conn.execute(
                "SELECT COUNT(*) as cnt, MIN(cached_at) as oldest, MAX(cached_at) as newest FROM search_cache"
            ) as cur:
                row = await cur.fetchone()
        return {
            "total_entries": row["cnt"],
            "oldest_entry_age_s": round(time.time() - row["oldest"], 1) if row["oldest"] else None,
            "newest_entry_age_s": round(time.time() - row["newest"], 1) if row["newest"] else None,
            "ttl_hours": _TTL / 3600,
            "db_path": str(_DB_PATH),
        }
    except Exception:
        logger.exception("Cache stats error")
        return {}
