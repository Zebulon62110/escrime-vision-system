import subprocess
import numpy as np
from core.interfaces import Encoder

class SoftwareEncoder(Encoder):
    def __init__(self, width, height, fps):
        self.process = subprocess.Popen(
            [
                "ffmpeg",
                "-y",
                "-f", "rawvideo",
                "-vcodec","rawvideo",
                "-pix_fmt","bgr24",
                "-s", f"{width}x{height}",
                "-r", str(fps),
                "-i","-",
                "-c:v","libx264",
                "-preset","veryfast",
                    "-f","rtsp",
                    "-rtsp_transport","tcp",
                    "rtsp://localhost:8554/live"
            ],
            stdin=subprocess.PIPE
        )

    def encode(self, frame: np.ndarray):
        self.process.stdin.write(frame.tobytes())

    def close(self):
        self.process.stdin.close()
        self.process.wait()
