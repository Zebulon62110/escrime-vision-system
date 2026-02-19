import threading
import time
import io
import cv2
import numpy as np
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, Response
import uvicorn

app = FastAPI()

# Global latest frame storage
_latest_frame = None
_frame_lock = threading.Lock()


def update_frame(frame):
    """Encode frame as JPEG and store as latest frame."""
    global _latest_frame
    ret, jpeg = cv2.imencode('.jpg', frame)
    if not ret:
        return
    with _frame_lock:
        _latest_frame = jpeg.tobytes()


def frame_generator():
    boundary = b'--frame'
    while True:
        with _frame_lock:
            frame = _latest_frame
        if frame is None:
            # send a tiny placeholder image
            img = 255 * np.ones((10, 10, 3), dtype='uint8')
            ret, jpg = cv2.imencode('.jpg', img)
            frame = jpg.tobytes()
        yield (b"\r\n" + boundary + b"\r\n"
               + b"Content-Type: image/jpeg\r\n"
               + b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n"
               + frame)
        time.sleep(1 / 15)


@app.get('/preview')
def preview():
    return StreamingResponse(frame_generator(), media_type='multipart/x-mixed-replace; boundary=frame')


@app.get('/snapshot')
def snapshot():
    """Return a single JPEG frame (not a stream)"""
    with _frame_lock:
        frame = _latest_frame
    if frame is None:
        # send a tiny placeholder image
        img = 255 * np.ones((10, 10, 3), dtype='uint8')
        ret, jpg = cv2.imencode('.jpg', img)
        frame = jpg.tobytes()
    return Response(content=frame, media_type='image/jpeg')


def _run_uvicorn():
    uvicorn.run(app, host='0.0.0.0', port=8080, log_level='warning')


def start_server(background=True):
    """Start the MJPEG preview server in a background thread."""
    if background:
        t = threading.Thread(target=_run_uvicorn, daemon=True)
        t.start()
    else:
        _run_uvicorn()
