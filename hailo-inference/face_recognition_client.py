#!/usr/bin/env python3
"""
Face Recognition Client
Sends images to face recognition server and receives recognition results.
"""

import base64
import json
import time
import requests
from pathlib import Path
import argparse
from typing import Tuple, Optional, Dict, Any, Union

import cv2
import numpy as np


class FaceRecognitionClient:
    """
    Client for face recognition server API
    """
    
    def __init__(self, api_url: str = "http://localhost:7999"):
        """
        Initialize the face recognition client
        
        Args:
            api_url: Face recognition API server URL
        """
        self.api_url = api_url.rstrip('/')
    
    @staticmethod
    def encode_image_from_path(image_path: str) -> str:
        """
        Encode image file to base64
        
        Args:
            image_path: Image file path
            
        Returns:
            base64 encoded image string
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    @staticmethod
    def encode_image_from_array(image_array: np.ndarray, fmt: str = ".png") -> str:
        """
        Encode numpy array (OpenCV BGR image) to base64
        
        Args:
            image_array: Image as numpy array (BGR, uint8)
            fmt: Image format extension for encoding (e.g. '.png', '.jpg')
            
        Returns:
            base64 encoded image string
        """
        success, encoded = cv2.imencode(fmt, image_array)
        if not success:
            raise ValueError("Failed to encode image array")
        return base64.b64encode(encoded.tobytes()).decode('utf-8')
    
    def check_server_health(self) -> bool:
        """
        Check server health status
        
        Returns:
            True if server is healthy
        """
        try:
            response = requests.get(f"{self.api_url}/health", timeout=5)
            response.raise_for_status()
            health_data = response.json()
            return health_data.get("status") == "healthy"
        except Exception:
            return False
    
    def recognize(
        self,
        image: Union[str, np.ndarray],
        measure_time: bool = False
    ) -> Tuple[Dict[str, Any], Optional[float]]:
        """
        Send image to face recognition server and receive recognition result.
        
        Args:
            image: Image file path (str) or image as numpy array (BGR, uint8)
            measure_time: Whether to measure response time
        
        Returns:
            (API response dictionary, response time (seconds) or None) tuple
        """
        # Encode image to base64 (from path or numpy array)
        if isinstance(image, np.ndarray):
            base64_image = self.encode_image_from_array(image)
        else:
            base64_image = self.encode_image_from_path(image)
        
        # Construct request payload
        payload = {
            "image": base64_image
        }
        
        # Send API request
        start_time = time.time() if measure_time else None
        response = requests.post(
            f"{self.api_url}/recognize",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        # Check response
        response.raise_for_status()
        response_json = response.json()
        
        elapsed_time = (time.time() - start_time) if measure_time else None
        return response_json, elapsed_time


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Face Recognition Client')
    parser.add_argument('--image', type=str, required=True,
                       help='Path to face image file')
    parser.add_argument('--api-url', type=str, default='http://localhost:7999',
                       help='API server URL (default: http://localhost:7999)')
    
    args = parser.parse_args()
    
    # Check if image file exists
    image_path = Path(args.image)
    if not image_path.exists():
        print(f"❌ Image file not found: {image_path}")
        return
    
    print("=" * 60)
    print("Face Recognition Client")
    print("=" * 60)
    print(f"📷 Image: {image_path}")
    print(f"🌐 API URL: {args.api_url}")
    print("-" * 60)
    
    # Initialize client
    client = FaceRecognitionClient(api_url=args.api_url)
    
    # Check server status
    print("🔍 Checking server status...")
    if not client.check_server_health():
        print(f"❌ Cannot connect to server: {args.api_url}")
        print(f"   Please check if the server is running.")
        return
    print("✅ Server connection successful!")
    print("-" * 60)
    
    try:
        # Send recognition request
        print("📤 Sending recognition request...")
        response, elapsed_time = client.recognize(str(image_path), measure_time=True)
        
        # Process response
        if response.get("success", False):
            name = response.get("name", "Unknown")
            similarity = response.get("similarity", 0.0)
            
            print("✅ Response received!")
            print("-" * 60)
            print(f"⏱️  Response time: {elapsed_time:.3f} seconds")
            print("-" * 60)
            print("💬 Recognition result:")
            print(f"  - Name: {name}")
            print(f"  - Similarity: {similarity:.4f}")
            print("-" * 60)
        else:
            error_msg = response.get("error", "Unknown error")
            print("❌ Recognition failed!")
            print("-" * 60)
            print(f"Error: {error_msg}")
            print("-" * 60)
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed: Cannot connect to face recognition server.")
        print(f"   Please check if the server is running at {args.api_url}.")
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP error: {e}")
        if hasattr(e.response, 'text'):
            print(f"   Response content: {e.response.text}")
    except Exception as e:
        print(f"❌ Error occurred: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
