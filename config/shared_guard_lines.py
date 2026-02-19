"""
Shared guard line adjustment state between web server and pipeline.
Manages horizontal offsets and tilt factors for guard lines.
"""
import os
import json
import threading

GUARD_LINES_FILE = os.path.join(os.path.dirname(__file__), "guard_lines_state.json")
_lock = threading.Lock()

# Default adjustments
DEFAULT_STATE = {
    "left_offset": 0,      # pixels to offset left guard line
    "right_offset": 0,     # pixels to offset right guard line
    "center_offset": 0,    # pixels to offset center line
    "left_tilt": 1.0,      # tilt factor for left line
    "right_tilt": 1.0,     # tilt factor for right line
    "center_tilt": 1.0,    # tilt factor for center line
}

def _ensure_file():
    """Ensure the guard lines state file exists."""
    if not os.path.exists(GUARD_LINES_FILE):
        with open(GUARD_LINES_FILE, 'w') as f:
            json.dump(DEFAULT_STATE, f, indent=2)

def set_guard_line_adjustment(line_id: str, offset_x: float = None, tilt: float = None) -> dict:
    """
    Set the adjustment for a guard line.
    
    Args:
        line_id: 'left', 'right', or 'center'
        offset_x: Horizontal offset in pixels (None to keep current)
        tilt: Tilt factor (None to keep current)
    
    Returns:
        Updated state dict
    """
    _ensure_file()
    with _lock:
        try:
            with open(GUARD_LINES_FILE, 'r') as f:
                state = json.load(f)
        except:
            state = DEFAULT_STATE.copy()
        
        # Update fields
        if offset_x is not None:
            state[f'{line_id}_offset'] = float(offset_x)
        if tilt is not None:
            state[f'{line_id}_tilt'] = float(tilt)
        
        # Write back
        with open(GUARD_LINES_FILE, 'w') as f:
            json.dump(state, f, indent=2)
        
        return state

def get_guard_lines_adjustments() -> dict:
    """Get all guard line adjustments."""
    _ensure_file()
    with _lock:
        try:
            with open(GUARD_LINES_FILE, 'r') as f:
                return json.load(f)
        except:
            return DEFAULT_STATE.copy()

def reset_guard_lines_adjustments() -> dict:
    """Reset all adjustments to defaults."""
    with _lock:
        with open(GUARD_LINES_FILE, 'w') as f:
            json.dump(DEFAULT_STATE, f, indent=2)
    return DEFAULT_STATE.copy()
