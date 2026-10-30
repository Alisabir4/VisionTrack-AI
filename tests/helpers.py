"""Shared small video fixture helpers."""
import cv2

def write_video(path,frame,count=20,fps=5):
    h,w=frame.shape[:2]; out=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*"mp4v"),fps,(w,h))
    if not out.isOpened(): raise RuntimeError("mp4v test fixture writer unavailable")
    for _ in range(count): out.write(frame)
    out.release(); return path
