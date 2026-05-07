"use client";

import { useState, useRef, FormEvent } from "react";
import { Search, Play, AlertCircle, Zap, Eye, TrendingUp } from "lucide-react";
import { searchVideos, SearchResponse, VideoResult } from "@/lib/api";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/* Helpers                                                              */
/* ------------------------------------------------------------------ */
function formatViews(n: number | null): string {
  if (n === null) return "";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M views`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K views`;
  return `${n} views`;
}

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat("en-US", { year: "numeric", month: "short" }).format(
      new Date(iso)
    );
  } catch {
    return iso;
  }
}

function formatDuration(dur: string | null): string {
  if (!dur) return "";
  // ISO 8601: PT4M30S → 4:30
  const match = dur.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/);
  if (!match) return dur;
  const h = parseInt(match[1] ?? "0");
  const m = parseInt(match[2] ?? "0");
  const s = parseInt(match[3] ?? "0");
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function scoreClass(score: number): "positive" | "neutral" | "negative" {
  if (score >= 10) return "positive";
  if (score >= 0) return "neutral";
  return "negative";
}

/* ------------------------------------------------------------------ */
/* Sub-components                                                       */
/* ------------------------------------------------------------------ */
function SkeletonCard() {
  return (
    <div className="skeleton-card skeleton" />
  );
}

function ScoreBreakdown({ breakdown }: { breakdown: Record<string, string | number> }) {
  const keys = Object.keys(breakdown);
  if (keys.length === 0) return null;

  return (
    <details className="breakdown-details">
      <summary>Score breakdown</summary>
      <div className="breakdown-table">
        {keys.map((k) => (
          <>
            <span key={`k-${k}`} className="breakdown-key">{k}</span>
            <span key={`v-${k}`} className="breakdown-val">{String(breakdown[k])}</span>
          </>
        ))}
      </div>
    </details>
  );
}

function VideoCard({ video, rank }: { video: VideoResult; rank: number }) {
  const ytUrl = `https://www.youtube.com/watch?v=${video.video_id}`;
  const cls = scoreClass(video.score);

  return (
    <a
      href={ytUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="video-card"
      id={`result-${video.video_id}`}
    >
      {/* Thumbnail */}
      <div className="card-thumb-wrap">
        <img
          src={video.thumbnail_url}
          alt={video.title}
          className="card-thumb"
          loading="lazy"
        />
        <div className="play-overlay">
          <div className="play-icon">
            <Play size={18} color="#fff" fill="#fff" />
          </div>
        </div>
        <div className="rank-badge">{rank}</div>
      </div>

      {/* Body */}
      <div className="card-body">
        <div>
          <div className="card-channel">{video.channel_name}</div>
          <div className="card-title">{video.title}</div>
          <div className="card-desc">{video.description}</div>
        </div>

        <div>
          <div className="card-meta-row">
            <div className="card-meta-left">
              {video.view_count !== null && (
                <span>{formatViews(video.view_count)}</span>
              )}
              {video.duration && (
                <span>{formatDuration(video.duration)}</span>
              )}
              <span>{formatDate(video.published_at)}</span>
            </div>

            <span className={cn("score-badge", cls)}>
              <TrendingUp size={11} />
              {video.score > 0 ? "+" : ""}
              {video.score}
            </span>
          </div>

          <ScoreBreakdown breakdown={video.score_breakdown} />
        </div>
      </div>
    </a>
  );
}

/* ------------------------------------------------------------------ */
/* Main Page                                                            */
/* ------------------------------------------------------------------ */
export default function HomePage() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<SearchResponse | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleSearch(e: FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;

    setLoading(true);
    setError(null);
    setData(null);

    try {
      const result = await searchVideos(q, 20);
      setData(result);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An unknown error occurred.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page-shell">
      <div className="content-wrap">
        {/* Hero */}
        <header className="hero">
          <div className="hero-badge">
            <Zap size={11} />
            Multi-signal AI Ranking
          </div>
          <h1 className="hero-title">Find Educational Animations</h1>
          <p className="hero-subtitle">
            Search YouTube for the best visual, animated, and simulation-based
            learning videos. Lectures filtered out automatically.
          </p>

          {/* Search */}
          <form className="search-form" onSubmit={handleSearch} id="search-form">
            <input
              ref={inputRef}
              id="search-input"
              className="search-input"
              type="text"
              placeholder="laws of motion, photosynthesis, wave interference..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              autoFocus
            />
            <button
              id="search-btn"
              type="submit"
              className="search-btn"
              disabled={loading || !query.trim()}
            >
              <Search size={16} />
              {loading ? "Searching..." : "Search"}
            </button>
          </form>
        </header>

        {/* Expanded queries pills */}
        {data && (
          <div className="query-pills" aria-label="Expanded search queries">
            {data.expanded_queries.map((q) => (
              <span key={q} className="query-pill">{q}</span>
            ))}
          </div>
        )}

        {/* Stats bar */}
        {data && !loading && (
          <div className="stats-bar">
            <span>
              Showing <strong>{data.results.length}</strong> best results
              from <strong>{data.total_fetched}</strong> fetched videos
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
              <Eye size={13} />
              Ranked by animation score
            </span>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="error-box" role="alert" id="error-box">
            <AlertCircle size={18} style={{ flexShrink: 0, marginTop: 2 }} />
            <div>
              <strong>Error:</strong> {error}
              {error.includes("YOUTUBE_API_KEY") && (
                <p style={{ marginTop: "0.4rem", fontSize: "0.8rem", opacity: 0.8 }}>
                  Add your YouTube Data API v3 key to backend/.env as YOUTUBE_API_KEY.
                </p>
              )}
              {error.includes("quota exhausted") && (
                <p style={{ marginTop: "0.4rem", fontSize: "0.8rem", opacity: 0.8 }}>
                  The YouTube Data API free quota (10,000 units/day) has been exhausted.
                  It resets at midnight Pacific Time (UTC-8). No action needed — try again later.
                </p>
              )}
            </div>
          </div>
        )}

        {/* Loading skeletons */}
        {loading && (
          <div className="results-grid" aria-busy="true">
            {Array.from({ length: 6 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        )}

        {/* Results */}
        {!loading && data && data.results.length > 0 && (
          <div className="results-grid" id="results-grid">
            {data.results.map((video, i) => (
              <VideoCard key={video.video_id} video={video} rank={i + 1} />
            ))}
          </div>
        )}

        {/* Empty */}
        {!loading && data && data.results.length === 0 && (
          <div className="empty-state" id="empty-state">
            <div className="empty-icon">
              <Search size={40} />
            </div>
            <p>No results found. Try a different query.</p>
          </div>
        )}
      </div>
    </main>
  );
}
