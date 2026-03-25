#!/usr/bin/env python3
"""
Utility script to register faces to the database
Usage: 
  Single image: python register_face.py --name "Junha" --image /workspace/database/base_image.jpg
  Directory: python register_face.py --directory /workspace/database/
"""

import argparse
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from face_recognizer import FaceRecognizer


def get_image_files(directory: Path):
    """
    Get all image files from a directory, excluding .pkl files
    
    Args:
        directory: Path to the directory
        
    Returns:
        List of image file paths
    """
    # Common image extensions supported by OpenCV
    image_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    
    image_files = []
    for ext in image_extensions:
        image_files.extend(directory.glob(f'*{ext}'))
        image_files.extend(directory.glob(f'*{ext.upper()}'))
    
    # Filter out .pkl files explicitly (though they shouldn't match image extensions)
    image_files = [f for f in image_files if f.suffix.lower() != '.pkl']
    
    return sorted(image_files)


def main():
    parser = argparse.ArgumentParser(description='Register faces to the database')
    parser.add_argument('--name', type=str, default=None,
                       help='Name of the person to register (required for single image, optional for directory - uses filename)')
    parser.add_argument('--image', type=str, default=None,
                       help='Path to a single image file')
    parser.add_argument('--directory', type=str, default="./database/",
                       help='Path to directory containing images to register')
    parser.add_argument('--database', type=str, 
                       default='./database/known_faces.pkl',
                       help='Path to the database file')
    parser.add_argument('--threshold', type=float, default=0.5,
                       help='Similarity threshold')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.directory is None and args.image is None:
        print("Error: Either --image or --directory must be provided")
        return 1
    
    if args.directory is not None and args.image is not None:
        print("Error: Cannot use both --image and --directory. Use one or the other.")
        return 1
    
    print("=" * 50)
    print("Face Registration Utility")
    print("=" * 50)
    
    # Initialize recognizer
    print("\nInitializing Face Recognizer (ArcFace)...")
    recognizer = FaceRecognizer(similarity_threshold=args.threshold)
    
    # # Load existing database if exists
    # if os.path.exists(args.database):
    #     recognizer.load_database(args.database)
    #     print(f"Existing faces in database: {list(recognizer.known_faces.keys())}")
    
    # Process single image or directory
    if args.image is not None:
        # Single image mode
        if not os.path.exists(args.image):
            print(f"Error: Image file not found: {args.image}")
            return 1
        
        if args.name is None:
            print("Error: --name is required when using --image")
            return 1
        
        print(f"\nRegistering face: {args.name}")
        print(f"Image: {args.image}")
        
        success = recognizer.register_from_file(args.name, args.image)
        
        if success:
            recognizer.save_database(args.database)
            print(f"\nSuccess! Database saved to: {args.database}")
            print(f"Total registered faces: {list(recognizer.known_faces.keys())}")
            return 0
        else:
            print("\nFailed to register face. Please check the image.")
            return 1
    
    else:
        # Directory mode
        directory = Path(args.directory)
        if not directory.exists() or not directory.is_dir():
            print(f"Error: Directory not found or is not a directory: {args.directory}")
            return 1
        
        print(f"\nScanning directory: {directory}")
        image_files = get_image_files(directory)
        
        if len(image_files) == 0:
            print("No image files found in directory (excluding .pkl files)")
            return 1
        
        print(f"Found {len(image_files)} image file(s)")
        print("-" * 50)
        
        success_count = 0
        fail_count = 0
        
        for img_path in image_files:
            # Use filename (without extension) as name if --name not provided
            if args.name:
                name = args.name
            else:
                name = img_path.stem  # filename without extension
            
            print(f"\nRegistering: {name}")
            print(f"  Image: {img_path}")
            
            success = recognizer.register_from_file(name, str(img_path))
            
            if success:
                success_count += 1
                print(f"  ✅ Success")
            else:
                fail_count += 1
                print(f"  ❌ Failed")
        
        # Save database after processing all images
        recognizer.save_database(args.database)
        
        print("\n" + "=" * 50)
        print(f"Registration complete!")
        print(f"  Successful: {success_count}")
        print(f"  Failed: {fail_count}")
        print(f"  Total: {len(image_files)}")
        print(f"\nDatabase saved to: {args.database}")
        print(f"Total registered faces: {list(recognizer.known_faces.keys())}")
        print("=" * 50)
        
        return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
