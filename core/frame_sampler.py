"""Profile-based sequential frame sampling with source indices and best-available PTS."""
from dataclasses import dataclass
from typing import Iterator
import math
import cv2

@dataclass(frozen=True)
class FrameSample:
    frame_index: int
    timestamp_s: float
    frame: object
    sampled: bool

def should_sample(frame_index: int, interval: int) -> bool:
    if interval < 1: raise ValueError("Sampling interval must be >= 1")
    return frame_index % interval == 0

def sequential_frames(capture: cv2.VideoCapture, fps: float, interval: int, cancel_event=None) -> Iterator[FrameSample]:
    """Decode all frames sequentially; use decoder PTS when available, else frame_index/fps."""
    if fps<=0: raise ValueError("fps must be positive")
    index=0; previous=-1.0
    while cancel_event is None or not cancel_event.is_set():
        ok,frame=capture.read()
        if not ok: break
        timestamp=index/fps
        if hasattr(capture,"get"):
            try:
                pts=float(capture.get(cv2.CAP_PROP_POS_MSEC))/1000.0
                if math.isfinite(pts) and pts>=0 and (index==0 or pts>previous): timestamp=pts
            except (TypeError,ValueError,cv2.error): pass
        if index>0 and timestamp<=previous: timestamp=index/fps
        previous=timestamp
        yield FrameSample(index,timestamp,frame,should_sample(index,interval))
        index+=1
