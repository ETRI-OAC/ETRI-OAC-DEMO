#!/usr/bin/env python3
"""
Face Recognition Server
Processes face recognition requests via REST API server.
"""

import base64
import io
import cv2
import numpy as np
from flask import Flask, request, jsonify
from face_recognizer import FaceRecognizer
import argparse
import os
import time
from pathlib import Path


app = Flask(__name__)
recognizer = None


def decode_base64_image(base64_string: str) -> np.ndarray:
    """
    Decode base64 string to OpenCV image
    
    Args:
        base64_string: base64 encoded image string
        
    Returns:
        OpenCV image (BGR format)
    """
    # Remove data:image/jpeg;base64, or data:image/png;base64, prefix
    if ',' in base64_string:
        base64_string = base64_string.split(',')[1]
    
    # base64 decoding
    image_data = base64.b64decode(base64_string)
    
    # Convert to numpy array
    nparr = np.frombuffer(image_data, dtype=np.uint8)
    
    # Decode to OpenCV image
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    return image


@app.route('/health', methods=['GET'])
def health_check():
    """Server health check"""
    return jsonify({
        "status": "healthy",
        "recognizer_loaded": recognizer is not None,
        "known_faces_count": len(recognizer.known_faces) if recognizer else 0
    })


@app.route('/recognize', methods=['POST'])
def recognize_face():
    """
    Process face recognition request
    
    Request body (JSON):
        {
            "image": "base64_encoded_image_string"
        }
    
    Response (JSON):
        {
            "name": "person_name or Unknown",
            "similarity": 0.85,
            "success": true
        }
    """
    try:
        # Check request data
        if not request.is_json:
            return jsonify({
                "success": False,
                "error": "Content-Type must be application/json"
            }), 400
        
        data = request.get_json()
        
        if 'image' not in data:
            return jsonify({
                "success": False,
                "error": "Missing 'image' field in request body"
            }), 400
        
        # Decode base64 image
        try:
            base64_image = data['image']
            face_image = decode_base64_image(base64_image)
            
            if face_image is None:
                return jsonify({
                    "success": False,
                    "error": "Failed to decode image"
                }), 400
                
        except Exception as e:
            return jsonify({
                "success": False,
                "error": f"Image decoding error: {str(e)}"
            }), 400
        
        # Parse optional landmarks (from YOLO keypoints)
        landmarks = data.get('landmarks', None)
        landmarks_5 = None
        if landmarks is not None:
            try:
                landmarks_5 = np.array(landmarks, dtype=np.float32)
                if landmarks_5.shape != (5, 2):
                    landmarks_5 = None
            except Exception:
                landmarks_5 = None

        # Perform face recognition
        if recognizer is None:
            return jsonify({
                "success": False,
                "error": "Face recognizer not initialized"
            }), 500

        lmk_info = f"landmarks={'yes' if landmarks_5 is not None else 'no'}"
        name, similarity = recognizer.recognize(face_image, landmarks_5=landmarks_5)

        if name != "Unknown":
            print(f"[RECOGNIZE] {name} (similarity: {similarity:.3f}) | {lmk_info}")
        else:
            print(f"[RECOGNIZE] Unknown (best: {similarity:.3f}) | {lmk_info}")

        return jsonify({
            "success": True,
            "name": name,
            "similarity": float(similarity)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Internal server error: {str(e)}"
        }), 500


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Face Recognition Server')
    parser.add_argument('--port', type=int, default=7999, help='Server port (default: 7999)')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Server host (default: 0.0.0.0)')
    parser.add_argument('--database', type=str, default='database/known_faces.pkl',
                       help='Path to known faces database (default: database/known_faces.pkl)')
    parser.add_argument('--threshold', type=float, default=0.5,
                       help='Similarity threshold (default: 0.5)')
    parser.add_argument('--model', type=str, default='buffalo_l',
                       help='InsightFace model name (default: buffalo_l)')
    parser.add_argument('--warmup', type=int, default=100,
                       help='Number of warmup iterations (default: 100)')
    parser.add_argument('--warmup-image', type=str, default=None,
                       help='Path to image for warmup (default: auto-detect or create dummy)')
    parser.add_argument('--hailo-hef', type=str, default=None,
                       help='Path to SCRFD .hef for Hailo-10 face detection (optional)')
    parser.add_argument('--hailo-device', type=str, default=None,
                       help='Hailo device ID (e.g. "0000:02:00.0"). Default: auto-detect')
    parser.add_argument('--hailo-index', type=int, default=0,
                       help='Hailo device index when multiple present (default: 0)')
    parser.add_argument('--use-hailo-server', action='store_true',
                       help='Use centralized hailo_inference_server instead of direct VDevice')
    parser.add_argument('--hailo-server-host', type=str, default='localhost',
                       help='Hailo inference server host (default: localhost)')
    parser.add_argument('--hailo-server-port', type=int, default=8003,
                       help='Hailo inference server port (default: 8003)')

    args = parser.parse_args()

    # Initialize FaceRecognizer
    global recognizer
    print("=" * 60)
    print("Initializing Face Recognition Server...")
    print("=" * 60)

    recognizer = FaceRecognizer(
        model_name=args.model,
        similarity_threshold=args.threshold,
        hailo_hef_path=args.hailo_hef,
        hailo_device_id=args.hailo_device,
        hailo_device_index=args.hailo_index,
        use_hailo_server=args.use_hailo_server,
        hailo_server_host=args.hailo_server_host,
        hailo_server_port=args.hailo_server_port,
    )
    
    # Load database
    db_path = Path(args.database)
    if db_path.exists():
        recognizer.load_database(str(db_path))
        print(f"✅ Database loaded: {len(recognizer.known_faces)} faces")
    else:
        print(f"⚠️  Database file not found: {db_path}")
        print("   Starting with empty database.")
    
    # Warmup phase
    if args.warmup > 0:
        print("-" * 60)
        print(f"🔥 Starting warmup ({args.warmup} iterations)...")
        warmup_start = time.time()
        
        # Find or create image for warmup
        warmup_image = None
        if args.warmup_image:
            warmup_path = Path(args.warmup_image)
            if warmup_path.exists():
                warmup_image = cv2.imread(str(warmup_path))
        else:
            # Automatically find image in test_face directory
            test_face_dir = Path(__file__).parent / "test_face"
            if test_face_dir.exists():
                for img_file in test_face_dir.glob("*.png"):
                    warmup_image = cv2.imread(str(img_file))
                    if warmup_image is not None:
                        break
                if warmup_image is None:
                    for img_file in test_face_dir.glob("*.jpeg"):
                        warmup_image = cv2.imread(str(img_file))
                        if warmup_image is not None:
                            break
        
        # Create dummy image if no image found
        if warmup_image is None:
            warmup_image = np.zeros((224, 224, 3), dtype=np.uint8)
            print("   (Using dummy image)")
        
        # Run warmup
        for i in range(args.warmup):
            recognizer.recognize(warmup_image)
        warmup_total_time = time.time() - warmup_start
        print(f"\n✅ Warmup complete! (Total {warmup_total_time:.2f} seconds)")
    
    print("-" * 60)
    print(f"🌐 Server starting: http://{args.host}:{args.port}")
    print(f"📋 Endpoints:")
    print(f"   - GET  /health     : Server health check")
    print(f"   - POST /recognize  : Face recognition request")
    print("=" * 60)
    
    # Run server
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
