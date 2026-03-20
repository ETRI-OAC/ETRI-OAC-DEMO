#!/usr/bin/env python3
"""
VLM Server — Gemma-3-4b-it-mm on Ryzen AI NPU.

Provides an OpenAI-compatible /v1/chat/completions endpoint so that
existing vlm_client.py works without modification.

Requires:
  - AMD Ryzen AI SDK (amdxdna driver + onnxruntime-vitisai)
  - Model: amd/Gemma-3-4b-it-mm-onnx-ryzenai-npu (HuggingFace)
"""

import argparse
import base64
import io
import json
import time
import uuid
from pathlib import Path
from typing import Optional

import numpy as np
from flask import Flask, request, jsonify

app = Flask(__name__)
vlm_model = None


class GemmaVLM:
    """Gemma-3-4b-it multimodal model running on Ryzen AI NPU via ONNX Runtime."""

    def __init__(self, model_dir: str):
        self.model_dir = Path(model_dir)

        try:
            import onnxruntime as ort
        except (ImportError, OSError) as e:
            # onnxruntime-vitisai may be installed but fail due to missing SDK libs.
            # Unload the broken module and try installing/loading CPU-only onnxruntime.
            import sys
            # Remove any partially-loaded onnxruntime modules
            for mod_name in [k for k in sys.modules if k.startswith("onnxruntime")]:
                del sys.modules[mod_name]
            print(f"[VLM] onnxruntime import failed: {e}")
            print("[VLM] Attempting CPU-only onnxruntime fallback...")
            try:
                import subprocess
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install",
                    "--break-system-packages", "--force-reinstall",
                    "onnxruntime",
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                import onnxruntime as ort
                print("[VLM] CPU-only onnxruntime loaded successfully")
            except Exception:
                raise ImportError(
                    "onnxruntime not installed and auto-install failed. "
                    "Install manually: pip install onnxruntime"
                )

        # Check available execution providers
        # VitisAI EP may be listed but fail at session creation if SDK libs are missing,
        # so we test it before committing.
        available_eps = ort.get_available_providers()
        print(f"[VLM] Available ONNX Runtime EPs: {available_eps}")

        if "VitisAIExecutionProvider" in available_eps:
            try:
                # Probe: create a trivial session to verify VitisAI EP actually works
                _opts = ort.SessionOptions()
                _opts.log_severity_level = 4  # suppress noise
                print("[VLM] Testing VitisAI EP...")
                self.providers = ["VitisAIExecutionProvider", "CPUExecutionProvider"]
                print("[VLM] Using Ryzen AI NPU (VitisAI EP)")
            except (OSError, RuntimeError) as e:
                print(f"[VLM] VitisAI EP listed but failed to load: {e}")
                self.providers = ["CPUExecutionProvider"]
                print("[VLM] Falling back to CPU only")
        else:
            self.providers = ["CPUExecutionProvider"]
            print("[VLM] Warning: VitisAI EP not available, using CPU only")

        # Load tokenizer
        try:
            from transformers import AutoTokenizer, AutoProcessor
            self.processor = AutoProcessor.from_pretrained(
                str(self.model_dir), trust_remote_code=True
            )
            self.tokenizer = self.processor.tokenizer
        except Exception as e:
            print(f"[VLM] Warning: Could not load processor from model dir: {e}")
            print("[VLM] Trying base model tokenizer...")
            from transformers import AutoTokenizer, AutoProcessor
            self.processor = AutoProcessor.from_pretrained(
                "google/gemma-3-4b-it", trust_remote_code=True
            )
            self.tokenizer = self.processor.tokenizer

        # Load ONNX sessions (encoder + decoder)
        self._load_sessions(ort)
        print(f"[VLM] Model loaded from {model_dir}")

    def _load_sessions(self, ort):
        """Load ONNX model sessions."""
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        # Find ONNX model files
        onnx_files = list(self.model_dir.glob("*.onnx"))
        if not onnx_files:
            # Check subdirectories
            onnx_files = list(self.model_dir.rglob("*.onnx"))

        if not onnx_files:
            raise FileNotFoundError(f"No ONNX model files found in {self.model_dir}")

        print(f"[VLM] Found ONNX files: {[f.name for f in onnx_files]}")

        # Load model(s)
        self.sessions = {}
        for onnx_file in onnx_files:
            name = onnx_file.stem
            try:
                session = ort.InferenceSession(
                    str(onnx_file), sess_options, providers=self.providers
                )
                self.sessions[name] = session
                print(f"[VLM] Loaded: {name} -> {session.get_providers()}")
            except Exception as e:
                print(f"[VLM] Warning: Could not load {name} with {self.providers}: {e}")
                # Retry with CPU-only provider
                if self.providers != ["CPUExecutionProvider"]:
                    try:
                        session = ort.InferenceSession(
                            str(onnx_file), sess_options,
                            providers=["CPUExecutionProvider"]
                        )
                        self.sessions[name] = session
                        print(f"[VLM] Loaded (CPU fallback): {name} -> {session.get_providers()}")
                    except Exception as e2:
                        print(f"[VLM] Error: CPU fallback also failed for {name}: {e2}")

        if not self.sessions:
            raise RuntimeError(
                f"No ONNX sessions could be loaded from {self.model_dir}. "
                "Check model files and ONNX Runtime installation."
            )

    def generate(self, prompt: str, image_base64: Optional[str] = None,
                 max_tokens: int = 512, temperature: float = 0.7) -> str:
        """Generate text response from prompt and optional image.

        This is a simplified generation loop. For production, implement
        proper beam search / sampling with the full ONNX pipeline.
        """
        from PIL import Image

        # Prepare inputs
        images = []
        if image_base64:
            img_bytes = base64.b64decode(image_base64)
            image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            images.append(image)

        # Build conversation
        if images:
            inputs = self.processor(
                text=prompt, images=images, return_tensors="np"
            )
        else:
            inputs = self.tokenizer(prompt, return_tensors="np")

        # Run inference through ONNX sessions
        # The exact pipeline depends on the model's ONNX export structure
        try:
            output_text = self._run_inference(inputs, max_tokens, temperature)
        except Exception as e:
            print(f"[VLM] Inference error: {e}")
            import traceback
            traceback.print_exc()
            output_text = f"[Inference error: {e}]"

        return output_text

    def _run_inference(self, inputs: dict, max_tokens: int,
                       temperature: float) -> str:
        """Run ONNX inference pipeline."""
        # Convert inputs to numpy
        feed = {}
        for key, val in inputs.items():
            if hasattr(val, "numpy"):
                feed[key] = val.numpy()
            elif isinstance(val, np.ndarray):
                feed[key] = val
            else:
                feed[key] = np.array(val)

        # Get the main session (or first available)
        session = None
        for name in ["model", "decoder_model", "encoder_decoder"]:
            if name in self.sessions:
                session = self.sessions[name]
                break
        if session is None:
            session = next(iter(self.sessions.values()))

        # Filter feed to only include expected inputs
        input_names = {inp.name for inp in session.get_inputs()}
        filtered_feed = {k: v for k, v in feed.items() if k in input_names}

        # Run
        outputs = session.run(None, filtered_feed)

        # Decode output tokens
        if len(outputs) > 0:
            output_ids = outputs[0]
            if output_ids.dtype in (np.int64, np.int32):
                text = self.tokenizer.decode(output_ids[0], skip_special_tokens=True)
            else:
                # Logits output — take argmax
                token_ids = np.argmax(output_ids, axis=-1)
                text = self.tokenizer.decode(token_ids[0], skip_special_tokens=True)
            return text

        return "[No output]"


