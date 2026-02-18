from abc import ABC, abstractmethod
import numpy as np

class FrameSource(ABC):
    @abstractmethod
    def read(self) -> tuple[bool, np.ndarray]:
        pass

    @abstractmethod
    def release(self):
        pass


class Detector(ABC):
    @abstractmethod
    def detect(self, frame: np.ndarray) -> list:
        pass


class Tracker(ABC):
    @abstractmethod
    def update(self, detections: list) -> list:
        pass


class Encoder(ABC):
    @abstractmethod
    def encode(self, frame: np.ndarray):
        pass

    @abstractmethod
    def close(self):
        pass
