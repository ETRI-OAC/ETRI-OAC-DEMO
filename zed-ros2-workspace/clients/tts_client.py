#!/usr/bin/env python3
"""
TTS Client
Sends text to TTS server; server speaks and responds when speaking is over.
"""

import time
import requests
import argparse
from typing import Tuple, Optional, Dict, Any


class TTSClient:
    """Client for TTS server API."""

    def __init__(self, api_url: str = "http://localhost:8002"):
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

    def speak(
        self,
        text: str,
        speed: float = 1.0,
        measure_time: bool = False,
    ) -> Tuple[Dict[str, Any], Optional[float]]:
        """
        Send text to server; server speaks and responds when done.

        Args:
            text: Text to synthesize and speak.
            speed: Speech speed (default 1.0).
            measure_time: Whether to measure response time.

        Returns:
            (response dict, elapsed seconds or None).
        """
        payload = {"text": text, "speed": speed}
        start = time.time() if measure_time else None
        response = requests.post(
            f"{self.api_url}/speak",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=120,
        )
        response.raise_for_status()
        result = response.json()
        elapsed = (time.time() - start) if measure_time else None
        return result, elapsed


def main():
    parser = argparse.ArgumentParser(description="TTS Client")
    parser.add_argument(
        "--text",
        type=str,
        default="원하시는 옵션을 선택해주세요.",
        help="Text to speak (default: 원하시는 옵션을 선택해주세요.)",
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default="http://localhost:8002",
        help="TTS API URL (default: http://localhost:8002)",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Speech speed (default: 1.0)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("TTS Client")
    print("=" * 60)
    print(f"Text: {args.text}")
    print(f"API URL: {args.api_url}")
    print("-" * 60)

    client = TTSClient(api_url=args.api_url)

    print("Checking server...")
    if not client.check_server_health():
        print(f"Cannot connect to server: {args.api_url}")
        print("Ensure the TTS server is running.")
        return
    print("Server OK.")
    print("-" * 60)

    try:
        print("Sending speak request (server will speak then respond)...")
        response, elapsed = client.speak(args.text, speed=args.speed, measure_time=True)
        if response.get("success"):
            print("Response: speaking finished.")
            if elapsed is not None:
                print(f"Total time (request -> response after playback): {elapsed:.3f} s")
        else:
            print(f"Error: {response.get('error', 'Unknown')}")
    except requests.exceptions.ConnectionError:
        print("Connection failed. Is the TTS server running?")
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
