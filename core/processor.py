"""Sequential CPU video pipeline. Detection is sampled; videos and heatmap frames stream to disk."""
from __future__ import annotations
import csv, json, os, time
from pathlib import Path
import cv2
import numpy as np
import psutil
from config import PROCESSED_DIR, HEATMAP_DIR, PROCESSING_WIDTH, PROFILES
from database.db import Database
from .tracker import PersonTracker
from .video_manager import inspect_video, VideoValidationError
from .frame_sampler import sequential_frames
from analytics.movement_heatmap import MovementHeatmap
from analytics.density_heatmap import colorize_density,density_time_windows
from analytics.zone_heatmap import create_zone_heatmap
from analytics.zone_analytics import analyze_zones
from analytics.entry_exit import count_line_crossings
from analytics.statistics import calculate_statistics,movement_activity_series

class ProcessingCancelled(Exception): pass

def _cleanup_failed_attempt(out_dir,heat_dir):
    for root,names in ((out_dir,("tracking.tmp.mp4","tracking_results.csv","detections.csv","trajectories.csv","analytics.json","frame_timeline.csv","frame_timeline.json","frame_timeline.tmp.json")),
                       (heat_dir,("movement.tmp.webm","movement_heatmap.webm","movement_heatmap.png","density_heatmap.png","zone_activity_heatmap.png"))):
        for name in names:
            path=root/name
            if path.is_file(): path.unlink()
        for folder_name in ("frames","density_windows"):
            folder=root/folder_name
            if folder.is_dir():
                for child in folder.iterdir():
                    if child.is_file() and (child.name.startswith("frame_") or child.name.startswith("density_")):
                        child.unlink()
                try: folder.rmdir()
                except OSError: pass

