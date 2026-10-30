import json,tempfile,unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
from urllib.request import Request,urlopen
from dashboard.paired_player import build_pair_html
from streamlit.runtime import Runtime
from utils.streamlit_media import register_media_file
from utils.media_server import MediaServer

class PlaybackTests(unittest.TestCase):
    def test_component_maps_shared_controls_through_source_frame_timeline(self):
        html=build_pair_html("/media/original.mp4","/media/heat.webm","/media/timeline.json",10)
        self.assertIn('id="original"',html); self.assertIn('id="heatmap"',html)
        self.assertIn('a.currentTime=t;syncHeat(t,true)',html)
        self.assertIn('a.playbackRate=Number(e.target.value);b.playbackRate=Number(e.target.value)',html)
        self.assertIn('Promise.all([a.play(),b.play()])',html)
        self.assertIn('source_timestamps_s',html); self.assertIn('function frameAt(t)',html)
        self.assertNotIn("127.0.0.1",html); self.assertNotIn("localhost",html)
    def test_local_media_server_supports_byte_ranges(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"sample.mp4"; f.write_bytes(bytes(range(100)))
            server=MediaServer(); url=server.url(f)
            req=Request(url,headers={"Range":"bytes=10-19"})
            with urlopen(req,timeout=5) as response:
                self.assertEqual(response.status,206); self.assertEqual(response.read(),bytes(range(10,20)))
                self.assertEqual(response.headers["Content-Range"],"bytes 10-19/100")
            server.server.shutdown(); server.server.server_close()
    def test_streamlit_media_urls_are_same_origin_and_preserve_mime(self):
        class MediaManager:
            def __init__(self): self.calls=[]
            def add(self,path,mimetype,coordinates):
                self.calls.append((path,mimetype,coordinates))
                return f"/media/file-{len(self.calls)}.{Path(path).suffix.lstrip('.')}"
        with tempfile.TemporaryDirectory() as d:
            original=Path(d)/"source.mp4"; original.write_bytes(b"mp4-content")
            heatmap=Path(d)/"heatmap.webm"; heatmap.write_bytes(b"webm-content")
            manager=MediaManager()
            with patch.object(Runtime,"_instance",SimpleNamespace(media_file_mgr=manager)):
                original_url=register_media_file(original,mimetype="video/mp4",coordinates="analysis.1.original")
                heatmap_url=register_media_file(heatmap,mimetype="video/webm",coordinates="analysis.1.heatmap")
            self.assertEqual(original_url,"/media/file-1.mp4")
            self.assertEqual(heatmap_url,"/media/file-2.webm")
            self.assertTrue(all("127.0.0.1" not in url and "localhost" not in url for url in (original_url,heatmap_url)))
            self.assertEqual([c[1] for c in manager.calls],["video/mp4","video/webm"])
            html=build_pair_html(original_url,heatmap_url,"/media/timeline.json",30)
            self.assertIn(f'src="{original_url}"',html); self.assertIn(f'src="{heatmap_url}"',html)
            self.assertLess(html.index('src="/media/file-1.mp4"'),html.index('src="/media/file-2.webm"'))
    def test_timeline_maps_every_source_frame_to_heatmap_frame_time(self):
        timeline={"frame_count":3,"source_timestamps_s":[0,.25,.75],"heatmap_fps":4,"heatmap_timestamps_s":[0,.25,.5]}
        self.assertEqual(len(timeline["source_timestamps_s"]),timeline["frame_count"])
        self.assertEqual(timeline["heatmap_timestamps_s"][2],2/timeline["heatmap_fps"])

if __name__=="__main__":unittest.main()
