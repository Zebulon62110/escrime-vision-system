#!/usr/bin/env python3
"""Quick test script to visualize piste detection on video frames."""

import cv2
import numpy as np
from vision.piste_detector import PisteDetector
from vision.person_detector import PersonDetector
from sources.video_file import VideoFileSource

def main():
    VIDEO_PATH = "data/test.mp4"
    
    source = VideoFileSource(VIDEO_PATH)
    piste_detector = PisteDetector()
    person_detector = PersonDetector(model_name="yolov8n.pt", device="cpu")
    
    frame_count = 0
    max_frames = 30  # test on first 30 frames
    
    while frame_count < max_frames:
        ret, frame = source.read()
        if not ret:
            break
        
        frame_count += 1
        
        # Detect piste
        piste_bbox = piste_detector.detect(frame)
        
        # Detect persons
        detections = person_detector.detect(frame)
        
        # Filter detections to within piste (if detected)
        filtered_detections = []
        if piste_bbox and detections:
            px1, py1, px2, py2 = piste_bbox
            for d in detections:
                bbox = d.get('bbox')
                if bbox:
                    x1, y1, x2, y2 = bbox
                    cx = (x1 + x2) / 2.0
                    cy = (y1 + y2) / 2.0
                    if px1 <= cx <= px2 and py1 <= cy <= py2:
                        filtered_detections.append(d)
        else:
            filtered_detections = detections or []
        
        # Draw on frame
        vis = frame.copy()
        
        # Draw piste (blue)
        if piste_bbox:
            x1, y1, x2, y2 = piste_bbox
            cv2.rectangle(vis, (int(x1), int(y1)), (int(x2), int(y2)), (255, 0, 0), 3)
            cv2.putText(vis, 'Piste', (int(x1), int(y1) - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        
        # Draw detected fencers (yellow)
        for d in filtered_detections:
            bbox = d.get('bbox')
            score = d.get('score', 0)
            if bbox:
                x1, y1, x2, y2 = bbox
                cv2.rectangle(vis, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 255), 2)
                cv2.putText(vis, f'Fencer {score:.2f}', (int(x1), int(y1) - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        
        # Add frame info
        info = f"Frame {frame_count}: piste={'YES' if piste_bbox else 'NO'}, fencers={len(filtered_detections)}"
        cv2.putText(vis, info, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Save sample frames (every 10 frames) instead of displaying
        if frame_count % 10 == 0 or piste_bbox:
            outfile = f"/tmp/piste_test_frame_{frame_count:04d}.png"
            cv2.imwrite(outfile, vis)
            print(f"Saved {outfile}: {info}")
    
    source.release()
    cv2.destroyAllWindows()
    print(f"Test complete. Processed {frame_count} frames.")

if __name__ == "__main__":
    main()
