# YTSearch — System Documentation

## What This System Does

Teachers and students searching YouTube for educational content get overwhelmed by lecture videos, facecam recordings, and exam-prep channels. This system filters YouTube search results using multiple automated signals to surface only genuine animation and simulation-based educational videos — the kind that actually help someone understand a concept visually.

---

## High-Level Architecture

```
Browser (Next.js)
       |
       | HTTP GET /search?q=...
       v
FastAPI Backend (Python)
       |
       |--- Query Expander
       |         generates 7 visual-suffix variants
       |
       |--- YouTube Data API v3
       |         fetches up to 50 unique videos
       |
       |--- Parallel Scoring Threads
       |         |--- Keyword Scorer     (title + description)
       |         |--- Channel Scorer     (trusted whitelist)
       |         |--- Thumbnail Scorer   (OpenCV face detection)
       |         |--- Transcript Scorer  (caption NLP)
       |
       |--- Sort by final score (descending)
       |
       v
Ranked JSON response -> Browser renders cards
```

---

## Directory Structure

```
ytsearch/
  backend/
    app/
      __init__.py
      config.py               Environment variable loading
      models.py               Pydantic request/response types
      main.py                 FastAPI application, routes
      query_expander.py       Query expansion logic
      youtube_client.py       YouTube Data API v3 async client
      face_detector.py        OpenCV thumbnail analysis
      transcript_scorer.py    Caption download and NLP scoring
      keyword_scorer.py       Keyword matching + channel whitelist
      scorer.py               Parallel orchestration + final ranking
    requirements.txt
    .env                      YOUTUBE_API_KEY (not committed)
  frontend/
    src/
      app/
        page.tsx              Main search UI (client component)
        layout.tsx            Root layout, Inter font, SEO metadata
        globals.css           Full design system (CSS variables)
      lib/
        api.ts                Typed fetch client for the backend
        utils.ts              cn() class merging utility
    .env.local                NEXT_PUBLIC_API_URL
  README.md
  SYSTEM.md                   (this file)
  plan.md                     Original MVP design notes
```

---

## Backend — Module by Module

### `config.py`

Loads environment variables using `pydantic-settings`. The only required variable is `YOUTUBE_API_KEY`. Pydantic reads from the `.env` file automatically when the app starts.

```python
class Settings(BaseSettings):
    youtube_api_key: str = ""
    model_config = {"env_file": ".env"}
```

If the key is missing or empty, the `/search` endpoint returns HTTP 503 before any API call is made.

---

### `models.py`

Defines the data shapes that flow through the entire system.

**`VideoResult`** — one YouTube video with all raw metadata plus scoring fields:

| Field | Type | Source |
|---|---|---|
| `video_id` | str | YouTube search result |
| `title` | str | snippet.title |
| `description` | str | snippet.description |
| `channel_name` | str | snippet.channelTitle |
| `channel_id` | str | snippet.channelId |
| `thumbnail_url` | str | snippet.thumbnails.high.url |
| `published_at` | str | snippet.publishedAt |
| `duration` | str | contentDetails.duration (ISO 8601) |
| `view_count` | int | statistics.viewCount |
| `score` | float | computed by scorer pipeline |
| `score_breakdown` | dict | per-component deltas + reasons |

**`SearchRequest`** — `{ query: str, max_results: int }` (POST body)

**`SearchResponse`** — `{ query, expanded_queries, results, total_fetched }`

---

### `query_expander.py`

Takes the user's raw query and generates 7 variants by appending visual suffixes.

**Input:** `"laws of motion"`

**Output:**
```
laws of motion
laws of motion animation
laws of motion simulation
laws of motion visual explanation
laws of motion 3d visualization
laws of motion motion graphics
laws of motion explained visually
```

**Why this matters:** The YouTube search algorithm ranks by watch time and clicks, not educational quality. By searching with explicit visual suffixes, the result pool is biased toward animation-style content before any scoring happens. This is the cheapest filter in the pipeline — zero API cost overhead.

---

### `youtube_client.py`

Handles all communication with the YouTube Data API v3.

