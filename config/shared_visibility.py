"""
Shared visibility state between web server and pipeline.
Manages whether piste and guard lines should be visible.
"""
import os
import json
import threading

VISIBILITY_FILE = os.path.join(os.path.dirname(__file__), "visibility_state.json")
_lock = threading.Lock()

def _ensure_file():
    """Ensure the visibility state file exists."""
    if not os.path.exists(VISIBILITY_FILE):
        with open(VISIBILITY_FILE, 'w') as f:
            json.dump({"piste_visible": True}, f)

def set_piste_visible(visible: bool):
    """Set whether the piste should be visible."""
    _ensure_file()
    with _lock:
        try:
            with open(VISIBILITY_FILE, 'w') as f:
                json.dump({"piste_visible": bool(visible)}, f)
        except Exception as e:
            print(f"[SharedVisibility] Error writing visibility state: {e}")

def get_piste_visible() -> bool:
    """Get whether the piste should be visible. Defaults to True."""
    _ensure_file()
    with _lock:
        try:
            with open(VISIBILITY_FILE, 'r') as f:
                data = json.load(f)
                return data.get("piste_visible", True)
        except Exception as e:
            print(f"[SharedVisibility] Error reading visibility state: {e}")
            return True
