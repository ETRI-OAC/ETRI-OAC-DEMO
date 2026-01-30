import sherpa_onnx
import wave
import numpy as np
import os

import soundfile as sf
import time

# TTS model configurations
MODEL_DIR = "./tts_model/sherpa-onnx-korean-tts/vits-mimic3-ko_KO-kss_low"
DATA_DIR = "./tts_model/sherpa-onnx-korean-tts/vits-mimic3-ko_KO-kss_low/espeak-ng-data"

config = sherpa_onnx.OfflineTtsConfig(
    model=sherpa_onnx.OfflineTtsModelConfig(
        vits=sherpa_onnx.OfflineTtsVitsModelConfig(
            model=os.path.join(MODEL_DIR, "ko_KO-kss_low.onnx"),
            lexicon="", # os.path.join(MODEL_DIR, "lexicon.txt")
            tokens=os.path.join(MODEL_DIR, "tokens.txt"),
            data_dir=DATA_DIR,
            # Set provider to 'cuda' for GPU acceleration on Jetson
        ),
        provider="cuda", 
        debug=True,
        num_threads=1,
    )
)
synthesizer = sherpa_onnx.OfflineTts(config)

# start generating audio 
start_time = time.time()
text_to_synthesize = "원하시는 옵션을 선택해주세요. "
print(f"Synthesizing: '{text_to_synthesize}'")
speaker_id = 0 # The default speaker ID is 0 for this single-speaker model
audio = synthesizer.generate(
    text=text_to_synthesize, 
    sid=speaker_id,
    speed=0.5  # 1.0 is normal speed
)
end_time = time.time()
print(f"Time taken: {end_time - start_time} seconds")
# save wav file 
output_filename = "korean_output.wav"
sf.write(output_filename, audio.samples, audio.sample_rate, subtype='PCM_16')
print(f"TTS Generation complete. Output saved to: {output_filename}")

"""
THINGS TO SOLVE
- ONNX NOT SUPPORTED
"""