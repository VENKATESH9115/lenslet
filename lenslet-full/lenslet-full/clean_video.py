from pathlib import Path
import os

import cv2
import imageio_ffmpeg
import numpy as np


source = Path("frontend/public/animations/camera-dismantling.mp4")
temporary = Path(os.environ["TEMP"]) / "lenslet-camera-clean-video.mp4"
preview = Path(os.environ["TEMP"]) / "lenslet-camera-clean-preview.png"

cap = cv2.VideoCapture(str(source))
if not cap.isOpened():
    raise RuntimeError("Could not open source video")

width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = cap.get(cv2.CAP_PROP_FPS) or 24

mask = np.zeros((height, width), dtype=np.uint8)
cv2.ellipse(mask, (1162, 600), (43, 42), 0, 0, 360, 255, -1)

writer = imageio_ffmpeg.write_frames(
    str(temporary),
    (width, height),
    fps=fps,
    codec="libx264",
    pix_fmt_out="yuv420p",
    quality=8,
    output_params=["-movflags", "+faststart"],
)
writer.send(None)

frame_number = 0
while True:
    ok, frame = cap.read()
    if not ok:
        break
    cleaned = cv2.inpaint(frame, mask, 7, cv2.INPAINT_TELEA)
    if frame_number == 48:
        cv2.imwrite(str(preview), cleaned)
    writer.send(cv2.cvtColor(cleaned, cv2.COLOR_BGR2RGB).tobytes())
    frame_number += 1

cap.release()
writer.close()
print(f"processed {frame_number} frames at {width}x{height} / {fps:g} fps")
