#!/usr/bin/env python3
"""
Calibrate piste detector by finding the true piste boundaries from all frames.

This script scans the video and finds which y-positions are consistently
detected as pistes across many frames, determining the exact boundaries.
"""

import cv2
import numpy as np
from collections import defaultdict
from vision.piste_detector import PisteDetector

VIDEO_PATH = "data/test.mp4"

cap = cv2.VideoCapture(VIDEO_PATH)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

detector = PisteDetector()

# Track which y-positions are detected as piste content across frames
piste_votes = defaultdict(int)  # y -> count

# Sample every N frames to speed up
sample_rate = 5
frames_to_process = list(range(0, total_frames, sample_rate))[:100]

print(f"Scanning {len(frames_to_process)} frames...")

for frame_idx in frames_to_process:
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, frame = cap.read()
    if not ret:
        continue
    
    pistes = detector.detect(frame)
    
    # For each piste, mark those y-positions as "piste pixels"
    for x1, y1, x2, y2 in pistes:
        for y in range(y1, y2):
            piste_votes[y] += 1

cap.release()

# Find clusters of consistently detected pixels
print("\nPiste position voting results:")
print(f"y-range  | votes | consensus | analysis")
print("---------+-------+----------+-------------------")

# Group consecutive pixels with votes
sorted_y = sorted(piste_votes.keys())
clusters = []
current_cluster = []
threshold = len(frames_to_process) * 0.3  # 30% of frames

for y in sorted_y:
    votes = piste_votes[y]
    if votes > threshold:
        if not current_cluster or y == current_cluster[-1][0] + 1:
            # Extend current cluster
            current_cluster.append((y, votes))
        else:
            # Start new cluster
            if current_cluster:
                clusters.append(current_cluster)
            current_cluster = [(y, votes)]
    elif current_cluster:
        # End cluster
        clusters.append(current_cluster)
        current_cluster = []

if current_cluster:
    clusters.append(current_cluster)

print(f"\nFound {len(clusters)} distinct piste regions:\n")

for i, cluster in enumerate(clusters):
    y_start = cluster[0][0]
    y_end = cluster[-1][0]
    height = y_end - y_start + 1
    avg_votes = np.mean([v for y, v in cluster])
    pct = avg_votes / len(frames_to_process) * 100
    
    print(f"Piste {i+1}: y={y_start:3d}-{y_end:3d} (h={height:2d}px) - {pct:5.1f}% detected")

print("\n--- Recommended detector parameters ---")
print("\nPistes should be at these positions:")
for i, cluster in enumerate(clusters[:4]):
    y_start = cluster[0][0]
    y_end = cluster[-1][0]
    print(f"  Piste {i+1}: y={y_start}-{y_end}")
