"""Minimal person detector wrapper using Ultralytics YOLO.

This class is a thin wrapper around a YOLO model. It performs lazy imports
so the rest of the codebase can be tested without installing the model.

Method `detect(frame)` returns a list of detections where each detection is
`{'bbox': (x1,y1,x2,y2), 'score': float}` and coordinates are in image pixels.
"""
from typing import List, Dict, Tuple


class PersonDetector:
    def __init__(self, model_name: str = "yolov8n.pt", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self.model = None

    def _ensure_model(self):
        if self.model is not None:
            return
        try:
            from ultralytics import YOLO
        except Exception as e:
            raise RuntimeError(
                "Ultralytics YOLO import failed. Install `ultralytics` to use PersonDetector"
            ) from e

        # Load model (lazy)
        self.model = YOLO(self.model_name)

    def detect(self, frame) -> List[Dict]:
        """Detect persons in a single frame.

        Args:
            frame: ndarray image (BGR as returned by OpenCV)

        Returns:
            List of detections: {'bbox': (x1,y1,x2,y2), 'score': float}
        """
        self._ensure_model()

        # Run inference
        results = self.model(frame)

        detections = []
        if len(results) == 0:
            return detections

        r = results[0]
        # `r.boxes` provides xyxy, cls, conf
        boxes = getattr(r, "boxes", None)
        if boxes is None:
            return detections

        xyxy = boxes.xyxy.cpu().numpy() if hasattr(boxes.xyxy, "cpu") else boxes.xyxy.numpy()
        confs = boxes.conf.cpu().numpy() if hasattr(boxes.conf, "cpu") else boxes.conf.numpy()
        clss = boxes.cls.cpu().numpy() if hasattr(boxes.cls, "cpu") else boxes.cls.numpy()

        for (x1, y1, x2, y2), conf, cls in zip(xyxy, confs, clss):
            # COCO class 0 is 'person'
            if int(cls) != 0:
                continue
            detections.append({
                "bbox": (float(x1), float(y1), float(x2), float(y2)),
                "score": float(conf),
            })

        return detections
