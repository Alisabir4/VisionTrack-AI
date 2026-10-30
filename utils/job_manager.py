"""Single-worker background processing with cooperative cancellation and progress."""
from __future__ import annotations
import threading, time
from dataclasses import dataclass, field
from core.processor import VideoProcessor, ProcessingCancelled
from database.db import Database

@dataclass
class JobState:
    analysis_id: int
    status: str="queued"
    progress: float=0.0
    message: str="Queued"
    cancel_event: threading.Event=field(default_factory=threading.Event)
    updated_at: float=field(default_factory=time.time)

class JobManager:
    def __init__(self,db=None):
        self.db=db or Database(); self.processor=VideoProcessor(self.db)
        self._jobs={}; self._lock=threading.RLock()
        with self.db.connection() as c:
            c.execute("UPDATE analyses SET status='failed',error='Interrupted by application restart',finished_at=? WHERE status IN ('queued','running')",(time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),))

    def start(self,analysis_id:int):
        analysis=self.db.get_analysis(analysis_id)
        if not analysis: raise ValueError("Analysis record not found")
        if analysis["status"]=="completed": return
        with self._lock:
            if analysis_id in self._jobs and self._jobs[analysis_id].status in ("queued","running"): return
            state=JobState(analysis_id); self._jobs[analysis_id]=state
            thread=threading.Thread(target=self._run,args=(state,),name=f"visiontrack-{analysis_id}",daemon=True)
            thread.start()

    def _run(self,state):
        state.status="running"; state.message="Starting video pipeline"; state.updated_at=time.time()
        self.db.set_analysis_status(state.analysis_id,"running")
        def progress(value,message):
            state.progress=float(value); state.message=str(message); state.updated_at=time.time()
        try:
            self.processor.process(state.analysis_id,cancel_event=state.cancel_event,progress=progress)
            state.status="completed"; state.progress=1.0; state.message="Processing complete"
        except ProcessingCancelled:
            state.status="cancelled"; state.message="Processing cancelled by user"
            self.db.set_analysis_status(state.analysis_id,"cancelled",error="Cancelled by user")
        except Exception as e:
            state.status="failed"; state.message=f"Processing failed: {e}"
            self.db.set_analysis_status(state.analysis_id,"failed",error=str(e))
        finally: state.updated_at=time.time()

    def cancel(self,analysis_id:int):
        with self._lock:
            state=self._jobs.get(analysis_id)
            if not state or state.status not in ("queued","running"): return False
            state.cancel_event.set(); state.message="Cancellation requested"; state.updated_at=time.time()
            return True

    def status(self,analysis_id:int):
        with self._lock:
            state=self._jobs.get(analysis_id)
            if state:
                return {"status":state.status,"progress":state.progress,"message":state.message,
                        "age_s":max(0,time.time()-state.updated_at)}
        row=self.db.get_analysis(analysis_id)
        return {"status":row["status"] if row else "missing","progress":1.0 if row and row["status"]=="completed" else 0.0,
                "message":row.get("error") or row["status"] if row else "Analysis not found","age_s":0}
