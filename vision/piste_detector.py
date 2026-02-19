"""Detect fencing pistes - supports manual ROI selection from web UI."""
import cv2
import numpy as np
from typing import List, Tuple
from config.shared_roi import get_manual_roi


class PisteDetector:
    """
    Detect fencing pistes (fencer detection area).
    
    Supports two modes:
    1. Manual ROI selection (user draws rectangle in web UI) - recommended
    2. Automatic detection (unreliable, kept for fallback)
    """
    
    def __init__(
        self,
        saturation_threshold: int = 35,
        gray_coverage_threshold: float = 0.5,
        min_piste_height: int = 15,
    ):
        """
        Args:
            saturation_threshold: HSV saturation threshold for gray pixels
            gray_coverage_threshold: Minimum fraction of row that must be gray
            min_piste_height: Minimum height for a region
        """
        self.saturation_threshold = saturation_threshold
        self.gray_coverage_threshold = gray_coverage_threshold
        self.min_piste_height = min_piste_height
        self.manual_roi = None  # Manual piste ROI if set by user

    def detect(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Return piste ROI(s) for fencer detection.
        
        If manual ROI is set (via web UI or API), returns it.
        Otherwise attempts automatic detection (fallback, unreliable).
        """
        if frame is None or frame.size == 0:
            return []
        
        # Check for manually selected ROI from web UI
        shared_roi = get_manual_roi()
        if shared_roi is not None:
            x1, y1, x2, y2 = shared_roi
            return [(x1, y1, x2, y2)]
        
        # Also check instance-level manual ROI
        if self.manual_roi is not None:
            x1, y1, x2, y2 = self.manual_roi
            return [(x1, y1, x2, y2)]
        
        # Fallback: automatic detection (unreliable but kept for compatibility)
        return self._detect_automatic(frame)
    
    def set_manual_roi(self, x1: int, y1: int, x2: int, y2: int):
        """Set manual piste ROI from user selection (web UI)."""
        self.manual_roi = (max(0, x1), max(0, y1), min(1280, x2), min(720, y2))
    
    def get_manual_roi(self):
        """Get the currently set manual ROI, or None."""
        return self.manual_roi
    
    def _detect_automatic(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        
        h, w = frame.shape[:2]
        
        # Convert to HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        saturation = hsv[:, :, 1]
        
        # Gray pixels have low saturation
        gray_mask = saturation < self.saturation_threshold
        
        # Horizontal projection
        h_proj = np.sum(gray_mask.astype(np.uint8), axis=1)
        
        # Threshold for region detection
        gray_threshold = int(w * self.gray_coverage_threshold)
        
        # Find regions with sufficient gray coverage
        piste_regions = []
        in_piste = False
        piste_start = 0
        
        for y in range(h):
            if h_proj[y] >= gray_threshold:
                if not in_piste:
                    piste_start = y
                    in_piste = True
            else:
                if in_piste:
                    if y - piste_start >= self.min_piste_height:
                        piste_regions.append((piste_start, y))
                    in_piste = False
        
        if in_piste and h - piste_start >= self.min_piste_height:
            piste_regions.append((piste_start, h))
        
        # Filter to reasonable piste regions
        # True pistes are: 16-20px (P1/P2) or can be from 15-70px (P3 as merged region)
        # We'll split large regions (>50px) later
        piste_regions = [
            (y1, y2) for y1, y2 in piste_regions
            if 15 <= (y2 - y1) <= 70 and 350 <= y1 < 600
        ]
        
        if len(piste_regions) == 0:
            piste_height = h // 4
            piste_regions = [(i * piste_height, (i + 1) * piste_height) for i in range(4)]
        
        # Split large regions (likely two merged pistes)
        piste_regions = self._split_large_regions_new(piste_regions)
        
        # Filter to keep best 4
        piste_regions = self._filter_pistes(piste_regions)
        
        # Convert to bounding boxes
        result = []
        for y1, y2 in piste_regions:
            result.append((0, y1, w, y2))
        
        return result
    
    def _find_bands_from_edges(self, edge_proj: np.ndarray, h: int, w: int) -> List[Tuple[int, int]]:
        """Placeholder - not used with saturation-based detection."""
        return []
    
    def _split_large_regions_new(self, regions: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """
        Split large regions that appear to be two merged pistes.
        Piste 3 is known to span approximately y=478-548, and should be split at y~513.
        """
        result = []
        for y1, y2 in regions:
            height = y2 - y1
            # If this looks like it could be piste 3 (in the ~478-548 range, height >= 40px),
            # split it at y=513 to separate piste 3a and 3b
            if 40 <= height and 450 <= y1 < 500:
                # This is likely the large piste 3 - split at fixed y=513
                result.append((y1, 513))
                result.append((513, y2))
            elif height > 50:  # Other large regions - split at middle
                mid = (y1 + y2) // 2
                result.append((y1, mid))
                result.append((mid, y2))
            else:
                result.append((y1, y2))
        return result
    
    def _split_large_regions(
        self, regions: List[Tuple[int, int]], h_proj: np.ndarray
    ) -> List[Tuple[int, int]]:
        """
        Split large regions that appear to be two merged pistes.
        This is not used with edge-based detection but kept for compatibility.
        """
        return regions
    
    def _filter_pistes(self, regions: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """
        Filter piste regions to keep only the 4 expected pistes.
        
        Expected piste positions:
        - Piste 1: y~404-420 (top)
        - Piste 2: y~426-446
        - Piste 3a: y~478-513 (part 1 of split)
        - Piste 3b: y~513-548 (part 2 of split)
        
        Rejects any "ghost" region at y>550.
        """
        regions = self._remove_overlaps(regions)
        
        # Include only regions in the main piste area (y < 550)
        # This automatically excludes the "ghost" piste at y=552+
        main_regions = [(y1, y2) for y1, y2 in regions if y2 < 550]
        
        # If we have exactly 4 or fewer, use what we have
        if len(main_regions) <= 4:
            return sorted(main_regions)
        
        # If we have > 4 in main area, keep the 4 largest
        regions_with_size = [(y2 - y1, y1, y2) for y1, y2 in main_regions]
        regions_with_size.sort(reverse=True)
        result = [(y1, y2) for _, y1, y2 in regions_with_size[:4]]
        return sorted(result)
    
    def _remove_overlaps(self, regions: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """Remove overlapping or too-close piste regions, keeping the best ones."""
        if len(regions) <= 4:
            # If we have 4 or fewer, they're probably good - just ensure no overlaps
            filtered = []
            for y1, y2 in regions:
                # Check if this overlaps with any already-added region
                overlaps = False
                for existing_y1, existing_y2 in filtered:
                    # Regions overlap if one starts before the other ends
                    if y1 < existing_y2 and y2 > existing_y1:
                        # Keep the larger one
                        if (y2 - y1) > (existing_y2 - existing_y1):
                            filtered.remove((existing_y1, existing_y2))
                        else:
                            overlaps = True
                            break
                
                if not overlaps:
                    filtered.append((y1, y2))
            
            return sorted(filtered)
        
        # If we have > 4 pistes, keep only the 4 largest
        regions_with_size = [(y2 - y1, y1, y2) for y1, y2 in regions]
        regions_with_size.sort(reverse=True)
        
        # Keep top 4 by size, then sort by y-position
        top_4 = [(y1, y2) for _, y1, y2 in regions_with_size[:4]]
        return sorted(top_4)
    
    def __call__(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        return self.detect(frame)
