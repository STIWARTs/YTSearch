"""
Thumbnail face-detection module using OpenCV Haar Cascade.

A thumbnail dominated by a large frontal face indicates a lecture-style
video (classroom/facecam). Such videos are penalised heavily.
"""
from __future__ import annotations

import logging
import urllib.request
import tempfile
import os

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
_face_cascade = cv2.CascadeClassifier(_CASCADE_PATH)

# If the largest detected face covers more than this fraction of the thumbnail
# area we apply the full penalty.
FACE_AREA_THRESHOLD = 0.08  # 8 % of total pixel area


def score_thumbnail(thumbnail_url: str) -> tuple[float, str]:
    """
    Returns (score_delta, reason).
    Negative when a large face is detected (lecture penalty).
    """
    if not thumbnail_url:
        return 0.0, "no_thumbnail"

    try:
        # Download thumbnail into a temporary file
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name

        urllib.request.urlretrieve(thumbnail_url, tmp_path)

        img = cv2.imread(tmp_path)
        os.unlink(tmp_path)

        if img is None:
            return 0.0, "decode_error"

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        total_area = h * w

        faces = _face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60),
        )

        if len(faces) == 0:
            return 0.0, "no_face"

        # Find the largest face
        largest = max(faces, key=lambda f: f[2] * f[3])
        face_area = largest[2] * largest[3]
        ratio = face_area / total_area

        if ratio >= FACE_AREA_THRESHOLD:
            return -50.0, f"large_face_ratio={ratio:.2f}"

        return 0.0, f"small_face_ratio={ratio:.2f}"

    except Exception as exc:
        logger.warning("Face detection error for %s: %s", thumbnail_url, exc)
        return 0.0, "error"
