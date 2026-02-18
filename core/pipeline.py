import cv2
import time

class VisionPipeline:
    def __init__(self, source, detector, tracker, encoder):
        self.source = source
        self.detector = detector
        self.tracker = tracker
        self.encoder = encoder

    def run(self):
        while True:
            ret, frame = self.source.read()
            if not ret:
                break

            detections = self.detector.detect(frame)
            tracks = self.tracker.update(detections)

            # TODO: framing logic

            self.encoder.encode(frame)

        self.cleanup()

    def cleanup(self):
        self.source.release()
        self.encoder.close()
