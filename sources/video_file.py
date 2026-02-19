import cv2
from core.interfaces import FrameSource

class VideoFileSource(FrameSource):
    def __init__(self, path: str, loop: bool = True):
        self.path = path
        self.loop = loop
        self.cap = cv2.VideoCapture(path)
        self.frame_count = 0

    def read(self):
        ret, frame = self.cap.read()
        if not ret and self.loop:
            # Video ended, restart from beginning
            self.cap.release()
            self.cap = cv2.VideoCapture(self.path)
            self.frame_count = 0
            ret, frame = self.cap.read()
        self.frame_count += 1
        return ret, frame

    def release(self):
        self.cap.release()
