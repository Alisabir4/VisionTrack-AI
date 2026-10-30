"""Precomputed heatmap views, opacity preview, and PNG export."""
import cv2
import streamlit as st
from pathlib import Path
from .common import choose_analysis

def render():
    st.title("Heatmap Analytics")
    analysis=choose_analysis()
    if not analysis:return
    key_id=analysis["id"]
    d=Path(analysis["heatmap_video_path"]).parent
    maps={"Movement heatmap":d/"movement_heatmap.png","Density heatmap":d/"density_heatmap.png","Zone activity":d/"zone_activity_heatmap.png"}
    st.caption("Maps and time windows are precomputed from tracking data. Playback never runs YOLO or rebuilds the map.")
    cols=st.columns(3)
    for col,(label,path) in zip(cols,maps.items()):
        col.subheader(label)
        if path.exists():
            col.image(str(path),width="stretch")
            col.download_button("Export PNG",path.read_bytes(),file_name=f"analysis_{key_id}_{path.name}",mime="image/png",key=f"download_{label}_{key_id}")
        else: col.info("No heatmap image is available.")
    window_dir=d/"density_windows"
    windows=sorted(window_dir.glob("density_*.png")) if window_dir.exists() else []
    if windows:
        selected_window=st.selectbox("Density time window",windows,key=f"density_window_{key_id}")
        st.image(str(selected_window),caption=f"Tracked-person spatial density · {selected_window.stem}",width="stretch")
        st.download_button("Export selected density window",selected_window.read_bytes(),file_name=selected_window.name,mime="image/png")
    opacity=st.slider("Overlay opacity preview",0.05,0.95,0.65,0.05,key=f"opacity_{key_id}")
    video=cv2.VideoCapture(analysis["video_path"]); ok,frame=video.read(); video.release()
    heat_path=maps["Movement heatmap"]
    if ok and heat_path.exists():
        base=cv2.resize(frame,(640,round(frame.shape[0]*640/frame.shape[1])))
        heat=cv2.imread(str(heat_path)); heat=cv2.resize(heat,(base.shape[1],base.shape[0]))
        st.image(cv2.addWeighted(base,1-opacity,heat,opacity,0),channels="BGR",caption="Original frame with precomputed movement map")
    st.info("The paired original/heatmap player is on the Video Analysis page. Its files stream from disk using byte-range requests.")
