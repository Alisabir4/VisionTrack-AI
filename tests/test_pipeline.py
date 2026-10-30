import tempfile,threading,unittest,json
from pathlib import Path
import cv2,numpy as np
from database.db import Database
from core.video_manager import inspect_video
from core.processor import VideoProcessor
from utils.report_generator import generate_reports
from tests.helpers import write_video

class PipelineTests(unittest.TestCase):
    def _run(self,root,frame,name,count=20):
        source=write_video(root/name,frame,count,5); meta=inspect_video(source); db=Database(root/(name+".sqlite3"))
        vid=db.upsert_video(meta,name); cfg={"confidence":.25,"image_size":480,"processing_width":480,
            "frame_interval":5,"heatmap_opacity":.65,"save_heatmap_frames":True,"threads":2}
        aid,cached=db.create_analysis(vid,name,"Fast",cfg); self.assertFalse(cached)
        progress=[]; result=VideoProcessor(db,root/"processed",root/"heatmaps").process(aid,cancel_event=threading.Event(),progress=lambda x,m:progress.append(x))
        return db,aid,result,meta,progress
    def test_end_to_end_person_tracking_heatmaps_reports_and_sync_timeline(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); frame=cv2.imread(str(Path(__file__).parents[1]/"samples"/"bus.jpg")); frame=cv2.resize(frame,(640,854))
            db,aid,result,source,progress=self._run(root,frame,"people.mp4",20)
            self.assertGreater(result["total_detections"],0); self.assertGreaterEqual(result["unique_tracked_people"],2)
            self.assertEqual(result["actual_frames_read"],20); self.assertEqual(result["sampled_frames"],4)
            points=db.get_points(aid)
            counts={}
            for row in points:
                self.assertGreater(row["x2"],row["x1"]); self.assertGreaterEqual(row["confidence"],.25)
                self.assertLessEqual(row["x2"],640.5); self.assertLessEqual(row["y2"],854.5)
                if row["track_id"] is not None: counts[row["track_id"]]=counts.get(row["track_id"],0)+1
            self.assertGreater(max(counts.values(),default=0),1,"ByteTrack IDs persist across repeated detections")
            self.assertTrue((root/"processed"/str(aid)/"tracking_results.csv").exists())
            self.assertTrue((root/"processed"/str(aid)/"trajectories.csv").exists())
            for name in ("movement_heatmap.png","density_heatmap.png","zone_activity_heatmap.png","movement_heatmap.webm"):
                self.assertTrue((root/"heatmaps"/str(aid)/name).exists(),name)
            source_meta=inspect_video(db.get_analysis(aid)["video_path"])
            heat_meta=inspect_video(db.get_analysis(aid)["heatmap_video_path"])
            self.assertEqual(source_meta.frame_count,heat_meta.frame_count)
            self.assertAlmostEqual(source_meta.fps,heat_meta.fps,places=2)
            self.assertAlmostEqual(source_meta.duration_s,heat_meta.duration_s,delta=.2)
            timeline=json.loads((root/"processed"/str(aid)/"frame_timeline.json").read_text())
            self.assertEqual(timeline["frame_count"],20); self.assertEqual(len(timeline["source_timestamps_s"]),20)
            self.assertAlmostEqual(timeline["heatmap_timestamps_s"][19],19/source_meta.fps,places=4)
            reports=generate_reports(aid,db,root/"reports")
            self.assertTrue(reports["pdf"].exists()); self.assertGreater(reports["pdf"].stat().st_size,1000)
            self.assertTrue(reports["tracking_csv"].exists()); self.assertTrue(reports["occupancy_png"].exists())
            self.assertEqual(db.get_analysis(aid)["status"],"completed")
            self.assertGreater(max(progress),0.9)
    def test_empty_scene_produces_real_zero_counts(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); frame=np.zeros((320,480,3),np.uint8)
            db,aid,result,source,progress=self._run(root,frame,"empty.mp4",10)
            self.assertEqual(result["total_detections"],0)
            self.assertEqual(result["unique_tracked_people"],0)
            self.assertEqual(result["peak_sampled_occupancy"],0)

if __name__=="__main__":unittest.main()


