"""Zone transitions and virtual-line crossing based on tracked IDs, with debounce."""
import cv2
import numpy as np
from collections import defaultdict

def polygon_pixels(polygon, width, height):
    return np.asarray([[round(float(x)*width),round(float(y)*height)] for x,y in polygon],dtype=np.int32)

def signed_polygon_distance(point, polygon_px):
    return cv2.pointPolygonTest(polygon_px, (float(point[0]),float(point[1])), True)

def analyze_zones(points, zones, width, height, *, hysteresis_px=10.0, stable_samples=2, min_transition_s=0.12):
    """Return sampled occupancy and debounced events using ByteTrack IDs."""
    grouped=defaultdict(list); all_times=sorted({float(p["timestamp_s"]) for p in points})
    for p in points:
        if p.get("track_id") is not None: grouped[int(p["track_id"])].append(p)
    events=[]; occupancy=defaultdict(set); zone_counts={}
    for zone in zones:
        name=zone["name"]; poly=polygon_pixels(zone["polygon"],width,height)
        state_by_id={}; candidate_by_id={}; stable_count=defaultdict(int); candidate_since={}; last_event={}
        unique_visitors=set(); activity_samples=0; movement_px=0.0; last_inside={}
        for track_id, rows in grouped.items():
            rows=sorted(rows,key=lambda r:(r["timestamp_s"],r["frame_index"]))
            for p in rows:
                dist=signed_polygon_distance((p["center_x"],p["center_y"]),poly)
                if track_id not in state_by_id:
                    state_by_id[track_id]=dist>=0
                    if state_by_id[track_id]: unique_visitors.add(track_id)
                current=state_by_id[track_id]; target=current
                if current and dist < -hysteresis_px: target=False
                elif not current and dist > hysteresis_px: target=True
                if target != current:
                    if candidate_by_id.get(track_id) != target:
                        candidate_by_id[track_id]=target; stable_count[track_id]=1; candidate_since[track_id]=p["timestamp_s"]
                    else: stable_count[track_id]+=1
                    elapsed=p["timestamp_s"]-candidate_since[track_id]
                    if stable_count[track_id]>=stable_samples and elapsed>=min_transition_s:
                        if p["timestamp_s"]-last_event.get(track_id,-1e9)>=min_transition_s:
                            event_type="entry" if target else "exit"
                            events.append({"zone_name":name,"track_id":track_id,"event_type":event_type,
                                           "frame_index":p["frame_index"],"timestamp_s":p["timestamp_s"]})
                            if target: unique_visitors.add(track_id)
                            state_by_id[track_id]=target; last_event[track_id]=p["timestamp_s"]
                        candidate_by_id.pop(track_id,None); stable_count[track_id]=0; candidate_since.pop(track_id,None)
                else:
                    candidate_by_id.pop(track_id,None); stable_count[track_id]=0; candidate_since.pop(track_id,None)
                if state_by_id[track_id]:
                    occupancy[(name,float(p["timestamp_s"]))].add(track_id); activity_samples+=1
                    previous=last_inside.get(track_id)
                    if previous is not None:
                        movement_px+=float(np.hypot(p["center_x"]-previous[0],p["center_y"]-previous[1]))
                    last_inside[track_id]=(p["center_x"],p["center_y"])
                else: last_inside.pop(track_id,None)
        for timestamp in all_times: occupancy.setdefault((name,timestamp),set())
        zone_events=[e for e in events if e["zone_name"]==name]
        zone_counts[name]={"unique_people_observed":len(unique_visitors),"activity_samples":activity_samples,
                           "movement_distance_px":round(movement_px,2),
                           "entry_events":sum(e["event_type"]=="entry" for e in zone_events),
                           "exit_events":sum(e["event_type"]=="exit" for e in zone_events),
                           "occupancy_samples":len(all_times),
                           "average_sampled_occupancy":(sum(len(occupancy[(name,t)]) for t in all_times)/len(all_times)) if all_times else 0.0,
                           "peak_sampled_occupancy":max((len(occupancy[(name,t)]) for t in all_times),default=0)}
    occ_rows=[{"zone_name":z,"timestamp_s":t,"occupancy":len(ids)} for (z,t),ids in sorted(occupancy.items(),key=lambda x:(x[0][0],x[0][1]))]
    return {"events":events,"zones":zone_counts,"occupancy":occ_rows}

def crossing_events(points, line, width, height, cooldown_s=1.0):
    """Count track-center crossings of a finite normalized line with a per-ID cooldown."""
    a=np.asarray([line[0][0]*width,line[0][1]*height],float)
    b=np.asarray([line[1][0]*width,line[1][1]*height],float)
    v=b-a
    def cross(u,w): return float(u[0]*w[1]-u[1]*w[0])
    grouped=defaultdict(list)
    for p in points:
        if p.get("track_id") is not None: grouped[int(p["track_id"])].append(p)
    events=[]
    for tid,rows in grouped.items():
        rows=sorted(rows,key=lambda p:(p["timestamp_s"],p["frame_index"])); last=-1e9
        for prev,curr in zip(rows,rows[1:]):
            p=np.asarray([prev["center_x"],prev["center_y"]],float)
            q=np.asarray([curr["center_x"],curr["center_y"]],float)
            r=q-p; denom=cross(r,v)
            if abs(denom)<1e-9: continue
            delta=a-p
            t=cross(delta,v)/denom; u=cross(delta,r)/denom
            if 0<=t<=1 and 0<=u<=1 and curr["timestamp_s"]-last>=cooldown_s:
                s1=cross(v,p-a); s2=cross(v,q-a)
                events.append({"track_id":tid,"event_type":"A_to_B" if s1<s2 else "B_to_A",
                               "frame_index":curr["frame_index"],"timestamp_s":curr["timestamp_s"]})
                last=curr["timestamp_s"]
    return events
