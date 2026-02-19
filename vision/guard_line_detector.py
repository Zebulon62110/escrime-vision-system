"""
Detect fencers positioned on their guard lines (2m from piste center).

Guard line rules:
- Piste length: 14 meters
- Guard lines: 2m on each side of center (5m and 9m from piste start)
- Valid position: Feet touching the piste within 2m zones on each side

This detector:
1. Calculates pixel-to-meter conversion from ROI dimensions
2. Detects fencers with feet ON guard lines (left/right)
3. Tracks stability on guard lines before locking
"""

from typing import List, Dict, Optional, Tuple
import numpy as np


class GuardLineDetector:
    """Detect fencers positioned on guard lines."""
    
    def __init__(self):
        """Initialize guard line detector."""
        self.piste_roi = None  # (x1, y1, x2, y2) in pixels
        self.pixels_per_meter = None  # Conversion factor
        
        # Initial calculated positions (from 5m/9m percentages)
        self.guard_line_left_x_calc = None  # Calculated x for 5m
        self.guard_line_right_x_calc = None  # Calculated x for 9m
        self.center_x_calc = None  # Calculated center at 7m
        
        # Adjustable positions (user can modify these)
        self.guard_line_left_x = None  # Actual x for left guard line (user adjustable)
        self.guard_line_right_x = None  # Actual x for right guard line (user adjustable)
        self.center_x = None  # Actual center position (user adjustable)
        
        # Perspective/tilt settings
        self.left_tilt = 1.0  # Tilt factor for left line (1.0 = no tilt, <1.0 = converges toward right)
        self.right_tilt = 1.0  # Tilt factor for right line (1.0 = no tilt, >1.0 = diverges away)
        self.center_tilt = 1.0  # Tilt factor for center line (usually 1.0 - straight)
        
        self.guard_line_tolerance = 20  # pixels tolerance for being "on" guard line
    
    def set_roi(self, roi: Tuple[int, int, int, int]) -> None:
        """
        Configure guard lines based on piste ROI.
        
        Args:
            roi: (x1, y1, x2, y2) piste boundaries in pixels
        
        Calculates INITIAL positions based on 5m/9m positions.
        User can then adjust these positions horizontally and apply tilt.
        """
        self.piste_roi = roi
        x1, y1, x2, y2 = roi
        
        # Length calculation (X axis for 14m piste length)
        piste_length_pixels = x2 - x1
        piste_length_meters = 14.0
        self.pixels_per_meter = piste_length_pixels / piste_length_meters
        
        # Calculate initial positions at 5m, 7m, 9m
        self.center_x_calc = x1 + (7.0 / piste_length_meters) * piste_length_pixels
        self.guard_line_left_x_calc = x1 + (5.0 / piste_length_meters) * piste_length_pixels
        self.guard_line_right_x_calc = x1 + (9.0 / piste_length_meters) * piste_length_pixels
        
        # Initialize adjustable positions to calculated values
        self.center_x = self.center_x_calc
        self.guard_line_left_x = self.guard_line_left_x_calc
        self.guard_line_right_x = self.guard_line_right_x_calc
        
        # Initial tilt (no tilt = straight lines)
        self.left_tilt = 1.0
        self.right_tilt = 1.0
        self.center_tilt = 1.0
        
        print(f"[GuardLineDetector] ROI set: {roi}")
        print(f"[GuardLineDetector] Pixels/meter: {self.pixels_per_meter:.2f}")
        print(f"[GuardLineDetector] Initial guard lines (X positions): 5m={self.guard_line_left_x:.0f}px, 7m={self.center_x:.0f}px, 9m={self.guard_line_right_x:.0f}px")
    
    def adjust_guard_line(self, line_id: str, offset_x: float, tilt: float = 1.0) -> None:
        """
        Adjust a guard line position and tilt.
        
        Args:
            line_id: 'left', 'center', or 'right'
            offset_x: Horizontal pixel offset from calculated position
            tilt: Tilt factor (1.0 = no tilt, <1.0 converges, >1.0 diverges)
        """
        if line_id == 'left' and self.guard_line_left_x_calc is not None:
            self.guard_line_left_x = self.guard_line_left_x_calc + offset_x
            self.left_tilt = tilt
            print(f"[GuardLineDetector] Left line adjusted: x={self.guard_line_left_x:.0f}, tilt={tilt:.2f}")
        
        elif line_id == 'right' and self.guard_line_right_x_calc is not None:
            self.guard_line_right_x = self.guard_line_right_x_calc + offset_x
            self.right_tilt = tilt
            print(f"[GuardLineDetector] Right line adjusted: x={self.guard_line_right_x:.0f}, tilt={tilt:.2f}")
        
        elif line_id == 'center' and self.center_x_calc is not None:
            self.center_x = self.center_x_calc + offset_x
            self.center_tilt = tilt
            print(f"[GuardLineDetector] Center line adjusted: x={self.center_x:.0f}, tilt={tilt:.2f}")
    
    def detect_on_guard_line(self, detections: List[Dict]) -> Dict:
        """
        Identify which detections are fencers on guard lines.
        
        Args:
            detections: List of {'bbox': (x1, y1, x2, y2), ...}
        
        Returns:
            {
                'left': detection or None,    # Fencer on left guard line (5m)
                'right': detection or None,   # Fencer on right guard line (9m)
                'on_line': [detections],      # All detections on guard lines
                'status': str
            }
        """
        if not self.piste_roi:
            return {'left': None, 'right': None, 'on_line': [], 'status': '❓ Guard lines not configured'}
        
        x1_roi, y1_roi, x2_roi, y2_roi = self.piste_roi
        center_y = (y1_roi + y2_roi) / 2.0
        
        on_guard_line = []
        left_fencers = []
        right_fencers = []
        
        for detection in detections:
            bbox = detection.get('bbox')
            if not bbox:
                continue
            
            x1, y1, x2, y2 = bbox
            feet_x = x2  # Right side of bounding box = feet position (length on X axis)
            
            # Check if feet are on piste (within ROI X bounds)
            if feet_x < x1_roi or feet_x > x2_roi:
                continue  # Not on piste
            
            # Check if feet are close to either guard line (within tolerance) on X axis (length)
            dist_to_left = abs(feet_x - self.guard_line_left_x)
            dist_to_right = abs(feet_x - self.guard_line_right_x)
            
            if dist_to_left <= self.guard_line_tolerance:
                # On left guard line (5m length)
                on_guard_line.append(detection)
                left_fencers.append((feet_x, detection, dist_to_left))
            
            elif dist_to_right <= self.guard_line_tolerance:
                # On right guard line (9m length)
                on_guard_line.append(detection)
                right_fencers.append((feet_x, detection, dist_to_right))
        
        # Select best fencer on each side (closest to guard line)
        left_detection = None
        right_detection = None
        
        if left_fencers:
            # Find the one closest to the guard line
            left_fencers.sort(key=lambda t: t[2])  # Sort by distance to line
            left_detection = left_fencers[0][1]
        
        if right_fencers:
            # Find the one closest to the guard line
            right_fencers.sort(key=lambda t: t[2])  # Sort by distance to line
            right_detection = right_fencers[0][1]
        
        # Status message
        status = "🔍 Waiting for 2 fencers on guard lines"
        if left_detection and right_detection:
            status = "✅ 2 fencers detected on guard lines - Ready to lock!"
        elif left_detection or right_detection:
            status = f"⚠️  Only 1 fencer on guard line (need 2)"
        
        return {
            'left': left_detection,
            'right': right_detection,
            'on_line': on_guard_line,
            'status': status
        }
    
    def is_on_guard_line(self, bbox: Tuple[int, int, int, int]) -> bool:
        """Check if a single detection is on a guard line."""
        if not self.piste_roi:
            return False
        
        x1_roi, y1_roi, x2_roi, y2_roi = self.piste_roi
        x1, y1, x2, y2 = bbox
        feet_x = x2  # Right side of bbox = feet position (length on X axis)
        
        if feet_x < x1_roi or feet_x > x2_roi:
            return False
        
        dist_to_left = abs(feet_x - self.guard_line_left_x)
        dist_to_right = abs(feet_x - self.guard_line_right_x)
        
        return dist_to_left <= self.guard_line_tolerance or dist_to_right <= self.guard_line_tolerance
    
    def get_guard_line_info(self) -> Dict:
        """Get current guard line configuration."""
        if not self.piste_roi:
            return {}
        
        return {
            'roi': self.piste_roi,
            'pixels_per_meter': self.pixels_per_meter,
            'center_x': self.center_x,
            'guard_line_left_x': self.guard_line_left_x,
            'guard_line_right_x': self.guard_line_right_x,
            'guard_line_tolerance': self.guard_line_tolerance
        }
    
    def get_visualization_lines(self) -> Dict:
        """
        Get line positions for visualization on the video frame.
        
        Returns:
            {
                'piste_roi': (x1, y1, x2, y2),       # Piste boundaries
                'center_x': float,                    # Center line (7m)
                'guard_line_left_x': float,           # Left guard line (5m)
                'guard_line_right_x': float,          # Right guard line (9m)
                'left_tilt': float,                   # Tilt factor for left line
                'right_tilt': float,                  # Tilt factor for right line
                'center_tilt': float,                 # Tilt factor for center line
            }
        """
        if not self.piste_roi:
            return {}
        
        return {
            'piste_roi': self.piste_roi,
            'center_x': self.center_x,
            'guard_line_left_x': self.guard_line_left_x,
            'guard_line_right_x': self.guard_line_right_x,
            'left_tilt': self.left_tilt,
            'right_tilt': self.right_tilt,
            'center_tilt': self.center_tilt,
        }
