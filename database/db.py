"""SQLite persistence for videos, jobs, sampled detections/tracks, zones and exports."""
from __future__ import annotations
import json, sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from config import DATABASE_PATH

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()

class Database:
    def __init__(self, path: str | Path = DATABASE_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connection(self):
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA journal_mode=WAL")
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def initialize(self):
        with self.connection() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS app_settings(key TEXT PRIMARY KEY, value_json TEXT NOT NULL, updated_at TEXT NOT NULL);            CREATE TABLE IF NOT EXISTS videos(
                id INTEGER PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE, path TEXT NOT NULL,
                original_name TEXT NOT NULL, file_size INTEGER NOT NULL, width INTEGER NOT NULL,
                height INTEGER NOT NULL, fps REAL NOT NULL, frame_count INTEGER NOT NULL,
                duration_s REAL NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS analyses(
                id INTEGER PRIMARY KEY, video_id INTEGER NOT NULL REFERENCES videos(id),
                cache_key TEXT NOT NULL UNIQUE, profile TEXT NOT NULL, config_json TEXT NOT NULL,
                status TEXT NOT NULL, created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
                processed_path TEXT, heatmap_video_path TEXT, summary_json TEXT NOT NULL DEFAULT '{}',
                error TEXT, cancel_requested INTEGER NOT NULL DEFAULT 0);
            CREATE INDEX IF NOT EXISTS ix_analyses_video ON analyses(video_id, created_at DESC);
            CREATE TABLE IF NOT EXISTS tracking_points(
                id INTEGER PRIMARY KEY, analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
                frame_index INTEGER NOT NULL, timestamp_s REAL NOT NULL, track_id INTEGER,
                x1 REAL NOT NULL, y1 REAL NOT NULL, x2 REAL NOT NULL, y2 REAL NOT NULL,
                confidence REAL NOT NULL, center_x REAL NOT NULL, center_y REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS ix_points_analysis_frame ON tracking_points(analysis_id, frame_index);
            CREATE INDEX IF NOT EXISTS ix_points_analysis_track ON tracking_points(analysis_id, track_id, timestamp_s);
            CREATE TABLE IF NOT EXISTS zones(
                id INTEGER PRIMARY KEY, video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
                name TEXT NOT NULL, polygon_json TEXT NOT NULL, created_at TEXT NOT NULL,
                UNIQUE(video_id, name));
            CREATE TABLE IF NOT EXISTS counting_lines(video_id INTEGER PRIMARY KEY REFERENCES videos(id) ON DELETE CASCADE, line_json TEXT NOT NULL, updated_at TEXT NOT NULL);\n            CREATE TABLE IF NOT EXISTS zone_events(
                id INTEGER PRIMARY KEY, analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
                zone_name TEXT NOT NULL, track_id INTEGER NOT NULL, event_type TEXT NOT NULL,
                frame_index INTEGER NOT NULL, timestamp_s REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS exports(
                id INTEGER PRIMARY KEY, analysis_id INTEGER NOT NULL REFERENCES analyses(id),
                kind TEXT NOT NULL, path TEXT NOT NULL, created_at TEXT NOT NULL);
            """)

    def upsert_video(self, metadata, original_name: str) -> int:
        with self.connection() as c:
            c.execute("""INSERT INTO videos(sha256,path,original_name,file_size,width,height,fps,frame_count,duration_s,created_at)
                         VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(sha256) DO UPDATE SET path=excluded.path""",
                      (metadata.sha256, str(metadata.path), original_name, metadata.file_size,
                       metadata.width, metadata.height, metadata.fps, metadata.frame_count,
                       metadata.duration_s, utcnow()))
            return c.execute("SELECT id FROM videos WHERE sha256=?", (metadata.sha256,)).fetchone()[0]

    def get_video(self, video_id: int):
        with self.connection() as c:
            row = c.execute("SELECT * FROM videos WHERE id=?", (video_id,)).fetchone()
            return dict(row) if row else None

    def create_analysis(self, video_id: int, cache_key: str, profile: str, config: dict) -> tuple[int, bool]:
        with self.connection() as c:
            found = c.execute("SELECT id,status FROM analyses WHERE cache_key=?", (cache_key,)).fetchone()
            if found and found["status"] == "completed":
                return found["id"], True
            if found and found["status"] in ("queued", "running"):
                return found["id"], True
            if found:
                c.execute("DELETE FROM tracking_points WHERE analysis_id=?", (found["id"],))
                c.execute("DELETE FROM zone_events WHERE analysis_id=?", (found["id"],))
            c.execute("""INSERT INTO analyses(video_id,cache_key,profile,config_json,status,created_at,started_at)
                         VALUES(?,?,?,?,?,?,?) ON CONFLICT(cache_key) DO UPDATE SET
                         status='queued',created_at=excluded.created_at,started_at=excluded.started_at,
                         finished_at=NULL,error=NULL,cancel_requested=0""",
                      (video_id, cache_key, profile, json.dumps(config), "queued", utcnow(), utcnow()))
            row = c.execute("SELECT id FROM analyses WHERE cache_key=?", (cache_key,)).fetchone()
            return row[0], False

    def set_analysis_status(self, analysis_id: int, status: str, *, error=None,
                            processed_path=None, heatmap_video_path=None, summary=None):
        with self.connection() as c:
            c.execute("""UPDATE analyses SET status=?,error=?,processed_path=COALESCE(?,processed_path),
                      heatmap_video_path=COALESCE(?,heatmap_video_path),
                      summary_json=COALESCE(?,summary_json),finished_at=? WHERE id=?""",
                      (status, error, str(processed_path) if processed_path else None,
                       str(heatmap_video_path) if heatmap_video_path else None,
                       json.dumps(summary) if summary is not None else None,
                       utcnow() if status in ("completed","failed","cancelled") else None, analysis_id))

    def get_analysis(self, analysis_id: int):
        with self.connection() as c:
            row = c.execute("""SELECT a.*,v.original_name,v.path AS video_path,v.sha256,
                       v.width,v.height,v.fps,v.frame_count,v.duration_s
                       FROM analyses a JOIN videos v ON a.video_id=v.id WHERE a.id=?""", (analysis_id,)).fetchone()
            if not row: return None
            d = dict(row); d["config"] = json.loads(d.pop("config_json")); d["summary"] = json.loads(d.pop("summary_json"))
            return d

    def list_analyses(self, limit=100):
        with self.connection() as c:
            rows = c.execute("""SELECT a.id,a.status,a.profile,a.created_at,a.finished_at,a.summary_json,
                         v.original_name,v.duration_s,v.sha256 FROM analyses a JOIN videos v ON a.video_id=v.id
                         ORDER BY a.created_at DESC LIMIT ?""", (limit,)).fetchall()
            result=[]
            for row in rows:
                d=dict(row); d["summary"]=json.loads(d.pop("summary_json")); result.append(d)
            return result

    def add_points(self, analysis_id: int, points: Iterable[dict]):
        rows = [(analysis_id,p["frame_index"],p["timestamp_s"],p.get("track_id"),p["x1"],p["y1"],p["x2"],p["y2"],p["confidence"],p["center_x"],p["center_y"]) for p in points]
        if not rows: return
        with self.connection() as c:
            c.executemany("""INSERT INTO tracking_points(analysis_id,frame_index,timestamp_s,track_id,x1,y1,x2,y2,confidence,center_x,center_y)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?)""", rows)

    def get_points(self, analysis_id: int):
        with self.connection() as c:
            return [dict(r) for r in c.execute("SELECT * FROM tracking_points WHERE analysis_id=? ORDER BY frame_index,id", (analysis_id,))]

    def replace_zones(self, video_id: int, zones: list[dict]):
        with self.connection() as c:
            c.execute("DELETE FROM zones WHERE video_id=?", (video_id,))
            for z in zones:
                c.execute("INSERT INTO zones(video_id,name,polygon_json,created_at) VALUES(?,?,?,?)",
                          (video_id,z["name"],json.dumps(z["polygon"]),utcnow()))

    def get_zones(self, video_id: int):
        with self.connection() as c:
            return [{"name":r["name"],"polygon":json.loads(r["polygon_json"])} for r in
                    c.execute("SELECT * FROM zones WHERE video_id=? ORDER BY id", (video_id,))]

    def replace_zone_events(self, analysis_id: int, events: list[dict]):
        with self.connection() as c:
            c.execute("DELETE FROM zone_events WHERE analysis_id=?", (analysis_id,))
            c.executemany("INSERT INTO zone_events(analysis_id,zone_name,track_id,event_type,frame_index,timestamp_s) VALUES(?,?,?,?,?,?)",
                          [(analysis_id,e["zone_name"],e["track_id"],e["event_type"],e["frame_index"],e["timestamp_s"]) for e in events])

    def add_export(self, analysis_id: int, kind: str, path: str | Path):
        with self.connection() as c:
            c.execute("INSERT INTO exports(analysis_id,kind,path,created_at) VALUES(?,?,?,?)",
                      (analysis_id,kind,str(path),utcnow()))

    def set_counting_line(self, video_id: int, line):
        with self.connection() as c:
            if line is None:
                c.execute("DELETE FROM counting_lines WHERE video_id=?", (video_id,))
            else:
                c.execute("INSERT INTO counting_lines(video_id,line_json,updated_at) VALUES(?,?,?) ON CONFLICT(video_id) DO UPDATE SET line_json=excluded.line_json,updated_at=excluded.updated_at",
                          (video_id,json.dumps(line),utcnow()))

    def get_counting_line(self, video_id: int):
        with self.connection() as c:
            row=c.execute("SELECT line_json FROM counting_lines WHERE video_id=?",(video_id,)).fetchone()
            return json.loads(row[0]) if row else None





    def get_setting(self, key: str, default=None):
        with self.connection() as c:
            row=c.execute("SELECT value_json FROM app_settings WHERE key=?",(key,)).fetchone()
            return json.loads(row[0]) if row else default

    def set_setting(self, key: str, value):
        with self.connection() as c:
            c.execute("INSERT INTO app_settings(key,value_json,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at",
                      (key,json.dumps(value),utcnow()))

    def request_cancel(self, analysis_id: int):
        with self.connection() as c:
            c.execute("UPDATE analyses SET cancel_requested=1 WHERE id=? AND status IN ('queued','running')",(analysis_id,))

    def get_zone_events(self, analysis_id: int):
        with self.connection() as c:
            return [dict(r) for r in c.execute("SELECT zone_name,track_id,event_type,frame_index,timestamp_s FROM zone_events WHERE analysis_id=? ORDER BY timestamp_s,id",(analysis_id,))]
