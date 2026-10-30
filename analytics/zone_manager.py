"""Persistent normalized polygon/line definitions and analytics-only recalculation."""
from __future__ import annotations
import json
from pathlib import Path
import cv2
from database.db import Database
from analytics.zone_analytics import analyze_zones
from analytics.entry_exit import count_line_crossings
from analytics.zone_heatmap import create_zone_heatmap
import config

class ZoneManager:
    def __init__(self,db=None): self.db=db or Database()
    @staticmethod
    def validate_zones(zones):
        names=set(); normalized=[]
        for z in zones:
            name=str(z.get("name","")).strip()
            pts=z.get("polygon",[])
            if not name or name in names: raise ValueError("Zone names must be non-empty and unique.")
            if len(pts)<3: raise ValueError(f"Zone '{name}' needs at least three normalized vertices.")
            coords=[]
            for point in pts:
                if len(point)!=2: raise ValueError("Each polygon vertex must be [x,y].")
                x,y=map(float,point)
                if not (0<=x<=1 and 0<=y<=1): raise ValueError("Normalized zone coordinates must be between 0 and 1.")
                coords.append([x,y])
            contour=cv2.contourArea(__import__('numpy').asarray(coords,dtype='float32'))
            if contour<=0: raise ValueError(f"Zone '{name}' has zero area.")
            names.add(name); normalized.append({"name":name,"polygon":coords})
        return normalized
    def set_zones(self,video_id,zones):
        zones=self.validate_zones(zones); self.db.replace_zones(video_id,zones); return zones
    def delete_zone(self,video_id,name):
        zones=[z for z in self.db.get_zones(video_id) if z["name"]!=name]
        self.db.replace_zones(video_id,zones); return zones
    def set_counting_line(self,video_id,line):
        if line is None: self.db.set_counting_line(video_id,None); return None
        if len(line)!=2 or any(len(pt)!=2 for pt in line): raise ValueError("A counting line needs two [x,y] endpoints.")
        line=[[float(x),float(y)] for x,y in line]
        if any(not 0<=v<=1 for pt in line for v in pt) or line[0]==line[1]:
            raise ValueError("Counting line endpoints must be distinct normalized coordinates in [0,1].")
        self.db.set_counting_line(video_id,line); return line

def recalculate_zone_analytics(db:Database,analysis_id:int):
    analysis=db.get_analysis(analysis_id)
    if not analysis or analysis["status"]!="completed": return None
    points=db.get_points(analysis_id); zones=db.get_zones(analysis["video_id"])
    result=analyze_zones(points,zones,analysis["width"],analysis["height"]) if zones else {"events":[],"zones":{},"occupancy":[]}
    line=db.get_counting_line(analysis["video_id"])
    line_result=count_line_crossings(points,line,analysis["width"],analysis["height"]) if line else {"events":[],"A_to_B":0,"B_to_A":0}
    events=result["events"]+[{"zone_name":"__counting_line__","track_id":e["track_id"],"event_type":e["event_type"],
                               "frame_index":e["frame_index"],"timestamp_s":e["timestamp_s"]} for e in line_result["events"]]
    db.replace_zone_events(analysis_id,events)
    summary=analysis["summary"]
    summary["zones"]=result["zones"]; summary["zone_occupancy_series"]=result["occupancy"]
    summary["line_events"]={"A_to_B":line_result["A_to_B"],"B_to_A":line_result["B_to_A"]}
    width=min(analysis["width"],config.PROCESSING_WIDTH); height=round(analysis["height"]*width/analysis["width"])
    img=create_zone_heatmap(zones,result["zones"],width,height)
    path=config.HEATMAP_DIR/str(analysis_id)/"zone_activity_heatmap.png"; path.parent.mkdir(parents=True,exist_ok=True)
    cv2.imwrite(str(path),img)
    json_path=config.PROCESSED_DIR/str(analysis_id)/"analytics.json"
    json_path.parent.mkdir(parents=True,exist_ok=True); json_path.write_text(json.dumps(summary,indent=2),encoding="utf-8")
    db.set_analysis_status(analysis_id,"completed",summary=summary)
    return summary

