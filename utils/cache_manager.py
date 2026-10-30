"""Stable cache identities and safe temporary-file cleanup."""
import hashlib, json
from pathlib import Path

def analysis_cache_key(video_sha256: str, settings: dict) -> str:
    payload=json.dumps(settings,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
    return hashlib.sha256(video_sha256.encode()+b"\0"+payload).hexdigest()

def remove_owned_temp(path: str | Path, *, root: str | Path):
    """Remove one explicitly named temp file only if it resolves under root."""
    root=Path(root).resolve(); target=Path(path).resolve()
    if root not in target.parents: raise ValueError("Refusing cleanup outside the selected storage root")
    if target.is_file() and target.name.endswith(".tmp"): target.unlink()
