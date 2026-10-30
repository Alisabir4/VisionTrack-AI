"""Historical report generation and cross-analysis comparisons."""
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px
from utils.report_generator import generate_reports
from analytics.statistics import occupancy_series
from .common import get_db,completed_analyses

def _show_analytics_charts(analysis,db):
    summary=analysis["summary"]; points=db.get_points(analysis["id"]); occupancy=occupancy_series(points)
    c1,c2=st.columns(2)
    if occupancy:
        df=pd.DataFrame(occupancy)
        fig=px.line(df,x="timestamp_s",y="occupancy",markers=True,template="plotly_dark",title="Tracked people over time")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",height=300); c1.plotly_chart(fig,width="stretch")
        fig=px.line(df,x="timestamp_s",y="detections",markers=True,template="plotly_dark",title="Person detections per inference sample")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",height=300); c2.plotly_chart(fig,width="stretch")
    activity=summary.get("movement_activity_series",[])
    if activity:
        df=pd.DataFrame(activity); fig=px.bar(df,x="timestamp_s",y="movement_distance_px",template="plotly_dark",title="Movement between sampled points")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",height=300); c1.plotly_chart(fig,width="stretch")
    zones=summary.get("zones",{})
    if zones:
        df=pd.DataFrame([{"zone":n,"activity samples":z.get("activity_samples",0),"entries":z.get("entry_events",0),"exits":z.get("exit_events",0)} for n,z in zones.items()])
        fig=px.bar(df,x="zone",y=["activity samples","entries","exits"],barmode="group",template="plotly_dark",title="Zone comparison")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",height=300); c2.plotly_chart(fig,width="stretch")
    line=summary.get("line_events",{}); fig=px.bar(pd.DataFrame([{"Direction":"A → B","Events":line.get("A_to_B",0)},{"Direction":"B → A","Events":line.get("B_to_A",0)}]),x="Direction",y="Events",template="plotly_dark",title="Counting-line crossings")
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",height=300); st.plotly_chart(fig,width="stretch")

def render():
    st.title("Reports")
    rows=completed_analyses()
    if not rows: st.info("No completed analyses to report."); return
    options={f"#{a['id']} · {a['original_name']} · {a['profile']}":a["id"] for a in rows}
    selected=st.selectbox("Analysis",list(options),key="report_analysis"); analysis_id=options[selected]
    db=get_db(); analysis=db.get_analysis(analysis_id)
    _show_analytics_charts(analysis,db)
    if st.button("Generate CSV, PDF and PNG reports",type="primary"):
        try:
            files=generate_reports(analysis_id,db); st.session_state.report_files={k:str(v) for k,v in files.items()}; st.success("Reports generated from persisted tracking and analytics records.")
        except Exception as e: st.error(f"Report generation failed: {e}")
    files=st.session_state.get("report_files",{})
    for label,key,mime in (("Tracking CSV","tracking_csv","text/csv"),("Summary CSV","summary_csv","text/csv"),("PDF report","pdf","application/pdf"),("Occupancy chart","occupancy_png","image/png"),("Zone chart","zone_png","image/png"),("Movement chart","movement_png","image/png")):
        if key in files and Path(files[key]).is_file():
            path=Path(files[key]); st.download_button(f"Download {label}",path.read_bytes(),file_name=path.name,mime=mime,key=f"download_{key}")
    st.subheader("Compare analyses")
    labels=list(options)
    if len(labels)>=2:
        chosen=st.multiselect("Select analyses",labels,default=labels[:2],max_selections=5,key="compare_analyses")
        comp=[]
        for label in chosen:
            row=db.get_analysis(options[label]); s=row["summary"]
            comp.append({"Analysis":label,"Unique IDs":s.get("unique_tracked_people",0),"Detections":s.get("total_detections",0),
                         "Peak sampled occupancy":s.get("peak_sampled_occupancy",0),"Processing FPS":s.get("processing_fps")})
        if comp:
            df=pd.DataFrame(comp); st.dataframe(df,width="stretch",hide_index=True)
            fig=px.bar(df,x="Analysis",y=["Unique IDs","Peak sampled occupancy"],barmode="group",template="plotly_dark")
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",height=320)
            st.plotly_chart(fig,width="stretch")
    else: st.caption("Complete at least two analyses to compare their actual results.")
