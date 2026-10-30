"""Overview metrics and recent analysis history."""
import streamlit as st
import pandas as pd
import plotly.express as px
from .common import get_db,completed_analyses,metric_row

def render():
    st.title("VisionTrack AI")
    st.caption("Recorded-video movement analytics · local CPU processing")
    db=get_db(); rows=db.list_analyses(500); done=[r for r in rows if r["status"]=="completed"]
    total_ids=sum(int(r["summary"].get("unique_tracked_people",0)) for r in done)
    avg_occ=(sum(float(r["summary"].get("average_sampled_occupancy",0)) for r in done)/len(done)) if done else 0
    metric_row([("Videos analyzed",str(len(done)),"Completed analyses in the local history"),
                ("Tracked IDs",str(total_ids),"Sum of unique track IDs per completed analysis; IDs are not deduplicated across videos"),
                ("Avg sampled occupancy",f"{avg_occ:.2f}","Mean of each completed analysis' inference-sampled occupancy"),
                ("Storage analyses",str(len(rows)),"Includes queued, failed, and cancelled jobs")])
    st.subheader("Activity summary")
    if done:
        frame=[]
        for r in reversed(done):
            s=r["summary"]
            frame.append({"Video":r["original_name"],"Unique IDs":s.get("unique_tracked_people",0),
                          "Detections":s.get("total_detections",0),"Peak sampled occupancy":s.get("peak_sampled_occupancy",0),
                          "Throughput (source fps)":s.get("processing_fps")})
        df=pd.DataFrame(frame[-20:])
        fig=px.bar(df,x="Video",y="Unique IDs",template="plotly_dark",color="Peak sampled occupancy",
                   color_continuous_scale=["#24415d","#43d7bd"])
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",height=360)
        st.plotly_chart(fig,width="stretch")
        st.subheader("Recent analyses")
        st.dataframe(pd.DataFrame([{k:r[k] for k in ("id","original_name","profile","status","created_at")} for r in rows[:12]]),width="stretch",hide_index=True)
    else:
        st.info("No completed analyses yet. Upload a recorded video from Video Analysis to begin.")
