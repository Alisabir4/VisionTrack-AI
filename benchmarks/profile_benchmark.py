"""End-to-end sampling-profile benchmark on a synthetic clip made from the shipped sample."""
from __future__ import annotations
import json,sys,tempfile,threading,time
from pathlib import Path
import cv2
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from config import PROFILES
from database.db import Database
from core.video_manager import inspect_video
from core.processor import VideoProcessor

ROOT.joinpath("work","ultralytics").mkdir(parents=True,exist_ok=True)
import os
os.environ.setdefault("YOLO_CONFIG_DIR",str(ROOT/"work"/"ultralytics"))

def main():
    image=cv2.imread(str(ROOT/"samples"/"bus.jpg"))
    width=640; height=round(image.shape[0]*width/image.shape[1]); image=cv2.resize(image,(width,height))
    output={"benchmark":"full sequential pipeline on repeated sample image frames","source_fps":5,"frames":60,"results":[]}
    with tempfile.TemporaryDirectory(prefix="visiontrack-profile-") as temp:
        root=Path(temp); source=root/"profile_sample.mp4"
        writer=cv2.VideoWriter(str(source),cv2.VideoWriter_fourcc(*"mp4v"),5,(width,height))
        if not writer.isOpened(): raise RuntimeError("mp4v writer unavailable")
        for _ in range(60): writer.write(image)
        writer.release(); meta=inspect_video(source); db=Database(root/"benchmark.sqlite3")
        vid=db.upsert_video(meta,source.name)
        for name,profile in PROFILES.items():
            settings={"confidence":0.25,"image_size":profile.image_size,"processing_width":640,
                      "frame_interval":profile.frame_interval,"heatmap_opacity":0.65,
                      "save_heatmap_frames":False,"threads":4}
            aid,_=db.create_analysis(vid,f"{meta.sha256}:{name}",name,settings)
            began=time.perf_counter(); summary=VideoProcessor(db,root/"processed",root/"heatmaps").process(
                aid,cancel_event=threading.Event()); elapsed=time.perf_counter()-began
            output["results"].append({"profile":name,"sample_interval":profile.frame_interval,
                "inference_image_size":profile.image_size,"sampled_frames":summary["sampled_frames"],
                "detections":summary["total_detections"],"unique_ids":summary["unique_tracked_people"],
                "wall_seconds":round(elapsed,3),"source_frames_per_second":summary["processing_fps"],
                "process_rss_peak_mb":summary["process_rss_peak_mb"],
                "host_cpu_percent_before_after":summary["cpu_percent_host_before_after"]})
            print(output["results"][-1],flush=True)
    path=ROOT/"benchmarks"/"processing_profiles.json"; path.write_text(json.dumps(output,indent=2),encoding="utf-8")
    print(f"Saved {path}")
if __name__=="__main__":main()

