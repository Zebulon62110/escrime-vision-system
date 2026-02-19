"""Detect fencing pistes by finding horizontal separators and analyzing structure."""
import cv2
import numpy as np
from typing import List, Tuple, Optional

class PisteDetectorV2:
    """Detect multiple fixed pistes using morphology and contour analysis."""
    
    def __init__(
        self,
        brightness_threshold: int = 140,  # lower to catch more boundaries
        min_horizontal_line_length: float = 0.4,  # fraction of image width
        blur_kernel: int = 5,
        close_kernel: int = 11,  # close gaps in lines
        erode_iterations: int = 1,
        dilate_iterations: int = 2,
    ):
        self.brightness_threshold = brightness_threshold
        self.min_horizontal_line_length = min_horizontal_line_length
        self.blur_kernel = blur_kernel
        self.close_kernel = close_kernel
        self.erode_iterations = erode_iterations
        self.dilate_iterations = dilate_iterations
    
    def detect(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detect pistes by finding bright lines separating regions.
        
        Returns:
            List of tuples (x1, y1, x2, y2) for each detected piste.
        """
        if frame is None or frame.size == 0:
            return []
        
        h, w = frame.shape[:2]
        
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Blur to reduce noise
        gray = cv2.GaussianBlur(gray, (self.blur_kernel, self.blur_kernel), 0)
        
        # Find bright areas (piste boundaries are usually lighter)
        _, bright = cv2.threshold(gray, self.brightness_threshold, 255, cv2.THRESH_BINARY)
        
        # Close gaps in bright regions (helps connect nearby lines)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (self.close_kernel, self.close_kernel))
        bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, kernel, iterations=1)
        
        # Horizontal projection: sum brightness per row
        h_proj = np.sum(bright, axis=1)
        
        # Normalize projection
        max_proj = np.max(h_proj) if np.max(h_proj) > 0 else 1
        h_proj_norm = h_proj / max_proj
        
        # Find local maxima (bright rows = likely piste boundaries)
        # Use a conservative threshold
        threshold = 0.15
        
        piste_regions = []
        state = 'dark'  # start in dark region
        region_start = 0
        
        for y in range(h):
            is_bright = h_proj_norm[y] > threshold
            
            if state == 'dark' and is_bright:
                # Entering bright region
                region_start = y
                state = 'bright'
            elif state == 'bright' and not is_bright:
                # Leaving bright region
                region_height = y - region_start
                # Only accept regions with reasonable height (pistes should be ~100-150px)
                if region_height > 40:
                    piste_regions.append((region_start, y))
                state = 'dark'
        
        # Handle last region
        if state == 'bright':
            region_height = h - region_start
            if region_height > 40:
                piste_regions.append((region_start, h))
        
        # Convert to bounding boxes
        result = []
        for y1, y2 in piste_regions:
            result.append((0, y1, w, y2))
        
        return result
    
    def __call__(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Shorthand for detect()."""
        return self.detect(frame)
