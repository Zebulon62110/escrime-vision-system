"""
Bout state machine for managing different phases of fencing bouts.

Phases:
1. WAITING: Awaiting ROI selection
   - Accept detections without ROI filtering
   - Awaiting user to select/validate piste ROI
   
2. ROI_VALIDATION: ROI selected, awaiting fencers on guard lines
   - Apply ROI filtering to detect only on piste
   - Wait for 2 fencers positioned on guard lines (5m and 9m marks)
   - Detect guard lines using GuardLineDetector
   
3. INITIALIZING: Fencers positioned on guard lines
   - FencerTracker collecting frames to stabilize IDs
   - Fencer 1 locked on left guard line, Fencer 2 on right
   
4. BOUT_ACTIVE: Fencers locked, bout in progress
   - Apply stable auto-framing
   - Limit frame box movement (prevent "seasickness")
   - Track 2 locked fencers
   
5. BOUT_FINISHED: Bout over
   - Reset back to WAITING
"""

from enum import Enum
from typing import Optional, Tuple, Dict
import time
from vision.guard_line_detector import GuardLineDetector


class BoutPhase(Enum):
    """Bout phases."""
    WAITING = "waiting"
    ROI_VALIDATION = "roi_validation"  # ROI selected, awaiting fencers on guard lines
    INITIALIZING = "initializing"
    BOUT_ACTIVE = "bout_active"
    BOUT_FINISHED = "bout_finished"