**Flow for each expanded query:**

1. Call `GET /search` with `part=snippet`, `type=video`, `maxResults=15`
2. Collect returned `videoId` values, skip any already seen (deduplication set)
3. Call `GET /videos` with `part=snippet,statistics,contentDetails` for all IDs in one batch request
4. Parse each item into a `VideoResult` object

**Two API calls per query**, not one. This is intentional: the `/search` endpoint does not return statistics or content details. The batch `/videos` call is cheaper than individual `/videos` calls.

**Error handling per query:**

- HTTP `403` or `429` — quota exhausted or rate limited. Logged, counter incremented, query skipped.
- HTTP any other error — logged, query skipped.
- Network timeout — logged, query skipped.
- API-level error embedded in a 200 response (rare) — detected by checking `response["error"]` key.

**Quota exhaustion detection:** If `queries_succeeded == 0` and `quota_errors > 0` after all queries run, the caller raises HTTP 503 with a human-readable message. The frontend renders this as a distinct error card explaining the daily reset time.

**YouTube API v3 quota cost:**

| Operation | Units |
|---|---|
| `/search` call | 100 units |
| `/videos` batch call | 1 unit |
| Free daily quota | 10,000 units |

With 7 expanded queries: `7 × (100 + 1) = 707 units per search`. The free tier supports roughly **14 searches per day**.

---

### `face_detector.py`

Uses OpenCV's Haar Cascade classifier to detect human faces in video thumbnails.

**Logic:**

1. Download the thumbnail image from YouTube's CDN into a temporary file
2. Convert to grayscale
3. Run `detectMultiScale` with the `haarcascade_frontalface_default.xml` cascade
4. Find the largest detected face
5. Calculate `face_area / total_image_area` ratio
6. If ratio >= `0.08` (8% of the image), apply a `-50` score penalty

**Why 8%?** A face that covers 8% or more of a thumbnail is large enough to be a deliberate "presenter cam" or "teacher face" composition. Smaller faces (group photos, diagrams with people for scale) are ignored.

**Score impact:** `-50` is the largest single penalty in the entire system. It is deliberately large because a frontal face thumbnail is the single strongest predictor that a video is a lecture, not an animation.

**Failure modes:** If the thumbnail download fails, the image cannot be decoded, or OpenCV throws an exception, the score delta returns `0.0` (no penalty, no bonus). The system degrades gracefully.

---

### `transcript_scorer.py`

Downloads the video's caption track using `youtube-transcript-api` (no API key required, uses YouTube's internal caption endpoint) and scores the full transcript text.

**Animation signals** (each hit: `+3`):
```
visualize, diagram, observe, simulation, motion, particle,
animate, model, trajectory, wave, oscillate, vector
```

**Lecture signals** (each hit: `-5`):
```
hello students, welcome to class, take your notebook, subscribe,
today we will learn, write this down, in this lecture, in this chapter
```

**Score formula:**
```
delta = (animation_hits × 3) - (lecture_hits × 5)
```

Lecture signals are weighted higher (`-5` vs `+3`) because a single "hello students" is a very reliable indicator of lecture content, whereas a single "visualize" could appear in any educational video.

**When no transcript is available:** Returns `(0.0, "no_transcript")`. No penalty for missing captions — many animation channels do not upload transcripts.

---

### `keyword_scorer.py`

Scores the video `title + description` string against two keyword lists.

**Good keywords** (`+5` each):
```
animation, simulation, visualized, diagram, 3d, motion graphics,
explained visually, visual, animated, physics simulation, interactive
```

**Bad keywords** (`-8` each):
```
lecture, neet, jee, classroom, facecam, live class, teacher explains,
class 11, class 12, cbse, board exam, ncert, study material
```

Bad keywords are weighted higher (`-8` vs `+5`) because a video title containing "NEET 2024 lecture" is almost certainly not an animation, while a title containing "animation" could still be a low-quality one.

