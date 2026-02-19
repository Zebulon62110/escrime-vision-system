import numpy as np
from core.interfaces import Encoder

try:
    from .rtsp_gst_server import push_frame
except Exception:
    def push_frame(frame):
        return False


class GstEncoder(Encoder):
    """Encoder that pushes frames to a local GStreamer RTSP server."""

    def __init__(self, width, height, fps):
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_count = 0

    def encode(self, frame: np.ndarray):
        self.frame_count += 1
        try:
            ok = push_frame(frame)
            if not ok and self.frame_count % 60 == 0:
                print("[GstEncoder] push_frame failed (server missing?)")
        except Exception:
            if self.frame_count % 60 == 0:
                print("[GstEncoder] exception pushing frame")

    def close(self):
        print(f"[GstEncoder] Pipeline finished - Total frames processed: {self.frame_count}")
