"""VisionTrack AI local Streamlit entry point. Recorded uploads only; CPU inference only."""
import os
from pathlib import Path
import streamlit as st

ROOT=Path(__file__).resolve().parent
os.environ.setdefault("YOLO_CONFIG_DIR",str(ROOT/"work"/"ultralytics"))
st.set_page_config(page_title="VisionTrack AI",page_icon="📹",layout="wide",initial_sidebar_state="expanded")
from dashboard.common import style_dashboard
style_dashboard()

PAGES={
    "Overview":("◈","dashboard.overview"),
    "Video Analysis":("▶","dashboard.video_analysis"),
    "Tracking Results":("◎","dashboard.tracking_results"),
    "Heatmaps":("▧","dashboard.heatmaps"),
    "Zone Analytics":("⌖","dashboard.zone_analytics"),
    "Reports":("▤","dashboard.reports"),
    "Settings":("⚙","dashboard.settings"),
}
with st.sidebar:
    st.markdown("# VisionTrack **AI**")
    st.caption("LOCAL · CPU ONLY · RECORDED VIDEO")
    page=st.radio("Navigation",list(PAGES),label_visibility="collapsed")
    st.divider()
    st.caption("YOLOv8n + ByteTrack\nNo camera · No cloud service")

module=__import__(PAGES[page][1],fromlist=["render"])
module.render()
