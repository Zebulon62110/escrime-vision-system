import os

from core.pipeline import VisionPipeline
from sources.video_file import VideoFileSource
from stream.encoder_software import SoftwareEncoder
from stream.encoder_dummy import DummyEncoder
from stream import mjpeg_server
from vision.person_detector import PersonDetector
from vision.piste_detector import PisteDetector
from vision.fencer_detector import FencerDetector
from vision.fencer_tracker import FencerTracker
from vision.bout_manager import BoutManager
try:
    from stream import rtsp_gst_server
    from stream.encoder_gst import GstEncoder
except Exception:
    rtsp_gst_server = None
    GstEncoder = None
import cv2
import numpy as np
import platform


# -------- CONFIG --------

VIDEO_PATH = "data/test.mp4"
WIDTH = 1280
HEIGHT = 720
FPS = 30

MODE = os.getenv("MODE", "DEV")


# -------- DUMMY MODULES (temporaire) --------

# Removed DummyTracker - now using FencerTracker for actual 2-fencer tracking


# -------- MAIN --------

def main():

    print(f"Starting pipeline in {MODE} mode")

    source = VideoFileSource(VIDEO_PATH)
    person_detector = PersonDetector(model_name="yolov8n.pt", device="cpu")
    fencer_detector = FencerDetector(person_detector=person_detector)
    piste_detector = PisteDetector()
    tracker = FencerTracker()  # Smart 2-fencer tracker with auto-initialization
    
    # Start MJPEG preview server in DEV (fallback)
    if MODE == "DEV":
        try:
            mjpeg_server.start_server(background=True)
            print("MJPEG preview available at http://localhost:8080/preview")
        except Exception:
            print("Failed to start MJPEG preview server")

    # Start Python RTSP server (GStreamer) if available, otherwise rely on external rtsp-simple-server
    use_gst = False
    # Ask server to use hardware encoder when running on Jetson/aarch64
    is_jetson = platform.machine().lower().startswith('aarch')
    if rtsp_gst_server is not None:
        try:
            rtsp_gst_server.start_server(background=True, port=8554, width=WIDTH, height=HEIGHT, fps=FPS, use_hw=is_jetson)
            use_gst = True
            print("GStreamer RTSP server started at rtsp://localhost:8554/live (use_hw=%s)" % is_jetson)
        except Exception:
            print("GStreamer RTSP server failed to start — will use external RTSP server if present")
    else:
        print("GStreamer bindings not installed; expecting external RTSP server (rtsp-simple-server / MediaMTX)")

    if MODE == "DEV":
        # prefer GstEncoder if available, otherwise DummyEncoder (updates MJPEG preview)
        if GstEncoder is not None and use_gst:
            encoder = GstEncoder(WIDTH, HEIGHT, FPS)
        else:
            encoder = DummyEncoder(WIDTH, HEIGHT, FPS)
    else:
        # Production: prefer pushing via ffmpeg to external RTSP server
        encoder = SoftwareEncoder(WIDTH, HEIGHT, FPS)

    # Create bout manager for state machine (WAITING → INITIALIZING → BOUT_ACTIVE)
    bout_manager = BoutManager()

    pipeline = VisionPipeline(
        source=source,
        person_detector=fencer_detector,  # Use specialized fencer detector
        piste_detector=piste_detector,
        tracker=tracker,
        bout_manager=bout_manager,
        encoder=encoder,
    )

    pipeline.run()


if __name__ == "__main__":
    main()


