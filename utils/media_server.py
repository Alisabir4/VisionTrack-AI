"""Local range-capable file server for browser playback without loading videos into Python RAM."""
from __future__ import annotations
import mimetypes, secrets, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

class MediaServer:
    def __init__(self):
        self.files={}; self.by_path={}; self.lock=threading.RLock(); self.server=None; self.port=None
    def start(self):
        if self.server: return
        owner=self
        class Handler(BaseHTTPRequestHandler):
            protocol_version="HTTP/1.1"
            def do_HEAD(self): self._serve(head=True)
            def do_GET(self): self._serve(head=False)
            def log_message(self,*args): pass
            def _serve(self,head=False):
                token=urlparse(self.path).path.removeprefix("/media/")
                with owner.lock: path=owner.files.get(token)
                if not path or not path.is_file(): self.send_error(404); return
                size=path.stat().st_size; start=0; end=size-1; status=200
                header=self.headers.get("Range")
                if header and header.startswith("bytes="):
                    try:
                        start_s,end_s=header[6:].split("-",1)
                        if start_s: start=int(start_s)
                        if end_s: end=min(int(end_s),size-1)
                        if start<0 or start>=size or end<start: raise ValueError
                        status=206
                    except ValueError:
                        self.send_response(416); self.send_header("Content-Range",f"bytes */{size}"); self.end_headers(); return
                length=end-start+1
                self.send_response(status)
                self.send_header("Content-Type",mimetypes.guess_type(path.name)[0] or "application/octet-stream")
                self.send_header("Accept-Ranges","bytes"); self.send_header("Content-Length",str(length))
                if status==206: self.send_header("Content-Range",f"bytes {start}-{end}/{size}")
                origin=self.headers.get("Origin","")
                if origin.startswith("http://localhost:") or origin.startswith("http://127.0.0.1:"):
                    self.send_header("Access-Control-Allow-Origin",origin); self.send_header("Vary","Origin")
                self.send_header("Cache-Control","no-store"); self.end_headers()
                if head: return
                with path.open("rb") as f:
                    f.seek(start); remaining=length
                    while remaining:
                        chunk=f.read(min(1024*512,remaining))
                        if not chunk: break
                        try: self.wfile.write(chunk)
                        except (BrokenPipeError,ConnectionResetError): break
                        remaining-=len(chunk)
        self.server=ThreadingHTTPServer(("127.0.0.1",0),Handler); self.server.daemon_threads=True
        self.port=self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever,name="visiontrack-media",daemon=True).start()
    def url(self,path):
        path=Path(path).resolve()
        if not path.is_file(): raise FileNotFoundError(path)
        self.start()
        with self.lock:
            token=self.by_path.get(str(path))
            if token is None:
                token=secrets.token_urlsafe(18); self.files[token]=path; self.by_path[str(path)]=token
        return f"http://127.0.0.1:{self.port}/media/{token}"

_media_server=None
def get_media_server():
    global _media_server
    if _media_server is None: _media_server=MediaServer()
    return _media_server

