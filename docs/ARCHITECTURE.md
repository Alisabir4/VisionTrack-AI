# Architecture

## Runtime flow

1. `dashboard/video_analysis.py` validates and stores the upload through `core/video_manager.py`. Video bytes are streamed to disk, hashed, and inspected with OpenCV.
2. `utils/job_manager.py` runs one analysis job away from the Streamlit rerun loop. Jobs expose progress, cancellation, and failure state.
3. `core/processor.py` decodes every source frame sequentially. `core/frame_sampler.py` carries source frame index and timestamp, and selects frames at the chosen profile interval. `core/tracker.py` invokes Ultralytics YOLO and ByteTrack on sampled frames, restricted to COCO person class 0.
4. The processor writes an annotated video at the source frame cadence, tracking/detection/trajectory CSVs, heatmap PNGs, sampled heatmap frames, density time windows, and a per-frame source-to-output timeline. SQLite stores analysis summaries, tracking points, zones, and events.
5. `analytics/` builds movement, density, zone, occupancy, and line-crossing results from saved detections. `utils/report_generator.py` exports tracking/summary CSV, PDF, and PNG charts.
6. The Streamlit pages read persisted results. `utils/media_server.py` serves local media with byte-range support. `dashboard/paired_player.py` maps original playback time through the generated timeline to the heatmap video.

## Data and outputs

- Model: `models/yolov8n.pt`.
- Sample image: `samples/bus.jpg`.
- SQLite: `database/visiontrack.sqlite3`.
- Uploaded videos: `storage/uploads/`.
- Processed videos, CSVs, and frame timelines: `storage/processed/<analysis_id>/`.
- Heatmaps and annotated heatmap video: `storage/heatmaps/<analysis_id>/`.
- Generated reports: `storage/reports/<analysis_id>/`.
- Runtime profile and Phase 1 benchmarks: `benchmarks/`.

The timeline JSON stores a timestamp per source frame and an output timestamp per heatmap frame. This supports mapping when decoder timestamps are uneven. Automated tests validate the mapping data and media byte ranges. Browser timing behavior remains unverified without approved Chrome access.

## Persistence model

`database/db.py` owns schema initialization and repository methods. The database records video metadata and content hashes, keyed analyses/configurations and summaries, sampled detection/track points, zone definitions, zone events, counting lines, settings, and report exports. Completed analysis configurations are cacheable; processing attempts can be cancelled and clean up partial output artifacts.

## Performance profiles

Profiles are settings, not throughput promises:

- Fast: every fifth frame, 480 pixel inference size.
- Balanced: every third frame, 640 pixel inference size.
- Accurate: every second frame, 800 pixel inference size.

All use CPU inference. Processing decodes every frame to keep output frame cadence and timestamps aligned, even when detector inference is sampled.
