#!/usr/bin/env python3
"""
STT Server — Whisper speech-to-text via REST API.

Backends:
  - hailo_genai: Hailo-10H GenAI runtime (encoder+decoder on Hailo, KV cache)
  - fast:        faster-whisper on CPU (CTranslate2, int8)
  - whisper:     original openai-whisper on CPU (fallback)

Auto-detection: tries hailo_genai first, falls back to CPU.
"""

import os
import sys
import tempfile
import argparse
import wave
from pathlib import Path

import numpy as np
from flask import Flask, request, jsonify

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
transcriber = None

""" GUI FUNCTIONS """
global text
text = ""
@app.route("/gui", methods=["GET"])
def send_text():
    return jsonify({"output": text})
""" GUI FUNCTIONS END """


# ---------------------------------------------------------------------------
# Backend: faster-whisper (CTranslate2, CPU-optimized) — default
# ---------------------------------------------------------------------------
class FasterWhisperTranscriber:
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
# Backend: Hailo-10H GenAI (full Whisper on Hailo with KV cache)
# ---------------------------------------------------------------------------
class HailoGenAIWhisperTranscriber:
    """Whisper on Hailo-10H via GenAI runtime (encoder+decoder, KV cache)."""

    SHARED_VDEVICE_GROUP_ID = "shared_vdevice"

    def __init__(self, hef_path: str = None):
        from hailo_platform import VDevice
        from hailo_platform.genai import Speech2Text

        self._Speech2TextTask = None
        try:
            from hailo_platform.genai import Speech2TextTask
            self._Speech2TextTask = Speech2TextTask
        except ImportError:
            pass

        # Resolve HEF path
        if hef_path is None:
            # Try standard locations
            candidates = [
                "/usr/local/hailo/resources/models/hailo10h/Whisper-Base.hef",
                "/root/workspace/hailo_models/whisper_base.hef",
                "/root/workspace/hailo_models/whisper_small.hef",
            ]
            for c in candidates:
                if os.path.exists(c):
                    hef_path = c
                    break

        if hef_path is None or not os.path.exists(hef_path):
            raise FileNotFoundError(f"Whisper HEF not found: {hef_path}")

        # Create shared VDevice (coexists with hailo_inference_server)
        params = VDevice.create_params()
        params.group_id = self.SHARED_VDEVICE_GROUP_ID
        self._vdevice = VDevice(params)

        self._speech2text = Speech2Text(self._vdevice, str(hef_path))
        print(f"[STT] Hailo GenAI Whisper loaded: {hef_path}")

    def transcribe(self, audio_path: str, language: str = None) -> str:
        # Load audio as float32
        audio_data = self._load_audio(audio_path)

        # Transcribe
        kwargs = {
            "audio_data": audio_data,
            "language": language or "ko",
            "timeout_ms": 30000,
        }
        if self._Speech2TextTask is not None:
            kwargs["task"] = self._Speech2TextTask.TRANSCRIBE

        segments = self._speech2text.generate_all_segments(**kwargs)

        if segments and len(segments) > 0:
            return ''.join(seg.text for seg in segments).strip()
        return ""

    @staticmethod
    def _load_audio(audio_path: str) -> np.ndarray:
        """Load audio file as float32 numpy array (16kHz mono)."""
        try:
            # Try with wave module first (WAV files)
            with wave.open(audio_path, 'rb') as wav:
                raw = wav.readframes(wav.getnframes())
                audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                return audio.astype('<f4')
        except wave.Error:
            pass

        # Fallback: use librosa/soundfile for other formats
        try:
            import soundfile as sf
            audio, sr = sf.read(audio_path, dtype='float32')
            if sr != 16000:
                import librosa
                audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
            return audio.astype('<f4')
        except Exception:
            pass

        # Last resort: ffmpeg → wav → retry
        import subprocess
        tmp_wav = audio_path + ".tmp.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-i", audio_path, "-ar", "16000", "-ac", "1", "-f", "wav", tmp_wav],
            capture_output=True
        )
        with wave.open(tmp_wav, 'rb') as wav:
            raw = wav.readframes(wav.getnframes())
            audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        os.unlink(tmp_wav)
        return audio.astype('<f4')

    def release(self):
        try:
            self._speech2text.release()
        except Exception:
            pass
        try:
            self._vdevice.release()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Backend: original openai-whisper (CPU fallback)
# ---------------------------------------------------------------------------
class OriginalWhisperTranscriber:
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
def auto_detect_backend() -> str:
    try:
        from hailo_platform import VDevice
        from hailo_platform.genai import Speech2Text
        # Check if Hailo device is available
        params = VDevice.create_params()
        params.group_id = "shared_vdevice"
        vd = VDevice(params)
        vd.release()
        print("[STT] Auto-detect: Hailo-10H GenAI available → using hailo_genai")
        return "hailo_genai"
    except Exception as e:
        print(f"[STT] Auto-detect: Hailo GenAI not available ({e}) → using CPU (faster-whisper)")
        return "fast"


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------
@app.route("/transcribe", methods=["POST"])
def transcribe_endpoint():
    global text
    try:
        if "audio" not in request.files:
            return jsonify({"success": False, "error": "Missing 'audio' file"}), 400

        file = request.files.get("audio")
        if file is None or file.filename == "":
            return jsonify({"success": False, "error": "No file selected"}), 400

        if transcriber is None:
            return jsonify({"success": False, "error": "Model not initialized"}), 500

        language = request.form.get("language") or None
        suffix = Path(file.filename).suffix or ".wav"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            file.save(tmp.name)
            try:
                text = transcriber.transcribe(tmp.name, language=language)
            finally:
                os.unlink(tmp.name)

        return jsonify({"success": True, "text": text})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def main():
    parser = argparse.ArgumentParser(description="STT Server (Whisper)")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--model", type=str, default="small",
                        choices=["tiny", "base", "small", "medium", "large"])
    parser.add_argument("--backend", type=str, default="auto",
                        choices=["auto", "hailo_genai", "fast", "whisper"])
    parser.add_argument("--hef-path", type=str, default=None,
                        help="Path to Whisper HEF (for hailo_genai backend)")
    args = parser.parse_args()

    backend = args.backend
    if backend == "auto":
        backend = auto_detect_backend()

    global transcriber
    print("=" * 60)
    print(f"Initializing STT Server (backend: {backend})...")
    print("=" * 60)

    if backend == "hailo_genai":
        try:
            transcriber = HailoGenAIWhisperTranscriber(hef_path=args.hef_path)
        except Exception as e:
            print(f"[STT] Hailo GenAI init failed ({e}), falling back to CPU")
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
