"""YOLOv8n CPU-only person detector."""
import os
from pathlib import Path
import torch
from config import MODEL_PATH, PERSON_CLASS_ID

# Keep Ultralytics runtime configuration inside the project workspace.
_ultralytics_config = Path(__file__).resolve().parents[1] / "work" / "ultralytics"
_ultralytics_config.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", str(_ultralytics_config))
from ultralytics import YOLO

class PersonDetector:
    def __init__(self, model_path: str | Path = MODEL_PATH, threads=4):
        if not Path(model_path).is_file():
            raise FileNotFoundError(f"YOLOv8n weights not found: {model_path}")
        torch.set_num_threads(max(1, min(int(threads), os.cpu_count() or 1, 4)))
        self.model = YOLO(str(model_path))
        self.model.to("cpu")

    def predict(self, frame, *, conf=0.25, imgsz=640):
        results = self.model.predict(frame, device="cpu", classes=[PERSON_CLASS_ID], conf=conf,
                                     imgsz=imgsz, verbose=False, stream=False)
        return results[0]


