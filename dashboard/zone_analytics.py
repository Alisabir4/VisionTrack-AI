"""Editable normalized polygon zones and line events recalculated from stored tracking rows."""
import json
import cv2
import streamlit as st
import pandas as pd
import plotly.express as px
from analytics.zone_manager import ZoneManager,recalculate_zone_analytics
from database.db import Database
from .common import get_db,completed_analyses

def _redraw_preview(path,zones):
    cap=cv2.VideoCapture(path); ok,frame=cap.read(); cap.release()
    if not ok:return None
    h,w=frame.shape[:2]
    for i,z in enumerate(zones):
        pts=[(int(x*w),int(y*h)) for x,y in z["polygon"]]
        cv2.polylines(frame,[__import__('numpy').array(pts,dtype='int32')],True,(70,220,170),3)
        if pts: cv2.putText(frame,z["name"],pts[0],cv2.FONT_HERSHEY_SIMPLEX,.8,(255,255,255),2)
    return frame

def render():
    st.title("Zone Analytics")
    analyses=completed_analyses()
    if not analyses: st.info("Complete a video analysis first. Zones can then be added and analytics recalculated from the saved tracks."); return
    options={f"#{a['id']} · {a['original_name']} · {a['profile']}":a["id"] for a in analyses}
    choice=st.selectbox("Video analysis",list(options),key="zone_analysis"); analysis=get_db().get_analysis(options[choice])
    db=get_db(); mgr=ZoneManager(db); video_id=analysis["video_id"]
    zones=db.get_zones(video_id)
    st.caption(f"Enter vertices as normalized [x,y] fractions from the top-left (0–1). Source resolution: {analysis['width']} × {analysis['height']}.")
    preview=_redraw_preview(analysis["video_path"],zones)
    if preview is not None: st.image(preview,channels="BGR",caption="Configured polygons over the first source frame",width="stretch")
    with st.form(f"zone_editor_{video_id}"):
        selected_name=st.selectbox("Zone to add or edit",["(new zone)"]+[z["name"] for z in zones],key=f"zone_edit_select_{video_id}")
        current=next((z for z in zones if z["name"]==selected_name),None)
        zone_name=st.text_input("Zone name",value=current["name"] if current else "Entrance")
        vertices=st.text_area("Polygon vertices JSON",value=json.dumps(current["polygon"] if current else [[0.1,0.1],[0.4,0.1],[0.4,0.5],[0.1,0.5]],indent=2),height=140)
        save=st.form_submit_button("Save or update zone",type="primary")
    if save:
        try:
            polygon=json.loads(vertices); updated=[z for z in zones if z["name"] not in {selected_name,zone_name.strip()}]
            updated.append({"name":zone_name.strip(),"polygon":polygon})
            mgr.set_zones(video_id,updated)
            for row in analyses:
                item=db.get_analysis(row["id"])
                if item["video_id"]==video_id: recalculate_zone_analytics(db,item["id"])
            st.success(f"Saved zone '{zone_name}'. Zone occupancy and entry/exit events recalculated from persisted tracks."); st.rerun()
        except (ValueError,TypeError,json.JSONDecodeError) as e: st.error(f"Zone was not saved: {e}")
    if zones:
        st.subheader("Configured zones")
        st.dataframe(pd.DataFrame([{"name":z["name"],"normalized vertices":json.dumps(z["polygon"])} for z in zones]),width="stretch",hide_index=True)
        with st.form(f"delete_zone_{video_id}"):
            delete_name=st.selectbox("Delete zone",[z["name"] for z in zones],key=f"delete_zone_select_{video_id}")
            delete=st.form_submit_button("Delete selected zone")
        if delete:
            mgr.delete_zone(video_id,delete_name)
            for row in analyses:
                item=db.get_analysis(row["id"])
                if item["video_id"]==video_id: recalculate_zone_analytics(db,item["id"])
            st.success(f"Deleted {delete_name}; saved analyses were recalculated without rerunning detection."); st.rerun()
    st.subheader("Virtual counting line")
    line=db.get_counting_line(video_id)
    with st.form(f"line_editor_{video_id}"):
        line_json=st.text_input("Line endpoints JSON · two normalized [x,y] points",value=json.dumps(line or [[0.5,0.05],[0.5,0.95]]))
        c1,c2=st.columns(2); save_line=c1.form_submit_button("Save counting line"); clear_line=c2.form_submit_button("Remove line")
    if save_line:
        try:
            mgr.set_counting_line(video_id,json.loads(line_json))
            for row in analyses:
                item=db.get_analysis(row["id"])
                if item["video_id"]==video_id: recalculate_zone_analytics(db,item["id"])
            st.success("Counting line saved. Crossing events recalculated from ByteTrack IDs."); st.rerun()
        except (ValueError,TypeError,json.JSONDecodeError) as e: st.error(str(e))
    if clear_line:
        mgr.set_counting_line(video_id,None)
        for row in analyses:
            item=db.get_analysis(row["id"])
            if item["video_id"]==video_id: recalculate_zone_analytics(db,item["id"])
        st.success("Counting line removed."); st.rerun()
    summary=db.get_analysis(analysis["id"])["summary"]
    st.subheader("Zone activity and crossings")
    zone_stats=summary.get("zones",{})
    if zone_stats:
        st.dataframe(pd.DataFrame([{"Zone":name,**stats} for name,stats in zone_stats.items()]),width="stretch",hide_index=True)
    else: st.info("No zones configured yet; add a polygon above.")
    line_events=summary.get("line_events",{})
    a,b=st.columns(2); a.metric("A → B crossings",line_events.get("A_to_B",0)); b.metric("B → A crossings",line_events.get("B_to_A",0))
    series=summary.get("zone_occupancy_series",[])
    if series:
        df=pd.DataFrame(series); fig=px.line(df,x="timestamp_s",y="occupancy",color="zone_name",markers=True,template="plotly_dark",title="Zone occupancy on sampled frames")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",height=320)
        st.plotly_chart(fig,width="stretch")

