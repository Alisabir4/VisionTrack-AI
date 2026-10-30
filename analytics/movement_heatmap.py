"""Incremental trajectory accumulator and colorizer."""
import cv2
import numpy as np

class MovementHeatmap:
    def __init__(self,width,height,blur_sigma=18.0,colormap=cv2.COLORMAP_JET):
        self.width=width; self.height=height; self.blur_sigma=blur_sigma; self.colormap=colormap
        self.canvas=np.zeros((height,width),dtype=np.float32); self.last={}
    def update(self,tracks):
        for t in tracks:
            tid=t.get("track_id")
            if tid is None: continue
            pt=(int(round(t["center_x"])),int(round(t["center_y"])))
            if tid in self.last: cv2.line(self.canvas,self.last[tid],pt,1.0,2,cv2.LINE_AA)
            cv2.circle(self.canvas,pt,3,1.0,-1,cv2.LINE_AA); self.last[tid]=pt
    def render(self):
        blurred=cv2.GaussianBlur(self.canvas,None,self.blur_sigma)
        peak=float(blurred.max())
        if peak<=0: return np.zeros((self.height,self.width,3),dtype=np.uint8)
        gray=np.uint8(np.clip(blurred/peak*255,0,255))
        return cv2.applyColorMap(gray,self.colormap)
    def save(self,path):
        cv2.imwrite(str(path),self.render()); return path
