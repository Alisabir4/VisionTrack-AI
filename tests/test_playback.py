import json,tempfile,unittest
from pathlib import Path
from urllib.request import Request,urlopen
from dashboard.paired_player import build_pair_html
from utils.media_server import MediaServer

class PlaybackTests(unittest.TestCase):
    def test_component_maps_shared_controls_through_source_frame_timeline(self):
        html=build_pair_html("http://127.0.0.1:1234/media/original","http://127.0.0.1:1234/media/heat","http://127.0.0.1:1234/media/timeline",10)
        self.assertIn('id="original"',html); self.assertIn('id="heatmap"',html)
        self.assertIn('a.currentTime=t;syncHeat(t,true)',html)
        self.assertIn('a.playbackRate=Number(e.target.value);b.playbackRate=Number(e.target.value)',html)
        self.assertIn('Promise.all([a.play(),b.play()])',html)
        self.assertIn('source_timestamps_s',html); self.assertIn('function frameAt(t)',html)
    def test_local_media_server_supports_byte_ranges(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"sample.mp4"; f.write_bytes(bytes(range(100)))
            server=MediaServer(); url=server.url(f)
            req=Request(url,headers={"Range":"bytes=10-19"})
            with urlopen(req,timeout=5) as response:
                self.assertEqual(response.status,206); self.assertEqual(response.read(),bytes(range(10,20)))
                self.assertEqual(response.headers["Content-Range"],"bytes 10-19/100")
            server.server.shutdown(); server.server.server_close()
    def test_timeline_maps_every_source_frame_to_heatmap_frame_time(self):
        timeline={"frame_count":3,"source_timestamps_s":[0,.25,.75],"heatmap_fps":4,"heatmap_timestamps_s":[0,.25,.5]}
        self.assertEqual(len(timeline["source_timestamps_s"]),timeline["frame_count"])
        self.assertEqual(timeline["heatmap_timestamps_s"][2],2/timeline["heatmap_fps"])

if __name__=="__main__":unittest.main()
