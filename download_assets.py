"""Download the local YOLOv8n weights and public Ultralytics sample over verified HTTPS."""
from pathlib import Path
import os
import urllib.request

ASSETS = {
    Path(__file__).resolve().parent / "models" / "yolov8n.pt":
        "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt",
    Path(__file__).resolve().parent / "samples" / "bus.jpg":
        "https://ultralytics.com/images/bus.jpg",
}

for target, url in ASSETS.items():
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".partial")
    request = urllib.request.Request(url, headers={"User-Agent": "VisionTrack-AI/Phase-1"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response, partial.open("wb") as out:
            length = response.headers.get("Content-Length")
            while chunk := response.read(1024 * 256):
                out.write(chunk)
        if not partial.exists() or partial.stat().st_size == 0:
            raise RuntimeError(f"Empty download: {url}")
        if length and partial.stat().st_size != int(length):
            raise RuntimeError(f"Incomplete download ({partial.stat().st_size}/{length} bytes): {url}")
        os.replace(partial, target)
        print(f"Saved {target} ({target.stat().st_size:,} bytes)")
    finally:
        if partial.exists():
            partial.unlink()
