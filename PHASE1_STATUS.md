# Phase 1 status

## Environment and network diagnosis

- Windows 10 (10.0.19045), Python 3.11.9, 4 logical CPUs, 15.88 GiB RAM reported by psutil.
- Windows blocked the WMI CPU inventory query, so only the OS processor identifier (`Intel64 Family 6 Model 78 Stepping 3`) was available.
- Initial network failures were caused by injected environment settings: `HTTP_PROXY`, `HTTPS_PROXY`, and `ALL_PROXY` all pointed to `http://127.0.0.1:9`, and `PIP_NO_INDEX=1` disabled package indexes. Connections failed at the proxy with `ConnectionRefusedError 10061`, before TLS certificate validation. The “SSL” error was therefore a misleading symptom, not a bad certificate.
- After requesting network permission, the blocking environment settings were removed by the execution environment. Verified HTTPS requests then returned HTTP 200 from PyPI and `download.pytorch.org`. No TLS verification was disabled.
- Pip initially received a stale cached `304` response while resolving packages. `--no-cache-dir` returned a fresh index response and fixed resolution. PyPI package-file transfers were slow (roughly 9–12 KB/s in observed attempts); longer read timeouts were needed.
- System date/time was 2026-10-30, Pakistan Standard Time (UTC+05:00). Python OpenSSL is 3.0.13. SSL default paths were present; no `SSL_CERT_FILE` override was set. Certifi was upgraded in the benchmark environment from 2026.07.22 to 2026.10.23. Pip was upgraded from 24.0 to 26.2.2.

## Installed and verified inference stack

A project virtual environment at `.venv-cpu` uses the system Python packages for the already-installed CPU PyTorch/OpenCV/NumPy baseline and contains the additional packages installed for this run. The system Python had torch 2.14.0+cpu, OpenCV 5.0.0, NumPy 2.4.6, and psutil 7.2.2. The environment has torchvision 0.29.2+cpu and Ultralytics 8.4.193. The official PyTorch CPU index selected a torchvision build matching torch 2.14.0; `torch.cuda.is_available()` is false.

Pip installation of the full requirements initially spent time resolving Ultralytics' optional `polars` dependency. The required CPU inference stack was installed and verified; the standard full requirements install remains available via README instructions on a normally connected machine.

Downloaded assets:

- `models/yolov8n.pt` (6,549,796 bytes), from the Ultralytics GitHub assets release.
- `samples/bus.jpg` (137,419 bytes), from Ultralytics.

The benchmark redirects Ultralytics settings into `work/ultralytics/` because the user profile settings directory is not writable in this environment.

## Actual CPU benchmark

Run: `.venv-cpu\\Scripts\\python.exe benchmark.py`

- Result: **PASS**; model loaded on CPU and detected 4 people (COCO class 0) in the 810 × 1080 sample.
- Warm-up: 9.7404 s (excluded from steady-state timing).
- Five measured `model.predict` runs: mean 0.4648 s/image, median 0.4572 s/image, **2.151 FPS**.
- Process RSS: 212.03 MB before model load, 372.52 MB peak, 160.48 MB increase.
- Host CPU samples before/after measured runs: 96.2% / 100.0%.
- CUDA available: false; selected device: CPU.

The FPS measures sampled-image inference only and excludes video decoding, frame sampling, and other video-processing work. CPU utilization is a host sample; RSS is process memory rather than total system RAM. Five runs on one sample are a baseline, not a hardware-wide guarantee.

Artifacts: `benchmarks/cpu_benchmark.json` and `benchmarks/cpu_inference_result.jpg`.

## Phase 1 acceptance

The CPU model loads, person detection works, benchmark measurements are saved, and no CUDA dependency is required. **Phase 1 acceptance criteria pass.** The subsequent project brief authorized implementation through Phases 2–10; see the project README, architecture, tests, and current benchmark artifacts for that work. Browser-level paired playback remains unverified because desktop approval for Chrome access was denied.
