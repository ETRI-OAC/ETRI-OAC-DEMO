#!/usr/bin/env python3
"""
STT Client
Sends a recorded voice file to STT server and receives transcribed text.
"""

import time
import requests
import argparse
from pathlib import Path
from typing import Tuple, Optional, Dict, Any


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
        default=None,
        help="Language code (e.g. ko, en); omit for auto-detect",
    )
    args = parser.parse_args()

    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(f"Audio file not found: {audio_path}")
        return

    print("=" * 60)
    print("STT Client")
    print("=" * 60)
    print(f"Audio: {audio_path}")
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
