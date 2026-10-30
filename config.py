"""Shared paths and CPU-first processing defaults."""
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env", override=False)
MODEL_PATH = PROJECT_DIR / "models" / "yolov8n.pt"
SAMPLE_IMAGE = PROJECT_DIR / "samples" / "bus.jpg"
BENCHMARK_DIR = PROJECT_DIR / "benchmarks"
STORAGE_DIR = PROJECT_DIR / "storage"
UPLOAD_DIR = STORAGE_DIR / "uploads"
PROCESSED_DIR = STORAGE_DIR / "processed"
HEATMAP_DIR = STORAGE_DIR / "heatmaps"
REPORT_DIR = STORAGE_DIR / "reports"
DATABASE_PATH = PROJECT_DIR / "database" / "visiontrack.sqlite3"
DEVICE = "cpu"
PERSON_CLASS_ID = 0
CONFIDENCE_THRESHOLD = 0.25
INFERENCE_IMAGE_SIZE = 640
PROCESSING_WIDTH = 640

@dataclass(frozen=True)
class ProcessingProfile:
    name: str
    frame_interval: int
    image_size: int

PROFILES = {
    "Fast": ProcessingProfile("Fast", 5, 480),
    "Balanced": ProcessingProfile("Balanced", 3, 640),
    "Accurate": ProcessingProfile("Accurate", 2, 800),
}