class VideoProcessor:
    def __init__(self,database:Database|None=None,processed_dir=PROCESSED_DIR,heatmap_dir=HEATMAP_DIR):
        self.db=database or Database(); self.processed_dir=Path(processed_dir); self.heatmap_dir=Path(heatmap_dir)

    def process(self,analysis_id:int,*,cancel_event,progress=None):
        analysis=self.db.get_analysis(analysis_id)
        if not analysis: raise ValueError(f"Unknown analysis {analysis_id}")
        process_start=time.perf_counter()
        monitor=psutil.Process(); rss_start=monitor.memory_info().rss; peak_rss=rss_start
        monitor.cpu_percent(None); cpu_before=psutil.cpu_percent(interval=0.1)
        profile=PROFILES[analysis["profile"]]
        settings=analysis["config"]
        meta=inspect_video(analysis["video_path"])
        cap=cv2.VideoCapture(str(meta.path))
        if not cap.isOpened(): raise VideoValidationError("Video could not be reopened for processing.")
        out_dir=self.processed_dir/str(analysis_id); heat_dir=self.heatmap_dir/str(analysis_id)
        out_dir.mkdir(parents=True,exist_ok=True); heat_dir.mkdir(parents=True,exist_ok=True)
        fps=meta.fps; out_width=min(meta.width,int(settings.get("processing_width",PROCESSING_WIDTH)))
        out_height=max(1,round(meta.height*out_width/meta.width))
        # Keep even dimensions for broadly compatible MP4 encoders.
        out_width=max(2,out_width-out_width%2); out_height=max(2,out_height-out_height%2)
        processed_final=out_dir/"tracking.mp4"; heat_video_final=heat_dir/"movement_heatmap.webm"
        processed_tmp=out_dir/"tracking.tmp.mp4"; heat_tmp=heat_dir/"movement.tmp.webm"
        tracking_fourcc=cv2.VideoWriter_fourcc(*"mp4v")
        heatmap_fourcc=cv2.VideoWriter_fourcc(*"VP80")
        tracking_writer=cv2.VideoWriter(str(processed_tmp),tracking_fourcc,fps,(out_width,out_height))
        heat_writer=cv2.VideoWriter(str(heat_tmp),heatmap_fourcc,fps,(out_width,out_height))
        if not tracking_writer.isOpened() or not heat_writer.isOpened():
            cap.release(); tracking_writer.release(); heat_writer.release()
            raise RuntimeError("OpenCV could not create the tracking MP4 or browser-compatible VP8 WebM heatmap.")
        conf=float(settings.get("confidence",0.25)); image_size=int(settings.get("image_size",profile.image_size))
        interval=int(settings.get("frame_interval",profile.frame_interval))
        tracker=PersonTracker(threads=int(settings.get("threads",4))); heat=MovementHeatmap(out_width,out_height)
        latest_heat=np.zeros((out_height,out_width,3),np.uint8)
        points_batch=[]; total_frames=max(1,meta.frame_count); index=0; sampled=0; detection_total=0; last_heatmap_export=-5.0
        wall_start=process_start
        csv_path=out_dir/"tracking_results.csv"
        points_path=out_dir/"detections.csv"
        zone_polys=self.db.get_zones(analysis["video_id"])
        try:
            trajectory_csv=out_dir/"trajectories.csv"; timeline_csv=out_dir/"frame_timeline.csv"; source_times=[]
            with points_path.open("w",newline="",encoding="utf-8") as pf, csv_path.open("w",newline="",encoding="utf-8") as tf, trajectory_csv.open("w",newline="",encoding="utf-8") as trf, timeline_csv.open("w",newline="",encoding="utf-8") as tlf:
                pw=csv.DictWriter(pf,fieldnames=["frame_index","timestamp_s","track_id","x1","y1","x2","y2","confidence","center_x","center_y"]); pw.writeheader()
                tw=csv.writer(tf); tw.writerow(["track_id","frame_index","timestamp_s","center_x","center_y"])
                trw=csv.writer(trf); trw.writerow(["track_id","frame_index","timestamp_s","center_x","center_y"])
                tlw=csv.writer(tlf); tlw.writerow(["source_frame_index","source_timestamp_s","heatmap_timestamp_s","inference_sampled"])
                for sample in sequential_frames(cap,fps,interval,cancel_event):
                    if cancel_event.is_set(): raise ProcessingCancelled()
                    frame=sample.frame; annot=frame
                    source_times.append(float(sample.timestamp_s))
                    tlw.writerow([sample.frame_index,f"{sample.timestamp_s:.9f}",f"{sample.frame_index/fps:.9f}",int(sample.sampled)])
                    small=cv2.resize(frame,(out_width,out_height),interpolation=cv2.INTER_AREA) if (frame.shape[1]!=out_width or frame.shape[0]!=out_height) else frame.copy()
                    if sample.sampled:
                        infer_w=min(frame.shape[1],int(settings.get("processing_width",PROCESSING_WIDTH)))
                        infer_h=max(1,round(frame.shape[0]*infer_w/frame.shape[1]))
                        infer=cv2.resize(frame,(infer_w,infer_h),interpolation=cv2.INTER_AREA) if infer_w!=frame.shape[1] else frame
                        tracks=tracker.update(infer,conf=conf,imgsz=image_size)
                        sampled+=1; mapped=[]; sx=frame.shape[1]/infer.shape[1]; sy=frame.shape[0]/infer.shape[0]
                        for tr in tracks:
                            x1,y1,x2,y2=(tr["x1"]*sx,tr["y1"]*sy,tr["x2"]*sx,tr["y2"]*sy)
                            cx=(x1+x2)/2; cy=(y1+y2)/2
                            row={"frame_index":sample.frame_index,"timestamp_s":round(sample.timestamp_s,6),
                                 "track_id":tr["track_id"],"x1":x1,"y1":y1,"x2":x2,"y2":y2,
                                 "confidence":tr["confidence"],"center_x":cx,"center_y":cy}
                            mapped.append(row); points_batch.append(row); detection_total+=1
                            color=(40,220,120)
                            cv2.rectangle(frame,(int(x1),int(y1)),(int(x2),int(y2)),color,2)
                            label=f"ID {tr['track_id']}  {tr['confidence']:.2f}" if tr["track_id"] is not None else f"person {tr['confidence']:.2f}"
                            cv2.putText(frame,label,(int(x1),max(20,int(y1)-8)),cv2.FONT_HERSHEY_SIMPLEX,0.55,color,2,cv2.LINE_AA)
                        heat.update([{**r,"center_x":r["center_x"]*out_width/frame.shape[1],
                                      "center_y":r["center_y"]*out_height/frame.shape[0]} for r in mapped])
                        latest_heat=heat.render()
                        snapshot_interval=float(settings.get("heatmap_snapshot_interval_s",5.0))
                        if settings.get("save_heatmap_frames",True) and sample.timestamp_s-last_heatmap_export>=snapshot_interval:
                            frame_dir=heat_dir/"frames"; frame_dir.mkdir(parents=True,exist_ok=True)
                            cv2.imwrite(str(frame_dir/f"frame_{sample.frame_index:09d}.png"),latest_heat)
                            last_heatmap_export=sample.timestamp_s
                        if points_batch:
                            self.db.add_points(analysis_id,points_batch)
                            pw.writerows(points_batch)
                            rows=[[r["track_id"],r["frame_index"],r["timestamp_s"],r["center_x"],r["center_y"]] for r in points_batch if r["track_id"] is not None]
                            tw.writerows(rows); trw.writerows(rows)
                            points_batch.clear()
                    # Preserve full source frame count/FPS: skipped frames reuse last rendered heatmap.
                    small_heat=latest_heat
                    opacity=float(settings.get("heatmap_opacity",0.65))
                    overlay=cv2.addWeighted(small,1.0-opacity,small_heat,opacity,0) if np.any(small_heat) else small
                    heat_writer.write(overlay)
                    if frame.shape[1]!=out_width or frame.shape[0]!=out_height:
                        annot=cv2.resize(frame,(out_width,out_height),interpolation=cv2.INTER_AREA)
                    tracking_writer.write(annot)
                    index=sample.frame_index+1
                    if index % max(1,int(fps)) == 0: peak_rss=max(peak_rss,monitor.memory_info().rss)
                    if progress and (index%max(1,int(fps))==0 or index==1):
                        progress(min(0.99,index/total_frames),f"Frame {index:,} of about {total_frames:,}; {sampled:,} inference samples")
                if points_batch:
                    self.db.add_points(analysis_id,points_batch); pw.writerows(points_batch)
                    rows=[[r["track_id"],r["frame_index"],r["timestamp_s"],r["center_x"],r["center_y"]] for r in points_batch if r["track_id"] is not None]
                    tw.writerows(rows); trw.writerows(rows)
            if cancel_event.is_set(): raise ProcessingCancelled()
        except Exception:
            cap.release(); tracking_writer.release(); heat_writer.release()
            _cleanup_failed_attempt(out_dir,heat_dir)
            raise
        finally:
            cap.release(); tracking_writer.release(); heat_writer.release()
        if index==0:
            _cleanup_failed_attempt(out_dir,heat_dir)
            raise VideoValidationError("No frames were decoded; the file may be corrupted.")
        heat_meta=inspect_video(heat_tmp)
        if heat_meta.frame_count != index or abs(heat_meta.fps-fps) > 0.01:
            _cleanup_failed_attempt(out_dir,heat_dir)
            raise VideoValidationError(f"Heatmap encoder output mismatch: expected {index} frames at {fps:g} FPS, got {heat_meta.frame_count} at {heat_meta.fps:g} FPS.")
        os.replace(processed_tmp,processed_final); os.replace(heat_tmp,heat_video_final)
        timeline_tmp=out_dir/"frame_timeline.tmp.json"
        timeline_tmp.write_text(json.dumps({"frame_count":index,"source_timestamps_s":source_times,
                                            "source_fps_metadata":fps,"heatmap_fps":fps,
                                            "heatmap_timestamps_s":[i/fps for i in range(index)]},separators=(",",":")),encoding="utf-8")
        os.replace(timeline_tmp,out_dir/"frame_timeline.json")
        peak_rss=max(peak_rss,monitor.memory_info().rss)
        cpu_after=psutil.cpu_percent(interval=0.1); process_cpu=monitor.cpu_percent(None)
        elapsed=time.perf_counter()-wall_start
        # Derive analytics from saved rows, never from fabricated estimates.
        points=self.db.get_points(analysis_id)
        zone_result=analyze_zones(points,zone_polys,meta.width,meta.height) if zone_polys else {"events":[],"zones":{},"occupancy":[]}
        line=self.db.get_counting_line(analysis["video_id"]) or settings.get("counting_line")
        line_result=count_line_crossings(points,line,meta.width,meta.height) if line else {"events":[],"A_to_B":0,"B_to_A":0}
        events=zone_result["events"]+[{"zone_name":"__counting_line__","track_id":e["track_id"],"event_type":e["event_type"],"frame_index":e["frame_index"],"timestamp_s":e["timestamp_s"]} for e in line_result["events"]]
        self.db.replace_zone_events(analysis_id,events)
        summary=calculate_statistics(points,elapsed,index,zone_result["zones"],
                                     {"A_to_B":line_result["A_to_B"],"B_to_A":line_result["B_to_A"]})
        summary.update({"source_width":meta.width,"source_height":meta.height,"source_fps":fps,
                        "source_frame_count":meta.frame_count,"actual_frames_read":index,
                        "frame_timeline_path":str(out_dir/"frame_timeline.json"),
                        "sample_interval":interval,"sampled_frames":sampled,"inference_image_size":image_size,
                        "profile":analysis["profile"],"video_sha256":meta.sha256,
                        "zone_occupancy_series":zone_result["occupancy"],
                        "movement_activity_series":movement_activity_series(points),
                        "cpu_percent_host_before_after":[cpu_before,cpu_after],
                        "process_cpu_percent_interval":process_cpu,
                        "process_rss_start_mb":round(rss_start/1024**2,2),
                        "process_rss_peak_mb":round(peak_rss/1024**2,2),
                        "process_rss_increase_mb":round((peak_rss-rss_start)/1024**2,2),
                        "heatmap_frame_semantics":"sampled cumulative movement map repeated between source-frame indices"})
        # Export overall movement/density/zone PNGs and machine-readable analytics.
        heat.save(heat_dir/"movement_heatmap.png")
        density_img=colorize_density(points,out_width,out_height)
        cv2.imwrite(str(heat_dir/"density_heatmap.png"),density_img)
        window_dir=heat_dir/"density_windows"; window_dir.mkdir(parents=True,exist_ok=True)
        for window_start,window_img in density_time_windows(points,out_width,out_height,window_s=10.0).items():
            cv2.imwrite(str(window_dir/f"density_{int(window_start):08d}s.png"),window_img)
        cv2.imwrite(str(heat_dir/"zone_activity_heatmap.png"),create_zone_heatmap(zone_polys,zone_result["zones"],out_width,out_height))
        (out_dir/"analytics.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
        self.db.set_analysis_status(analysis_id,"completed",processed_path=processed_final,
                                   heatmap_video_path=heat_video_final,summary=summary)
        if progress: progress(1.0,f"Complete: {index:,} frames; {summary['unique_tracked_people']} tracked IDs")
        return summary




