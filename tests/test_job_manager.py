import tempfile,time,unittest
from pathlib import Path
import cv2
from database.db import Database
from core.video_manager import inspect_video
from core.processor import ProcessingCancelled
from utils.job_manager import JobManager
from tests.helpers import write_video

class JobManagerTests(unittest.TestCase):
    def test_background_job_cancels_cooperatively(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); frame=cv2.imread(str(Path(__file__).parents[1]/"samples"/"bus.jpg")); frame=cv2.resize(frame,(320,426))
            source=write_video(root/"clip.mp4",frame,6,3); db=Database(root/"db.sqlite3"); vid=db.upsert_video(inspect_video(source),"clip.mp4")
            aid,_=db.create_analysis(vid,"cancel-key","Fast",{})
            manager=JobManager(db)
            def wait_for_cancel(analysis_id,cancel_event,progress):
                while not cancel_event.wait(.02): progress(.25,"running test worker")
                raise ProcessingCancelled()
            manager.processor.process=wait_for_cancel
            manager.start(aid)
            deadline=time.time()+3
            while manager.status(aid)["status"]!="running" and time.time()<deadline: time.sleep(.01)
            self.assertTrue(manager.cancel(aid))
            deadline=time.time()+3
            while manager.status(aid)["status"] not in ("cancelled","failed") and time.time()<deadline: time.sleep(.01)
            self.assertEqual(manager.status(aid)["status"],"cancelled")
            self.assertEqual(db.get_analysis(aid)["status"],"cancelled")

if __name__=="__main__":unittest.main()
