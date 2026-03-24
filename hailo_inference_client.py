#!/usr/bin/env python3
"""
Hailo Inference Client — lightweight TCP client for hailo_inference_server.

Usage:
    from hailo_inference_client import HailoInferenceClient

    client = HailoInferenceClient()          # connects to localhost:8003
    outputs = client.infer("yolov8m_pose", input_tensor)
    # outputs: {output_name: np.ndarray, ...}

The client maintains a persistent TCP connection for minimal per-request
overhead (~1-2ms round-trip on localhost for a 640×640×3 uint8 tensor).
Automatically reconnects on failure.
"""

import pickle
import socket
import struct
from typing import Dict, Optional

import numpy as np


class HailoInferenceClient:
    """Persistent TCP client for the Hailo inference server."""

    def __init__(self, host: str = "localhost", port: int = 8003):
        self.host = host
        self.port = port
        self._sock: Optional[socket.socket] = None

    def _connect(self) -> None:
        """Establish TCP connection to inference server."""
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._sock.connect((self.host, self.port))

    def _recv_exact(self, n: int) -> bytes:
        """Receive exactly n bytes."""
        chunks = []
        remaining = n
        while remaining > 0:
            chunk = self._sock.recv(min(remaining, 65536))
            if not chunk:
                raise ConnectionError("Server disconnected")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def infer(self, model_name: str, tensor: np.ndarray,
              _retried: bool = False) -> Dict[str, np.ndarray]:
        """Send inference request and return output tensors.

        Args:
            model_name: Name of the loaded model (e.g. "yolov8m_pose")
            tensor: Input tensor (NHWC uint8 or float32, matching model input)

        Returns:
            Dict mapping output tensor names to numpy arrays.

        Raises:
            RuntimeError: If server returns an error.
            ConnectionError: If unable to connect after retry.
        """
        if self._sock is None:
            self._connect()

        request = {"model": model_name, "tensor": tensor}
        payload = pickle.dumps(request, protocol=pickle.HIGHEST_PROTOCOL)

        try:
            # Send request
            self._sock.sendall(struct.pack(">I", len(payload)) + payload)

            # Receive response
            length_bytes = self._recv_exact(4)
            resp_len = struct.unpack(">I", length_bytes)[0]
            resp_bytes = self._recv_exact(resp_len)

        except (ConnectionError, BrokenPipeError, OSError):
            if _retried:
                raise ConnectionError(
                    f"Cannot connect to Hailo inference server at {self.host}:{self.port}")
            # Reconnect and retry once
            self._sock = None
            self._connect()
            return self.infer(model_name, tensor, _retried=True)

        response = pickle.loads(resp_bytes)
        if not response.get("ok"):
            raise RuntimeError(f"Hailo server error: {response.get('error', 'unknown')}")

        return response["outputs"]

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def __del__(self):
        self.close()
