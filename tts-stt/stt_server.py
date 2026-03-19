#!/usr/bin/env python3
"""
STT Server — Whisper speech-to-text via REST API.

Hailo auto-detection:
  - 2+ Hailo devices: uses device[1] for Whisper encoder (device[0] is for pose/face)
  - 1 or 0 Hailo:    uses faster-whisper on CPU

Override with --backend and --hailo-index.
"""

import os
import sys
import tempfile
import argparse
from pathlib import Path

from flask import Flask, request, jsonify

# hailo_utils.py is in the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
transcriber = None

""" GUI FUNCTIONS """
global text
text = ""
@app.route("/gui", methods=["GET"])
def send_text():
    """Send transcribed text to GUI client."""
    return jsonify({
        "output": text,
        })
""" GUI FUNCTIONS END """


# ---------------------------------------------------------------------------
# Backend: faster-whisper (CTranslate2, CPU-optimized) — default
# ---------------------------------------------------------------------------
class FasterWhisperTranscriber:
    """CPU-optimized Whisper using CTranslate2 (faster-whisper)."""

    def __init__(self, model_size: str = "small"):
        from faster_whisper import WhisperModel
        self.model = WhisperModel(
            model_size, device="cpu", compute_type="int8"
        )
        print(f"[STT] faster-whisper loaded: {model_size} (CPU int8)")

    def transcribe(self, audio_path: str, language: str = None) -> str:
        segments, _ = self.model.transcribe(
            audio_path, language=language, beam_size=5
        )
        return " ".join(seg.text for seg in segments).strip()


# ---------------------------------------------------------------------------
# Backend: Hailo-10 (encoder on Hailo, decoder on CPU)
# ---------------------------------------------------------------------------
class HailoWhisperTranscriber:
    """Whisper with encoder on Hailo-10, decoder on CPU.

    HEF preparation:
      1. Export Whisper encoder to ONNX:
         python -c "
         import whisper, torch
         model = whisper.load_model('small')
         dummy = torch.randn(1, 80, 3000)
         torch.onnx.export(model.encoder, dummy, 'whisper_encoder.onnx',
                           input_names=['mel'], output_names=['output'])
         "
      2. Convert to HEF:
         hailo optimize whisper_encoder.onnx --hw-arch hailo10h
         hailo compile whisper_encoder.har --hw-arch hailo10h
    """

    def __init__(self, encoder_hef_path: str, model_size: str = "small",
                 device_id: str = None):
        from hailo_platform import (
            HEF, VDevice, HailoStreamInterface,
            ConfigureParams, InputVStreamParams, OutputVStreamParams,
            FormatType,
        )
        import numpy as np

        if not os.path.exists(encoder_hef_path):
            raise FileNotFoundError(f"Encoder HEF not found: {encoder_hef_path}")

        self.hef = HEF(encoder_hef_path)

        if device_id:
            params = VDevice.create_params()
            params.device_ids = [device_id]
            self.target = VDevice(params)
            print(f"[HAILO-STT] Using device: {device_id}")
        else:
            self.target = VDevice()
            print("[HAILO-STT] Using default device")

        configure_params = ConfigureParams.create_from_hef(
            self.hef, interface=HailoStreamInterface.PCIe
        )
        self.network_group = self.target.configure(self.hef, configure_params)[0]

        self.input_params = InputVStreamParams.make_from_network_group(
            self.network_group, quantized=False, format_type=FormatType.FLOAT32
        )
        self.output_params = OutputVStreamParams.make_from_network_group(
            self.network_group, quantized=False, format_type=FormatType.FLOAT32
        )

        # CPU decoder
        import whisper
        self.whisper_model = whisper.load_model(model_size)
        print(f"[STT] Hailo Whisper loaded: encoder=Hailo, decoder=CPU ({model_size})")

    def transcribe(self, audio_path: str, language: str = None) -> str:
        import whisper
        import torch
        from hailo_platform import InferVStreams

        audio = whisper.load_audio(audio_path)
        audio = whisper.pad_or_trim(audio)
        mel = whisper.log_mel_spectrogram(audio).unsqueeze(0).numpy()

        # Encoder on Hailo
        input_name = self.hef.get_input_vstream_infos()[0].name
        with InferVStreams(
            self.network_group, self.input_params, self.output_params
        ) as pipeline:
            output = pipeline.infer({input_name: mel})

        # Decoder on CPU
        options = whisper.DecodingOptions(language=language, fp16=False)
        result = whisper.decode(self.whisper_model, mel[0], options)
        return result.text.strip()


