"""Application-level access to persisted analytics for dashboards and exports."""
from database.db import Database
from .statistics import calculate_statistics,occupancy_series

def load_analysis(analysis_id:int,db=None):
    db=db or Database(); row=db.get_analysis(analysis_id)
    if not row: raise KeyError(f"Analysis {analysis_id} not found")
    points=db.get_points(analysis_id)
    summary=row["summary"]
    return {"analysis":row,"summary":summary,"points":points,
            "occupancy_series":occupancy_series(points),"zone_events":db.get_zone_events(analysis_id)}
