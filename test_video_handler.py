#!/usr/bin/env python
"""
Test script to verify the implementation of video format handlers in EDSL.
This script creates example MP4 and WebM files using the handlers, and then
demonstrates how to use the FileStore class with these video files.
"""

from edsl.scenarios.file_store import FileStore
from edsl.scenarios.file_methods import FileMethods
import os

def main():
    print("Supported file types:", FileMethods.supported_file_types())
    
    # Verify MP4 handler
    print("\nTesting MP4 handler:")
    mp4_handler = FileMethods.get_handler("mp4")
    if mp4_handler:
        print(f"Found handler for MP4: {mp4_handler.__name__}")
        
        # Create an example MP4 file
        try:
            example_mp4_path = mp4_handler().example()
            print(f"Created example MP4 file at: {example_mp4_path}")
            print(f"File exists: {os.path.exists(example_mp4_path)}")
            print(f"File size: {os.path.getsize(example_mp4_path)} bytes")
            
            # Create a FileStore object with the MP4 file
            mp4_file = FileStore(example_mp4_path)
            print(f"Created FileStore object: {mp4_file}")
            print(f"MIME type: {mp4_file.mime_type}")
            print(f"Suffix: {mp4_file.suffix}")
        except Exception as e:
            print(f"Error creating MP4 example: {e}")
    else:
        print("No handler found for MP4 files.")
    
    # Verify WebM handler
    print("\nTesting WebM handler:")
    webm_handler = FileMethods.get_handler("webm")
    if webm_handler:
        print(f"Found handler for WebM: {webm_handler.__name__}")
        
        # Create an example WebM file
        try:
            example_webm_path = webm_handler().example()
            print(f"Created example WebM file at: {example_webm_path}")
            print(f"File exists: {os.path.exists(example_webm_path)}")
            print(f"File size: {os.path.getsize(example_webm_path)} bytes")
            
            # Create a FileStore object with the WebM file
            webm_file = FileStore(example_webm_path)
            print(f"Created FileStore object: {webm_file}")
            print(f"MIME type: {webm_file.mime_type}")
            print(f"Suffix: {webm_file.suffix}")
        except Exception as e:
            print(f"Error creating WebM example: {e}")
    else:
        print("No handler found for WebM files.")
    
    # Test FileStore.example method
    print("\nTesting FileStore.example method:")
    for video_format in ['mp4', 'webm']:
        try:
            print(f"\nCreating example {video_format} file:")
            video_file = FileStore.example(video_format)
            print(f"Created FileStore object: {video_file}")
            print(f"MIME type: {video_file.mime_type}")
            print(f"Suffix: {video_file.suffix}")
            print(f"Path: {video_file.path}")
            print(f"File exists: {os.path.exists(video_file.path)}")
            print(f"File size: {os.path.getsize(video_file.path)} bytes")
            print(f"Is video: {video_file.is_video()}")
            
            # Try to get video metadata
            try:
                metadata = video_file.get_video_metadata()
                print(f"Video metadata: {metadata}")
            except Exception as e:
                print(f"Error getting video metadata: {e}")
        except Exception as e:
            print(f"Error creating example {video_format} file: {e}")

if __name__ == "__main__":
    main()