"""Overall and temporal density heatmaps from tracked centers."""
import cv2
import numpy as np

def density_array(points,width,height,bins=80):
    xy=np.asarray([[p["center_x"],p["center_y"]] for p in points if p.get("track_id") is not None],dtype=np.float32)
    if not len(xy): return np.zeros((height,width),np.float32)
    hist,_,_=np.histogram2d(xy[:,1],xy[:,0],bins=(min(bins,height),min(bins,width)),range=((0,height),(0,width)))
    scaled=cv2.resize(hist.astype(np.float32),(width,height),interpolation=cv2.INTER_CUBIC)
    return cv2.GaussianBlur(scaled,(0,0),max(2,min(width,height)/80))

def colorize_density(points,width,height,colormap=cv2.COLORMAP_TURBO):
    arr=density_array(points,width,height); peak=float(arr.max())
    if peak<=0: return np.zeros((height,width,3),np.uint8)
    return cv2.applyColorMap(np.uint8(np.clip(arr/peak*255,0,255)),colormap)


def density_time_windows(points,width,height,window_s=10.0,colormap=cv2.COLORMAP_TURBO):
    """Generate density images by fixed video-time windows and one overall image."""
    if window_s<=0: raise ValueError("window_s must be positive")
    grouped={}
    for p in points:
        if p.get("track_id") is None: continue
        start=int(float(p["timestamp_s"])//window_s)*window_s
        grouped.setdefault(start,[]).append(p)
    return {start:colorize_density(rows,width,height,colormap) for start,rows in sorted(grouped.items())}
