# Installation (Windows)

## Requirements

- Windows 10/11, Python 3.11, and a CPU.
- A working, verified TLS path to PyPI and the official PyTorch CPU wheel index.
- Several gigabytes of free disk space for the environment, model, uploads, and outputs.

## Environment setup

Run from the project directory in PowerShell:

```powershell
py -3.11 -m venv .venv-cpu
.\.venv-cpu\Scripts\python.exe -m pip install --upgrade pip certifi
.\.venv-cpu\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
.\.venv-cpu\Scripts\python.exe -m pip install -r requirements.txt
.\.venv-cpu\Scripts\python.exe download_assets.py
```

The PyTorch CPU index uses verified HTTPS; do not add `--trusted-host`, disable certificate checks, or fetch wheels from untrusted mirrors. If the machine has an approved organizational TLS-inspection proxy, install the organization’s official root certificate through IT and configure Python/pip to trust that certificate. Otherwise resolve the proxy/firewall or clock problem with the network administrator, then retry the commands.

The Phase 1 investigation is documented in `PHASE1_STATUS.md`. In the completed setup, standard verified requests worked after the environment’s network access was granted; no SSL verification bypass was used.

## Launch

```powershell
.\.venv-cpu\Scripts\python.exe -m streamlit run app.py
```

Stop the local server with Ctrl+C. Local app data and outputs remain in the project directories listed in `docs/ARCHITECTURE.md`.

## Verification

```powershell
.\.venv-cpu\Scripts\python.exe -c "import torch, torchvision, ultralytics; print(torch.__version__, torchvision.__version__, ultralytics.__version__, torch.cuda.is_available())"
.\.venv-cpu\Scripts\python.exe -m compileall -q .
.\.venv-cpu\Scripts\python.exe -m unittest discover -s tests -v
.\.venv-cpu\Scripts\python.exe work\apptest_pages.py
.\.venv-cpu\Scripts\python.exe benchmark.py
```

The expected device is CPU (`torch.cuda.is_available()` should be `False`). `benchmark.py` runs actual YOLOv8n person inference against `samples/bus.jpg` and records time, FPS, CPU/RSS, and an annotated image. The profile benchmark processes a short generated clip and records end-to-end throughput and peak process RSS.