**Trusted channel whitelist** (`+30` flat bonus):
```
Kurzgesagt, MinutePhysics, CrashCourse, Veritasium, 3Blue1Brown,
VSauce, SciShow, TED-Ed, Mark Rober, Smarter Every Day,
Numberphile, Tibees, Physics Girl, Looking Glass Universe
```

The `+30` channel bonus is enough to push a trusted-channel video to the top even if it lacks animation keywords, because these channels consistently produce high-quality visual content.

---

### `scorer.py`

Orchestrates all four scorers in parallel and produces the final ranking.

**Concurrency model:**

All scoring operations involve blocking I/O:
- `face_detector.py` — downloads an image over HTTP, then runs CPU-bound OpenCV
- `transcript_scorer.py` — downloads captions over HTTP
- `keyword_scorer.py` — pure CPU, but negligible

Running these sequentially for 50 videos would be slow. Instead, `scorer.py` uses `asyncio.run_in_executor` with a `ThreadPoolExecutor(max_workers=8)` to run each video's full scoring pipeline concurrently in a thread pool. The event loop stays free.

```python
tasks = [
    loop.run_in_executor(_executor, _score_single, video)
    for video in videos
]
scored = await asyncio.gather(*tasks)
```

**Final score formula per video:**
```
score = keyword_score + channel_score + face_score + transcript_score
```

All components are signed floats. The list is sorted descending. The top `max_results` (default 20) are returned.

**Score breakdown:** Every component writes its delta and reason string into `score_breakdown`, which the frontend exposes as a collapsible `<details>` element on each card.

---

### `main.py`

The FastAPI application. Two routes:

**`GET /health`** — returns `{ status: "ok", api_key_set: bool }`. Used to verify the backend is running and the key is loaded.

**`GET /search?q=...&max_results=...`** and **`POST /search`** (JSON body) — both call the same handler function. The GET variant exists for easy browser/curl testing.

**CORS** is configured to allow `http://localhost:3000` and `http://127.0.0.1:3000` so the Next.js dev server can call the backend without browser security errors.

**Error hierarchy:**
1. No API key → HTTP 503 (immediate, no YouTube calls made)
2. All queries quota-exhausted → HTTP 503 with reset time hint
3. Partial quota failure (some queries succeed) → returns partial results, no error
4. Network issue on individual query → skipped silently, rest continues

---

## Frontend — Module by Module

### `globals.css`

The entire visual design is defined here using CSS custom properties (no Tailwind utility classes for component-level styling).

**Design tokens:**
```css
--bg-base:      #0b0d12   /* page background */
--bg-card:      #151923   /* video card */
--accent:       #4f75ff   /* interactive blue */
--good:         #22d3a5   /* positive score */
--bad:          #f25f5c   /* negative score */
--text-muted:   #6b7a99
```

**Key CSS patterns used:**
- Ambient gradient blobs via `::before`/`::after` pseudo-elements with `filter: blur(120px)` — gives the page depth without images
- Shimmer skeleton animation using `background-position` keyframe — shown while the API is in-flight
- `display: -webkit-box` with `-webkit-line-clamp` for multi-line text truncation
- `transform: translateY(-2px)` and `box-shadow` on card hover — tactile lift effect
- `transition` on all interactive elements for smoothness

---

### `layout.tsx`

Sets up the Inter font via `next/font/google` and injects full SEO metadata:
- `<title>` tag
- `<meta name="description">`
- `<meta name="keywords">`

---

### `lib/api.ts`

A typed fetch wrapper. Calls the backend and returns a strongly-typed `SearchResponse`. Throws an `Error` with the API error message string on non-200 responses.

The base URL is read from `NEXT_PUBLIC_API_URL` (set in `.env.local`). Defaults to `http://localhost:8000` if not set.

---

### `page.tsx`

The entire UI in a single client component. Key sections:

**Hero** — badge, gradient title, subtitle, search form.

**Search form** — controlled input, submit button disabled while loading or when query is empty.

**Expanded query pills** — shown after first search, one pill per query variant. Shows the user what was actually searched.

**Stats bar** — `Showing N best results from M fetched videos` with a ranking label.

**Skeleton loaders** — 6 animated shimmer cards shown during the API call. Replaced by real cards on completion.

