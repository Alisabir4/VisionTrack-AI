import tempfile,unittest
from pathlib import Path
import cv2
from database.db import Database
from core.video_manager import inspect_video
from tests.helpers import write_video

class DatabaseTests(unittest.TestCase):
    def test_cache_settings_points_and_events_persist(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); frame=cv2.imread(str(Path(__file__).parents[1]/"samples"/"bus.jpg")); frame=cv2.resize(frame,(320,426))
            source=write_video(root/"clip.mp4",frame,8,4); meta=inspect_video(source)
            db=Database(root/"db.sqlite3"); vid=db.upsert_video(meta,"clip.mp4")
            aid,cached=db.create_analysis(vid,"key","Fast",{"confidence":.25}); self.assertFalse(cached)
            db.add_points(aid,[{"frame_index":0,"timestamp_s":0,"track_id":3,"x1":1,"y1":2,"x2":10,"y2":20,"confidence":.8,"center_x":5,"center_y":11}])
            db.set_analysis_status(aid,"completed",summary={"unique_tracked_people":1})
            aid2,cached=db.create_analysis(vid,"key","Fast",{"confidence":.25})
            self.assertEqual(aid,aid2); self.assertTrue(cached)
            self.assertEqual(db.get_points(aid)[0]["track_id"],3)
            db.set_setting("processing",{"threads":2}); self.assertEqual(db.get_setting("processing")["threads"],2)
            db.replace_zones(vid,[{"name":"Lobby","polygon":[[0,0],[1,0],[1,1]]}])
            self.assertEqual(db.get_zones(vid)[0]["name"],"Lobby")
            db.set_counting_line(vid,[[.5,0],[.5,1]]); self.assertEqual(db.get_counting_line(vid),[[.5,0],[.5,1]])

if __name__=="__main__":unittest.main()
