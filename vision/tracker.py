"""Simple centroid-based tracker for stable IDs.

This tracker is intentionally lightweight and dependency-free. It matches
detections between frames by centroid distance and assigns persistent IDs.

Track structure returned by `update()`:
  {'id': int, 'bbox': (x1,y1,x2,y2), 'centroid': (cx,cy)}
"""
from typing import List, Dict, Tuple
import numpy as np


class CentroidTracker:
    def __init__(self, max_disappeared: int = 10, max_distance: float = 50.0):
        self.next_id = 1
        self.objects = {}  # id -> bbox
        self.centroids = {}  # id -> (cx,cy)
        self.disappeared = {}  # id -> frames disappeared
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance

    @staticmethod
    def _centroid_from_bbox(bbox: Tuple[float, float, float, float]):
        x1, y1, x2, y2 = bbox
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        return (cx, cy)

    def register(self, bbox: Tuple[float, float, float, float]):
        obj_id = self.next_id
        self.next_id += 1
        self.objects[obj_id] = bbox
        self.centroids[obj_id] = self._centroid_from_bbox(bbox)
        self.disappeared[obj_id] = 0
        return obj_id

    def deregister(self, obj_id: int):
        del self.objects[obj_id]
        del self.centroids[obj_id]
        del self.disappeared[obj_id]

    def update(self, detections: List[Dict]) -> List[Dict]:
        """Update tracks with detections.

        Args:
            detections: list of {'bbox': (x1,y1,x2,y2), ...}

        Returns:
            list of tracks: {'id', 'bbox', 'centroid'}
        """
        if len(detections) == 0:
            # mark all existing as disappeared
            for obj_id in list(self.disappeared.keys()):
                self.disappeared[obj_id] += 1
                if self.disappeared[obj_id] > self.max_disappeared:
                    self.deregister(obj_id)
            return [
                {"id": obj_id, "bbox": self.objects[obj_id], "centroid": self.centroids[obj_id]}
                for obj_id in self.objects
            ]

        input_bboxes = [d["bbox"] for d in detections]
        input_centroids = np.array([self._centroid_from_bbox(b) for b in input_bboxes])

        if len(self.objects) == 0:
            # register all
            for bbox in input_bboxes:
                self.register(bbox)
        else:
            # build distance matrix
            object_ids = list(self.centroids.keys())
            object_centroids = np.array([self.centroids[i] for i in object_ids])

            # distances: rows = objects, cols = inputs
            D = np.linalg.norm(object_centroids[:, None, :] - input_centroids[None, :, :], axis=2)

            # for each object, find closest input; greedy matching
            rows = D.min(axis=1).argsort()
            cols = D.argmin(axis=1)[rows]

            assigned_cols = set()
            for r, c in zip(rows, cols):
                if c in assigned_cols:
                    continue
                dist = D[r, c]
                if dist > self.max_distance:
                    continue
                obj_id = object_ids[r]
                bbox = input_bboxes[c]
                self.objects[obj_id] = bbox
                self.centroids[obj_id] = tuple(input_centroids[c].tolist())
                self.disappeared[obj_id] = 0
                assigned_cols.add(c)

            # register unassigned input detections
            for i, bbox in enumerate(input_bboxes):
                if i not in assigned_cols:
                    self.register(bbox)

            # mark disappeared for unassigned existing
            assigned_ids = {object_ids[r] for r, c in zip(rows, cols) if c in assigned_cols}
            for obj_id in list(self.objects.keys()):
                if obj_id not in assigned_ids and obj_id in self.disappeared:
                    self.disappeared[obj_id] += 1
                    if self.disappeared[obj_id] > self.max_disappeared:
                        self.deregister(obj_id)

        # prepare output
        tracks = [
            {"id": obj_id, "bbox": self.objects[obj_id], "centroid": self.centroids[obj_id]}
            for obj_id in self.objects
        ]
        return tracks