**Video cards** — each card contains:
- Thumbnail with play-button overlay on hover and rank badge (1, 2, 3...)
- Channel name (linked accent color)
- Title (2-line clamp)
- Description (2-line clamp)
- View count, duration, publish date
- Score badge (green/gray/red based on value)
- Collapsible score breakdown table

**Error box** — shown on API failure. Detects specific error strings to show contextual hints:
- `YOUTUBE_API_KEY` in the message → setup instruction
- `quota exhausted` in the message → daily reset explanation

**Empty state** — shown when the API succeeds but returns zero results.

---

## Data Flow — End to End

```
1. User types "laws of motion" and clicks Search
2. page.tsx calls searchVideos("laws of motion", 20) from lib/api.ts
3. api.ts fetches GET http://localhost:8000/search?q=laws%20of%20motion&max_results=20
4. main.py receives request, checks API key is set
5. query_expander.py returns 7 query strings
6. youtube_client.py loops over queries:
     - GET /search (100 units each) -> video IDs
     - GET /videos batch (1 unit each) -> full metadata
     - Builds VideoResult list, deduplicates by video_id
7. scorer.py dispatches all videos to thread pool:
     - Each thread runs keyword, channel, face, transcript scoring
     - asyncio.gather() waits for all threads
8. Results sorted by score descending, top 20 taken
9. SearchResponse JSON returned to browser
10. page.tsx updates state, React re-renders
11. Video cards appear with scores and breakdown
```

---

## Scoring — Concrete Example

**Video:** "Newton's Laws of Motion | 3D Animation" by Kurzgesagt

| Component | Delta | Reason |
|---|---|---|
| Keyword | +25 | animation (+5), 3d (+5), motion (+5), visual (+5), animated (+5) |
| Channel | +30 | trusted_channel=Kurzgesagt |
| Face detection | 0 | no_face (animated thumbnail) |
| Transcript | +9 | visualize, particle, motion hits |
| **Total** | **+64** | |

**Video:** "Newton Laws of Motion - NEET Class 11 Lecture" by SomeCoachingChannel

| Component | Delta | Reason |
|---|---|---|
| Keyword | -32 | lecture (-8), neet (-8), class 11 (-8), classroom (-8) |
| Channel | 0 | not_trusted |
| Face detection | -50 | large_face_ratio=0.41 |
| Transcript | -25 | hello students, welcome to class, take your notebook, in this lecture, write this down hits |
| **Total** | **-107** | |

The animation video ranks 171 points above the lecture video.

---

## Operational Notes

### YouTube API Quota

The free tier provides **10,000 units/day**. Each full search request costs approximately **707 units** (7 queries × 101 units). This allows roughly **14 searches/day** for free.

Quota resets daily at **midnight Pacific Time** (UTC-8 / UTC-7 in summer), which is approximately **12:30 PM IST** or **1:30 PM IST** during Indian summer.

To increase quota: Google Cloud Console → YouTube Data API v3 → Quotas → Request increase. Google typically approves educational/personal projects within 24-48 hours at no cost.

### Running the Backend

```powershell
cd backend
.\.venv\Scripts\uvicorn app.main:app --reload
```

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/health

### Running the Frontend

```powershell
cd frontend
npm run dev
```

- App: http://localhost:3000

### Environment Variables

| Variable | Location | Description |
|---|---|---|
| `YOUTUBE_API_KEY` | `backend/.env` | YouTube Data API v3 key |
| `NEXT_PUBLIC_API_URL` | `frontend/.env.local` | Backend base URL (default: http://localhost:8000) |

---

## What Is Not Built Yet (Planned)

- **SQLite caching** — cache scored results by query so repeat searches do not cost quota
- **Sentence Transformers semantic search** — `all-MiniLM-L6-v2` model to understand synonyms without exact keyword matches (e.g., searching "inertia" also matches "Newton's first law")
- **User feedback loop** — thumbs up/down on results to refine the channel whitelist and keyword weights
- **Quota budget tracking** — persist daily usage count and warn the user before they hit the limit
