"""Detect fencing pistes using Hough line detection for robust, stable results."""
import cv2
import numpy as np
from typing import List, Tuple, Optional

class PisteDetectorV3:
    """Detect fixed pistes using Hough line detection."""
    
    def __init__(
        self,
        canny_low: int = 50,
        canny_high: int = 150,
        hough_threshold: int = 100,  # minimum votes for a line
        hough_min_length: float = 0.6,  # fraction of image width
        hough_max_gap: float = 0.1,  # fraction of image width
        horizontal_tolerance: float = 5,  # degrees tolerance for horizontal
    ):
        self.canny_low = canny_low
        self.canny_high = canny_high
        self.hough_threshold = hough_threshold
        self.hough_min_length = hough_min_length
        self.hough_max_gap = hough_max_gap
        self.horizontal_tolerance = horizontal_tolerance
        
        # Cache for detected separators (should be stable)
        self._cached_separators = None
        self._cached_frame_count = 0
    
    def detect(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detect pistes by finding horizontal lines that separate them.
        
        Returns:
            List of tuples (x1, y1, x2, y2) for each piste region.
        """
        if frame is None or frame.size == 0:
            return []
        
        h, w = frame.shape[:2]
        
        # Grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Edge detection
        edges = cv2.Canny(gray, self.canny_low, self.canny_high)
        
        # Dilate to connect broken edges
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        edges = cv2.dilate(edges, kernel, iterations=1)
        
        # Hough line detection - find lines
        min_length = int(w * self.hough_min_length)
        max_gap = int(w * self.hough_max_gap)
        
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi/180,
            threshold=self.hough_threshold,
            minLineLength=min_length,
            maxLineGap=max_gap
        )
        
        # Extract horizontal lines (separators)
        horizontal_lines = []
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                # Check if line is roughly horizontal
                angle_deg = abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)
                if angle_deg < self.horizontal_tolerance or angle_deg > (180 - self.horizontal_tolerance):
                    # Average y position
                    y_avg = (y1 + y2) // 2
                    horizontal_lines.append((y_avg, min(x1, x2), max(x1, x2)))
        
        # Cluster nearby horizontal lines (multiple detections of same separator)
        if not horizontal_lines:
            return []
        
        horizontal_lines.sort()
        separators = []
        current_group = [horizontal_lines[0][0]]
        
        for y, x1, x2 in horizontal_lines[1:]:
            if y - current_group[-1] < 20:  # cluster tolerance
                current_group.append(y)
            else:
                # Average the cluster
                sep_y = int(np.mean(current_group))
                separators.append(sep_y)
                current_group = [y]
        
        # Add last cluster
        if current_group:
            sep_y = int(np.mean(current_group))
            separators.append(sep_y)
        
        # Sort separators
        separators = sorted(set(separators))
        
        # Build piste regions from separators
        piste_regions = []
        
        # Region before first separator (piste 1)
        if separators:
            piste_regions.append((0, separators[0]))
            
            # Regions between separators
            for i in range(len(separators) - 1):
                piste_regions.append((separators[i], separators[i+1]))
            
            # Region after last separator
            piste_regions.append((separators[-1], h))
        else:
            # No separators found, treat whole image as one piste
            piste_regions.append((0, h))
        
        # Convert to bounding boxes and filter small regions
        result = []
        min_height = 40  # minimum piste height
        
        for y1, y2 in piste_regions:
            if y2 - y1 >= min_height:
                result.append((0, y1, w, y2))
        
        return result
    
    def __call__(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Shorthand for detect()."""
        return self.detect(frame)
