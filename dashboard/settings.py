"""CPU profile defaults, storage visibility, and conservative temporary cleanup."""
import streamlit as st
from config import PROFILES,UPLOAD_DIR,PROCESSED_DIR,HEATMAP_DIR,REPORT_DIR
from utils.performance_optimizer import storage_usage,clean_owned_temporary_files,configure_cpu
from .common import get_db

def render():
    st.title("Settings")
    db=get_db(); defaults=db.get_setting("processing",{"default_profile":"Balanced","confidence":0.25,"processing_width":640,"threads":4,"heatmap_opacity":0.65,"heatmap_snapshot_interval_s":5})
    with st.form("global_settings"):
        profile=st.selectbox("Default processing profile",list(PROFILES),index=list(PROFILES).index(defaults.get("default_profile","Balanced")))
        c1,c2,c3=st.columns(3)
        confidence=c1.slider("Default person confidence",0.05,0.95,float(defaults.get("confidence",0.25)),0.05)
        width=c2.select_slider("Processing width",options=[480,640,800,960],value=int(defaults.get("processing_width",640)))
        threads=c3.select_slider("CPU inference threads",options=[1,2,3,4],value=int(defaults.get("threads",4)))
        c4,c5=st.columns(2)
        opacity=c4.slider("Heatmap overlay opacity",0.1,0.9,float(defaults.get("heatmap_opacity",0.65)),0.05)
        snapshots=c5.select_slider("PNG heatmap snapshot spacing",options=[1,5,10,30,60],value=int(defaults.get("heatmap_snapshot_interval_s",5)),help="Video heatmap retains every source frame; PNG snapshots are written at this interval to limit disk use.")
        save=st.form_submit_button("Save defaults",type="primary")
    if save:
        db.set_setting("processing",{"default_profile":profile,"confidence":confidence,"processing_width":width,
                                      "threads":threads,"heatmap_opacity":opacity,"heatmap_snapshot_interval_s":snapshots})
        st.success("Settings saved to SQLite.")
    st.subheader("CPU profiles")
    st.dataframe([{"Profile":p.name,"Sample interval":f"Every {p.frame_interval}th frame","Inference size":f"{p.image_size}px"} for p in PROFILES.values()],width="stretch",hide_index=True)
    st.caption("Profile throughput depends on video decoding, source resolution, and CPU load. No fixed FPS is assumed.")
    roots={"uploads":UPLOAD_DIR,"processed":PROCESSED_DIR,"heatmaps":HEATMAP_DIR,"reports":REPORT_DIR}
    usage=storage_usage(roots)
    cols=st.columns(len(usage))
    for col,(name,item) in zip(cols,usage.items()): col.metric(name.title(),f"{item['mb']:.1f} MB")
    if st.button("Remove abandoned temporary files",help="Removes only partial uploads and files ending .tmp/.tmp.mp4 under VisionTrack storage. Completed videos and reports are retained."):
        deleted=clean_owned_temporary_files(roots.values()); st.success(f"Removed {len(deleted)} temporary files.")
    st.caption(f"Current process was configured for {configure_cpu(threads)} CPU threads. Inference stays on CPU; CUDA is not used.")
