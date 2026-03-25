#!/usr/bin/env python3
"""
STT Client
Sends a recorded voice file to STT server and receives transcribed text.
Can record from the default microphone (sounddevice + pydub) and send to server without saving.
"""

import time
import wave
import requests
import argparse
from io import BytesIO
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

import sounddevice as sd
import numpy as np
from pydub import AudioSegment


def _record_sounddevice(duration_sec: int, sample_rate: int, channels: int):
    """Record using InputStream and stop after duration_sec (avoids sd.wait() hanging on some devices)."""
    block_ms = 100
    block_frames = int(sample_rate * block_ms / 1000) * channels
    chunks = []
    with sd.InputStream(
        samplerate=sample_rate,
        channels=channels,
        dtype="float32",
        blocksize=block_frames,
    ) as stream:
        deadline = time.monotonic() + duration_sec
        while time.monotonic() < deadline:
            frame, _ = stream.read(block_frames)
            chunks.append(frame)
        recording = np.concatenate(chunks, axis=0)
        return recording[: int(duration_sec * sample_rate) * channels].reshape(-1, channels)


class STTClient:
    """Client for STT server API."""

    def __init__(self, api_url: str = "http://localhost:8001"):
        self.api_url = api_url.rstrip("/")

    def check_server_health(self) -> bool:
        """Check server health. Returns True if healthy."""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=5)
            response.raise_for_status()
            data = response.json()
            return data.get("status") == "healthy"
        except Exception:
            return False

    def record_from_mic(
        self,
        duration_sec: float,
        sample_rate: int = 44100,
        channels: int = 1,
    ) -> bytes:
        """
        Record from the default microphone for the given duration (no file saved).

        Uses sounddevice (PortAudio). Returns audio as .m4a (AAC) bytes.

        Args:
            duration_sec: Recording length in seconds.
            sample_rate: Sample rate in Hz (default 44100).
            channels: Number of channels (default 1).

        Returns:
            Audio bytes (m4a format) to send to the server.
        """
        duration_sec = float(duration_sec)
        recording = _record_sounddevice(int(round(duration_sec)), sample_rate, channels)
        rec_int16 = (np.clip(recording, -1.0, 1.0) * 32767).astype(np.int16)

        wav_bio = BytesIO()
        with wave.open(wav_bio, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(rec_int16.tobytes())
        wav_bio.seek(0)
        segment = AudioSegment.from_wav(wav_bio)
        m4a_bio = BytesIO()
        segment.export(m4a_bio, format="ipod", codec="aac")
        m4a_bio.seek(0)
        return m4a_bio.read()

    def transcribe_from_mic(
        self,
        duration_sec: float,
        sample_rate: int = 44100,
        channels: int = 1,
        language: Optional[str] = None,
        measure_time: bool = False,
    ) -> Tuple[Dict[str, Any], Optional[float]]:
        """
        Record from the default microphone for the given duration and send to server for transcription.

        No file is saved; recording and upload happen in one process.

        Args:
            duration_sec: Recording length in seconds.
            sample_rate: Sample rate in Hz (default 44100).
            channels: Number of channels (default 1).
            language: Optional language code (e.g. 'ko', 'en'); None = auto-detect.
            measure_time: Whether to measure response time.

        Returns:
            (response dict with 'success' and 'text', elapsed seconds or None).
        """
        audio_bytes = self.record_from_mic(duration_sec, sample_rate=sample_rate, channels=channels)
        return self.transcribe_audio(audio_bytes, language=language, measure_time=measure_time)

    def transcribe_audio(
        self,
        audio_bytes: bytes,
        language: Optional[str] = None,
        measure_time: bool = False,
    ) -> Tuple[Dict[str, Any], Optional[float]]:
        """
        Send audio bytes to server and get transcribed text (does not read from file).

        Args:
            audio_bytes: Audio file content (e.g. m4a, wav bytes).
            language: Optional language code (e.g. 'ko', 'en'); None = auto-detect.
            measure_time: Whether to measure response time.

        Returns:
            (response dict with 'success' and 'text', elapsed seconds or None).
        """
        start = time.time() if measure_time else None
        files = {"audio": ("audio.m4a", BytesIO(audio_bytes))}
        data = {} if language is None else {"language": language}
        response = requests.post(
            f"{self.api_url}/transcribe",
            files=files,
            data=data,
            timeout=120,
        )
        response.raise_for_status()
        result = response.json()
        elapsed = (time.time() - start) if measure_time else None
        return result, elapsed

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        measure_time: bool = False,
    ) -> Tuple[Dict[str, Any], Optional[float]]:
        """
        Send audio file to server and get transcribed text.

        Args:
            audio_path: Path to audio file (WAV, M4A, MP3, FLAC, etc.).
            language: Optional language code (e.g. 'ko', 'en'); None = auto-detect.
            measure_time: Whether to measure response time.

        Returns:
            (response dict with 'success' and 'text', elapsed seconds or None).
        """
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        start = time.time() if measure_time else None
        with open(path, "rb") as f:
            files = {"audio": (path.name, f)}
            data = {} if language is None else {"language": language}
            response = requests.post(
                f"{self.api_url}/transcribe",
                files=files,
                data=data,
                timeout=120,
            )
        response.raise_for_status()
        result = response.json()
        elapsed = (time.time() - start) if measure_time else None
        return result, elapsed


def main():
    parser = argparse.ArgumentParser(description="STT Client")
    parser.add_argument(
        "--audio",
        type=str,
        default="example_voice.m4a",
        help="Path to audio file (default: example_voice.m4a)",
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default="http://localhost:8001",
        help="STT API URL (default: http://localhost:8001)",
    )
    parser.add_argument(
        "--language",
        type=str,
        default='ko',
        help="Language code (e.g. ko, en); omit for auto-detect",
    )
    parser.add_argument(
        "--use-mic",
        action="store_true",
        help="Use microphone to record audio",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("STT Client")
    print("=" * 60)
    print(f"API URL: {args.api_url}")
    print("-" * 60)

    client = STTClient(api_url=args.api_url)

    print("Checking server...")
    if not client.check_server_health():
        print(f"Cannot connect to server: {args.api_url}")
        print("Ensure the STT server is running.")
        return
    print("Server OK.")
    print("-" * 60)

    try:
        if args.use_mic:
            print("Recording from microphone...")
            response, elapsed = client.transcribe_from_mic(duration_sec=5, language=args.language, measure_time=True)
        else:
            audio_path = Path(args.audio)
            if not audio_path.exists():
                print(f"Audio file not found: {audio_path}")
                return
            else:
                print(f"Audio: {audio_path}")
            print("Sending transcribe request...")
            response, elapsed = client.transcribe(
                str(audio_path),
                language=args.language,
                measure_time=True,
            )

        if response.get("success"):
            text = response.get("text", "")
            print("Transcribed text:")
            print("-" * 60)
            print(text or "(empty)")
            print("-" * 60)
            if elapsed is not None:
                print(f"Time: {elapsed:.3f} s")
        else:
            print(f"Error: {response.get('error', 'Unknown')}")
    except requests.exceptions.ConnectionError:
        print("Connection failed. Is the STT server running?")
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(e.response.text)
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    print("=" * 60)


if __name__ == "__main__":
    main()
