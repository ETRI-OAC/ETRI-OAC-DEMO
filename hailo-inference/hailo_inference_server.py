#!/usr/bin/env python3
"""
Hailo-10 Inference Server — centralized device scheduler.

Owns the Hailo VDevice exclusively and serves inference requests from
multiple clients (oak_server for pose, face_recognition for ArcFace embedding,
stt_server for Whisper encoder/decoder, etc.) via a lightweight TCP socket protocol.

Supports both single-network-group HEFs (InferModel API) and
multi-network-group HEFs like Whisper (HEF + VDevice.configure API).

Protocol (size-prefixed pickle):
  Request:  4-byte big-endian length + pickle({model, tensor} or {model, tensors})
  Response: 4-byte big-endian length + pickle({output_name: ndarray, ...})

For multi-input models, use "tensors" dict instead of "tensor":
  Request: {model: "whisper_base/encoder", tensors: {input_name: ndarray, ...}}

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
_HAILO_DIR = os.path.dirname(os.path.abspath(__file__))
_OAK_WRAPPER = os.path.join(_PROJECT_ROOT, "oak-camera", "oak_wrapper")
sys.path.insert(0, _HAILO_DIR)
sys.path.insert(0, _OAK_WRAPPER)

from hailo_utils import detect_hailo_device, is_hailo_available
from hailo_model_downloader import get_hef_path


class HailoInferenceServer:
    """Multi-model inference server over a single Hailo VDevice."""

    def __init__(self, port: int = 8003, device_index: int = 0):
        self.port = port
        self._lock = threading.Lock()
        self._models: Dict[str, dict] = {}  # "name" or "name/group" → model entry
        self._running = False

        from hailo_platform import VDevice, HEF, FormatType
        self._VDevice = VDevice
        self._HEF = HEF
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
        """Load a HEF model. Auto-detects single vs multi network group.

        Single group HEFs use the InferModel API (existing behavior).
        Multi-group HEFs (e.g. Whisper encoder+decoder) use HEF + VDevice.configure,
        registering each group as "name/group_name".
        """
        if not os.path.exists(hef_path):
            raise FileNotFoundError(f"HEF not found: {hef_path}")

        # Check number of network groups
        hef = self._HEF(hef_path)
        group_names = hef.get_network_group_names()

        if len(group_names) <= 1:
            # Single group — use InferModel API (fast, simple)
            self._load_single_group(name, hef_path)
        else:
            # Multi group — use HEF + VDevice.configure API
            self._load_multi_group(name, hef_path, hef, group_names)

    def _load_single_group(self, name: str, hef_path: str) -> None:
        """Load single-network-group HEF via InferModel API."""
        infer_model = self._vdevice.create_infer_model(hef_path)
        infer_model.set_batch_size(1)

        for out in infer_model.outputs:
            infer_model.output(out.name).set_format_type(self._FormatType.FLOAT32)

        ctx = infer_model.configure()
        configured = ctx.__enter__()

        inp = infer_model.inputs[0]
        print(f"[HAILO-SERVER] Loaded + configured: {name} ({hef_path})")
        print(f"  input: {inp.name} shape={inp.shape}")
        for out in infer_model.outputs:
            print(f"  output: {out.name} shape={out.shape}")

        self._models[name] = {
            "type": "infer_model",
            "infer_model": infer_model,
            "configured": configured,
            "ctx": ctx,
        }

    def _load_multi_group(self, name: str, hef_path: str, hef, group_names: list) -> None:
        """Load multi-network-group HEF via VDevice.configure API."""
        print(f"[HAILO-SERVER] Loading multi-group HEF: {name} ({hef_path})")
        print(f"  Network groups: {group_names}")

        network_groups = self._vdevice.configure(hef)

        for ng, gname in zip(network_groups, group_names):
            # Derive a short alias from the group name
            # e.g. "whisper_base_10s_encoder" → "encoder"
            parts = gname.split("_")
            # Try to find "encoder" or "decoder" in the name
            short = gname
            for keyword in ["encoder", "decoder"]:
                if keyword in gname:
                    short = keyword
                    break

            model_key = f"{name}/{short}"

            input_infos = hef.get_input_vstream_infos(gname)
            output_infos = hef.get_output_vstream_infos(gname)

            print(f"  [{model_key}] (group: {gname})")
            for info in input_infos:
                print(f"    input: {info.name} shape={info.shape}")
            for info in output_infos:
                print(f"    output: {info.name} shape={info.shape}")

            self._models[model_key] = {
                "type": "network_group",
                "network_group": ng,
                "group_name": gname,
                "hef": hef,
                "input_infos": input_infos,
                "output_infos": output_infos,
            }

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------
    def infer(self, model_name: str, input_tensor: Optional[np.ndarray] = None,
              input_tensors: Optional[Dict[str, np.ndarray]] = None) -> Dict[str, np.ndarray]:
        """Run inference on a loaded model. Thread-safe.

        Args:
            model_name: "yolov8m_pose" (single group) or "whisper_base/encoder" (multi group)
            input_tensor: Single input tensor (for single-input models)
            input_tensors: Dict of {input_name: tensor} (for multi-input models)
        """
        if model_name not in self._models:
            raise ValueError(f"Model not loaded: {model_name}")

        entry = self._models[model_name]

        if entry["type"] == "infer_model":
            return self._infer_single(entry, input_tensor)
        else:
            return self._infer_network_group(entry, input_tensor, input_tensors)

    def _infer_single(self, entry: dict, input_tensor: np.ndarray) -> Dict[str, np.ndarray]:
        """Inference via InferModel API (single network group)."""
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

    def _infer_network_group(self, entry: dict, input_tensor: Optional[np.ndarray],
                              input_tensors: Optional[Dict[str, np.ndarray]]) -> Dict[str, np.ndarray]:
        """Inference via ConfiguredNetworkGroup API (multi network group)."""
        from hailo_platform import InputVStreamParams, OutputVStreamParams

        ng = entry["network_group"]
        input_infos = entry["input_infos"]
        output_infos = entry["output_infos"]

        # Build input dict
        if input_tensors is not None:
            inputs = input_tensors
        elif input_tensor is not None and len(input_infos) == 1:
            inputs = {input_infos[0].name: input_tensor}
        else:
            raise ValueError(f"Model has {len(input_infos)} inputs, provide 'tensors' dict")

        with self._lock:
            in_params = InputVStreamParams.make(ng, quantized=False,
                                                 format_type=self._FormatType.FLOAT32)
            out_params = OutputVStreamParams.make(ng, quantized=False,
                                                   format_type=self._FormatType.FLOAT32)

            from hailo_platform import InferVStreams
            with InferVStreams(ng, in_params, out_params) as pipeline:
                results = pipeline.infer(inputs)

        return results

    # ------------------------------------------------------------------
    # TCP server
    # ------------------------------------------------------------------
    def _recv_exact(self, conn: socket.socket, n: int) -> bytes:
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
        try:
            while self._running:
                try:
                    length_bytes = self._recv_exact(conn, 4)
                except ConnectionError:
                    break
                msg_len = struct.unpack(">I", length_bytes)[0]
                if msg_len == 0 or msg_len > 500_000_000:  # 500MB for Whisper
                    break

                payload = self._recv_exact(conn, msg_len)
                request = pickle.loads(payload)

                model_name = request["model"]
                input_tensor = request.get("tensor", None)
                input_tensors = request.get("tensors", None)

                try:
                    outputs = self.infer(model_name, input_tensor, input_tensors)
                    response = {"ok": True, "outputs": outputs}
                except Exception as e:
                    response = {"ok": False, "error": str(e)}

                resp_bytes = pickle.dumps(response, protocol=pickle.HIGHEST_PROTOCOL)
                conn.sendall(struct.pack(">I", len(resp_bytes)) + resp_bytes)

        except Exception as e:
            print(f"[HAILO-SERVER] Client {addr} error: {e}")
        finally:
            conn.close()

    def serve(self) -> None:
        self._running = True
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", self.port))
        srv.listen(8)
        srv.settimeout(1.0)

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
            if entry["type"] == "infer_model":
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
                        default=["yolov8m_pose", "scrfd_10g", "arcface_r50", "whisper_base"],
                        help="Models to load (default: yolov8m_pose scrfd_10g arcface_r50 whisper_base)")
    args = parser.parse_args()

    if not is_hailo_available():
        print("[HAILO-SERVER] ERROR: No Hailo device found. Exiting.")
        sys.exit(1)

    server = HailoInferenceServer(port=args.port, device_index=args.device_index)

    for model_name in args.models:
        hef_path = get_hef_path(model_name)
        if hef_path:
            try:
                server.load_model(model_name, hef_path)
            except Exception as e:
                print(f"[HAILO-SERVER] WARNING: Failed to load {model_name}: {e}")
        else:
            print(f"[HAILO-SERVER] WARNING: Could not find HEF for {model_name}, skipping")

    server.serve()


if __name__ == "__main__":
    main()
