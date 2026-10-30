"""Sequential frame reading and upload validation; video data is never read wholesale."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import math
import os
import re
import tempfile
from typing import BinaryIO, Iterable, Iterator

import cv2

SUPPORTED_EXTENSIONS = {".mp4", ".avi", ".mov"}
INSPECTABLE_EXTENSIONS = SUPPORTED_EXTENSIONS | {".webm"}
CHUNK_SIZE = 1024 * 1024

class VideoValidationError(ValueError):
    """An uploaded video is unsupported, empty, or not decodable."""

@dataclass(frozen=True)
class VideoMetadata:
    path: Path
    sha256: str
    file_size: int
    width: int
    height: int
    fps: float
    frame_count: int
    duration_s: float
    codec: str = "unknown"

    def as_dict(self) -> dict:
        return {"path": str(self.path), "sha256": self.sha256, "file_size": self.file_size,
                "width": self.width, "height": self.height, "fps": self.fps,
                "frame_count": self.frame_count, "duration_s": self.duration_s, "codec": self.codec}

def safe_filename(name: str) -> str:
    base = Path(name.replace("\\", "/")).name
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._") or "video"
    return clean[:120]

def save_upload(name: str, source: BinaryIO | Iterable[bytes], upload_dir: Path) -> tuple[Path, str, int]:
    """Stream an upload to disk while hashing; existing originals are never overwritten."""
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise VideoValidationError(f"Unsupported format {suffix or '(no extension)'}; use MP4, AVI, or MOV.")
    upload_dir.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".upload-", suffix=suffix, dir=upload_dir)
    digest = hashlib.sha256()
    total = 0
    try:
        with os.fdopen(fd, "wb") as out:
            if isinstance(source,(bytes,bytearray,memoryview)):
                data=memoryview(source)
                for offset in range(0,len(data),CHUNK_SIZE):
                    chunk=data[offset:offset+CHUNK_SIZE]; out.write(chunk); digest.update(chunk); total+=len(chunk)
            elif hasattr(source, "read"):
                while chunk := source.read(CHUNK_SIZE):
                    if not isinstance(chunk, bytes):
                        chunk = bytes(chunk)
                    out.write(chunk); digest.update(chunk); total += len(chunk)
            else:
                for chunk in source:
                    if chunk:
                        out.write(chunk); digest.update(chunk); total += len(chunk)
        if total == 0:
            raise VideoValidationError("The uploaded file is empty.")
        sha = digest.hexdigest()
        target = upload_dir / f"{sha}{suffix}"
        if target.exists():
            os.unlink(temp_name)
        else:
            os.replace(temp_name, target)
        return target, sha, total
    except Exception:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
        raise

def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()

def inspect_video(path: str | Path) -> VideoMetadata:
    path = Path(path)
    if path.suffix.lower() not in INSPECTABLE_EXTENSIONS:
        raise VideoValidationError(f"Unsupported video extension: {path.suffix}")
    if not path.is_file() or path.stat().st_size == 0:
        raise VideoValidationError("Video file is missing or empty.")
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise VideoValidationError("OpenCV cannot open this video. It may be corrupted or use an unsupported codec.")
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if width <= 0 or height <= 0 or count <= 0 or not math.isfinite(fps) or fps <= 0:
            raise VideoValidationError("Video metadata is invalid or incomplete; the file may be corrupted.")
        # Decode one frame as a stronger sanity check than container metadata alone.
        ok, frame = cap.read()
        if not ok or frame is None or frame.size == 0:
            raise VideoValidationError("The video container opened but no frames could be decoded.")
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        return VideoMetadata(path=path, sha256=sha256_file(path),
                             file_size=path.stat().st_size, width=width, height=height,
                             fps=fps, frame_count=count, duration_s=count / fps)
    finally:
        cap.release()

