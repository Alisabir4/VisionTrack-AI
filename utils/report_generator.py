"""CSV, PDF and PNG report exports generated from persisted observations."""
from __future__ import annotations
import csv,json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image
import config
from analytics.statistics import occupancy_series,movement_activity_series

def _save(fig,path):
    fig.tight_layout(); fig.savefig(path,dpi=150,facecolor=fig.get_facecolor()); plt.close(fig); return path

def _charts(summary,points,outdir):
    series=occupancy_series(points); fig,ax=plt.subplots(figsize=(8,3.4),facecolor="#0d1524"); ax.set_facecolor("#111d30")
    ax.plot([x["timestamp_s"] for x in series],[x["occupancy"] for x in series],color="#42d6bd",lw=2)
    ax.set_xlabel("Video time (s)",color="#c4d2e5"); ax.set_ylabel("Tracked occupancy on sampled frames",color="#c4d2e5")
    ax.tick_params(colors="#c4d2e5"); ax.grid(color="#34445b",alpha=.5); occ=_save(fig,outdir/"occupancy_chart.png")
    zones=summary.get("zones",{}); fig,ax=plt.subplots(figsize=(8,3.4),facecolor="#0d1524"); ax.set_facecolor("#111d30")
    names=list(zones); vals=[zones[n].get("activity_samples",0) for n in names]
    ax.bar(names,vals,color="#4fa3ff"); ax.set_ylabel("Tracked person samples in zone",color="#c4d2e5"); ax.tick_params(colors="#c4d2e5"); ax.grid(axis="y",color="#34445b",alpha=.5); zone=_save(fig,outdir/"zone_comparison.png")
    activity=movement_activity_series(points); fig,ax=plt.subplots(figsize=(8,3.4),facecolor="#0d1524"); ax.set_facecolor("#111d30")
    ax.bar([x["timestamp_s"] for x in activity],[x["movement_distance_px"] for x in activity],width=.08,color="#f6ad55")
    ax.set_xlabel("Video time (s)",color="#c4d2e5"); ax.set_ylabel("Movement between sampled points (px)",color="#c4d2e5"); ax.tick_params(colors="#c4d2e5"); ax.grid(axis="y",color="#34445b",alpha=.5); move=_save(fig,outdir/"movement_activity.png")
    return occ,zone,move

def generate_reports(analysis_id,db=None,report_dir=None):
    from database.db import Database
    db=db or Database(); analysis=db.get_analysis(analysis_id)
    if not analysis or analysis["status"]!="completed": raise ValueError("Reports require a completed analysis.")
    summary=analysis["summary"]; points=db.get_points(analysis_id)
    base=Path(report_dir) if report_dir is not None else config.REPORT_DIR
    outdir=base/str(analysis_id); outdir.mkdir(parents=True,exist_ok=True)
    csv_path=outdir/"tracking_results.csv"
    fields=["frame_index","timestamp_s","track_id","x1","y1","x2","y2","confidence","center_x","center_y"]
    with csv_path.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows([{k:p.get(k) for k in fields} for p in points])
    summary_csv=outdir/"analysis_summary.csv"
    with summary_csv.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f); w.writerow(["metric","value"])
        for k,v in summary.items(): w.writerow([k,json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v])
    charts=_charts(summary,points,outdir)
    pdf=outdir/"analysis_report.pdf"; styles=getSampleStyleSheet(); story=[
        Paragraph("VisionTrack AI — Video Analysis Report",styles["Title"]),
        Paragraph(f"Video: {analysis['original_name']}",styles["Normal"]),
        Paragraph(f"Analysis #{analysis_id} · Profile {analysis['profile']} · Status {analysis['status']}",styles["Normal"]),Spacer(1,12)]
    zones=summary.get("zones",{}); line=summary.get("line_events",{})
    total_entries=sum(z.get("entry_events",0) for z in zones.values()); total_exits=sum(z.get("exit_events",0) for z in zones.values())
    rows=[["Metric","Measured value"],["Unique tracked IDs",str(summary.get("unique_tracked_people",0))],
          ["Person detections (sampled frames)",str(summary.get("total_detections",0))],
          ["Average sampled occupancy",f"{summary.get('average_sampled_occupancy',0):.2f}"],
          ["Peak sampled occupancy",str(summary.get("peak_sampled_occupancy",0))],
          ["Zone entry/exit events",f"{total_entries} / {total_exits}"],
          ["Line crossings A→B / B→A",f"{line.get('A_to_B',0)} / {line.get('B_to_A',0)}"],
          ["Processing duration",f"{summary.get('processing_duration_s',0):.2f} s"],
          ["Processing throughput",f"{summary.get('processing_fps') or 0:.2f} source frames/s"],
          ["Mean detection confidence",(f"{summary['mean_detection_confidence']:.3f}" if summary.get('mean_detection_confidence') is not None else "N/A")],
          ["Movement path length",f"{summary.get('movement_distance_px',0):.1f} px"]]
    table=Table(rows,colWidths=[250,230]); table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#132c44")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.4,colors.HexColor("#8ba0b8")),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f1f5f9")]),("PADDING",(0,0),(-1,-1),7)]))
    story.extend([table,Spacer(1,9),Paragraph("Counts are based on inference-sampled frames; occupancy and movement are not interpolated across skipped frames.",styles["Italic"]),Spacer(1,8),Image(str(charts[0]),width=500,height=212),Spacer(1,8)])
    if zones:
        zrows=[["Zone","Unique IDs","Activity samples","Entries","Exits","Peak occupancy"]]
        zrows.extend([[name,v.get("unique_people_observed",0),v.get("activity_samples",0),v.get("entry_events",0),v.get("exit_events",0),v.get("peak_sampled_occupancy",0)] for name,v in zones.items()])
        ztable=Table(zrows,repeatRows=1); ztable.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#132c44")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.4,colors.grey),("PADDING",(0,0),(-1,-1),5)]))
        story.extend([ztable,Spacer(1,8),Image(str(charts[1]),width=500,height=212),Spacer(1,8)])
    story.append(Image(str(charts[2]),width=500,height=212))
    SimpleDocTemplate(str(pdf),pagesize=letter,title="VisionTrack AI Report").build(story)
    for kind,path in (("csv_tracking",csv_path),("csv_summary",summary_csv),("pdf",pdf),("png_occupancy",charts[0]),("png_zone",charts[1]),("png_movement",charts[2])): db.add_export(analysis_id,kind,path)
    return {"tracking_csv":csv_path,"summary_csv":summary_csv,"pdf":pdf,"occupancy_png":charts[0],"zone_png":charts[1],"movement_png":charts[2]}
