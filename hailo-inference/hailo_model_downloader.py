"""
Hailo HEF model auto-downloader.
Downloads models from Hailo Model Zoo S3 on first use.
Shared by all components that need HEF files.
"""

import os
import subprocess
import urllib.request
from pathlib import Path
from typing import Optional

# Default model directory: <project_root>/hailo_models/
# oak_wrapper/ → oak-camera/ → project_root/
DEFAULT_MODEL_DIR = Path(__file__).parent.parent / "hailo_models"

# S3 base URL for pre-compiled HEF files
_S3_BASE = "https://hailo-model-zoo.s3.eu-west-2.amazonaws.com/ModelZoo/Compiled/v5.2.0"

# Known models and their Hailo Model Zoo names
KNOWN_MODELS = {
    "yolov8m_pose": {
        "zoo_name": "yolov8m_pose",
        "filename": "yolov8m_pose.hef",
        "description": "YOLOv8m pose estimation (COCO-17 keypoints)",
        "s3_urls": {
            "hailo10h": f"{_S3_BASE}/hailo10h/yolov8m_pose.hef",
        },
    },
    "scrfd_10g": {
        "zoo_name": "scrfd_10g",
        "filename": "scrfd_10g.hef",
        "description": "SCRFD face detection (10G FLOPs, legacy)",
        "s3_urls": {
            "hailo10h": f"{_S3_BASE}/hailo10h/scrfd_10g.hef",
        },
    },
    "arcface_mobilefacenet": {
        "zoo_name": "arcface_mobilefacenet",
        "filename": "arcface_mobilefacenet.hef",
        "description": "ArcFace MobileFaceNet face embedding (112x112 → 512-dim)",
        "s3_urls": {
            "hailo10h": f"{_S3_BASE}/hailo10h/arcface_mobilefacenet.hef",
        },
    },
}


def get_hef_path(model_name: str, model_dir: Optional[str] = None,
                 hw_arch: str = "hailo10h") -> Optional[str]:
    """Get path to HEF file, downloading if necessary.

    Args:
        model_name: Model key from KNOWN_MODELS (e.g. 'yolov8m_pose', 'scrfd_10g')
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

    print(f"[HAILO-DL] Downloading {model_name} ({model_info['description']})...")

    # 1st: try direct S3 download (no CLI dependency)
    s3_url = model_info.get("s3_urls", {}).get(hw_arch)
    if s3_url:
        result = _try_s3_download(s3_url, hef_path)
        if result:
            return result

    # 2nd: try hailo model-zoo CLI
    try:
        result = subprocess.run(
            ["hailo", "model-zoo", "download",
             "--model", model_info["zoo_name"],
             "--hw-arch", hw_arch],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0:
            for search_dir in [Path.cwd(), Path.home() / ".hailo"]:
                for hef_file in search_dir.rglob(model_info["filename"]):
                    hef_file.rename(hef_path)
                    print(f"[HAILO-DL] Downloaded via CLI: {hef_path}")
                    return str(hef_path)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    _print_manual_instructions(model_info, dest_dir, hw_arch, s3_url)
    return None


def _try_s3_download(url: str, dest: Path) -> Optional[str]:
    """Download a HEF file directly from S3."""
    try:
        print(f"[HAILO-DL] Fetching {url} ...")
        tmp = dest.with_suffix(".hef.part")
        urllib.request.urlretrieve(url, tmp)
        tmp.rename(dest)
        print(f"[HAILO-DL] Saved: {dest}")
        return str(dest)
    except Exception as e:
        print(f"[HAILO-DL] S3 download failed: {e}")
        if tmp.exists():
            tmp.unlink()
        return None


def _print_manual_instructions(model_info: dict, dest_dir: Path,
                                hw_arch: str, s3_url: Optional[str]) -> None:
    print(f"[HAILO-DL] Auto-download failed. Download manually:")
    if s3_url:
        print(f"  wget -P {dest_dir}/ '{s3_url}'")
    else:
        print(f"  hailo model-zoo download --model {model_info['zoo_name']} --hw-arch {hw_arch}")
        print(f"  cp {model_info['filename']} {dest_dir}/")
