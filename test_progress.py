#!/usr/bin/env python3
"""
Test script to demonstrate the enhanced transfer progress display
"""

import time
from eldersvr_cli.utils.progress import TransferProgress

def simulate_transfer():
    """Simulate a file transfer with real-time progress updates"""
    
    # Create progress tracker
    progress = TransferProgress()
    
    # Add two devices
    progress.add_device("ABC123", "Master Phone")
    progress.add_device("XYZ789", "Slave VR Headset")
    
    # Simulate master device transfer (JSON + videos + images)
    print("Starting Master Device Transfer...")
    
    # JSON transfer
    progress.update_json_status("ABC123", "in_progress")
    time.sleep(1)
    progress.update_json_status("ABC123", "completed", 1024)
    
    # Video transfer
    total_videos = 10
    for i in range(total_videos + 1):
        progress.update_videos_progress("ABC123", i, total_videos, "in_progress")
        time.sleep(0.3)
    progress.update_videos_progress("ABC123", total_videos, total_videos, "completed")
    
    # Image transfer
    total_images = 20
    for i in range(total_images + 1):
        progress.update_images_progress("ABC123", i, total_images, "in_progress")
        time.sleep(0.15)
    progress.update_images_progress("ABC123", total_images, total_images, "completed")
    
    # Simulate slave device transfer (JSON + videos + images)
    print("\nStarting Slave Device Transfer...")
    
    # JSON transfer
    progress.update_json_status("XYZ789", "in_progress")
    time.sleep(1)
    progress.update_json_status("XYZ789", "completed", 1024)
    
    # Video transfer
    for i in range(total_videos + 1):
        progress.update_videos_progress("XYZ789", i, total_videos, "in_progress")
        time.sleep(0.3)
    progress.update_videos_progress("XYZ789", total_videos, total_videos, "completed")
    
    # Image transfer
    for i in range(total_images + 1):
        progress.update_images_progress("XYZ789", i, total_images, "in_progress")
        time.sleep(0.15)
    progress.update_images_progress("XYZ789", total_images, total_images, "completed")
    
    # Final summary
    time.sleep(2)
    print("\n" * 5)
    print("=" * 60)
    print("TRANSFER COMPLETE!")
    print("=" * 60)
    summary = progress.get_summary()
    print(f"Total devices: {summary['total_devices']}")
    print(f"Successfully completed: {summary['completed_devices']}")
    print(f"Files transferred: {summary['completed_files']}/{summary['total_files']}")
    print("=" * 60)

if __name__ == "__main__":
    try:
        simulate_transfer()
    except KeyboardInterrupt:
        print("\n\nTransfer interrupted by user")