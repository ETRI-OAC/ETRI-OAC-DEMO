#!/usr/bin/env python3
"""
TTS Server
Accepts text via REST API, synthesizes with Sherpa-ONNX, plays audio, then responds when speaking is over.
"""

import os
import time
import argparse
from pathlib import Path

import sherpa_onnx
import sounddevice as sd
from flask import Flask, request, jsonify

app = Flask(__name__)
synthesizer = None
debug_mode = False

# TTS model paths (relative to script or cwd)
SCRIPT_DIR = Path(__file__).parent.resolve()
MODEL_DIR = SCRIPT_DIR / "tts_model" / "sherpa-onnx-korean-tts" / "vits-mimic3-ko_KO-kss_low"
DATA_DIR = MODEL_DIR / "espeak-ng-data"


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

        # Play audio and block until finished
        samples = audio.samples
        sample_rate = audio.sample_rate
        sd.play(samples, sample_rate)
        sd.wait()

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

    global synthesizer, debug_mode
    debug_mode = args.debug
    print("=" * 60)
    print("Initializing TTS Server (Sherpa-ONNX)...")
    print("=" * 60)
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
