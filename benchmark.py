"""Run and record a reproducible CPU-only YOLOv8n inference benchmark."""
from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import config

# Keep Ultralytics settings in the project; the user-profile directory may be read-only.
os.environ.setdefault("YOLO_CONFIG_DIR", str(config.PROJECT_DIR / "work" / "ultralytics"))

import cv2
import psutil
import torch
from ultralytics import YOLO


def benchmark(image_path: Path, runs: int, output: Path) -> dict:
    if not image_path.is_file():
        raise FileNotFoundError(f"Sample image not found: {image_path}")
    if runs < 1:
        raise ValueError("runs must be at least 1")

    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"OpenCV could not decode image: {image_path}")

    proc = psutil.Process()
    rss_before = proc.memory_info().rss
    cpu_before = psutil.cpu_percent(interval=0.2)
    model = YOLO(str(config.MODEL_PATH))
    model.to("cpu")
    # Warm up once; keep this separate from steady-state timing.
    t0 = time.perf_counter()
    warm_results = model.predict(image, device="cpu", classes=[config.PERSON_CLASS_ID],
                                 conf=config.CONFIDENCE_THRESHOLD, imgsz=config.INFERENCE_IMAGE_SIZE,
                                 verbose=False)
    warm_seconds = time.perf_counter() - t0
    timings = []
    peak_rss = proc.memory_info().rss
    results = warm_results
    for _ in range(runs):
        start = time.perf_counter()
        results = model.predict(image, device="cpu", classes=[config.PERSON_CLASS_ID],
                                conf=config.CONFIDENCE_THRESHOLD, imgsz=config.INFERENCE_IMAGE_SIZE,
                                verbose=False)
        timings.append(time.perf_counter() - start)
        peak_rss = max(peak_rss, proc.memory_info().rss)
    cpu_after = psutil.cpu_percent(interval=0.2)

    boxes = results[0].boxes
    detections = []
    if boxes is not None:
        for box in boxes:
            xyxy = [round(float(x), 2) for x in box.xyxy[0].tolist()]
            detections.append({"class_id": int(box.cls[0]), "class_name": "person",
                               "confidence": round(float(box.conf[0]), 4), "xyxy": xyxy})
    annotated_path = output.parent / "cpu_inference_result.jpg"
    cv2.imwrite(str(annotated_path), results[0].plot())
    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "python": platform.python_version(),
        "processor": platform.processor(), "logical_cpu_count": os.cpu_count(),
        "torch_version": torch.__version__, "cuda_available": torch.cuda.is_available(),
        "device": "cpu", "model": str(config.MODEL_PATH), "image": str(image_path),
        "image_resolution": {"width": int(image.shape[1]), "height": int(image.shape[0])},
        "confidence_threshold": config.CONFIDENCE_THRESHOLD,
        "inference_image_size": config.INFERENCE_IMAGE_SIZE,
        "warmup_seconds": round(warm_seconds, 4), "measured_runs": runs,
        "run_seconds": [round(x, 4) for x in timings],
        "mean_inference_seconds": round(statistics.mean(timings), 4),
        "median_inference_seconds": round(statistics.median(timings), 4),
        "steady_state_fps": round(1 / statistics.mean(timings), 3),
        "cpu_percent_sample_before_after": [cpu_before, cpu_after],
        "process_rss_before_mb": round(rss_before / 1024**2, 2),
        "process_rss_peak_mb": round(peak_rss / 1024**2, 2),
        "process_rss_increase_mb": round((peak_rss - rss_before) / 1024**2, 2),
        "detection_count": len(detections), "detections": detections,
        "annotated_image": str(annotated_path),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, default=config.SAMPLE_IMAGE)
    parser.add_argument("--runs", type=int, default=config.BENCHMARK_RUNS)
    parser.add_argument("--output", type=Path, default=config.BENCHMARK_DIR / "cpu_benchmark.json")
    args = parser.parse_args()
    print(json.dumps(benchmark(args.image, args.runs, args.output), indent=2))

