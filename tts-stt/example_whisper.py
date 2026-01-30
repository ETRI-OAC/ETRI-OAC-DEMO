import whisper
import soundfile as sf
import librosa
import numpy as np
import time
import os
import argparse

def transcribe_audio_file(audio_path, model_name="tiny", language=None):
    """
    오디오 파일을 입력받아 텍스트로 변환
    지원 포맷: WAV, M4A, MP3, FLAC 등 (ffmpeg가 지원하는 모든 포맷)
    
    Args:
        audio_path: 입력 오디오 파일 경로
        model_name: Whisper 모델 크기 (tiny, base, small, medium, large)
        language: 언어 코드 (예: 'ko', 'en'). None이면 자동 감지
    """
    print(f"Loading Whisper model: {model_name}")
    model = whisper.load_model(model_name)
    
    print(f"Loading audio file: {audio_path}")
    # whisper.load_audio는 ffmpeg를 사용하여 다양한 오디오 포맷(m4a, mp3, wav, flac 등)을 지원하며
    # 자동으로 16kHz로 리샘플링하고 정규화합니다
    audio = whisper.load_audio(audio_path)
    
    # 오디오를 패딩/트리밍하여 30초로 맞춤
    audio = whisper.pad_or_trim(audio)
    
    # log-Mel spectrogram 생성
    mel = whisper.log_mel_spectrogram(audio, n_mels=model.dims.n_mels).to(model.device)
    
    # 언어 자동 감지 (language가 None인 경우)
    if language is None:
        print("Detecting language...")
        _, probs = model.detect_language(mel)
        detected_language = max(probs, key=probs.get)
        print(f"Detected language: {detected_language} (probability: {probs[detected_language]:.2f})")
        language = detected_language
    
    # 디코딩 옵션 설정
    options = whisper.DecodingOptions(language=language)
    
    # STT 수행
    print("Transcribing audio...")
    start_time = time.time()
    result = whisper.decode(model, mel, options)
    elapsed_time = time.time() - start_time
    
    print(f"\n--- Recognized Text ---")
    print(result.text)
    print(f"\nTime taken: {elapsed_time:.2f} seconds")
    
    return result.text


def transcribe_with_full_api(audio_path, model_name="tiny", language=None):
    """
    Whisper의 전체 API를 사용하여 더 자세한 정보를 얻는 버전
    """
    print(f"Loading Whisper model: {model_name}")
    model = whisper.load_model(model_name)
    
    print(f"Transcribing audio file: {audio_path}")
    start_time = time.time()
    
    # transcribe 메서드는 ffmpeg를 통해 다양한 오디오 포맷을 지원하며
    # 자동으로 언어 감지, 디코딩 등을 수행합니다
    result = model.transcribe(audio_path, language=language)
    
    elapsed_time = time.time() - start_time
    
    print(f"\n--- Transcription Results ---")
    print(f"Language: {result['language']}")
    print(f"Text: {result['text']}")
    print(f"\nTime taken: {elapsed_time:.2f} seconds")
    
    return result


def record_and_transcribe(duration=5, device_id=None, model_name="tiny", language=None):
    """
    마이크로 녹음하고 실시간으로 STT 수행
    
    Args:
        duration: 녹음 시간 (초)
        device_id: 오디오 디바이스 ID (None이면 기본 디바이스)
        model_name: Whisper 모델 크기
        language: 언어 코드
    """
    import sounddevice as sd
    
    DEVICE_RATE = 48000  # 마이크 샘플링 레이트
    WHISPER_RATE = 16000  # Whisper가 요구하는 샘플링 레이트
    CHANNELS = 1
    D_TYPE = 'float32'
    
    print(f"Recording for {duration} seconds at {DEVICE_RATE} Hz...")
    my_recording = sd.rec(
        int(duration * DEVICE_RATE),
        samplerate=DEVICE_RATE,
        channels=CHANNELS,
        device=device_id,
        dtype=D_TYPE
    )
    
    sd.wait()
    print("Recording finished.")
    
    # 리샘플링
    print(f"Resampling audio from {DEVICE_RATE} Hz to {WHISPER_RATE} Hz...")
    my_recording_flat = my_recording.flatten()
    audio_ready = librosa.resample(
        my_recording_flat,
        orig_sr=DEVICE_RATE,
        target_sr=WHISPER_RATE,
        res_type='polyphase'
    )
    print("Resampling complete.")
    
    # 임시 파일로 저장하여 transcribe 사용
    temp_file = "/tmp/temp_recording.wav"
    sf.write(temp_file, audio_ready, WHISPER_RATE, subtype='PCM_16')
    
    # STT 수행
    result = transcribe_with_full_api(temp_file, model_name=model_name, language=language)
    
    # 임시 파일 삭제
    os.remove(temp_file)
    
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Whisper STT Example")
    parser.add_argument(
        "--audio",
        type=str,
        default=None,
        help="Path to audio file (WAV, M4A, MP3, FLAC 등 지원). If not provided, will record from microphone."
    )
    parser.add_argument(
        "--model",
        type=str,
        default="tiny",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size (default: tiny)"
    )
    parser.add_argument(
        "--language",
        type=str,
        default=None,
        help="Language code (e.g., 'ko', 'en'). If not provided, will auto-detect."
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=5,
        help="Recording duration in seconds (only used when --audio is not provided)"
    )
    parser.add_argument(
        "--device-id",
        type=int,
        default=None,
        help="Audio device ID for recording (only used when --audio is not provided)"
    )
    parser.add_argument(
        "--full-api",
        action="store_true",
        help="Use full Whisper API (transcribe method) instead of decode method"
    )
    
    args = parser.parse_args()
    
    if args.audio:
        # 파일에서 STT 수행
        if os.path.exists(args.audio):
            if args.full_api:
                transcribe_with_full_api(args.audio, model_name=args.model, language=args.language)
            else:
                transcribe_audio_file(args.audio, model_name=args.model, language=args.language)
        else:
            print(f"Error: Audio file not found: {args.audio}")
    else:
        # 마이크로 녹음 후 STT 수행
        try:
            record_and_transcribe(
                duration=args.duration,
                device_id=args.device_id,
                model_name=args.model,
                language=args.language
            )
        except ImportError:
            print("Error: sounddevice is required for recording. Install it with: pip install sounddevice")
        except Exception as e:
            print(f"Error during recording: {e}")

