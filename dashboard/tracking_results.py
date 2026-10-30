"""Tracked-video playback, ID trajectories and structured exports."""
import streamlit as st
import pandas as pd
import plotly.express as px
from .common import choose_analysis,get_db,metric_row

def render():
    st.title("Tracking Results")
    analysis=choose_analysis()
    if not analysis:return
    summary=analysis["summary"]; points=get_db().get_points(analysis["id"])
    metric_row([("Unique track IDs",summary.get("unique_tracked_people",0),"IDs produced by ByteTrack"),
                ("Person detections",summary.get("total_detections",0),"Counts on inference-sampled frames"),
                ("Sampled occupancy peak",summary.get("peak_sampled_occupancy",0),summary.get("occupancy_basis")),
                ("Processing throughput",f"{summary.get('processing_fps') or 0:.2f} fps","Full source frames processed per wall second")])
    st.subheader("Processed video")
    if analysis.get("processed_path"): st.video(analysis["processed_path"])
    else: st.info("Annotated video is unavailable for this record.")
    if points:
        track_ids=sorted({p["track_id"] for p in points if p.get("track_id") is not None})
        selected=st.multiselect("Show track IDs",track_ids,default=track_ids[:10],key=f"tracks_{analysis['id']}")
        rows=[p for p in points if p.get("track_id") in selected]
        if rows:
            stride=max(1,len(rows)//5000); df=pd.DataFrame(rows[::stride])
            fig=px.line(df,x="center_x",y="center_y",color="track_id",hover_data=["timestamp_s","frame_index"],
                        template="plotly_dark",title="Movement trajectories (source-video pixels)")
            fig.update_yaxes(autorange="reversed",scaleanchor="x",scaleratio=1)
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",height=480)
            st.plotly_chart(fig,width="stretch")
        st.caption(f"Trajectory coordinates are recorded on inference-sampled frames; tracks are not interpolated across skipped frames.")
        csv_path=__import__('pathlib').Path(analysis["processed_path"]).parent/"tracking_results.csv"
        if csv_path.exists(): st.download_button("Download tracking CSV",csv_path.read_bytes(),file_name=f"analysis_{analysis['id']}_tracking.csv",mime="text/csv")
    else: st.info("This completed video contained no sampled person detections.")
