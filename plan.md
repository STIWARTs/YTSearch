SYSTEM DESIGN 

Teacher Query
    ↓
YouTube API
    ↓
Get 50 videos
    ↓
Analyze title/description
    ↓
Analyze transcript
    ↓
Analyze thumbnail face detection
    ↓
Calculate score
    ↓
Return filtered educational animations


# STEP 1 — SEARCH VIDEOS

Free YouTube API.

Use expanded queries:

Example:

laws of motion animation
laws of motion simulation
laws of motion visual explanation


# STEP 2 — FETCH TRANSCRIPTS (FREE)

Use:

youtube-transcript-api GitHub

Install:

pip install youtube-transcript-api

Example:

from youtube_transcript_api import YouTubeTranscriptApi

transcript = YouTubeTranscriptApi.get_transcript(video_id)

This is HUGE for your project.


# STEP 3 — FACE DETECTION (FREE)

This is your MOST IMPORTANT FILTER.

Install:

pip install opencv-python

Use OpenCV Haar Cascade.

Example:

import cv2

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
)
LOGIC

If thumbnail contains:

large human face
classroom facecam

then:

score -= 50

This removes most lecture videos.


# STEP 4 — KEYWORD SCORING

VERY effective.

GOOD KEYWORDS
good_keywords = [
    "animation",
    "simulation",
    "visualized",
    "diagram",
    "3d",
    "motion graphics",
    "explained visually"
]
BAD KEYWORDS
bad_keywords = [
    "lecture",
    "neet",
    "jee",
    "classroom",
    "facecam",
    "live class",
    "teacher explains"
]


# STEP 5 — TRUSTED CHANNEL BOOSTING

Hardcode initial whitelist.

Example:

trusted_channels = [
    "Kurzgesagt",
    "MinutePhysics",
    "CrashCourse",
    "Veritasium",
    "3Blue1Brown"
]


# STEP 6 — TRANSCRIPT ANALYSIS

FREE + powerful.

GOOD SIGNALS
animation_signals = [
    "visualize",
    "diagram",
    "observe",
    "simulation",
    "motion",
    "particle"
]
BAD SIGNALS
lecture_signals = [
    "hello students",
    "welcome to class",
    "subscribe",
    "take your notebook"
]


# STEP 7 — FINAL SCORE    

Simple weighted scoring.

Example:

score = 0

score += keyword_score
score += transcript_score
score += trusted_channel_bonus
score -= face_penalty

Sort descending.

Done.


# IMPORTANT INSIGHT

You DO NOT initially need:

deep ML
custom models
expensive AI APIs

Good heuristic ranking already works surprisingly well.

Especially for educational filtering.


# BEST FREE EMBEDDING MODEL

Later use:

Sentence Transformers

Install:

pip install sentence-transformers

Model:

all-MiniLM-L6-v2

Fully free.

Very powerful.

# WHAT THIS ENABLES

Teacher searches:

laws of motion

Your semantic engine also understands:

inertia
acceleration
Newton laws
momentum

without exact keywords.


# RECOMMENDED MVP STACK

FRONTEND
Next.js
Tailwind
Shadcn UI

BACKEND
FastAPI

Why:

Python ecosystem
OpenCV
transcript libraries
ML support
DATABASE

Initially:

SQLite

No need PostgreSQL initially.


# SEARCH PIPELINE SHOULD BUILD    

User Query
   ↓
Query Expansion
   ↓
YouTube API
   ↓
Get top 50 videos
   ↓
Thumbnail Face Detection
   ↓
Transcript Analysis
   ↓
Keyword Scoring
   ↓
Trusted Channel Boost
   ↓
Final Ranked Results

...MVP...