# VisionTrack AI

CPU-first video movement analytics for Windows 10/11 and Python 3.11. The app analyzes uploaded MP4, AVI, and MOV clips with YOLOv8n person detection and ByteTrack, then provides movement/density heatmaps, zone and line analytics, tracking results, reports, and configurable processing profiles.

## Features

- Chunked video upload persistence, duplicate detection by SHA-256, and corrupt/unsupported file checks.
- Fast, Balanced, and Accurate CPU profiles with configurable inference cadence and image size.
- Sequential video decoding with decoder timestamps when available and a frame timeline for paired playback mapping.
- Person class detection, ByteTrack IDs, bounding boxes, trajectories, movement/density maps, and 10-second density windows.
- Editable polygon zones and directional counting lines with sampled occupancy, entries, exits, and crossing counts.
- Background analysis jobs with progress, cancellation, and cleanup of incomplete outputs.
- SQLite persistence and cached analysis results.
- Dashboard pages for overview, video analysis, tracking, heatmaps, zones, reports, and settings.
- CSV, PDF, and PNG report exports.

See [installation](docs/INSTALLATION.md), [architecture](docs/ARCHITECTURE.md), and [Phase 1 network/environment notes](PHASE1_STATUS.md).

## Local environment and secrets

The current application does not require API keys, tokens, passwords, or external-service credentials. For local-only environment overrides, copy the template in PowerShell:

```powershell
Copy-Item .env.example .env
```

`config.py` loads `.env` with `python-dotenv` without overriding environment variables already set by the operating system. Keep real values only in your local `.env`; never paste them into source code, documentation, screenshots, or commits. `.env`, credential files, local databases, uploaded videos, generated videos, virtual environments, and caches are excluded by `.gitignore`. The checked-in `.env.example` contains placeholders only.

## Install

Use Python 3.11. Install a CPU-only PyTorch/torchvision pair from the official PyTorch CPU wheel index with standard TLS validation, then install the rest of the requirements. Follow [docs/INSTALLATION.md](docs/INSTALLATION.md) for exact commands and the safe certificate/network diagnosis used for this environment.

## Launch

```powershell
.\.venv-cpu\Scripts\python.exe -m streamlit run app.py
```

Open the local Streamlit URL shown in the terminal. Uploaded media and generated artifacts are stored under `storage/`; the SQLite database is `database/visiontrack.sqlite3`.

## Verify

```powershell
.\.venv-cpu\Scripts\python.exe -m compileall -q .
.\.venv-cpu\Scripts\python.exe -m unittest discover -s tests -v
.\.venv-cpu\Scripts\python.exe work\apptest_pages.py
.\.venv-cpu\Scripts\python.exe benchmark.py
```

The tests include an actual CPU inference/tracking video, an empty-scene case, analytics and database checks, and timeline/media-range checks. The Streamlit AppTest renders all seven pages. The project’s profile benchmark can be rerun with `benchmarks/profile_benchmark.py`.

## Measured performance

On the available 4-logical-CPU Windows host, a 60-frame, 5 FPS synthetic clip made from the shipped bus image measured:

| Profile | Inference size | Sample interval | Throughput (source frames/s) | Peak process RSS |
|---|---:|---:|---:|---:|
| Fast | 480 | 5 | 7.00 | 413.09 MB |
| Balanced | 640 | 3 | 8.23 | 441.62 MB |
| Accurate | 800 | 2 | 4.53 | 433.27 MB |

These values are measured on a repeated still image and are not a guarantee for other footage or processors. Full metadata and the benchmark context are in `benchmarks/processing_profiles.json`. The separate Phase 1 single-image inference baseline is in `benchmarks/cpu_benchmark.json`.

## Limitations

- CPU performance varies by machine and source codec/resolution.
- Occupancy and movement statistics use sampled inference frames; no interpolation is claimed between sampled frames.
- Timeline mapping and range requests have automated metadata/unit coverage, but browser-level paired playback was not verified in this run because Google Chrome computer-use access was denied by the desktop approval gate.
- Streamlit’s uploader may buffer the selected file before the app saves it in chunks. The configured maximum upload size is 512 MB.
- Zone/line counts are based on tracked detections; occlusion and tracker ID switches can affect them.
