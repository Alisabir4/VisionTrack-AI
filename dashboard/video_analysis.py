"""Recorded video upload, CPU profile configuration, progress and synchronized playback."""
import threading
from pathlib import Path
import streamlit as st
from config import PROFILES,UPLOAD_DIR
from core.video_manager import save_upload,inspect_video,VideoValidationError
from utils.cache_manager import analysis_cache_key
from utils.media_server import get_media_server
from dashboard.paired_player import paired_video_player
from .common import get_db,get_jobs

@st.fragment(run_every=1.0)
def _job_fragment(analysis_id):
    state=get_jobs().status(analysis_id)
    st.progress(float(state["progress"]),text=state["message"])
    if state["status"] in ("queued","running"):
        if st.button("Cancel processing",key=f"cancel_{analysis_id}",type="secondary"):
            get_jobs().cancel(analysis_id); get_db().request_cancel(analysis_id); st.warning("Cancellation requested; the worker will stop at the next frame boundary.")
    elif state["status"]=="completed":
        st.success("Analysis completed. Open results to view synchronized playback and analytics.")
        if st.button("View analysis results",key=f"view_{analysis_id}"):
            st.session_state.selected_analysis_id=analysis_id; st.rerun()
    elif state["status"] in ("failed","cancelled"):
        row=get_db().get_analysis(analysis_id)
        st.error(state["message"] or (row and row["error"]) or state["status"])

def _show_pair(analysis):
    try:
        original=inspect_video(analysis["video_path"])
        heat=inspect_video(analysis["heatmap_video_path"])
    except Exception as e:
        st.error(f"Playback media validation failed: {e}"); return
    matched=(original.frame_count==heat.frame_count and abs(original.fps-heat.fps)<0.01 and
             abs(original.duration_s-heat.duration_s)<=max(0.05,1/original.fps))
    timeline_path=Path(analysis["processed_path"]).parent/"frame_timeline.json"
    if matched and timeline_path.is_file():
        st.success(f"Frame-count/FPS metadata matches ({original.frame_count:,} frames at {original.fps:g} FPS); the player has a stored per-frame source timestamp map.")
    elif matched:
        st.warning("Frame-count/FPS metadata matches, but the source timestamp map is missing; browser playback sync is unverified.")
    else:
        st.warning("The output timeline metadata differs from the source. Shared controls are provided, but synchronization is not verified for this file.")
    try:
        server=get_media_server()
        timeline_url=server.url(timeline_path) if timeline_path.is_file() else None
        paired_video_player(server.url(analysis["video_path"]),server.url(analysis["heatmap_video_path"]),timeline_url,heat.fps)
    except Exception as e: st.error(f"Could not prepare local playback streams: {e}")

def render():
    st.title("Video Analysis")
    st.caption("Upload a previously recorded MP4, AVI, or MOV (512 MB limit). Processing reads frames sequentially from disk on CPU.")
    db=get_db(); current_video_id=st.session_state.get("vt_video_id")
    upload=st.file_uploader("Choose a recorded video",type=["mp4","avi","mov"],key="visiontrack_upload")
    if upload is not None:
        key=f"{upload.name}:{upload.size}"
        if st.session_state.get("vt_upload_key")!=key:
            try:
                upload.seek(0); path,sha,size=save_upload(upload.name,upload,UPLOAD_DIR)
                metadata=inspect_video(path); video_id=db.upsert_video(metadata,upload.name)
                st.session_state.vt_upload_key=key; st.session_state.vt_video_id=video_id
                st.session_state.vt_video_metadata=metadata.as_dict()
                st.success("Upload validated and stored locally. The original file is preserved.")
                current_video_id=video_id
            except (VideoValidationError,OSError) as e:
                st.error(str(e)); return
        else:
            current_video_id=st.session_state.get("vt_video_id")
    if current_video_id:
        row=db.get_video(current_video_id)
        if row:
            m=row; c=st.columns(4)
            c[0].metric("Resolution",f"{m['width']} × {m['height']}")
            c[1].metric("Duration",f"{m['duration_s']:.2f} s")
            c[2].metric("Frame rate",f"{m['fps']:.2f} FPS")
            c[3].metric("Frames",f"{m['frame_count']:,}")
            with st.expander("Review source video",expanded=False): st.video(m["path"])
            settings=db.get_setting("processing",{"default_profile":"Balanced","confidence":0.25,"processing_width":640,"threads":4,"heatmap_opacity":0.65,"heatmap_snapshot_interval_s":5})
            with st.form("analysis_options"):
                profile_name=st.selectbox("Processing profile",list(PROFILES),index=list(PROFILES).index(settings.get("default_profile","Balanced")))
                profile=PROFILES[profile_name]
                c1,c2,c3=st.columns(3)
                confidence=c1.slider("Person confidence",0.05,0.95,float(settings.get("confidence",0.25)),0.05)
                image_size=c2.select_slider("Inference resolution",options=[480,640,800],value=profile.image_size)
                width=c3.select_slider("Processing width",options=[480,640,800,960],value=int(settings.get("processing_width",640)))
                c4,c5=st.columns(2)
                interval=c4.select_slider("Inference every Nth frame",options=[2,3,5,10],value=profile.frame_interval)
                opacity=c5.slider("Heatmap overlay opacity",0.1,0.9,float(settings.get("heatmap_opacity",0.65)),0.05)
                submitted=st.form_submit_button("Start CPU analysis",type="primary")
            if submitted:
                config={"confidence":confidence,"image_size":int(image_size),"processing_width":int(width),
                        "frame_interval":int(interval),"heatmap_opacity":float(opacity),"heatmap_snapshot_interval_s":int(settings.get("heatmap_snapshot_interval_s",5)),"save_heatmap_frames":True,
                        "threads":int(settings.get("threads",4))}
                settings.update({"default_profile":profile_name,"confidence":confidence,"processing_width":int(width),"heatmap_opacity":float(opacity)})
                db.set_setting("processing",settings)
                key=analysis_cache_key(row["sha256"],{"profile":profile_name,**config})
                analysis_id,cached=db.create_analysis(current_video_id,key,profile_name,config)
                st.session_state.selected_analysis_id=analysis_id
                if db.get_analysis(analysis_id)["status"]!="completed": get_jobs().start(analysis_id)
                st.rerun()
    analysis_id=st.session_state.get("selected_analysis_id")
    if analysis_id:
        analysis=db.get_analysis(analysis_id)
        if analysis:
            st.divider(); st.subheader(f"Analysis #{analysis_id} · {analysis['original_name']}")
            if analysis["status"] in ("queued","running"):
                _job_fragment(analysis_id)
            elif analysis["status"]=="completed":
                st.success("Analysis is complete. Original and movement heatmap share source-frame timestamps.")
                _show_pair(analysis)
            elif analysis["status"] in ("failed","cancelled"):
                st.error(analysis["error"] or analysis["status"])
                if st.button("Retry analysis",key=f"retry_{analysis_id}"):
                    new_id,cached=db.create_analysis(analysis["video_id"],analysis["cache_key"],analysis["profile"],analysis["config"])
                    get_jobs().start(new_id); st.session_state.selected_analysis_id=new_id; st.rerun()




