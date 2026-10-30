import unittest
import numpy as np
from analytics.movement_heatmap import MovementHeatmap
from analytics.density_heatmap import colorize_density
from analytics.zone_analytics import analyze_zones
from analytics.entry_exit import count_line_crossings
from analytics.zone_manager import ZoneManager

class AnalyticsTests(unittest.TestCase):
    def test_movement_and_density_heatmaps_have_expected_dimensions(self):
        hm=MovementHeatmap(100,80); hm.update([{"track_id":1,"center_x":10,"center_y":20}]); hm.update([{"track_id":1,"center_x":70,"center_y":40}])
        img=hm.render(); self.assertEqual(img.shape,(80,100,3)); self.assertGreater(int(img.max()),0)
        density=colorize_density([{"track_id":1,"center_x":20,"center_y":30}],100,80)
        self.assertEqual(density.shape,(80,100,3)); self.assertGreater(int(density.max()),0)
    def test_zone_entries_exits_debounce_and_line_crossing(self):
        points=[]
        for i,(t,x) in enumerate([(0,10),(.2,40),(.4,50),(.6,20),(.8,10),(1.0,10)]):
            points.append({"track_id":7,"frame_index":i*2,"timestamp_s":t,"center_x":x,"center_y":50})
        zone={"name":"test","polygon":[[.25,.25],[.75,.25],[.75,.75],[.25,.75]]}
        result=analyze_zones(points,[zone],100,100)
        self.assertEqual([e["event_type"] for e in result["events"]],["entry","exit"])
        self.assertEqual(result["zones"]["test"]["unique_people_observed"],1)
        line=count_line_crossings([{"track_id":1,"timestamp_s":0,"frame_index":0,"center_x":40,"center_y":50},
                                   {"track_id":1,"timestamp_s":2,"frame_index":2,"center_x":60,"center_y":50}],[[.5,.1],[.5,.9]],100,100)
        self.assertEqual(len(line["events"]),1)
    def test_zone_validation(self):
        self.assertEqual(ZoneManager.validate_zones([{"name":"A","polygon":[[0,0],[1,0],[1,1]]}])[0]["name"],"A")
        with self.assertRaises(ValueError): ZoneManager.validate_zones([{"name":"A","polygon":[[2,0],[1,0],[1,1]]}])

if __name__=="__main__":unittest.main()
