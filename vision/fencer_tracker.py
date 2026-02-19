"""Specialized fencer tracker for 2-fencer fencing bouts.

Identifies and tracks exactly 2 fencers throughout a bout using:
1. Guard line position as primary identification method
2. Persistent ID assignment (Fencer 1=left, Fencer 2=right)
3. Centroid-based tracking throughout the bout
4. Auto-framing to keep both fencers in view
5. Handling of temporary occlusion/dropout with tolerance

Primary workflow:
- INITIALIZATION: Detect when each fencer is on their designated guard line
  - Fencer 1: left side of left guard line (5m)
  - Fencer 2: right side of right guard line (9m)
- TRACKING: Track with persistent IDs until bout ends
- VALIDATION: Continuously validate if fencers remain on guard lines
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class TrackedFencer:
    """Represents a tracked fencer with persistent state."""
    id: int
    bbox: Tuple[int, int, int, int]
    centroid: Tuple[float, float]
    frames_alive: int
    frames_since_detection: int


class FencerTracker:
    """Track exactly 2 fencers throughout a bout with auto-framing."""
    
    NUM_FENCERS = 2  # Always expect exactly 2 fencers
    
    def __init__(
        self,
        max_tracking_distance: float = 100.0,  # Max distance for centroid matching
        dropout_tolerance: int = 30,  # Frames to wait before losing track (1 second @ 30fps)
    ):
        """
        Args:
            max_tracking_distance: Max centroid distance to match detection to track
            dropout_tolerance: Frames before a track is forgotten
        """
        self.max_tracking_distance = max_tracking_distance
        self.dropout_tolerance = dropout_tolerance
        
        # State
        self.initialized = False  # True when 2 fencers are locked
        self.fencers: Dict[int, TrackedFencer] = {}  # id -> TrackedFencer
        self.frame_count = 0
    
    def update(self, detections: List[Dict], guard_line_detector=None) -> Tuple[List[Dict], Dict]:
        """
        Update tracks with new detections.
        
        Args:
            detections: List of {'bbox': (x1,y1,x2,y2), ...}
            guard_line_detector: Optional GuardLineDetector to identify fencers by guard line position
        
        Returns:
            (tracks, frame_info) where:
            - tracks: List of {'id', 'bbox', 'centroid'} for active fencers
            - frame_info: {'initialized': bool, 'num_fencers': int, 'frame_box': (x1,y1,x2,y2) or None}
        """
        self.frame_count += 1
        
        if not self.initialized:
            return self._update_initialization(detections, guard_line_detector)
        else:
            return self._update_tracking(detections)
    
    def _update_initialization(self, detections: List[Dict], guard_line_detector=None) -> Tuple[List[Dict], Dict]:
        """
        During initialization phase, collect detections to identify 2 stable fencers.
        Uses guard lines to identify fencers by their position relative to guard lines.
        """
        if len(detections) < self.NUM_FENCERS:
            # Not enough fencers yet - return raw detections as provisional tracks for visualization
            # Assign provisional IDs (100, 101, ...) to show detections
            provisional_tracks = []
            for i, detection in enumerate(sorted(detections, key=lambda d: d.get('bbox', (0, 0, 0, 0))[0])):
                # Create provisional track with ID 100+i
                track = {
                    'id': 100 + i,  # Provisional ID (different from real 1,2)
                    'bbox': detection.get('bbox'),
                    'centroid': (
                        (detection['bbox'][0] + detection['bbox'][2]) / 2.0,
                        (detection['bbox'][1] + detection['bbox'][3]) / 2.0
                    ) if 'bbox' in detection else (0, 0)
                }
                provisional_tracks.append(track)
            
            return provisional_tracks, {
                'initialized': False,
                'num_fencers': len(detections),
                'frame_box': None,
                'status': f'🔍 Waiting for {self.NUM_FENCERS} stable fencers (found {len(detections)})'
            }
        
        # Try to initialize using guard lines if detector is available
        if guard_line_detector and guard_line_detector.piste_roi:
            result = self._initialize_with_guard_lines(detections, guard_line_detector)
            if result is not None:
                return result
        
        # Guard line initialization not ready yet - wait and show provisional tracks
        provisional_tracks = []
        for i, detection in enumerate(sorted(detections, key=lambda d: d.get('bbox', (0, 0, 0, 0))[0])):
            track = {
                'id': 100 + i,
                'bbox': detection.get('bbox'),
                'centroid': (
                    (detection['bbox'][0] + detection['bbox'][2]) / 2.0,
                    (detection['bbox'][1] + detection['bbox'][3]) / 2.0
                ) if 'bbox' in detection else (0, 0)
            }
            provisional_tracks.append(track)
        
        return provisional_tracks, {
            'initialized': False,
            'num_fencers': len(detections),
            'frame_box': None,
            'status': '🔍 Waiting for fencers on guard lines...'
        }
    
    def _update_tracking(self, detections: List[Dict]) -> Tuple[List[Dict], Dict]:
        """
        Track the 2 locked fencers throughout the bout.
        Once locked, only the 2 fencers are tracked with persistent IDs (1, 2).
        Other detections are shown as provisional tracks (100+) but never locked.
        """
        # Match detections to existing tracks using centroid distance
        detection_centroids = np.array([
            self._centroid_from_bbox(d['bbox']) for d in detections
        ]) if detections else np.empty((0, 2))
        
        track_ids = list(self.fencers.keys())
        track_centroids = np.array([
            self.fencers[fid].centroid for fid in track_ids
        ]) if track_ids else np.empty((0, 2))
        
        # Track-to-detection matching
        assigned_tracks = set()
        assigned_detections = set()
        
        if len(detections) > 0 and len(track_ids) > 0:
            # Distance matrix: rows=tracks, cols=detections
            distances = np.linalg.norm(
                track_centroids[:, None, :] - detection_centroids[None, :, :],
                axis=2
            )
            
            # Greedy matching: for each track, find closest unassigned detection
            for track_idx, track_id in enumerate(track_ids):
                if len(unassigned_detections := [i for i in range(len(detections)) if i not in assigned_detections]) == 0:
                    break
                
                unassigned_dists = distances[track_idx, unassigned_detections]
                closest_rel_idx = np.argmin(unassigned_dists)
                closest_detection_idx = unassigned_detections[closest_rel_idx]
                closest_dist = unassigned_dists[closest_rel_idx]
                
                if closest_dist <= self.max_tracking_distance:
                    # Update track
                    detection = detections[closest_detection_idx]
                    bbox = detection['bbox']
                    centroid = self._centroid_from_bbox(bbox)
                    
                    fencer = self.fencers[track_id]
                    
                    # Check if this would cause overlap with the other fencer
                    min_separation = 50  # Minimum pixel distance between fencers
                    other_fencer_id = 2 if track_id == 1 else 1
                    if other_fencer_id in self.fencers:
                        other_fencer = self.fencers[other_fencer_id]
                        new_separation = abs(centroid[0] - other_fencer.centroid[0])
                        
                        if new_separation < min_separation:
                            # Reject this detection - would cause overlap
                            # Keep the previous fencer position
                            print(f"[FencerTracker] Fencer {track_id}: Detection rejected (would overlap with Fencer {other_fencer_id}). Separation would be {new_separation:.0f}px (min {min_separation}px)")
                            fencer.frames_since_detection += 1
                        else:
                            # Safe to update
                            fencer.bbox = bbox
                            fencer.centroid = centroid
                            fencer.frames_since_detection = 0
                            fencer.frames_alive += 1
                            assigned_tracks.add(track_id)
                            assigned_detections.add(closest_detection_idx)
                    else:
                        # No other fencer to check against - safe to update
                        fencer.bbox = bbox
                        fencer.centroid = centroid
                        fencer.frames_since_detection = 0
                        fencer.frames_alive += 1
                        assigned_tracks.add(track_id)
                        assigned_detections.add(closest_detection_idx)
        
        # Mark unmatched tracks as missing
        for track_id in track_ids:
            if track_id not in assigned_tracks:
                self.fencers[track_id].frames_since_detection += 1
                self.fencers[track_id].frames_alive += 1
        
        # Remove tracks that have been missing too long
        for track_id in list(self.fencers.keys()):
            if self.fencers[track_id].frames_since_detection > self.dropout_tolerance:
                print(f"[FencerTracker] Lost Fencer {track_id} after {self.dropout_tolerance} frames of absence")
                del self.fencers[track_id]
        
        # Collect the 2 locked fencers
        locked_tracks = [
            {
                'id': fencer.id,
                'bbox': fencer.bbox,
                'centroid': fencer.centroid
            }
            for fencer in self.fencers.values()
        ]
        
        # Debug logging every 100 frames (less spam)
        if self.frame_count % 100 == 0:
            print(f"[FencerTracker] Tracking: {len(locked_tracks)}/2 locked fencers, "
                  f"{len(detections)} detections available")
        
        # Also show unmatched detections as "other fencers" (provisional, not locked)
        # This helps visualize if there are other people in the scene
        other_tracks = []
        for i, detection_idx in enumerate(range(len(detections))):
            if detection_idx not in assigned_detections:
                detection = detections[detection_idx]
                track = {
                    'id': 100 + i,  # Provisional ID (never locked)
                    'bbox': detection.get('bbox'),
                    'centroid': self._centroid_from_bbox(detection['bbox']) if 'bbox' in detection else (0, 0)
                }
                other_tracks.append(track)
        
        # Combine locked fencers + other detections
        all_tracks = locked_tracks + other_tracks
        
        # Calculate optimal framing box (only based on the 2 locked fencers)
        frame_box = self._calculate_frame_box()
        
        return all_tracks, {
            'initialized': True,
            'num_fencers': len(locked_tracks),  # Only count the 2 locked fencers
             'frame_box': frame_box,
            'status': f'🤺 Tracking {len(locked_tracks)}/2 fencers' + (f' + {len(other_tracks)} other' if other_tracks else '')
        }
    
    def _initialize_with_guard_lines(self, detections: List[Dict], guard_line_detector) -> Optional[Tuple[List[Dict], Dict]]:
        """
        Initialize fencers using guard line positions as reference.
        
        Fencer 1: Must be on LEFT side of left guard line (x < left_line_x)
        Fencer 2: Must be on RIGHT side of right guard line (x > right_line_x)
        
        Args:
            detections: Current frame detections
            guard_line_detector: GuardLineDetector with piste ROI and guard line positions
        
        Returns:
            (tracks, frame_info) if successful, None if not ready yet
        """
        if not guard_line_detector.piste_roi:
            return None
        
        roi = guard_line_detector.piste_roi
        left_line_x = guard_line_detector.guard_line_left_x
        right_line_x = guard_line_detector.guard_line_right_x
        
        # Separate detections by guard line position
        left_side_detections = []  # Detections on left side of left line (x < left_line_x)
        right_side_detections = []  # Detections on right side of right line (x > right_line_x)
        
        for detection in detections:
            bbox = detection['bbox']
            centroid_x = (bbox[0] + bbox[2]) / 2.0
            
            if centroid_x < left_line_x:
                left_side_detections.append(detection)
            elif centroid_x > right_line_x:
                right_side_detections.append(detection)
        
        # Check if we have at least one detection on each side
        if len(left_side_detections) < 1 or len(right_side_detections) < 1:
            # Not ready yet - still waiting for fencers to be on their guard lines
            status = f'🔍 Waiting for fencers on guard lines... (left: {len(left_side_detections)}, right: {len(right_side_detections)})'
            return None
        
        # Take the most stable detection from each side (average position if multiple)
        def get_best_detection(detections_list):
            """Get the detection with most consistent position (by clustering)."""
            if len(detections_list) == 1:
                return detections_list[0]
            
            # If multiple detections, take the one closest to side boundary
            # For left side: rightmost one (closest to left_line_x)
            # For right side: leftmost one (closest to right_line_x)
            if detections_list[0]['bbox'][0] < left_line_x:  # Left side
                return max(detections_list, key=lambda d: (d['bbox'][0] + d['bbox'][2]) / 2.0)
            else:  # Right side
                return min(detections_list, key=lambda d: (d['bbox'][0] + d['bbox'][2]) / 2.0)
        
        fencer1_detection = get_best_detection(left_side_detections)
        fencer2_detection = get_best_detection(right_side_detections)
        
        # Verify they're not too close (should be at least 100px apart)
        bbox1 = fencer1_detection['bbox']
        bbox2 = fencer2_detection['bbox']
        centroid1 = ((bbox1[0] + bbox1[2]) / 2.0, (bbox1[1] + bbox1[3]) / 2.0)
        centroid2 = ((bbox2[0] + bbox2[2]) / 2.0, (bbox2[1] + bbox2[3]) / 2.0)
        
        separation = abs(centroid2[0] - centroid1[0])
        min_separation = 80  # Minimum pixel distance between fencers
        
        if separation < min_separation:
            # Fencers too close - wait for better positioning
            return None
        
        # Lock the 2 fencers
        for fencer_id, detection in [(1, fencer1_detection), (2, fencer2_detection)]:
            bbox = detection['bbox']
            centroid = (
                (bbox[0] + bbox[2]) / 2.0,
                (bbox[1] + bbox[3]) / 2.0
            )
            
            self.fencers[fencer_id] = TrackedFencer(
                id=fencer_id,
                bbox=bbox,
                centroid=centroid,
                frames_alive=0,
                frames_since_detection=0
            )
        
        self.initialized = True
        
        print(f"[FencerTracker] ✓ LOCKED 2 fencers using guard lines!")
        print(f"  → Fencer 1 (LEFT): x={centroid1[0]:.0f} (left of {left_line_x})")
        print(f"  → Fencer 2 (RIGHT): x={centroid2[0]:.0f} (right of {right_line_x})")
        print(f"  → Separation: {separation:.0f}px")
        
        # Generate output
        tracks = [
            {
                'id': fencer.id,
                'bbox': fencer.bbox,
                'centroid': fencer.centroid
            }
            for fencer in self.fencers.values()
        ]
        
        frame_box = self._calculate_frame_box()
        
        return tracks, {
            'initialized': True,
            'num_fencers': len(tracks),
            'frame_box': frame_box,
            'status': '✓ Fencers locked on guard lines - starting bout!'
        }
    
    def _calculate_frame_box(self) -> Optional[Tuple[int, int, int, int]]:
        """
        Calculate optimal bounding box to frame all active fencers.
        Includes padding for better composition.
        """
        if not self.fencers:
            return None
        
        bboxes = [f.bbox for f in self.fencers.values()]
        
        x1_min = min(b[0] for b in bboxes)
        y1_min = min(b[1] for b in bboxes)
        x2_max = max(b[2] for b in bboxes)
        y2_max = max(b[3] for b in bboxes)
        
        # Add padding (10% on each side)
        width = x2_max - x1_min
        height = y2_max - y1_min
        padding_x = int(width * 0.1)
        padding_y = int(height * 0.1)
        
        frame_x1 = max(0, x1_min - padding_x)
        frame_y1 = max(0, y1_min - padding_y)
        frame_x2 = x2_max + padding_x
        frame_y2 = y2_max + padding_y
        
        return (frame_x1, frame_y1, frame_x2, frame_y2)
    
    @staticmethod
    def _centroid_from_bbox(bbox: Tuple[int, int, int, int]) -> Tuple[float, float]:
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    def validate_fencers_on_guard_lines(self, guard_line_detector, current_detections: List[Dict] = None) -> Dict:
        """
        Validate that locked fencers are positioned on their correct guard lines.
        
        Args:
            guard_line_detector: GuardLineDetector instance
            current_detections: Optional list of current detections for validation
        
        Returns:
            {
                'fencer_1_on_guard': bool (on left/5m line),
                'fencer_2_on_guard': bool (on right/9m line),
                'both_on_guard': bool,
                'status': str (user-friendly message)
            }
        """
        if not self.initialized or not self.fencers or len(self.fencers) < 2:
            return {
                'fencer_1_on_guard': False,
                'fencer_2_on_guard': False,
                'both_on_guard': False,
                'status': '❓ Fencers not initialized'
            }
        
        # If no detections provided, we can't validate
        if not current_detections:
            return {
                'fencer_1_on_guard': False,
                'fencer_2_on_guard': False,
                'both_on_guard': False,
                'status': '❓ No detections to validate'
            }
        
        # Get guard line detection results
        guard_result = guard_line_detector.detect_on_guard_line(current_detections)
        left_detection = guard_result.get('left')
        right_detection = guard_result.get('right')
        
        # Check Fencer 1 (should be on left line at ~5m)
        fencer_1 = self.fencers.get(1)
        fencer_2 = self.fencers.get(2)
        
        fencer_1_on_guard = False
        fencer_2_on_guard = False
        
        # Validate Fencer 1 is on left guard line
        if fencer_1 and left_detection:
            f1_bbox = fencer_1.bbox
            left_bbox = left_detection.get('bbox')
            # Check if they're the same detection (same or very close bbox)
            if left_bbox and self._bboxes_overlap_significantly(f1_bbox, left_bbox):
                fencer_1_on_guard = True
        
        # Validate Fencer 2 is on right guard line
        if fencer_2 and right_detection:
            f2_bbox = fencer_2.bbox
            right_bbox = right_detection.get('bbox')
            # Check if they're the same detection
            if right_bbox and self._bboxes_overlap_significantly(f2_bbox, right_bbox):
                fencer_2_on_guard = True
        
        both_on_guard = fencer_1_on_guard and fencer_2_on_guard
        
        # Generate status message
        if both_on_guard:
            status = "✅ Both fencers on guard lines - Ready!"
        elif fencer_1_on_guard and not fencer_2_on_guard:
            status = "⚠️ Fencer 1 on guard line ✓, Fencer 2 NOT on guard line ✗"
        elif not fencer_1_on_guard and fencer_2_on_guard:
            status = "⚠️ Fencer 1 NOT on guard line ✗, Fencer 2 on guard line ✓"
        else:
            status = "⚠️ Neither fencer on guard lines - Check positions!"
        
        return {
            'fencer_1_on_guard': fencer_1_on_guard,
            'fencer_2_on_guard': fencer_2_on_guard,
            'both_on_guard': both_on_guard,
            'status': status
        }
    
    @staticmethod
    def _bboxes_overlap_significantly(bbox1: Tuple[int, int, int, int], bbox2: Tuple[int, int, int, int], threshold: float = 0.5) -> bool:
        """
        Check if two bounding boxes overlap significantly (Intersection over Union > threshold).
        
        Args:
            bbox1, bbox2: (x1, y1, x2, y2)
            threshold: Minimum IoU to consider significant overlap (0.5 = 50%)
        
        Returns:
            True if IoU > threshold
        """
        x1_1, y1_1, x2_1, y2_1 = bbox1
        x1_2, y1_2, x2_2, y2_2 = bbox2
        
        # Calculate intersection
        xi1 = max(x1_1, x1_2)
        yi1 = max(y1_1, y1_2)
        xi2 = min(x2_1, x2_2)
        yi2 = min(y2_1, y2_2)
        
        if xi2 < xi1 or yi2 < yi1:
            return False  # No intersection
        
        intersection = (xi2 - xi1) * (yi2 - yi1)
        
        # Calculate union
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union = area1 + area2 - intersection
        
        iou = intersection / union if union > 0 else 0
        return iou > threshold

