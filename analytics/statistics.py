"""Analytics based only on stored tracking/detection records."""
from collections import defaultdict
from math import hypot
import statistics

def calculate_statistics(points, processing_s=None, processed_frames=None, zones=None, line_events=None):
    frames=defaultdict(list); track_points=defaultdict(list)
    for p in points:
        frames[int(p["frame_index"])].append(p)
        if p.get("track_id") is not None: track_points[int(p["track_id"])].append(p)
    occupancy=[len({p["track_id"] for p in rows if p.get("track_id") is not None}) for rows in frames.values()]
    confidences=[float(p["confidence"]) for p in points]
    distances={tid:sum(hypot(b["center_x"]-a["center_x"],b["center_y"]-a["center_y"])
                       for a,b in zip(sorted(rows,key=lambda x:x["timestamp_s"]),sorted(rows,key=lambda x:x["timestamp_s"])[1:]))
               for tid,rows in track_points.items()}
    duration=float(processing_s or 0); frame_count=int(processed_frames or 0)
    return {
        "total_detections":len(points),"unique_tracked_people":len(track_points),
        "sampled_frame_count":len(frames),"average_sampled_occupancy":statistics.mean(occupancy) if occupancy else 0.0,
        "peak_sampled_occupancy":max(occupancy,default=0),"movement_distance_px":round(sum(distances.values()),2),
        "most_active_track_id":max(distances,key=distances.get) if distances else None,
        "most_active_track_distance_px":round(max(distances.values(),default=0),2),
        "mean_detection_confidence":statistics.mean(confidences) if confidences else None,
        "min_detection_confidence":min(confidences,default=None),"max_detection_confidence":max(confidences,default=None),
        "processing_duration_s":round(duration,3),"processed_video_frames":frame_count,
        "processing_fps":round(frame_count/duration,3) if duration>0 else None,
        "occupancy_basis":"tracked people on inference-sampled frames; not interpolated between samples",
        "zones":zones or {},"line_events":line_events or {"A_to_B":0,"B_to_A":0},
    }

def occupancy_series(points):
    by_frame=defaultdict(list)
    for p in points: by_frame[(int(p["frame_index"]),float(p["timestamp_s"]))].append(p)
    return [{"frame_index":f,"timestamp_s":t,"detections":len(rows),
             "occupancy":len({p["track_id"] for p in rows if p.get("track_id") is not None})}
            for (f,t),rows in sorted(by_frame.items())]


def movement_activity_series(points):
    """Per-observation path length between consecutive sampled points for each track."""
    grouped=defaultdict(list)
    for p in points:
        if p.get("track_id") is not None: grouped[int(p["track_id"])].append(p)
    activity=defaultdict(float)
    for rows in grouped.values():
        rows=sorted(rows,key=lambda x:(x["timestamp_s"],x["frame_index"]))
        for a,b in zip(rows,rows[1:]):
            dist=hypot(b["center_x"]-a["center_x"],b["center_y"]-a["center_y"])
            activity[float(b["timestamp_s"])]+=dist
    return [{"timestamp_s":t,"movement_distance_px":round(d,2)} for t,d in sorted(activity.items())]
