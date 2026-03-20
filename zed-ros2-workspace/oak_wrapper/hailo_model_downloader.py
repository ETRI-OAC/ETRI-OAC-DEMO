"""
Hailo HEF model auto-downloader.
Downloads models from Hailo Model Zoo on first use.
Shared by all components that need HEF files.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional

# Default model directory (relative to project root)
DEFAULT_MODEL_DIR = Path(__file__).parent.parent / "hailo_models"

# Known models and their Hailo Model Zoo names
KNOWN_MODELS = {
    "yolov8s_pose": {
        "zoo_name": "yolov8s_pose",
        "filename": "yolov8s_pose.hef",
        "description": "YOLOv8s pose estimation (COCO-17 keypoints)",
    },
    "scrfd_2.5g": {
        "zoo_name": "scrfd_2.5g",
        "filename": "scrfd_2.5g.hef",
        "description": "SCRFD face detection (2.5G FLOPs)",
    },
    "scrfd_10g": {
        "zoo_name": "scrfd_10g",
        "filename": "scrfd_10g.hef",
        "description": "SCRFD face detection (10G FLOPs, more accurate)",
    },
}


def get_hef_path(model_name: str, model_dir: Optional[str] = None,
                 hw_arch: str = "hailo10h") -> Optional[str]:
    """Get path to HEF file, downloading if necessary.

    Args:
        model_name: Model key from KNOWN_MODELS (e.g. 'yolov8s_pose', 'scrfd_2.5g')
        model_dir: Directory to store models. Default: <project_root>/hailo_models/
        hw_arch: Hailo hardware architecture (default: hailo10h)

    Returns:
        Absolute path to .hef file, or None if download failed.
    """
    if model_name not in KNOWN_MODELS:
        print(f"[HAILO-DL] Unknown model: {model_name}")
        print(f"[HAILO-DL] Available: {list(KNOWN_MODELS.keys())}")
        return None

    model_info = KNOWN_MODELS[model_name]
    dest_dir = Path(model_dir) if model_dir else DEFAULT_MODEL_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    hef_path = dest_dir / model_info["filename"]

    # Already downloaded
    if hef_path.exists():
        print(f"[HAILO-DL] Model found: {hef_path}")
        return str(hef_path)

    # Download via hailo model-zoo CLI
    print(f"[HAILO-DL] Downloading {model_name} ({model_info['description']})...")
    try:
        result = subprocess.run(
            ["hailo", "model-zoo", "download",
             "--model", model_info["zoo_name"],
             "--hw-arch", hw_arch],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            print(f"[HAILO-DL] hailo model-zoo failed: {result.stderr.strip()}")
            return _try_pip_download(model_name, model_info, dest_dir, hw_arch)

        # Find the downloaded .hef file
        # hailo model-zoo downloads to current directory or a known path
        for search_dir in [Path.cwd(), Path.home() / ".hailo"]:
            for hef_file in search_dir.rglob(model_info["filename"]):
                # Move to our model directory
                hef_file.rename(hef_path)
                print(f"[HAILO-DL] Downloaded: {hef_path}")
                return str(hef_path)

        # If file not found in expected locations, check stdout for path
        print(f"[HAILO-DL] Download succeeded but file not found. Check output:")
        print(result.stdout[:500])
        return None

    except FileNotFoundError:
        print("[HAILO-DL] 'hailo' CLI not found. Trying pip hailo_model_zoo...")
        return _try_pip_download(model_name, model_info, dest_dir, hw_arch)
    except subprocess.TimeoutExpired:
        print("[HAILO-DL] Download timed out (300s)")
        return None


def _try_pip_download(model_name: str, model_info: dict,
                      dest_dir: Path, hw_arch: str) -> Optional[str]:
    """Fallback: try downloading via hailo_model_zoo Python package."""
    hef_path = dest_dir / model_info["filename"]
    try:
        from hailo_model_zoo.core.main_utils import get_network
        # This is a simplified attempt — actual API may differ
        print(f"[HAILO-DL] Attempting Python API download...")
        result = subprocess.run(
            ["python3", "-c", f"""
from hailo_model_zoo import download_model
download_model('{model_info["zoo_name"]}', hw_arch='{hw_arch}', output_dir='{dest_dir}')
"""],
            capture_output=True, text=True, timeout=300,
        )
        if hef_path.exists():
            print(f"[HAILO-DL] Downloaded: {hef_path}")
            return str(hef_path)
    except Exception:
        pass

    print(f"[HAILO-DL] Auto-download failed. Please download manually:")
    print(f"  pip install hailo_model_zoo  (가상환경 활성화 또는 Docker 내부에서 실행)")
    print(f"  hailo model-zoo download --model {model_info['zoo_name']} --hw-arch {hw_arch}")
    print(f"  cp {model_info['filename']} {dest_dir}/")
    return None
