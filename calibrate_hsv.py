#!/usr/bin/env python3
"""HSV calibration tool to find piste color range."""

import cv2
import numpy as np
from sources.video_file import VideoFileSource

def main():
    VIDEO_PATH = "data/test.mp4"
    
    source = VideoFileSource(VIDEO_PATH)
    
    # Read a few frames and analyze HSV
    hue_values = []
    sat_values = []
    val_values = []
    
    print("Analyzing HSV color distribution in video...")
    
    for frame_idx in range(50):  # sample 50 frames
        ret, frame = source.read()
        if not ret:
            break
        
        # Convert to HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Flatten and collect all HSV values (skip very dark/bright areas)
        h = hsv[:, :, 0].flatten()
        s = hsv[:, :, 1].flatten()
        v = hsv[:, :, 2].flatten()
        
        # Filter to moderate brightness/saturation (likely piste area, not shadows/sky)
        mask = (v > 50) & (v < 200) & (s > 20) & (s < 255)
        
        hue_values.extend(h[mask])
        sat_values.extend(s[mask])
        val_values.extend(v[mask])
    
    source.release()
    
    if not hue_values:
        print("No pixels found in value range!")
        return
    
    print(f"\nAnalyzed {len(hue_values)} pixels from 50 frames")
    print(f"\nHue statistics (0-180):")
    print(f"  Min: {np.min(hue_values)}, Max: {np.max(hue_values)}")
    print(f"  Mean: {np.mean(hue_values):.1f}, Std: {np.std(hue_values):.1f}")
    print(f"  Median: {np.median(hue_values):.1f}")
    print(f"  25th percentile: {np.percentile(hue_values, 25):.1f}")
    print(f"  75th percentile: {np.percentile(hue_values, 75):.1f}")
    
    print(f"\nSaturation statistics (0-255):")
    print(f"  Min: {np.min(sat_values)}, Max: {np.max(sat_values)}")
    print(f"  Mean: {np.mean(sat_values):.1f}, Std: {np.std(sat_values):.1f}")
    print(f"  Median: {np.median(sat_values):.1f}")
    
    print(f"\nValue (Brightness) statistics (0-255):")
    print(f"  Min: {np.min(val_values)}, Max: {np.max(val_values)}")
    print(f"  Mean: {np.mean(val_values):.1f}, Std: {np.std(val_values):.1f}")
    print(f"  Median: {np.median(val_values):.1f}")
    
    # Suggest initial HSV range for piste (typically green or light colored)
    h_mean = np.mean(hue_values)
    h_std = np.std(hue_values)
    
    print(f"\n\nSuggested HSV ranges for PisteDetector:")
    print(f"  hue_low={int(max(0, h_mean - 2*h_std))}")
    print(f"  hue_high={int(min(180, h_mean + 2*h_std))}")
    print(f"  saturation_low={int(np.percentile(sat_values, 10))}")
    print(f"  saturation_high=255")
    print(f"  brightness_low={int(np.percentile(val_values, 10))}")
    print(f"  brightness_high=255")

if __name__ == "__main__":
    main()
