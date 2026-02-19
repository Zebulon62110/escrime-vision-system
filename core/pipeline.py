import cv2
import time
import json
import os
from config.shared_roi import get_manual_roi
from config.shared_visibility import get_piste_visible
from config.shared_guard_lines import get_guard_lines_adjustments

STATS_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "pipeline_stats.json")

class VisionPipeline:
    def __init__(self, source, person_detector, piste_detector, tracker, bout_manager, encoder):
        self.source = source
        self.person_detector = person_detector
        self.piste_detector = piste_detector
        self.tracker = tracker
        self.bout_manager = bout_manager
        self.encoder = encoder
        self.fencer_count = 0
        self.guard_validation = {}  # Track fencer positioning on guard lines
        self.roi_signaled = False  # Track if we've already signaled ROI selection to BoutManager

    def _save_stats(self):
        """Save pipeline stats to JSON file for web API"""
        try:
            stats = {
                "fencer_count": self.fencer_count,
                "guard_validation": self.guard_validation,
                "timestamp": time.time()
            }
            with open(STATS_FILE, 'w') as f:
                json.dump(stats, f)
        except Exception as e:
            print(f"[Pipeline] Failed to save stats: {e}")

    def run(self):
        while True:
            ret, frame = self.source.read()
            if not ret:
                break

            # Detect pistes (list of regions)
            piste_bboxes = self.piste_detector.detect(frame)

            # Check if a ROI has been selected by user
            current_roi = get_manual_roi()
            if current_roi is not None and not self.roi_signaled:
                self.bout_manager.signal_roi_selected(current_roi)
                self.roi_signaled = True
            
            # If ROI was cleared, reset the signal
            if current_roi is None:
                self.roi_signaled = False

            # Decide whether to apply ROI filtering based on bout phase
            # In WAITING: No ROI filtering (awaiting ROI selection)
            # In INITIALIZING: ROI filtering ON (only detect fencers on the piste)
            # In BOUT_ACTIVE: ROI filtering ON (track only on piste)
            apply_roi_filter = self.bout_manager.should_apply_roi_filter()
            
            # Apply color filtering (white/gray fencers only) to exclude referee and spectators
            apply_color_filter = True  # Always filter for white/gray clothing
            
            # Detect persons (fencers) - with optional ROI filtering and color filtering
            detections = self.person_detector.detect(frame, apply_roi_filter=apply_roi_filter, apply_color_filter=apply_color_filter)
            
            # Update fencer tracker with detections
            # Returns (tracks, frame_info) where tracks are the tracked fencers
            # Pass guard_line_detector to help identify fencers by guard line position
            tracks, track_info = self.tracker.update(detections, guard_line_detector=self.bout_manager.guard_line_detector)
            
            # Validate that fencers are on their correct guard lines
            guard_validation = self.tracker.validate_fencers_on_guard_lines(
                self.bout_manager.guard_line_detector,
                current_detections=detections
            )
            track_info['guard_validation'] = guard_validation
            
            # Update bout manager state based on tracker status
            current_phase = self.bout_manager.transition(track_info)
            
            # Save fencer count and tracker status to stats file
            self.fencer_count = len(tracks)
            self.guard_validation = guard_validation  # Store validation results for web API
            self._save_stats()

            # Draw overlays
            vis = frame.copy()
            
            # Apply any pending guard line adjustments from shared state
            adjustments = get_guard_lines_adjustments()
            if self.bout_manager.guard_line_detector.piste_roi and adjustments:
                # Apply left line adjustment
                if adjustments.get('left_offset') is not None or adjustments.get('left_tilt') is not None:
                    self.bout_manager.guard_line_detector.adjust_guard_line(
                        'left',
                        offset_x=adjustments.get('left_offset', 0),
                        tilt=adjustments.get('left_tilt', 1.0)
                    )
                # Apply right line adjustment
                if adjustments.get('right_offset') is not None or adjustments.get('right_tilt') is not None:
                    self.bout_manager.guard_line_detector.adjust_guard_line(
                        'right',
                        offset_x=adjustments.get('right_offset', 0),
                        tilt=adjustments.get('right_tilt', 1.0)
                    )
                # Apply center line adjustment
                if adjustments.get('center_offset') is not None or adjustments.get('center_tilt') is not None:
                    self.bout_manager.guard_line_detector.adjust_guard_line(
                        'center',
                        offset_x=adjustments.get('center_offset', 0),
                        tilt=adjustments.get('center_tilt', 1.0)
                    )
            
            # Draw guard lines if ROI is configured AND piste is set to be visible
            guard_line_viz = self.bout_manager.guard_line_detector.get_visualization_lines()
            if guard_line_viz and get_piste_visible():
                try:
                    x1_roi, y1_roi, x2_roi, y2_roi = guard_line_viz.get('piste_roi', (0, 0, 0, 0))
                    center_x_roi = (x1_roi + x2_roi) / 2.0
                    
                    # Draw piste boundary rectangle
                    cv2.rectangle(vis, (int(x1_roi), int(y1_roi)), (int(x2_roi), int(y2_roi)), 
                                (100, 100, 100), 2)
                    
                    # Perspective effect: lines diverge away from center as they go deeper
                    # Can be adjusted via tilt factors
                    left_tilt = guard_line_viz.get('left_tilt', 1.0)
                    right_tilt = guard_line_viz.get('right_tilt', 1.0)
                    center_tilt = guard_line_viz.get('center_tilt', 1.0)
                    perspective_factor = 0.15  # Divergence factor for depth effect
                    piste_depth = y2_roi - y1_roi
                    
                    # Left guard line (5m length) - GREEN vertical line with adjustable perspective
                    left_x = guard_line_viz.get('guard_line_left_x')
                    if left_x:
                        # Top of line (near camera)
                        x_top = int(left_x)
                        # Bottom of line (far from camera) - diverges away from center with tilt
                        divergence = (center_x_roi - left_x) * perspective_factor * left_tilt
                        x_bottom = int(left_x - divergence)
                        
                        # Draw thick line with perspective
                        cv2.line(vis, (x_top, int(y1_roi)), (x_bottom, int(y2_roi)), (0, 255, 0), 3)
                        # Draw top marker
                        cv2.circle(vis, (x_top, int(y1_roi) - 20), 8, (0, 255, 0), -1)
                        # Draw bottom marker
                        cv2.circle(vis, (x_bottom, int(y2_roi) + 20), 8, (0, 255, 0), -1)
                        # Draw label
                        cv2.putText(vis, "5m", (x_top - 15, int(y1_roi) - 40),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    
                    # Right guard line (9m length) - GREEN vertical line with adjustable perspective
                    right_x = guard_line_viz.get('guard_line_right_x')
                    if right_x:
                        # Top of line (near camera)
                        x_top = int(right_x)
                        # Bottom of line (far from camera) - diverges away from center with tilt
                        divergence = (right_x - center_x_roi) * perspective_factor * right_tilt
                        x_bottom = int(right_x + divergence)
                        
                        # Draw thick line with perspective
                        cv2.line(vis, (x_top, int(y1_roi)), (x_bottom, int(y2_roi)), (0, 255, 0), 3)
                        # Draw top marker
                        cv2.circle(vis, (x_top, int(y1_roi) - 20), 8, (0, 255, 0), -1)
                        # Draw bottom marker
                        cv2.circle(vis, (x_bottom, int(y2_roi) + 20), 8, (0, 255, 0), -1)
                        # Draw label
                        cv2.putText(vis, "9m", (x_top - 15, int(y1_roi) - 40),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    
                    # Center line (7m length) - BLUE vertical line with adjustable perspective
                    center_x = guard_line_viz.get('center_x')
                    if center_x:
                        # Center line typically stays mostly straight but can have slight tilt
                        x_top = int(center_x)
                        # Minimal divergence for center (usually center_tilt = 1.0 for straight)
                        divergence = (center_tilt - 1.0) * perspective_factor * (right_x - left_x) if right_x and left_x else 0
                        x_bottom = int(center_x + divergence)
                        
                        # Draw vertical line with adjustable perspective
                        cv2.line(vis, (x_top, int(y1_roi)), (x_bottom, int(y2_roi)), (255, 100, 0), 2)
                        # Small markers
                        cv2.circle(vis, (x_top, int(y1_roi) - 20), 5, (255, 100, 0), -1)
                        cv2.circle(vis, (x_bottom, int(y2_roi) + 20), 5, (255, 100, 0), -1)
                except Exception as e:
                    print(f"[Pipeline] Error drawing guard lines: {e}")
            
            # Draw bout phase at top
            phase_text = self.bout_manager.get_phase_display()
            cv2.putText(vis, phase_text, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 2)
            
            # Draw tracked fencers with their IDs
            for track in tracks:
                bbox = track.get('bbox')
                track_id = track.get('id', 0)
                
                if bbox and len(bbox) == 4:
                    x1, y1, x2, y2 = bbox
                    
                    # Color and style based on fencer ID
                    if track_id == 1:
                        # Fencer 1 - BLUE
                        color = (255, 0, 0)  # BGR: Blue
                        thickness = 3
                        label = 'Fencer 1'
                    elif track_id == 2:
                        # Fencer 2 - ORANGE
                        color = (0, 165, 255)  # BGR: Orange
                        thickness = 3
                        label = 'Fencer 2'
                    elif track_id >= 100:
                        # Other detections - YELLOW (provisional, not locked)
                        color = (0, 255, 255)  # BGR: Yellow
                        thickness = 1
                        label = f'Other'
                    else:
                        # Fallback
                        color = (200, 200, 200)  # Gray
                        thickness = 1
                        label = f'ID {track_id}'
                    
                    cv2.rectangle(vis, (int(x1), int(y1)), (int(x2), int(y2)), color, thickness)
                    # Draw ID label
                    cv2.putText(vis, label, (int(x1), int(y1) - 5),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            # Draw optimal framing box (to keep both fencers in view) with smoothing
            raw_frame_box = track_info.get('frame_box')
            frame_box = self.bout_manager.smooth_frame_box(raw_frame_box)
            
            if frame_box:
                x1, y1, x2, y2 = frame_box
                cv2.rectangle(vis, (int(x1), int(y1)), (int(x2), int(y2)), (255, 255, 0), 2)  # Cyan

            # Draw tracking status on screen
            status = track_info.get('status', 'Tracking...')
            cv2.putText(vis, status, (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)

            self.encoder.encode(vis)

        self.cleanup()

    def cleanup(self):
        self.source.release()
        self.encoder.close()
