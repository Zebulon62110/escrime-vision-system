import numpy as np

from vision.tracker import CentroidTracker


def test_tracker_id_persistence():
	tracker = CentroidTracker(max_disappeared=5, max_distance=50)

	# Frame 1: two objects
	dets1 = [
		{"bbox": (10, 10, 50, 50), "score": 0.9},
		{"bbox": (100, 100, 140, 140), "score": 0.9},
	]
	tracks1 = tracker.update(dets1)
	ids1 = sorted([t["id"] for t in tracks1])
	assert len(ids1) == 2

	# Frame 2: small movement -> should keep same IDs
	dets2 = [
		{"bbox": (12, 12, 52, 52), "score": 0.9},
		{"bbox": (102, 98, 142, 138), "score": 0.9},
	]
	tracks2 = tracker.update(dets2)
	ids2 = sorted([t["id"] for t in tracks2])
	assert set(ids1) == set(ids2)


def test_tracker_new_object_registration():
	tracker = CentroidTracker(max_disappeared=5, max_distance=50)

	dets1 = [{"bbox": (0, 0, 20, 20), "score": 0.9}]
	tracks1 = tracker.update(dets1)
	assert len(tracks1) == 1
	first_id = tracks1[0]["id"]

	# Frame 2: same object + new object
	dets2 = [
		{"bbox": (2, 2, 22, 22), "score": 0.9},
		{"bbox": (100, 100, 140, 140), "score": 0.9},
	]
	tracks2 = tracker.update(dets2)
	ids = [t["id"] for t in tracks2]
	assert first_id in ids
	assert len(tracks2) == 2
