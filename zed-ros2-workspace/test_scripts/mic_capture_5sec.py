#!/usr/bin/env python3
"""
Test script: capture microphone input for 5 seconds and save as .m4a.

Option A (needs PortAudio): pip install sounddevice numpy pydub
  - System: apt install libportaudio2 ffmpeg

Option B (no PortAudio): only ffmpeg required
  - System: apt install ffmpeg
  - Uses ffmpeg to record from default input (pulse or alsa).
"""

import os
import tempfile
import time
import sounddevice as sd
import numpy as np
from pydub import AudioSegment

def record_sounddevice(duration_sec: int, sample_rate: int, channels: int):
    """Record using InputStream and stop after duration_sec (avoids sd.wait() hanging on some devices)."""
    block_ms = 100
    block_frames = int(sample_rate * block_ms / 1000) * channels
    total_frames = int(duration_sec * sample_rate) * channels
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
        # Trim to exact duration
        recording = np.concatenate(chunks, axis=0)
        return recording[: int(duration_sec * sample_rate) * channels].reshape(-1, channels)


def main():
    duration_sec = 5
    sample_rate = 44100
    channels = 1
    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "mic_recording.m4a",
    )

    print(f"Recording from default microphone for {duration_sec} seconds...")
    print("Speak now.")
    recording = record_sounddevice(duration_sec, sample_rate, channels)
    print("Recording finished. Saving to .m4a ...")

    rec_int16 = (np.clip(recording, -1.0, 1.0) * 32767).astype(np.int16)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        temp_wav = f.name
    try:
        import wave
        with wave.open(temp_wav, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(rec_int16.tobytes())
        segment = AudioSegment.from_wav(temp_wav)
        segment.export(output_path, format="ipod", codec="aac")
    finally:
        if os.path.exists(temp_wav):
            os.remove(temp_wav)

    print(f"Saved: {output_path}")

if __name__ == "__main__":
    main()