class BoutManager:
    """Manage state transitions and behavior during different bout phases."""
    
    def __init__(
        self,
        initialization_duration: float = 5.0,  # Seconds to wait for tracker to lock fencers
        max_frame_velocity: float = 50.0,  # Max pixels/frame for smooth framing
        guard_line_stability_frames: int = 10,  # Frames fencers must be on guard lines before locking
    ):
        """
        Args:
            initialization_duration: Time to wait for tracker initialization
            max_frame_velocity: Max frame box movement per frame (prevents jarring motions)
            guard_line_stability_frames: Frames to collect before confirming fencers on guard lines
        """
        self.phase = BoutPhase.WAITING
        self.initialization_duration = initialization_duration
        self.max_frame_velocity = max_frame_velocity
        self.guard_line_stability_frames = guard_line_stability_frames
        self.roi_selected = False  # Signal that piste/ROI has been selected
        
        # Guard line detector
        self.guard_line_detector = GuardLineDetector()
        
        # Track how long fencers have been on guard lines
        self.guard_line_frame_count = 0
        self.fencer_left_on_line = False
        self.fencer_right_on_line = False
        
        self.phase_start_time = time.time()
        self.last_frame_box: Optional[Tuple[int, int, int, int]] = None
        self.smoothed_frame_box: Optional[Tuple[int, int, int, int]] = None
    
    def signal_roi_selected(self, roi: Tuple[int, int, int, int] = None):
        """
        Signal that user has selected and validated the piste ROI.
        Allow transition to ROI_VALIDATION phase.
        
        Args:
            roi: (x1, y1, x2, y2) piste boundaries in pixels
        """
        self.roi_selected = True
        if roi:
            self.guard_line_detector.set_roi(roi)
        print("[BoutManager] 📍 ROI selected - ready to detect fencers on guard lines")
    
    def transition(self, tracker_info: Dict, bout_finished: bool = False) -> BoutPhase:
        """
        Determine phase transition based on tracker state and signals.
        
        Args:
            tracker_info: Output from FencerTracker.update() with initialization status
            bout_finished: Signal that bout has ended (user clicked stop)
        
        Returns:
            Current phase after transition
        """
        initialized = tracker_info.get('initialized', False)
        num_fencers = tracker_info.get('num_fencers', 0)
        time_in_phase = time.time() - self.phase_start_time
        
        if bout_finished:
            self.phase = BoutPhase.BOUT_FINISHED
            self.phase_start_time = time.time()
            return self.phase
        
        if self.phase == BoutPhase.WAITING:
            # Only transition to INITIALIZING once BOTH conditions are met:
            # 1. User has selected and validated the piste ROI
            # 2. We detect 2+ fencers on the piste (with ROI filtering applied)
            if self.roi_selected and num_fencers >= 2:
                self.phase = BoutPhase.INITIALIZING
                self.phase_start_time = time.time()
                print(f"[BoutManager] ⚡ Phase → INITIALIZING (ROI validated, {num_fencers} fencers on piste)")
        
        elif self.phase == BoutPhase.INITIALIZING:
            # Transition to BOUT_ACTIVE once tracker is initialized
            # (tracker collected enough frames and locked 2 fencers on the piste)
            if initialized:
                self.phase = BoutPhase.BOUT_ACTIVE
                self.phase_start_time = time.time()
                self.last_frame_box = None  # Reset for smooth transition
                print(f"[BoutManager] 🤺 Phase → BOUT_ACTIVE (fencers locked)")
                return self.phase
            
            # Timeout: go back to waiting if initialization takes too long
            elif time_in_phase > self.initialization_duration * 2:
                self.phase = BoutPhase.WAITING
                self.phase_start_time = time.time()
                self.roi_selected = False  # Reset
                print(f"[BoutManager] ⏱ Phase → WAITING (initialization timeout)")
        
        elif self.phase == BoutPhase.BOUT_ACTIVE:
            # Stay in BOUT_ACTIVE unless bout_finished signal received
            # Or if all fencers disappear for extended time
            if num_fencers < 2:
                # Could add logic here to handle temporary occlusion
                pass
        
        elif self.phase == BoutPhase.BOUT_FINISHED:
            # Reset after 2 seconds
            if time_in_phase > 2.0:
                self.phase = BoutPhase.WAITING
                self.phase_start_time = time.time()
                self.last_frame_box = None
                print(f"[BoutManager] 🔄 Phase → WAITING (reset for next bout)")
        
        return self.phase
    
    def should_apply_roi_filter(self) -> bool:
        """
        Determine if ROI filtering should be applied.
        
        Returns:
            True if in INITIALIZING or BOUT_ACTIVE phase (apply strict ROI filtering to piste only)
            False if in WAITING (allow all detections, awaiting ROI selection)
        """
        return self.phase in (BoutPhase.INITIALIZING, BoutPhase.BOUT_ACTIVE)
    
    def smooth_frame_box(
        self,
        new_frame_box: Optional[Tuple[int, int, int, int]]
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Apply smoothing to frame box to prevent jarring camera movements.
        
        Args:
            new_frame_box: Proposed frame box from FencerTracker
        
        Returns:
            Smoothed frame box (clamped to max velocity)
        """
        if new_frame_box is None:
            self.last_frame_box = None
            self.smoothed_frame_box = None
            return None
        
        # First frame
        if self.last_frame_box is None:
            self.last_frame_box = new_frame_box
            self.smoothed_frame_box = new_frame_box
            return new_frame_box
        
        # Clamp movement to max velocity
        x1, y1, x2, y2 = new_frame_box
        last_x1, last_y1, last_x2, last_y2 = self.last_frame_box
        
        # Calculate movement
        dx1 = max(-self.max_frame_velocity, min(self.max_frame_velocity, x1 - last_x1))
        dy1 = max(-self.max_frame_velocity, min(self.max_frame_velocity, y1 - last_y1))
        dx2 = max(-self.max_frame_velocity, min(self.max_frame_velocity, x2 - last_x2))
        dy2 = max(-self.max_frame_velocity, min(self.max_frame_velocity, y2 - last_y2))
        
        # Apply clamped movement
        smoothed_x1 = int(last_x1 + dx1)
        smoothed_y1 = int(last_y1 + dy1)
        smoothed_x2 = int(last_x2 + dx2)
        smoothed_y2 = int(last_y2 + dy2)
        
        self.smoothed_frame_box = (smoothed_x1, smoothed_y1, smoothed_x2, smoothed_y2)
        self.last_frame_box = (smoothed_x1, smoothed_y1, smoothed_x2, smoothed_y2)
        
        return self.smoothed_frame_box
    
    def get_phase_display(self) -> str:
        """Get human-readable phase name for UI display."""
        phase_names = {
            BoutPhase.WAITING: "⏳ Waiting for fencers",
            BoutPhase.INITIALIZING: "🔍 Initializing fencer detection",
            BoutPhase.BOUT_ACTIVE: "🤺 Bout in progress",
            BoutPhase.BOUT_FINISHED: "☑️ Bout finished",
        }
        return phase_names.get(self.phase, "Unknown")
