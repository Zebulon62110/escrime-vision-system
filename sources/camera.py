import cv2
from core.interfaces import FrameSource

class CameraSource(FrameSource):
    def __init__(self, pipeline: str):
        self.cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

    def read(self):
        return self.cap.read()

    def release(self):
        self.cap.release()
