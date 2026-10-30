"""Spatial zone activity map; values are observed unique visitors per configured polygon."""
import cv2
import numpy as np
from .zone_analytics import polygon_pixels

def create_zone_heatmap(zones,zone_stats,width,height,colormap=cv2.COLORMAP_HOT):
    canvas=np.zeros((height,width),np.float32)
    vals=[zone_stats.get(z["name"],{}).get("activity_samples",0) for z in zones]
    maxv=max(vals,default=0)
    for z,v in zip(zones,vals):
        if v<=0: continue
        poly=polygon_pixels(z["polygon"],width,height)
        cv2.fillPoly(canvas,[poly],float(v)); cv2.polylines(canvas,[poly],True,float(v),2)
    if maxv<=0: return np.zeros((height,width,3),np.uint8)
    gray=np.uint8(np.clip(canvas/maxv*255,0,255)); return cv2.applyColorMap(gray,colormap)