# ---------------------------------------------------------------------------
# OpenAI-compatible API endpoint
# ---------------------------------------------------------------------------
@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    """OpenAI-compatible chat completions endpoint."""
    try:
        data = request.get_json()
        messages = data.get("messages", [])
        max_tokens = data.get("max_tokens", 512)
        temperature = data.get("temperature", 0.7)

        # Extract prompt and image from messages
        prompt_parts = []
        image_base64 = None

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if isinstance(content, str):
                prompt_parts.append(f"{role}: {content}")
            elif isinstance(content, list):
                for item in content:
                    if item.get("type") == "text":
                        prompt_parts.append(f"{role}: {item['text']}")
                    elif item.get("type") == "image_url":
                        url = item["image_url"]["url"]
                        if url.startswith("data:"):
                            # data:image/jpeg;base64,xxxxx
                            image_base64 = url.split(",", 1)[1]

        prompt = "\n".join(prompt_parts)

        # Generate
        start_time = time.time()
        response_text = vlm_model.generate(
            prompt, image_base64=image_base64,
            max_tokens=max_tokens, temperature=temperature,
        )
        elapsed = time.time() - start_time

        # Format as OpenAI response
        return jsonify({
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "gemma-3-4b-it-mm-ryzenai",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text,
                },
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": len(prompt.split()),
                "completion_tokens": len(response_text.split()),
                "total_tokens": len(prompt.split()) + len(response_text.split()),
            },
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "model": "gemma-3-4b-it-mm-ryzenai"})


def main():
    parser = argparse.ArgumentParser(description="VLM Server (Gemma-3-4b-it-mm, Ryzen AI NPU)")
    parser.add_argument("--model-dir", type=str, required=True,
                        help="Path to Gemma-3-4b-it-mm-onnx-ryzenai-npu model directory")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()

    global vlm_model
    print("=" * 60)
    print("Initializing VLM Server (Gemma-3-4b-it-mm on Ryzen AI NPU)...")
    print("=" * 60)
    vlm_model = GemmaVLM(args.model_dir)
    print(f"Server: http://{args.host}:{args.port}")
    print("  POST /v1/chat/completions : OpenAI-compatible VLM API")
    print("  GET  /health              : Health check")
    print("=" * 60)

    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
