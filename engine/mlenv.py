"""A private Python 3.11 environment for the AI tools (transcription, segmentation).

Lives in ~/.reel-styles/venv (outside the repo); created and filled on first use, one package set
at a time, so a tool only downloads what it needs.
"""
import os
import shutil
import subprocess
import sys

HOME = os.path.expanduser(os.environ.get("REEL_HOME", "~/.reel-styles"))
VENV = os.path.join(HOME, "venv")
PY = os.path.join(VENV, "bin", "python")
MODELS = os.path.join(HOME, "models")


def _base_python():
    for c in ("python3.12", "python3.11", "/opt/homebrew/bin/python3.11", "python3.10"):
        p = shutil.which(c) or (c if os.path.exists(c) else None)
        if p:
            return p
    sys.exit("error: the AI tools need Python 3.10+ (brew install python@3.11)")


def ensure(packages):
    """Create the venv if needed and install whatever of `packages` (pip specs) is missing."""
    os.makedirs(MODELS, exist_ok=True)
    if not os.path.exists(PY):
        print(f"creating {VENV} …", flush=True)
        subprocess.run([_base_python(), "-m", "venv", VENV], check=True)
        subprocess.run([PY, "-m", "pip", "install", "-q", "--upgrade", "pip"], check=True)
    missing = []
    for spec in packages:
        mod = spec.split("==")[0].split(">=")[0].split("[")[0].replace("-", "_")
        mod = {"faster_whisper": "faster_whisper", "onnxruntime": "onnxruntime", "opencv_python_headless": "cv2",
               "mediapipe": "mediapipe", "numpy": "numpy", "pillow": "PIL", "huggingface_hub": "huggingface_hub"}.get(mod, mod)
        if subprocess.run([PY, "-c", f"import {mod}"], capture_output=True).returncode != 0:
            missing.append(spec)
    if missing:
        print(f"installing {' '.join(missing)} (one-time) …", flush=True)
        subprocess.run([PY, "-m", "pip", "install", "-q", *missing], check=True)
    return PY
