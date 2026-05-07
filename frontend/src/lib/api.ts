export interface VideoResult {
  video_id: string;
  title: string;
  description: string;
  channel_name: string;
  channel_id: string;
  thumbnail_url: string;
  published_at: string;
  duration: string | null;
  view_count: number | null;
  score: number;
  score_breakdown: Record<string, string | number>;
}

export interface SearchResponse {
  query: string;
  expanded_queries: string[];
  results: VideoResult[];
  total_fetched: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function searchVideos(
  query: string,
  maxResults = 20
): Promise<SearchResponse> {
  const url = `${API_BASE}/search?q=${encodeURIComponent(query)}&max_results=${maxResults}`;
  const res = await fetch(url, { cache: "no-store" });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }

  return res.json() as Promise<SearchResponse>;
}
