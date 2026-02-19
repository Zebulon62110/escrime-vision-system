"""
Shared ROI configuration between web server and pipeline.

The web server saves selected ROI to a file, and the pipeline reads it.
This uses file persistence since Python processes don't share memory.
"""
import json
import os

# File path for ROI persistence
ROI_FILE = os.path.join(os.path.dirname(__file__), "manual_roi.json")

def set_manual_roi(x1: int, y1: int, x2: int, y2: int):
    """Set the manual ROI from web UI selection."""
    roi_data = {
        "x1": max(0, int(x1)),
        "y1": max(0, int(y1)),
        "x2": min(1280, int(x2)),
        "y2": min(720, int(y2))
    }
    try:
        with open(ROI_FILE, 'w') as f:
            json.dump(roi_data, f)
        print(f"[SharedROI] ✓ Saved ROI to {ROI_FILE}: {roi_data}")
    except Exception as e:
        print(f"[SharedROI] ✗ Failed to save ROI: {e}")

def get_manual_roi():
    """Get the current manual ROI, or None if not set."""
    try:
        if os.path.exists(ROI_FILE):
            with open(ROI_FILE, 'r') as f:
                roi_data = json.load(f)
                roi = (roi_data["x1"], roi_data["y1"], roi_data["x2"], roi_data["y2"])
                print(f"[SharedROI] ✓ Loaded ROI from file: {roi}")
                return roi
    except Exception as e:
        print(f"[SharedROI] ✗ Failed to load ROI: {e}")
    return None

def clear_manual_roi():
    """Clear the manual ROI."""
    try:
        if os.path.exists(ROI_FILE):
            os.remove(ROI_FILE)
            print(f"[SharedROI] ✓ Cleared ROI file")
    except Exception as e:
        print(f"[SharedROI] ✗ Failed to clear ROI: {e}")
