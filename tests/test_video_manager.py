import tempfile,unittest
from pathlib import Path
import cv2
from core.video_manager import inspect_video,save_upload,VideoValidationError
from core.frame_sampler import sequential_frames
from tests.helpers import write_video

class VideoManagerTests(unittest.TestCase):
    def test_metadata_and_chunked_upload(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); frame=cv2.imread(str(Path(__file__).parents[1]/"samples"/"bus.jpg")); frame=cv2.resize(frame,(320,426))
            source=write_video(root/"clip.mp4",frame,12,6)
            meta=inspect_video(source)
            self.assertEqual((meta.width,meta.height,meta.frame_count),(320,426,12))
            self.assertAlmostEqual(meta.duration_s,2.0,delta=.1)
            with source.open("rb") as stream: uploaded,sha,size=save_upload("copy.MP4",stream,root/"uploads")
            self.assertEqual(sha,meta.sha256); self.assertEqual(size,source.stat().st_size)
            self.assertTrue(uploaded.exists())
    def test_rejects_unsupported_and_corrupt(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(VideoValidationError): save_upload("x.mkv",b"abc",Path(d))
            bad=Path(d)/"bad.mp4"; bad.write_bytes(b"not a video")
            with self.assertRaises(VideoValidationError): inspect_video(bad)
    def test_sampling_preserves_original_indices_and_timestamps(self):
        class Capture:
            def __init__(self): self.i=0
            def read(self):
                if self.i==10:return False,None
                self.i+=1; return True,self.i
        frames=list(sequential_frames(Capture(),10,3))
        self.assertEqual([x.frame_index for x in frames if x.sampled],[0,3,6,9])
        self.assertEqual(frames[9].timestamp_s,.9)
        self.assertEqual(len(frames),10)
    def test_prefers_decoder_timestamps_when_present(self):
        class PtsCapture:
            def __init__(self): self.i=0
            def read(self):
                if self.i==3:return False,None
                self.i+=1; return True,self.i
            def get(self,prop): return [0,100,350][self.i-1]
        frames=list(sequential_frames(PtsCapture(),10,1))
        self.assertEqual([f.timestamp_s for f in frames],[0,.1,.35])

if __name__=="__main__":unittest.main()

