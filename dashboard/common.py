"""Shared dashboard data, styling and selection helpers."""
import streamlit as st
import pandas as pd
import plotly.express as px
from database.db import Database
from utils.job_manager import JobManager

@st.cache_resource
def get_db(): return Database()

@st.cache_resource
def get_jobs(): return JobManager(get_db())

def completed_analyses(): return [a for a in get_db().list_analyses(500) if a["status"]=="completed"]

def choose_analysis(label="Analysis"):
    rows=completed_analyses()
    if not rows:
        st.info("No completed analyses yet. Process a video on the Video Analysis page."); return None
    labels={f"#{r['id']} · {r['original_name']} · {r['profile']} · {r['created_at'][:19]}":r["id"] for r in rows}
    selected=st.selectbox(label,list(labels),key=f"select_{label}")
    return get_db().get_analysis(labels[selected])

def metric_row(values):
    cols=st.columns(len(values))
    for col,(label,value,help_text) in zip(cols,values): col.metric(label,value,help=help_text)

def occupancy_chart(points):
    if not points: st.info("No tracked points were recorded."); return
    frame_rows={}
    for p in points:
        key=(p["frame_index"],p["timestamp_s"]); frame_rows.setdefault(key,set())
        if p.get("track_id") is not None: frame_rows[key].add(p["track_id"])
    df=pd.DataFrame([{"time_s":t,"tracked occupancy":len(ids)} for (_,t),ids in sorted(frame_rows.items())])
    fig=px.line(df,x="time_s",y="tracked occupancy",template="plotly_dark",markers=True,
                color_discrete_sequence=["#43d7bd"])
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",height=300,margin=dict(l=10,r=10,t=15,b=10))
    st.plotly_chart(fig,width="stretch")

def style_dashboard():
    st.markdown("""<style>
    .stApp{background:#0a1020;color:#e9eff8}.block-container{padding-top:1.6rem;max-width:1450px}
    [data-testid="stSidebar"]{background:#0e1728;border-right:1px solid #202f44}
    h1,h2,h3{color:#edf4ff}p,.stMarkdown{color:#c6d3e5}
    div[data-testid="stMetric"]{background:linear-gradient(140deg,#111d30,#131f34);border:1px solid #24344b;padding:16px;border-radius:14px}
    .stButton>button{border-radius:9px;border:1px solid #2a485b;background:#122a3b;color:#e5f3ff}
    </style>""",unsafe_allow_html=True)
