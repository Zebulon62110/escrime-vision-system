import numpy as np
from core.interfaces import Encoder
try:
    from .mjpeg_server import update_frame
except Exception:
    # fallback if server module not available
    def update_frame(frame):
        return


class DummyEncoder(Encoder):
    """Encodeur dummy pour le mode DEV - met à jour l'aperçu MJPEG"""

    def __init__(self, width, height, fps):
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_count = 0

    def encode(self, frame: np.ndarray):
        self.frame_count += 1
        # update preview server with current frame
        try:
            update_frame(frame)
        except Exception:
            pass
        if self.frame_count % 30 == 0:  # Afficher tous les 30 frames
            print(f"[Encoder] Frame {self.frame_count} encoded (shape: {frame.shape})")

    def close(self):
        print(f"[Encoder] Pipeline finished - Total frames processed: {self.frame_count}")
