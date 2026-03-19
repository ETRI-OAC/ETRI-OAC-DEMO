#!/usr/bin/env python3
"""
Simple IoU-based person tracker for persistent ID assignment across frames.

Lightweight SORT-style tracker that matches bounding boxes between frames
using IoU (Intersection over Union) and assigns persistent integer IDs.
No external dependencies required.
"""

from typing import List, Optional
import numpy as np


class PersonTracker:
    """Assign persistent IDs to detected bounding boxes across frames."""

    def __init__(self, iou_threshold: float = 0.3, max_lost: int = 15):
        """
        Args:
            iou_threshold: Minimum IoU to match a detection to an existing track.
            max_lost: Number of frames a track can be unmatched before removal.
        """
        self.iou_threshold = iou_threshold
        self.max_lost = max_lost
        self._next_id = 0
        # Each track: {"id": int, "bbox": [x1,y1,x2,y2], "lost": int}
        self._tracks: List[dict] = []

    def update(self, bboxes: List[List[float]]) -> List[int]:
        """
        Match new detections to existing tracks and return assigned IDs.

        Args:
            bboxes: List of [x1, y1, x2, y2] bounding boxes for this frame.

        Returns:
            List of integer IDs, one per input bbox, in the same order.
        """
        if len(bboxes) == 0:
            # Age out all tracks
            self._tracks = [
                t for t in self._tracks if t["lost"] < self.max_lost
            ]
            for t in self._tracks:
                t["lost"] += 1
            return []

        if len(self._tracks) == 0:
            # No existing tracks — create new ones for all detections
            ids = []
            for bbox in bboxes:
                track_id = self._next_id
                self._next_id += 1
                self._tracks.append({"id": track_id, "bbox": bbox, "lost": 0})
                ids.append(track_id)
            return ids

        # Compute IoU matrix: tracks × detections
        iou_matrix = np.zeros((len(self._tracks), len(bboxes)))
        for i, track in enumerate(self._tracks):
            for j, bbox in enumerate(bboxes):
                iou_matrix[i, j] = _iou(track["bbox"], bbox)

        # Greedy matching (highest IoU first)
        matched_track_indices = set()
        matched_det_indices = set()
        assignments: dict = {}  # det_index -> track_index

        # Flatten and sort by IoU descending
        flat_indices = np.argsort(-iou_matrix.ravel())
        for flat_idx in flat_indices:
            ti = int(flat_idx // len(bboxes))
            di = int(flat_idx % len(bboxes))
            if ti in matched_track_indices or di in matched_det_indices:
                continue
            if iou_matrix[ti, di] < self.iou_threshold:
                break  # All remaining are below threshold
            assignments[di] = ti
            matched_track_indices.add(ti)
            matched_det_indices.add(di)

        # Build result IDs
        result_ids = []
        for di, bbox in enumerate(bboxes):
            if di in assignments:
                ti = assignments[di]
                self._tracks[ti]["bbox"] = bbox
                self._tracks[ti]["lost"] = 0
                result_ids.append(self._tracks[ti]["id"])
            else:
                # New track
                track_id = self._next_id
                self._next_id += 1
                self._tracks.append({"id": track_id, "bbox": bbox, "lost": 0})
                result_ids.append(track_id)

        # Age unmatched tracks
        for ti, track in enumerate(self._tracks):
            if ti not in matched_track_indices:
                track["lost"] += 1

        # Remove dead tracks
        self._tracks = [t for t in self._tracks if t["lost"] < self.max_lost]

        return result_ids


def _iou(box_a: List[float], box_b: List[float]) -> float:
    """Compute IoU between two [x1, y1, x2, y2] boxes."""
    x1 = max(box_a[0], box_b[0])
    y1 = max(box_a[1], box_b[1])
    x2 = min(box_a[2], box_b[2])
    y2 = min(box_a[3], box_b[3])

    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, box_a[2] - box_a[0]) * max(0.0, box_a[3] - box_a[1])
    area_b = max(0.0, box_b[2] - box_b[0]) * max(0.0, box_b[3] - box_b[1])
    union = area_a + area_b - inter

    if union <= 0:
        return 0.0
    return inter / union
