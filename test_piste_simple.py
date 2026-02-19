#!/usr/bin/env python3
"""Quick test of piste detection without YOLO (faster)."""

import cv2
import numpy as np
from vision.piste_detector import PisteDetector
from sources.video_file import VideoFileSource

def main():
    VIDEO_PATH = "data/test.mp4"
    
    source = VideoFileSource(VIDEO_PATH)
    piste_detector = PisteDetector()
    
    frame_count = 0
    max_frames = 30
    piste_found_frames = 0
    
    print("Testing piste detection on video frames...")
    
    while frame_count < max_frames:
        ret, frame = source.read()
        if not ret:
            break
        
        frame_count += 1
        
        # Detect piste
        piste_bbox = piste_detector.detect(frame)
        
        if piste_bbox:
            piste_found_frames += 1
            x1, y1, x2, y2 = piste_bbox
            print(f"Frame {frame_count:3d}: PISTE DETECTED at ({int(x1)}, {int(y1)}, {int(x2)}, {int(y2)}) size={int(x2-x1)}x{int(y2-y1)}")
            
            # Save frame with piste marker
            vis = frame.copy()
            cv2.rectangle(vis, (int(x1), int(y1)), (int(x2), int(y2)), (255, 0, 0), 3)
            cv2.putText(vis, 'PISTE DETECTED', (int(x1), int(y1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
            cv2.imwrite(f"/tmp/piste_detected_frame_{frame_count:04d}.png", vis)
        else:
            if frame_count % 10 == 0:
                print(f"Frame {frame_count:3d}: No piste detected")
    
    source.release()
    
    print(f"\nResults: {piste_found_frames}/{frame_count} frames had piste detected")
    print(f"Detection rate: {100*piste_found_frames/max(frame_count,1):.1f}%")
    
    if piste_found_frames == 0:
        print("\nNo piste detected. Need to adjust HSV parameters.")
        print("Saved 10 sample frames to /tmp for inspection:")
        import os
        os.system("ls -1 /tmp/piste_detected_frame_*.png 2>/dev/null | head -n 10 || echo 'No frames saved'")

if __name__ == "__main__":
    main()
