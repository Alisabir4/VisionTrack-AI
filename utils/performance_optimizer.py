"""CPU and storage helpers used by analysis settings and cleanup."""
from pathlib import Path
import os, psutil, torch

def configure_cpu(threads=None):
    count=max(1,min(int(threads or os.cpu_count() or 1),4))
    torch.set_num_threads(count)
    return count

def storage_usage(paths):
    totals={}
    for name,path in paths.items():
        p=Path(path); total=0
        if p.exists():
            for f in p.rglob("*"):
                if f.is_file():
                    try: total+=f.stat().st_size
                    except OSError: pass
        totals[name]={"bytes":total,"mb":round(total/1024**2,2)}
    return totals

def memory_snapshot():
    proc=psutil.Process(); vm=psutil.virtual_memory()
    return {"process_rss_mb":round(proc.memory_info().rss/1024**2,2),
            "system_used_mb":round(vm.used/1024**2,2),"system_total_mb":round(vm.total/1024**2,2)}

def clean_owned_temporary_files(roots):
    """Delete only recognizable temporary files inside explicitly listed project storage roots."""
    removed=[]
    suffixes=(".partial",".tmp",".tmp.mp4")
    for root in map(lambda x:Path(x).resolve(),roots):
        if not root.exists(): continue
        for f in root.rglob("*"):
            if f.is_file() and (f.name.startswith(".upload-") or f.name.endswith(suffixes)):
                if root not in f.resolve().parents: continue
                f.unlink(missing_ok=True); removed.append(str(f))
    return removed
