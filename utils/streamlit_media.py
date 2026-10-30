"""Register local media with Streamlit so browsers fetch it from the app origin."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from streamlit.runtime import Runtime


def register_media_file(path: str | Path, *, mimetype: str, coordinates: str) -> str:
    """Return a same-origin Streamlit media URL for an existing local file.

    Streamlit's own media endpoint is reachable through Community Cloud's
    reverse proxy and supports browser byte-range requests. Unlike a separate
    loopback server, the resulting URL never points at the viewer's machine.
    """
    media_path = Path(path).resolve()
    if not media_path.is_file():
        raise FileNotFoundError(f"Playback media file is missing: {media_path.name}")
    url = Runtime.instance().media_file_mgr.add(
        str(media_path), mimetype, coordinates
    )
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/media/"):
        raise RuntimeError("Streamlit returned a non-local media endpoint URL.")
    return url
