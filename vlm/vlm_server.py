#!/usr/bin/env python3
"""
VLM Server — Gemma-3-4b-it-mm on Ryzen AI NPU via onnxruntime-genai.

Provides an OpenAI-compatible /v1/chat/completions endpoint so that
existing vlm_client.py works without modification.

Requires:
  - onnxruntime-genai (installed from AMD Ryzen AI SDK wheels or pip)
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
    """Gemma-3-4b-it multimodal model via onnxruntime-genai."""

    def __init__(self, model_dir: str):
        self.model_dir = Path(model_dir)

        try:
            import onnxruntime_genai as og
        except ImportError:
            raise ImportError(
                "onnxruntime-genai not installed. "
                "Install from AMD Ryzen AI SDK wheels or: pip install onnxruntime-genai"
            )

        self._og = og
        print(f"[VLM] onnxruntime-genai version: {og.__version__}")

        # Load model (auto-detects NPU/CPU from genai_config.json)
        print(f"[VLM] Loading model from {model_dir} ...")
        self.model = og.Model(str(self.model_dir))
        print("[VLM] Model loaded")

        # Create processor and tokenizer
        self.processor = self.model.create_multimodal_processor()
        self.tokenizer = og.Tokenizer(self.model)
        self.tokenizer_stream = self.tokenizer.create_stream()

        print(f"[VLM] Ready (model_dir={model_dir})")

    def generate(self, prompt: str, image_base64: Optional[str] = None,
                 max_tokens: int = 512, temperature: float = 0.7) -> str:
        """Generate text response from prompt and optional image."""
        og = self._og

        # Build chat template
        chat_prompt = f"<start_of_turn>user\n{prompt}<end_of_turn>\n<start_of_turn>model\n"

        if image_base64:
            # Multimodal: image + text
            from PIL import Image
            img_bytes = base64.b64decode(image_base64)
            image = Image.open(io.BytesIO(img_bytes)).convert("RGB")

            # onnxruntime-genai expects raw image bytes or PIL
            img_buf = io.BytesIO()
            image.save(img_buf, format="PNG")
            raw_bytes = img_buf.getvalue()

            # Create inputs with image
            inputs = self.processor(chat_prompt, images=og.Images.open_bytes(raw_bytes))
        else:
            # Text-only
            inputs = self.processor(chat_prompt)

        # Generation parameters
        params = og.GeneratorParams(self.model)
        params.set_search_options(
            max_length=max_tokens + inputs.num_tokens if hasattr(inputs, 'num_tokens') else max_tokens + 256,
            temperature=temperature,
            top_p=0.95,
            top_k=1,
            do_sample=True,
        )
        params.set_inputs(inputs)

        # Generate
        generator = og.Generator(self.model, params)
        output_tokens = []

        try:
            while not generator.is_done():
                generator.compute_logits()
                generator.generate_next_token()
                token = generator.get_next_tokens()[0]
                output_tokens.append(token)
                if len(output_tokens) >= max_tokens:
                    break
        except Exception as e:
            print(f"[VLM] Generation error: {e}")

        # Decode
        output_text = self.tokenizer.decode(output_tokens)

        # Clean up end-of-turn markers
        for marker in ["<end_of_turn>", "<eos>"]:
            if marker in output_text:
                output_text = output_text[:output_text.index(marker)]

        return output_text.strip()


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
                prompt_parts.append(content)
            elif isinstance(content, list):
                for item in content:
                    if item.get("type") == "text":
                        prompt_parts.append(item["text"])
                    elif item.get("type") == "image_url":
                        url = item["image_url"]["url"]
                        if url.startswith("data:"):
                            image_base64 = url.split(",", 1)[1]

        prompt = "\n".join(prompt_parts)

        # Generate
        start_time = time.time()
        response_text = vlm_model.generate(
            prompt, image_base64=image_base64,
            max_tokens=max_tokens, temperature=temperature,
        )
        elapsed = time.time() - start_time
        print(f"[VLM] Generated {len(response_text)} chars in {elapsed:.1f}s")

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
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "model": "gemma-3-4b-it-mm-ryzenai"})


def main():
    parser = argparse.ArgumentParser(description="VLM Server (Gemma-3-4b-it-mm, onnxruntime-genai)")
    parser.add_argument("--model-dir", type=str, required=True,
                        help="Path to Gemma-3-4b-it-mm-onnx-ryzenai-npu model directory")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()

    global vlm_model
    print("=" * 60)
    print("Initializing VLM Server (Gemma-3-4b-it-mm, onnxruntime-genai)")
    print("=" * 60)
    vlm_model = GemmaVLM(args.model_dir)
    print(f"Server: http://{args.host}:{args.port}")
    print("  POST /v1/chat/completions : OpenAI-compatible VLM API")
    print("  GET  /health              : Health check")
    print("=" * 60)

    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
