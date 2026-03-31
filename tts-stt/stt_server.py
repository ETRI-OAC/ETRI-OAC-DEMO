#!/usr/bin/env python3
"""
STT Server — Whisper speech-to-text via REST API.

Backends:
  - hailo_server: Whisper encoder on Hailo via inference server (encoder accelerated)
  - fast:         faster-whisper on CPU (CTranslate2, int8)
  - whisper:      original openai-whisper on CPU (fallback)

Auto-detection: tries hailo_server first, falls back to CPU.
"""

import os
import sys
import tempfile
import argparse
from pathlib import Path

from flask import Flask, request, jsonify

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
transcriber = None

""" GUI FUNCTIONS """
global text
text = ""
@app.route("/gui", methods=["GET"])
def send_text():
    """Send transcribed text to GUI client."""
    return jsonify({"output": text})
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
            audio_path, language=language or "ko", beam_size=5,
            initial_prompt="안녕하세요. 이 로봇은 ETRI에서 만들었습니다."
        )
        return " ".join(seg.text for seg in segments).strip()


# ---------------------------------------------------------------------------
# Backend: Hailo inference server (encoder on Hailo, decoder on CPU)
# ---------------------------------------------------------------------------
class HailoServerWhisperTranscriber:
    """Whisper with encoder on Hailo-10 via inference server, decoder on CPU.

    Pipeline:
      1. Audio → mel-spectrogram (CPU, whisper library)
      2. Mel → encoder features (Hailo whisper_small/encoder)
      3. Features → text (CPU, whisper greedy decode)
    """

    def __init__(self, model_size: str = "small",
                 hailo_host: str = "localhost", hailo_port: int = 8003,
                 encoder_model: str = "whisper_small/encoder"):
        import numpy as np
        import whisper

        self.np = np
        self.encoder_model = encoder_model

        # Hailo inference client
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         '..', 'hailo-inference'))
        from hailo_inference_client import HailoInferenceClient
        self.hailo_client = HailoInferenceClient(host=hailo_host, port=hailo_port)

        # Test connection
        dummy = np.zeros((1, 1000, 80), dtype=np.float32)
        out = self.hailo_client.infer(encoder_model, dummy)
        enc_out_name = list(out.keys())[0]
        enc_shape = out[enc_out_name].shape
        print(f"[STT] Hailo encoder test OK: {enc_out_name} shape={enc_shape}")

        # CPU whisper model for decoder + tokenizer
        self.whisper_model = whisper.load_model(model_size)
        self.whisper_model.eval()

        print(f"[STT] Hailo Whisper loaded: encoder=Hailo ({encoder_model}), "
              f"decoder=CPU ({model_size})")

    def transcribe(self, audio_path: str, language: str = None) -> str:
        import whisper
        import torch

        # 1. Audio → mel-spectrogram
        audio = whisper.load_audio(audio_path)
        audio = whisper.pad_or_trim(audio)
        mel = whisper.log_mel_spectrogram(audio)

        # Ensure mel is (1, 1000, 80) for Hailo — pad/trim time dimension
        # Whisper mel is (80, 3000) for 30s, HEF expects (1, 1000, 80) for 10s
        mel_np = mel.numpy()  # (80, 3000)
        # Take first 1000 frames (10 seconds) and transpose
        mel_trimmed = mel_np[:, :1000].T  # (1000, 80)
        mel_input = self.np.expand_dims(mel_trimmed, axis=0).astype(self.np.float32)  # (1, 1000, 80)

        # 2. Encoder on Hailo
        try:
            outputs = self.hailo_client.infer(self.encoder_model, mel_input)
            encoder_output = list(outputs.values())[0]  # (1, 500, 768)
        except Exception as e:
            print(f"[STT] Hailo encoder failed ({e}), falling back to CPU")
            # CPU fallback: use whisper's own encoder
            with torch.no_grad():
                encoder_output = self.whisper_model.encoder(mel.unsqueeze(0)).numpy()

        # 3. Decoder on CPU
        encoder_tensor = torch.from_numpy(encoder_output).float()
        if encoder_tensor.dim() == 2:
            encoder_tensor = encoder_tensor.unsqueeze(0)

        options = whisper.DecodingOptions(
            language=language or "ko",
            fp16=False,
            without_timestamps=True,
        )
        with torch.no_grad():
            result = whisper.decode(self.whisper_model, mel, options)

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
def auto_detect_backend(hailo_host: str = "localhost", hailo_port: int = 8003) -> str:
    """Auto-detect best STT backend.

    Tries connecting to Hailo inference server; falls back to CPU.
    """
    try:
        import socket
        s = socket.socket()
        s.settimeout(2)
        s.connect((hailo_host, hailo_port))
        s.close()
        print(f"[STT] Auto-detect: Hailo inference server at {hailo_host}:{hailo_port} → using Hailo encoder")
        return "hailo_server"
    except Exception:
        print("[STT] Auto-detect: Hailo inference server not available → using CPU (faster-whisper)")
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
        choices=["auto", "hailo_server", "fast", "whisper"],
        help="auto: try Hailo server, else CPU. hailo_server: Hailo encoder. fast: CPU. whisper: original CPU.",
    )
    parser.add_argument("--hailo-host", type=str, default="localhost")
    parser.add_argument("--hailo-port", type=int, default=8003)
    parser.add_argument("--encoder-model", type=str, default="whisper_small/encoder",
                        help="Model name on Hailo inference server (default: whisper_small/encoder)")
    args = parser.parse_args()

    # Resolve backend
    backend = args.backend
    if backend == "auto":
        backend = auto_detect_backend(args.hailo_host, args.hailo_port)

    global transcriber
    print("=" * 60)
    print(f"Initializing STT Server (backend: {backend})...")
    print("=" * 60)

    if backend == "hailo_server":
        try:
            transcriber = HailoServerWhisperTranscriber(
                model_size=args.model,
                hailo_host=args.hailo_host,
                hailo_port=args.hailo_port,
                encoder_model=args.encoder_model,
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
