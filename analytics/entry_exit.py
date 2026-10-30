"""Virtual line counts derived from ByteTrack IDs."""
from .zone_analytics import crossing_events

def count_line_crossings(points,line,width,height):
    events=crossing_events(points,line,width,height)
    return {"events":events,"A_to_B":sum(e["event_type"]=="A_to_B" for e in events),
            "B_to_A":sum(e["event_type"]=="B_to_A" for e in events)}
