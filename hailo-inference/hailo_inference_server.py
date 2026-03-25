#!/usr/bin/env python3
"""
Hailo-10 Inference Server — centralized device scheduler.

Owns the Hailo VDevice exclusively and serves inference requests from
multiple clients (oak_server for pose, face_recognition for SCRFD, etc.)
via a lightweight TCP socket protocol.

Protocol (size-prefixed pickle):
  Request:  4-byte big-endian length + pickle({model, tensor})
  Response: 4-byte big-endian length + pickle({output_name: ndarray, ...})

Port: 8003 (configurable via --port)
"""

import argparse
import os
import pickle
import signal
import socket
import struct
import sys
import threading
import time
from typing import Dict, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Add project root to path so we can import hailo_utils / hailo_model_downloader
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_OAK_WRAPPER = os.path.join(_PROJECT_ROOT, "oak-camera", "oak_wrapper")
sys.path.insert(0, _OAK_WRAPPER)

from hailo_utils import detect_hailo_device, is_hailo_available
from hailo_model_downloader import get_hef_path


class HailoInferenceServer:
    """Multi-model inference server over a single Hailo VDevice."""

    def __init__(self, port: int = 8003, device_index: int = 0):
        self.port = port
        self._lock = threading.Lock()  # serialize Hailo access
        self._models: Dict[str, dict] = {}  # name → {infer_model, configured, ctx}
        self._running = False

        from hailo_platform import VDevice, FormatType
        self._FormatType = FormatType

        device_id = detect_hailo_device(device_index=device_index)
        if device_id:
            params = VDevice.create_params()
            params.device_ids = [device_id]
            self._vdevice = VDevice(params)
            print(f"[HAILO-SERVER] Using device: {device_id}")
        else:
            self._vdevice = VDevice()
            print("[HAILO-SERVER] Using default device")

    # ------------------------------------------------------------------
    # Model management
    # ------------------------------------------------------------------
    def load_model(self, name: str, hef_path: str) -> None:
        """Load a HEF model and configure it immediately.

        All models are configured at startup and kept active simultaneously
        (multi-context). This eliminates the ~400ms context switch penalty
        that occurs when using single-context with on-demand configure().
        """
        if not os.path.exists(hef_path):
            raise FileNotFoundError(f"HEF not found: {hef_path}")

        infer_model = self._vdevice.create_infer_model(hef_path)
        infer_model.set_batch_size(1)

        for out in infer_model.outputs:
            infer_model.output(out.name).set_format_type(self._FormatType.FLOAT32)

        # Configure immediately — keep context alive for the server lifetime
        ctx = infer_model.configure()
        configured = ctx.__enter__()

        # Print model info
        inp = infer_model.inputs[0]
        print(f"[HAILO-SERVER] Loaded + configured: {name} ({hef_path})")
        print(f"  input: {inp.name} shape={inp.shape}")
        for out in infer_model.outputs:
            print(f"  output: {out.name} shape={out.shape}")

        self._models[name] = {
            "infer_model": infer_model,
            "configured": configured,
            "ctx": ctx,
        }

    def infer(self, model_name: str, input_tensor: np.ndarray) -> Dict[str, np.ndarray]:
        """Run inference on a loaded model. Thread-safe.

        No context switch needed — all models stay configured simultaneously.
        The lock only serializes access to the Hailo device (one inference at a time).
        """
        if model_name not in self._models:
            raise ValueError(f"Model not loaded: {model_name}")

        entry = self._models[model_name]
        infer_model = entry["infer_model"]
        configured = entry["configured"]

        with self._lock:
            bindings = configured.create_bindings()
            input_name = infer_model.inputs[0].name
            bindings.input(input_name).set_buffer(input_tensor)

            out_bufs: Dict[str, np.ndarray] = {}
            for out in infer_model.outputs:
                buf = np.empty(tuple(out.shape), dtype=np.float32)
                bindings.output(out.name).set_buffer(buf)
                out_bufs[out.name] = buf

            configured.run([bindings], 10000)

        return {name: bindings.output(name).get_buffer() for name in out_bufs}

    # ------------------------------------------------------------------
    # TCP server
    # ------------------------------------------------------------------
    def _recv_exact(self, conn: socket.socket, n: int) -> bytes:
        """Receive exactly n bytes."""
        chunks = []
        remaining = n
        while remaining > 0:
            chunk = conn.recv(min(remaining, 65536))
            if not chunk:
                raise ConnectionError("Client disconnected")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _handle_client(self, conn: socket.socket, addr: Tuple) -> None:
        """Handle a single client connection (may send multiple requests)."""
        try:
            while self._running:
                # Read 4-byte length prefix
                try:
                    length_bytes = self._recv_exact(conn, 4)
                except ConnectionError:
                    break
                msg_len = struct.unpack(">I", length_bytes)[0]
                if msg_len == 0 or msg_len > 50_000_000:  # 50MB sanity limit
                    break

                # Read request payload
                payload = self._recv_exact(conn, msg_len)
                request = pickle.loads(payload)

                model_name = request["model"]
                input_tensor = request["tensor"]

                # Run inference
                try:
                    outputs = self.infer(model_name, input_tensor)
                    response = {"ok": True, "outputs": outputs}
                except Exception as e:
                    response = {"ok": False, "error": str(e)}

                # Send response
                resp_bytes = pickle.dumps(response, protocol=pickle.HIGHEST_PROTOCOL)
                conn.sendall(struct.pack(">I", len(resp_bytes)) + resp_bytes)

        except Exception as e:
            print(f"[HAILO-SERVER] Client {addr} error: {e}")
        finally:
            conn.close()

    def serve(self) -> None:
        """Start the TCP server."""
        self._running = True
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", self.port))
        srv.listen(8)
        srv.settimeout(1.0)  # allow periodic check of _running

        print(f"[HAILO-SERVER] Listening on port {self.port}")
        print(f"[HAILO-SERVER] Models: {list(self._models.keys())}")
        print("[HAILO-SERVER] Ctrl+C to stop.")

        def _shutdown(signum, frame):
            print("\n[HAILO-SERVER] Shutting down...")
            self._running = False

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        while self._running:
            try:
                conn, addr = srv.accept()
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                t = threading.Thread(target=self._handle_client, args=(conn, addr),
                                     daemon=True)
                t.start()
            except socket.timeout:
                continue
            except OSError:
                break

        srv.close()
        self._cleanup()

    def _cleanup(self) -> None:
        for name, entry in self._models.items():
            try:
                entry["ctx"].__exit__(None, None, None)
            except Exception:
                pass
        self._models.clear()
        print("[HAILO-SERVER] Cleaned up.")


def main():
    parser = argparse.ArgumentParser(description="Hailo-10 Inference Server")
    parser.add_argument("--port", type=int, default=8003, help="TCP port (default: 8003)")
    parser.add_argument("--device-index", type=int, default=0,
                        help="Hailo device index (default: 0)")
    parser.add_argument("--models", type=str, nargs="*",
                        default=["yolov8m_pose", "scrfd_10g"],
                        help="Models to load (default: yolov8m_pose scrfd_10g)")
    args = parser.parse_args()

    if not is_hailo_available():
        print("[HAILO-SERVER] ERROR: No Hailo device found. Exiting.")
        sys.exit(1)

    server = HailoInferenceServer(port=args.port, device_index=args.device_index)

    for model_name in args.models:
        hef_path = get_hef_path(model_name)
        if hef_path:
            server.load_model(model_name, hef_path)
        else:
            print(f"[HAILO-SERVER] WARNING: Could not find HEF for {model_name}, skipping")

    server.serve()


if __name__ == "__main__":
    main()
