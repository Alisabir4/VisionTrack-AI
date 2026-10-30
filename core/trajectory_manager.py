"""Tracks and CSV serialization for trajectories."""
from collections import defaultdict
import csv
from pathlib import Path

class TrajectoryManager:
    def __init__(self):
        self.points=defaultdict(list)

    def add(self, track_id, frame_index, timestamp_s, x, y):
        if track_id is None: return
        self.points[int(track_id)].append({"frame_index":int(frame_index),"timestamp_s":float(timestamp_s),"x":float(x),"y":float(y)})

    @property
    def unique_ids(self): return len(self.points)

    def distance(self, track_id):
        pts=self.points.get(int(track_id),[])
        return sum(((b["x"]-a["x"])**2+(b["y"]-a["y"])**2)**0.5 for a,b in zip(pts,pts[1:]))

    def save_csv(self,path):
        path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
        with path.open("w",newline="",encoding="utf-8") as f:
            w=csv.writer(f); w.writerow(["track_id","frame_index","timestamp_s","center_x","center_y"])
            for track_id,pts in sorted(self.points.items()):
                for p in pts: w.writerow([track_id,p["frame_index"],f'{p["timestamp_s"]:.6f}',f'{p["x"]:.2f}',f'{p["y"]:.2f}'])
        return path
