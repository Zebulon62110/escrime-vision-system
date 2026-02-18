from core.interfaces import Encoder

class NVENCEncoder(Encoder):
    def __init__(self):
        # implémentation spécifique Jetson via GStreamer
        pass

    def encode(self, frame):
        pass

    def close(self):
        pass
