"""
Specialized fencer detector for escrime.

Fencers wear white protective gear (tenue blanche) with/without mask.
This detector:
1. Uses YOLO to detect persons
2. Filters by white color (majority of fencer outfit)
3. Filters by ROI (piste region)
"""
import cv2
import numpy as np
import time
from typing import List, Dict, Tuple, Optional
from config.shared_roi import get_manual_roi


class FencerDetector:
    """Detect fencers on the piste based on YOLO person detection + white color filter."""
    
    def __init__(self, person_detector, roi: Optional[Tuple[int, int, int, int]] = None, roi_cache_duration: int = 10):
        """
        Args:
            person_detector: PersonDetector instance (YOLO-based)
            roi: Optional (x1, y1, x2, y2) piste region. If None, uses shared ROI.
            roi_cache_duration: How many seconds to cache ROI before reloading from file (default: 10s)
        """
        self.person_detector = person_detector
        self.roi = roi
        self.roi_cache_duration = roi_cache_duration
        self.last_roi_load_time = 0
        self.cached_roi = None
        self.min_white_ratio = 0.15  # At least 15% of bbox should be white/gray (for outfit)
        
        # HSV ranges for white and light gray clothing (typical fencer attire)
        # Fencers wear white protective gear (jacket, mask, gloves)
        self.white_threshold_lower = np.array([0, 0, 150])      # HSV: low saturation, high value
        self.white_threshold_upper = np.array([180, 50, 255])   # Almost white

        # Light gray range (for some fencing gear variants)
        self.gray_threshold_lower = np.array([0, 0, 100])       # Low saturation, medium value
        self.gray_threshold_upper = np.array([180, 30, 180])    # Light gray
    
    def detect(self, frame: np.ndarray, apply_roi_filter: bool = True, apply_color_filter: bool = True) -> List[Dict]:
        """
        Detect fencers in the frame.
        
        Caches ROI from file - reloads only every roi_cache_duration seconds for efficiency.
        
        Args:
            frame: Input frame to process
            apply_roi_filter: If False, returns all detections without ROI filtering
                            (useful for initialization phase)
            apply_color_filter: If True, filters detections to only white/gray clothed persons (fencers)
                              (helps exclude referee and spectators)
        
        Returns:
            List of detections. If apply_roi_filter=True, only returns fencers 
            whose feet touch the piste. If apply_color_filter=True, only returns
            detections with sufficient white/gray coverage (fencer outfit).
        """
        if frame is None or frame.size == 0:
            return []
        
        # Detect all persons using YOLO first
        all_persons = self.person_detector.detect(frame)
        
        if not all_persons:
            return []
        
        # Apply white/gray color filtering if requested
        if apply_color_filter:
            hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            filtered_persons = []
            for detection in all_persons:
                white_ratio = self._get_white_ratio(hsv_frame, detection.get('bbox'))
                # Include both white and light gray fencers
                gray_ratio = self._get_gray_ratio(hsv_frame, detection.get('bbox'))
                fencer_ratio = max(white_ratio, gray_ratio)
                
                if fencer_ratio >= self.min_white_ratio:
                    filtered_persons.append(detection)
                    # Only log if rejected (less spam)
                else:
                    pass  # Silently reject (likely referee or spectator)
            
            all_persons = filtered_persons
        
        if not all_persons:
            return []
        
        # If not filtering by ROI, return all color-filtered detections
        if not apply_roi_filter:
            return all_persons
        
        # Load ROI from file only if cache expired (every 10 seconds by default)
        current_time = time.time()
        if (current_time - self.last_roi_load_time) >= self.roi_cache_duration:
            self.cached_roi = self.roi or get_manual_roi()
            self.last_roi_load_time = current_time
        
        roi = self.cached_roi
        
        if roi is None:
            # No ROI selected - return empty list (only when filtering by ROI)
            return []
        
        x1_roi, y1_roi, x2_roi, y2_roi = roi
        
        # During initialization, we collect all detections without ROI restriction
        # During tracking (BOUT_ACTIVE), we use the exact ROI with minimal expansion
        # The ROI is drawn by the user as the exact piste boundaries
        # Minimal expansion only to account for slight position variation (5% instead of 15%)
        roi_width = x2_roi - x1_roi
        roi_height = y2_roi - y1_roi
        margin_x = int(roi_width * 0.05)  # Reduced from 0.15 to 0.05 for stricter piste adherence
        margin_y = int(roi_height * 0.05)  # Reduced from 0.15 to 0.05
        
        x1_expanded = max(0, x1_roi - margin_x)
        y1_expanded = max(0, y1_roi - margin_y)
        x2_expanded = min(frame.shape[1], x2_roi + margin_x)
        y2_expanded = min(frame.shape[0], y2_roi + margin_y)
        
        # Filter detections - keep persons whose FEET touch the piste (with margin)
        # Feet are the bottom part of the bbox (y2 coordinate)
        fencers = []
        for detection in all_persons:
            bbox = detection.get('bbox')
            if not bbox or len(bbox) < 4:
                continue
            
            x1, y1, x2, y2 = bbox[:4]
            
            # Check if the FEET (bottom of person bbox, y2 coordinate) are touching the piste area
            # Horizontal overlap with piste
            x_overlaps = not (x2 < x1_expanded or x1 > x2_expanded)
            
            # Vertical overlap - feet must be in contact with piste area
            feet_in_piste_area = (y2 >= y1_expanded and y2 <= y2_expanded)
            
            if x_overlaps and feet_in_piste_area:
                fencers.append(detection)
        
        return fencers
    
    def _get_white_ratio(self, frame_hsv: np.ndarray, bbox: Tuple) -> float:
        """Calculate white pixel ratio for a bbox."""
        if not bbox or len(bbox) < 4:
            return 0.0
        
        x1, y1, x2, y2 = bbox[:4]
        roi_hsv = frame_hsv[int(y1):int(y2), int(x1):int(x2)]
        
        if roi_hsv.size == 0:
            return 0.0
        
        white_mask = cv2.inRange(roi_hsv, self.white_threshold_lower, self.white_threshold_upper)
        return np.count_nonzero(white_mask) / white_mask.size
    
    def _get_gray_ratio(self, frame_hsv: np.ndarray, bbox: Tuple) -> float:
        """Calculate light gray pixel ratio for a bbox."""
        if not bbox or len(bbox) < 4:
            return 0.0
        
        x1, y1, x2, y2 = bbox[:4]
        roi_hsv = frame_hsv[int(y1):int(y2), int(x1):int(x2)]
        
        if roi_hsv.size == 0:
            return 0.0
        
        gray_mask = cv2.inRange(roi_hsv, self.gray_threshold_lower, self.gray_threshold_upper)
        return np.count_nonzero(gray_mask) / gray_mask.size
    
    def set_roi(self, x1: int, y1: int, x2: int, y2: int):
        """Update the ROI for fencer detection."""
        self.roi = (max(0, x1), max(0, y1), x2, y2)
