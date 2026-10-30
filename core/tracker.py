"""Persistent ByteTrack wrapper. Updates only on sampled frames."""
from pathlib import Path
from config import MODEL_PATH
from .detector import PersonDetector

class PersonTracker(PersonDetector):
    def __init__(self, model_path: str | Path = MODEL_PATH, tracker_config="bytetrack.yaml", threads=4):
        super().__init__(model_path,threads=threads)
        self.tracker_config = tracker_config
        self._started = False

    def update(self, frame, *, conf=0.25, imgsz=640):
        result = self.model.track(frame, device="cpu", classes=[0], conf=conf, imgsz=imgsz,
                                  tracker=self.tracker_config, persist=self._started,
                                  verbose=False, stream=False)[0]
        self._started = True
        output=[]
        boxes=result.boxes
        if boxes is None:
            return output
        ids = boxes.id
        for idx, box in enumerate(boxes):
            coords=[float(v) for v in box.xyxy[0].tolist()]
            track_id=int(ids[idx]) if ids is not None else None
            output.append({"track_id":track_id,"x1":coords[0],"y1":coords[1],"x2":coords[2],"y2":coords[3],
                           "confidence":float(box.conf[0]),"class_id":int(box.cls[0])})
        return output


