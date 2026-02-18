import os

from core.pipeline import VisionPipeline
from sources.video_file import VideoFileSource
from stream.encoder_software import SoftwareEncoder


# -------- CONFIG --------

VIDEO_PATH = "data/test.mp4"
WIDTH = 1280
HEIGHT = 720
FPS = 30

MODE = os.getenv("MODE", "DEV")


# -------- DUMMY MODULES (temporaire) --------

class DummyDetector:
    def detect(self, frame):
        return []


class DummyTracker:
    def update(self, detections):
        return []


# -------- MAIN --------

def main():

    print(f"Starting pipeline in {MODE} mode")

    source = VideoFileSource(VIDEO_PATH)
    detector = DummyDetector()
    tracker = DummyTracker()
    encoder = SoftwareEncoder(WIDTH, HEIGHT, FPS)

    pipeline = VisionPipeline(
        source=source,
        detector=detector,
        tracker=tracker,
        encoder=encoder,
    )

    pipeline.run()


if __name__ == "__main__":
    main()
