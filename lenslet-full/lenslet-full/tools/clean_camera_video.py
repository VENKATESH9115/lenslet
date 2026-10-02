"""Remove visible source-camera/platform marks from the Lenslet hero video.

The source clip is intentionally kept as the visual base. This pass removes
the bright manufacturer/model lettering in the camera's badge zones and the
fixed corner glyph, then leaves all other pixels untouched as far as the
inpainting pass allows.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def logo_mask(frame: np.ndarray) -> np.ndarray:
    height, width = frame.shape[:2]
    mask = np.zeros((height, width), dtype=np.uint8)

    # The generated clip keeps the camera inside these stable zones while it
    # moves through the assembled/exploded beats. Restricting the text mask to
    # these zones prevents bright particles from being altered elsewhere.
    zones = (
        (327, 96, 573, 233),   # raised rear/top housing
        (480, 130, 713, 287),   # top-center housing
        (673, 220, 860, 380),  # body badge / model mark
    )
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    for x1, y1, x2, y2 in zones:
        roi_gray = gray[y1:y2, x1:x2]
        roi_hsv = hsv[y1:y2, x1:x2]

        # Manufacturer lettering is pale and low-chroma. The slightly lower
        # threshold also catches the grey mark on the dark housing without
        # touching the copper highlights around it.
        pale = (roi_gray >= 105) & (roi_hsv[:, :, 1] <= 105)
        local = (pale.astype(np.uint8) * 255)
        local = cv2.morphologyEx(local, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
        local = cv2.dilate(local, np.ones((3, 3), np.uint8), iterations=1)
        mask[y1:y2, x1:x2] = np.maximum(mask[y1:y2, x1:x2], local)

    # A few frames render the same wordmark as low-contrast grey, so it does
    # not survive the absolute-brightness threshold above. Use a local
    # top-hat filter in tight badge boxes to isolate only the lettering rather
    # than painting over the whole housing.
    text_boxes = (
        (420, 125, 530, 175),
        (420, 170, 505, 220),
        (565, 215, 685, 270),
        (145, 185, 255, 265),
        (340, 245, 465, 305),
    )
    for x1, y1, x2, y2 in text_boxes:
        roi_gray = gray[y1:y2, x1:x2]
        roi_hsv = hsv[y1:y2, x1:x2]
        local_bg = cv2.morphologyEx(
            roi_gray,
            cv2.MORPH_OPEN,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21)),
        )
        detail = cv2.subtract(roi_gray, local_bg)
        local = ((detail >= 8) & (roi_hsv[:, :, 1] <= 145)).astype(np.uint8) * 255
        local = cv2.morphologyEx(local, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
        local = cv2.dilate(local, np.ones((3, 3), np.uint8), iterations=1)
        mask[y1:y2, x1:x2] = np.maximum(mask[y1:y2, x1:x2], local)

    # Fixed silver corner glyph present in the supplied source clip.
    cv2.ellipse(mask, (1161, 600), (38, 36), 0, 0, 360, 255, -1)
    mask = cv2.GaussianBlur(mask, (3, 3), 0)
    _, mask = cv2.threshold(mask, 32, 255, cv2.THRESH_BINARY)
    return mask


def clean(source: Path, destination: Path) -> None:
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open source video: {source}")

    fps = capture.get(cv2.CAP_PROP_FPS) or 24.0
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    destination.parent.mkdir(parents=True, exist_ok=True)

    writer = cv2.VideoWriter(
        str(destination),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        capture.release()
        raise RuntimeError(f"Could not create output video: {destination}")

    index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        mask = logo_mask(frame)
        cleaned = cv2.inpaint(frame, mask, 3, cv2.INPAINT_TELEA)
        writer.write(cleaned)
        index += 1

    capture.release()
    writer.release()
    if index != frames:
        raise RuntimeError(f"Processed {index} frames, expected {frames}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    clean(args.source, args.destination)


if __name__ == "__main__":
    main()