# ---------------------------------------------------------------------------
# Backend: original openai-whisper (CPU fallback)
# ---------------------------------------------------------------------------
class OriginalWhisperTranscriber:
    """Original openai-whisper on CPU."""

    def __init__(self, model_size: str = "small"):
        import whisper
        self.model = whisper.load_model(model_size)
        print(f"[STT] openai-whisper loaded: {model_size} (CPU)")

    def transcribe(self, audio_path: str, language: str = None) -> str:
        result = self.model.transcribe(audio_path, language=language, fp16=False)
        return (result.get("text") or "").strip()


# ---------------------------------------------------------------------------
# Auto-detect backend
# ---------------------------------------------------------------------------
def auto_detect_backend(hailo_index: int = 1) -> str:
    """Auto-detect best STT backend.

    - 2+ Hailo devices → 'hailo' (uses device[hailo_index], default device[1])
    - 1 or 0 Hailo    → 'fast' (CPU faster-whisper)
    """
    try:
        from hailo_utils import scan_hailo_devices
        devices = scan_hailo_devices()
        if len(devices) >= 2:
            print(f"[STT] Auto-detect: {len(devices)} Hailo devices found → using Hailo device[{hailo_index}]")
            return "hailo"
        else:
            print(f"[STT] Auto-detect: {len(devices)} Hailo device(s) → using CPU (faster-whisper)")
            return "fast"
    except ImportError:
        print("[STT] Auto-detect: hailo_platform not installed → using CPU (faster-whisper)")
        return "fast"


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------
@app.route("/transcribe", methods=["POST"])
def transcribe_endpoint():
    global text
    try:
        if "audio" not in request.files and not request.files.get("audio"):
            return jsonify({
                "success": False,
                "error": "Missing 'audio' file in request (multipart/form-data)",
            }), 400

        file = request.files.get("audio")
        if file is None or file.filename == "":
            return jsonify({
                "success": False,
                "error": "No file selected for 'audio'",
            }), 400

        if transcriber is None:
            return jsonify({
                "success": False,
                "error": "Whisper model not initialized",
            }), 500

        language = request.form.get("language") or None
        suffix = Path(file.filename).suffix or ".wav"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            file.save(tmp.name)
            try:
                text = transcriber.transcribe(tmp.name, language=language)
            finally:
                os.unlink(tmp.name)

        return jsonify({
            "success": True,
            "text": text,
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


def main():
    parser = argparse.ArgumentParser(description="STT Server (Whisper)")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument(
        "--model", type=str, default="small",
        choices=["tiny", "base", "small", "medium", "large"],
    )
    parser.add_argument(
        "--backend", type=str, default="auto",
        choices=["auto", "hailo", "fast", "whisper"],
        help="auto: Hailo if 2+ devices, else CPU. hailo: force Hailo. fast: CPU. whisper: original CPU.",
    )
    parser.add_argument("--encoder-hef", type=str, default=None,
                        help="Path to Whisper encoder .hef (required for hailo backend)")
    parser.add_argument("--hailo-index", type=int, default=1,
                        help="Hailo device index for STT (default: 1, i.e. second device)")
    args = parser.parse_args()

    # Resolve backend
    backend = args.backend
    if backend == "auto":
        backend = auto_detect_backend(hailo_index=args.hailo_index)

    global transcriber
    print("=" * 60)
    print(f"Initializing STT Server (backend: {backend})...")
    print("=" * 60)

    if backend == "hailo":
        if not args.encoder_hef:
            print("Warning: --encoder-hef not specified for hailo backend, falling back to CPU")
            backend = "fast"

    if backend == "hailo":
        try:
            from hailo_utils import detect_hailo_device
            device_id = detect_hailo_device(device_index=args.hailo_index)
            transcriber = HailoWhisperTranscriber(
                encoder_hef_path=args.encoder_hef,
                model_size=args.model,
                device_id=device_id,
            )
        except Exception as e:
            print(f"[STT] Hailo init failed ({e}), falling back to CPU")
            backend = "fast"

    if backend == "fast":
        transcriber = FasterWhisperTranscriber(model_size=args.model)
    elif backend == "whisper":
        transcriber = OriginalWhisperTranscriber(model_size=args.model)

    print(f"Model loaded: {args.model}")
    print("-" * 60)
    print(f"Server: http://{args.host}:{args.port}")
    print("  POST /transcribe : Upload audio file (multipart 'audio') -> text")
    print("=" * 60)

    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
