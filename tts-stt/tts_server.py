#!/usr/bin/env python3
"""
TTS Server
Accepts text via REST API, synthesizes with Sherpa-ONNX, plays audio, then responds when speaking is over.
"""

import os
import time
import argparse
from pathlib import Path

import numpy as np
import sherpa_onnx
import sounddevice as sd
from flask import Flask, request, jsonify

# ALSA/PortAudio often reject 22050 Hz; resample to device-supported rate.
# Set at startup via _detect_playback_sample_rate().
PLAYBACK_SAMPLE_RATE = 48000

app = Flask(__name__)
synthesizer = None
debug_mode = False

# TTS model paths (relative to script or cwd)
SCRIPT_DIR = Path(__file__).parent.resolve()
MODEL_DIR = SCRIPT_DIR / "tts_model" / "sherpa-onnx-korean-tts" / "vits-mimic3-ko_KO-kss_low"
DATA_DIR = MODEL_DIR / "espeak-ng-data"


def _detect_playback_sample_rate() -> int:
    """Use default output device's preferred rate; fallback to 48000 then 44100."""
    try:
        out_id = sd.default.device[1]
        info = sd.query_devices(out_id, "output")
        rate = int(info["default_samplerate"])
        if rate > 0:
            return rate
    except Exception:
        pass
    return 48000


def resample_audio(samples: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Resample to target_sr so ALSA/PortAudio accepts the rate. Uses numpy only."""
    if orig_sr == target_sr:
        return samples
    n = len(samples)
    num_new = int(round(n * target_sr / orig_sr))
    x_old = np.arange(n, dtype=np.float64)
    x_new = np.linspace(0, n - 1, num_new, dtype=np.float64)
    out = np.interp(x_new, x_old, samples.astype(np.float64)).astype(np.float32)
    return out


def _play_audio(samples: np.ndarray, sample_rate: int) -> None:
    """Play samples at sample_rate; on PortAudio error try 48000 then 44100."""
    rates_to_try = [sample_rate]
    if sample_rate not in (48000, 44100):
        rates_to_try.extend([48000, 44100])
    last_err = None
    for sr in rates_to_try:
        play_s = resample_audio(samples, sample_rate, sr) if sr != sample_rate else samples
        try:
            sd.play(play_s, sr)
            sd.wait()
            return
        except sd.PortAudioError as e:
            last_err = e
            continue
    raise last_err or sd.PortAudioError("Playback failed")


def create_synthesizer(provider="cuda"):
    """Create Sherpa-ONNX offline TTS synthesizer."""
    config = sherpa_onnx.OfflineTtsConfig(
        model=sherpa_onnx.OfflineTtsModelConfig(
            vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                model=str(MODEL_DIR / "ko_KO-kss_low.onnx"),
                lexicon="",
                tokens=str(MODEL_DIR / "tokens.txt"),
                data_dir=str(DATA_DIR),
            ),
            provider=provider,
            debug=False,
            num_threads=1,
        )
    )
    return sherpa_onnx.OfflineTts(config)


@app.route("/health", methods=["GET"])
def health_check():
    """Server health check."""
    return jsonify({
        "status": "healthy",
        "synthesizer_loaded": synthesizer is not None,
    })


@app.route("/speak", methods=["POST"])
def speak():
    """
    Synthesize text to speech, play it, then respond when playback is over.

    Request body (JSON):
        {
            "text": "string to speak",
            "speed": 0.5  (optional, 1.0 is normal)
        }

    Response (JSON):
        {
            "success": true,
            "message": "speaking finished"
        }
    """
    try:
        if not request.is_json:
            return jsonify({
                "success": False,
                "error": "Content-Type must be application/json",
            }), 400

        data = request.get_json()
        if "text" not in data:
            return jsonify({
                "success": False,
                "error": "Missing 'text' field in request body",
            }), 400

        text = data["text"].strip()
        if not text:
            return jsonify({
                "success": False,
                "error": "Text cannot be empty",
            }), 400

        speed = float(data.get("speed", 1.0))
        speed = max(0.25, min(3.0, speed))

        if synthesizer is None:
            return jsonify({
                "success": False,
                "error": "TTS synthesizer not initialized",
            }), 500

        # Generate audio (measure inference time in debug mode)
        speaker_id = 0
        if debug_mode:
            t0 = time.perf_counter()
        audio = synthesizer.generate(
            text=text,
            sid=speaker_id,
            speed=speed,
        )
        if debug_mode:
            inference_time = time.perf_counter() - t0
            num_samples = len(audio.samples)
            duration_sec = num_samples / audio.sample_rate
            rtf = inference_time / duration_sec if duration_sec > 0 else 0
            print(f"[debug] inference: {inference_time:.3f}s | audio: {duration_sec:.3f}s | RTF: {rtf:.3f}")

        # Play audio and block until finished (resample if needed for ALSA compatibility)
        samples = np.asarray(audio.samples, dtype=np.float32)
        sample_rate = audio.sample_rate
        _play_audio(samples, sample_rate)

        response_data = {
            "success": True,
            "message": "speaking finished",
        }
        if debug_mode:
            response_data["inference_time_seconds"] = round(inference_time, 4)
            response_data["audio_duration_seconds"] = round(duration_sec, 4)
            response_data["rtf"] = round(rtf, 4)
        return jsonify(response_data)

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


def main():
    parser = argparse.ArgumentParser(description="TTS Server (Sherpa-ONNX)")
    parser.add_argument("--port", type=int, default=8002, help="Server port (default: 8002)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Server host (default: 0.0.0.0)")
    parser.add_argument(
        "--provider",
        type=str,
        default="cuda",
        choices=["cpu", "cuda"],
        help="ONNX provider (default: cuda)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Log and return inference speed (inference time, audio duration, RTF)",
    )
    args = parser.parse_args()

    global synthesizer, debug_mode, PLAYBACK_SAMPLE_RATE
    debug_mode = args.debug
    PLAYBACK_SAMPLE_RATE = _detect_playback_sample_rate()
    print("=" * 60)
    print("Initializing TTS Server (Sherpa-ONNX)...")
    print("=" * 60)
    print(f"Playback sample rate (from default device): {PLAYBACK_SAMPLE_RATE} Hz")
    synthesizer = create_synthesizer(provider=args.provider)
    print("Synthesizer ready.")
    print("-" * 60)
    print(f"Server: http://{args.host}:{args.port}")
    print("  GET  /health  : Health check")
    print("  POST /speak   : Send JSON {\"text\": \"...\"} -> speak and respond when done")
    if debug_mode:
        print("  [debug] Inference speed will be logged and included in /speak response")
    print("=" * 60)

    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
