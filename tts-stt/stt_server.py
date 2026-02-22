#!/usr/bin/env python3
"""
STT Server
Accepts a recorded voice file via REST API, transcribes with Whisper, returns text.
"""

import os
import tempfile
import argparse
from pathlib import Path

import whisper
from flask import Flask, request, jsonify

app = Flask(__name__)
model = None

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

def load_whisper_model(model_name: str = "tiny"):
    """Load Whisper model."""
    return whisper.load_model(model_name)

@app.route("/transcribe", methods=["POST"])
def transcribe():
    """
    Transcribe uploaded audio file to text.

    Request: multipart/form-data with field "audio" (file).
    Supported formats: WAV, M4A, MP3, FLAC, etc. (ffmpeg).

    Response (JSON):
        {
            "success": true,
            "text": "transcribed string"
        }
    """
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

        if model is None:
            return jsonify({
                "success": False,
                "error": "Whisper model not initialized",
            }), 500

        language = request.form.get("language") or None
        suffix = Path(file.filename).suffix or ".wav"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            file.save(tmp.name)
            try:
                result = model.transcribe(tmp.name, language=language)
                text = (result.get("text") or "").strip()
            finally:
                os.unlink(tmp.name)

        # send text to GUI client
        # function here

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
    parser.add_argument("--port", type=int, default=8001, help="Server port (default: 8001)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Server host (default: 0.0.0.0)")
    parser.add_argument(
        "--model",
        type=str,
        default="small",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size (default: small)",
    )
    args = parser.parse_args()

    global model
    print("=" * 60)
    print("Initializing STT Server (Whisper)...")
    print("=" * 60)
    model = load_whisper_model(model_name=args.model)
    print(f"Whisper model loaded: {args.model}")
    print("-" * 60)
    print(f"Server: http://{args.host}:{args.port}")
    print("  GET  /health     : Health check")
    print("  POST /transcribe : Upload audio file (multipart 'audio') -> text")
    print("=" * 60)

    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
