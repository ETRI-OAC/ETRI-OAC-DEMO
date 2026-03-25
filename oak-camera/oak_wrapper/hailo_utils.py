"""
Hailo-10 device auto-detection utility.
Shared by all components that use Hailo (OAK-ROS2 pose, Face Recognition).

Multiple Hailo devices:
  When multiple Hailo devices are present, each service picks a device
  by index (0, 1, 2, ...) to avoid conflicts. If only one device exists,
  all services share it (Hailo supports multi-context on a single device).
"""

from typing import Optional, List


def scan_hailo_devices() -> List[str]:
    """Scan all available Hailo devices.

    Returns:
        List of device ID strings (e.g. ['0000:01:00.0', '0000:02:00.0']).
        Empty list if no devices found or HailoRT not installed.
    """
    try:
        from hailo_platform import VDevice
        device_ids = VDevice.scan()
        if device_ids:
            print(f"[HAILO] Found {len(device_ids)} device(s): {device_ids}")
            return list(device_ids)
    except ImportError:
        pass
    except Exception:
        # scan() not available in some HailoRT versions — try opening default
        try:
            from hailo_platform import VDevice
            target = VDevice()
            del target
            print("[HAILO] Device available (scan not supported, using default)")
            return ["default"]
        except Exception:
            pass

    print("[HAILO] No Hailo device found")
    return []


def detect_hailo_device(device_index: int = 0) -> Optional[str]:
    """Auto-detect Hailo device by index.

    Args:
        device_index: Which device to pick when multiple are present.
                      0 = first, 1 = second, etc.

    Returns:
        Device ID string or None if not enough devices found.
        Returns None for "default" (lets HailoRT pick automatically).
    """
    devices = scan_hailo_devices()
    if not devices:
        return None
    if device_index >= len(devices):
        print(f"[HAILO] Requested device index {device_index} but only "
              f"{len(devices)} device(s) available. Using device 0.")
        device_index = 0
    device_id = devices[device_index]
    if device_id == "default":
        return None  # Let HailoRT pick
    print(f"[HAILO] Selected device[{device_index}]: {device_id}")
    return device_id


def is_hailo_available() -> bool:
    """Check if any Hailo device is available."""
    return len(scan_hailo_devices()) > 0
