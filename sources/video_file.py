import cv2
from core.interfaces import FrameSource

class VideoFileSource(FrameSource):
    def __init__(self, path: str):
        self.cap = cv2.VideoCapture(path)

    def read(self):
        return self.cap.read()

    def release(self):
        self.cap.release()
