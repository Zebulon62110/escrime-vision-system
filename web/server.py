from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import threading
import uvicorn
import os
import urllib.request
from fastapi.responses import StreamingResponse, Response
import subprocess
import sys
import json

# Import shared ROI config
try:
    from config.shared_roi import set_manual_roi, get_manual_roi
    SHARED_ROI_AVAILABLE = True
    print("[Server] ✓ Successfully imported shared_roi")
except ImportError as e:
    SHARED_ROI_AVAILABLE = False
    print(f"[Server] ✗ Failed to import shared_roi: {e}")
    def set_manual_roi(*args): pass
    def get_manual_roi(): return None

# Import shared visibility config
try:
    from config.shared_visibility import set_piste_visible, get_piste_visible
    SHARED_VISIBILITY_AVAILABLE = True
    print("[Server] ✓ Successfully imported shared_visibility")
except ImportError as e:
    SHARED_VISIBILITY_AVAILABLE = False
    print(f"[Server] ✗ Failed to import shared_visibility: {e}")
    def set_piste_visible(*args): pass
    def get_piste_visible(): return True

# Import shared guard lines config
try:
    from config.shared_guard_lines import set_guard_line_adjustment, get_guard_lines_adjustments, reset_guard_lines_adjustments
    SHARED_GUARD_LINES_AVAILABLE = True
    print("[Server] ✓ Successfully imported shared_guard_lines")
except ImportError as e:
    SHARED_GUARD_LINES_AVAILABLE = False
    print(f"[Server] ✗ Failed to import shared_guard_lines: {e}")
    def set_guard_line_adjustment(*args, **kwargs): return {}
    def get_guard_lines_adjustments(): return {}
    def reset_guard_lines_adjustments(): return {}

# Import piste detector for ROI detection
try:
    from vision.piste_detector import PisteDetector
    from sources.video_file import VideoFileSource
    PISTE_DETECTOR_AVAILABLE = True
except ImportError:
    PISTE_DETECTOR_AVAILABLE = False

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# serve static files from web/static
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# in-memory config
_config = {
    "mode": os.getenv("MODE", "DEV"),
    "selected_piste": None,
    "available_piste_rois": [],  # list of detected pistes (ROI regions)
    # use proxy endpoints so the browser (on Windows) can reach WSL-local services
    "stream_hls_url": "/proxy/hls/live/index.m3u8",
    "stream_mjpeg_url": "/proxy/mjpeg",
}


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.get("/api/status")
def status():
    response = dict(_config)
    # Also include the current ROI from shared_roi if available
    if SHARED_ROI_AVAILABLE:
        current_roi = get_manual_roi()
        response["current_roi_from_pipeline"] = current_roi
    return JSONResponse(response)


@app.get("/api/fencer-count")
def fencer_count():
    """Get current detected fencer count from pipeline stats."""
    try:
        if os.path.exists("config/pipeline_stats.json"):
            with open("config/pipeline_stats.json", 'r') as f:
                stats = json.load(f)
                return JSONResponse({
                    "success": True,
                    "fencer_count": stats.get("fencer_count", 0),
                    "timestamp": stats.get("timestamp", 0)
                })
        else:
            return JSONResponse({
                "success": True,
                "fencer_count": 0,
                "timestamp": 0
            })
    except Exception as e:
        print(f"[Server] Error reading fencer count: {e}")
        return JSONResponse({
            "success": False,
            "fencer_count": 0,
            "error": str(e)
        })


@app.get("/api/guard-validation")
def guard_validation_status():
    """Get current guard line validation status for fencers."""
    try:
        if os.path.exists("config/pipeline_stats.json"):
            with open("config/pipeline_stats.json", 'r') as f:
                stats = json.load(f)
                validation = stats.get("guard_validation", {})
                return JSONResponse({
                    "success": True,
                    "fencer_1_on_guard": validation.get("fencer_1_on_guard", False),
                    "fencer_2_on_guard": validation.get("fencer_2_on_guard", False),
                    "both_on_guard": validation.get("both_on_guard", False),
                    "status": validation.get("status", "Initializing..."),
                    "timestamp": stats.get("timestamp", 0)
                })
        else:
            return JSONResponse({
                "success": True,
                "fencer_1_on_guard": False,
                "fencer_2_on_guard": False,
                "both_on_guard": False,
                "status": "No data yet",
                "timestamp": 0
            })
    except Exception as e:
        print(f"[Server] Error reading guard validation: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        })


@app.post("/api/select")
async def select(request: Request):
    data = await request.json()
    piste = data.get("piste")
    _config["selected_piste"] = piste
    return JSONResponse({"ok": True, "selected_piste": piste})


@app.get("/api/detect-pistes")
def detect_pistes():
    """Detect pistes in the video and return list of ROI bounding boxes."""
    if not PISTE_DETECTOR_AVAILABLE:
        return JSONResponse({"error": "Piste detector not available"}, status_code=503)
    
    VIDEO_PATH = os.getenv("VIDEO_PATH", "data/test.mp4")
    if not os.path.exists(VIDEO_PATH):
        return JSONResponse({"error": f"Video file not found: {VIDEO_PATH}"}, status_code=404)
    
    try:
        source = VideoFileSource(VIDEO_PATH)
        piste_detector = PisteDetector()
        
        detected_rois = []
        piste_all_frames = {}  # piste_index -> list of frames where it appears
        frame_count = 0
        max_samples = 100  # sample first 100 frames
        
        while frame_count < max_samples:
            ret, frame = source.read()
            if not ret:
                break
            
            frame_count += 1
            piste_boxes = piste_detector.detect(frame)
            
            if piste_boxes:
                for piste_idx, (x1, y1, x2, y2) in enumerate(piste_boxes):
                    roi = {
                        "id": piste_idx,
                        "x1": int(x1),
                        "y1": int(y1),
                        "x2": int(x2),
                        "y2": int(y2),
                        "width": int(x2 - x1),
                        "height": int(y2 - y1),
                    }
                    
                    if piste_idx not in piste_all_frames:
                        piste_all_frames[piste_idx] = {"roi": roi, "frames": []}
                    piste_all_frames[piste_idx]["frames"].append(frame_count)
        
        source.release()
        
        # Build final ROI list from most common pistes
        unique_rois = []
        for piste_idx in sorted(piste_all_frames.keys()):
            info = piste_all_frames[piste_idx]
            roi = info["roi"]
            appearances = len(info["frames"])
            
            # Only include pistes that appear in a reasonable number of frames
            if appearances > 5:
                roi["id"] = len(unique_rois)
                unique_rois.append(roi)
        
        _config["available_piste_rois"] = unique_rois
        if unique_rois:
            _config["selected_piste"] = 0
        
        return JSONResponse({
            "success": True,
            "total_frames_sampled": frame_count,
            "total_piste_detections": len(piste_all_frames),
            "stable_pistes": len(unique_rois),
            "rois": unique_rois,
        })
    
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/select-roi")
async def select_roi(request: Request):
    """
    Save manually selected piste ROI (rectangle drawn by user).
    
    Expected JSON: { "x1": int, "y1": int, "x2": int, "y2": int }
    This ROI is immediately applied to the pipeline detector.
    """
    try:
        body = await request.json()
        x1 = int(body.get("x1", 0))
        y1 = int(body.get("y1", 0))
        x2 = int(body.get("x2", 1280))
        y2 = int(body.get("y2", 720))
        
        # Validate coordinates
        if x1 < 0 or y1 < 0 or x2 > 1280 or y2 > 720:
            return JSONResponse({"success": False, "error": "Coordinates out of bounds"}, status_code=400)
        
        if x1 >= x2 or y1 >= y2:
            return JSONResponse({"success": False, "error": "Invalid rectangle"}, status_code=400)
        
        width = x2 - x1
        height = y2 - y1
        
        # Save to shared config so the pipeline detector uses it immediately
        print(f"[Server] set_manual_roi called with: ({x1}, {y1}, {x2}, {y2})")
        set_manual_roi(x1, y1, x2, y2)
        print(f"[Server] SHARED_ROI_AVAILABLE = {SHARED_ROI_AVAILABLE}")
        
        # Reset piste visibility to true so guard lines are visible immediately
        set_piste_visible(True)
        print(f"[Server] Piste visibility reset to True")
        
        # Also store in API config for status endpoint
        _config["selected_piste"] = {
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "width": width, "height": height
        }
        
        return JSONResponse({
            "success": True,
            "message": f"Piste ROI selected: x={x1}-{x2}, y={y1}-{y2}",
            "width": width,
            "height": height
        })
    
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/clear-roi")
async def clear_roi():
    """Clear the manually selected piste ROI and reset the system."""
    try:
        from config.shared_roi import clear_manual_roi
        clear_manual_roi()
        _config["selected_piste"] = None
        return JSONResponse({
            "success": True,
            "message": "Piste ROI cleared"
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/toggle-piste-visibility")
async def toggle_piste_visibility():
    """Toggle the piste and guard lines visibility."""
    current = get_piste_visible()
    new_state = not current
    set_piste_visible(new_state)
    return JSONResponse({
        "success": True,
        "piste_visible": new_state,
        "message": f"Piste {'shown' if new_state else 'hidden'}"
    })


@app.get("/api/piste-visibility")
def get_piste_visibility_endpoint():
    """Get the current piste visibility state."""
    return JSONResponse({
        "success": True,
        "piste_visible": get_piste_visible()
    })


@app.post("/api/adjust-guard-line")
async def adjust_guard_line(request: Request):
    """
    Adjust a guard line position and/or tilt.
    
    Expected JSON: {
        "line_id": "left" | "right" | "center",
        "offset_x": float (pixels),  # optional
        "tilt": float (1.0 = straight, <1.0 = converge, >1.0 = diverge)  # optional
    }
    """
    try:
        body = await request.json()
        line_id = body.get("line_id", "").lower()
        offset_x = body.get("offset_x")
        tilt = body.get("tilt")
        
        if line_id not in ["left", "right", "center"]:
            return JSONResponse({"success": False, "error": "Invalid line_id"}, status_code=400)
        
        # Update state
        new_state = set_guard_line_adjustment(line_id, offset_x, tilt)
        
        return JSONResponse({
            "success": True,
            "line_id": line_id,
            "adjustments": new_state
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/guard-lines-adjustments")
def get_guard_lines_adjustments_endpoint():
    """Get all current guard line adjustments."""
    return JSONResponse({
        "success": True,
        "adjustments": get_guard_lines_adjustments()
    })


@app.post("/api/reset-guard-lines")
async def reset_guard_lines():
    """Reset all guard line adjustments to defaults."""
    try:
        state = reset_guard_lines_adjustments()
        return JSONResponse({
            "success": True,
            "message": "Guard lines reset to defaults",
            "adjustments": state
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/fencers-count")
def get_fencers_count():
    """Get the current number of detected fencers in the pipeline."""
    # This is a simplified endpoint that returns the fencer count
    # In production, this would be connected to real-time pipeline statistics
    try:
        # For now, return a mock value (0 until we track real statistics)
        # TODO: Integrate with actual pipeline statistics
        return JSONResponse({
            "detected_fencers": 0,  # Will be updated with real count from pipeline
            "timestamp": None
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


def run_server(port: int = 8000, background: bool = True):
    if background:
        # Start uvicorn in a separate process so it outlives the short-lived
        # caller (e.g. `python -c 'run_server(..., background=True)'`).
        logs_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
        try:
            os.makedirs(logs_dir, exist_ok=True)
        except Exception:
            logs_dir = "/tmp"

        out = open(os.path.join(logs_dir, f"web_{port}.log"), "a")
        err = out
        cmd = [sys.executable, "-m", "uvicorn", "web.server:app", "--host", "0.0.0.0", "--port", str(port), "--log-level", "warning"]
        # start_new_session=True detaches the child from the parent's process group
        subprocess.Popen(cmd, stdout=out, stderr=err, start_new_session=True)
    else:
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


@app.get('/proxy/hls/{path:path}')
def proxy_hls(path: str):
    """Proxy HLS files from the local MediaMTX HLS endpoint so the browser can fetch them."""
    upstream = f'http://127.0.0.1:8888/{path}'
    req = urllib.request.Request(upstream, headers={"User-Agent": "escrime-proxy"})
    try:
        resp = urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)
    data = resp.read()
    ctype = resp.getheader('Content-Type') or 'application/vnd.apple.mpegurl'
    return Response(content=data, media_type=ctype)


@app.get('/proxy/mjpeg')
def proxy_mjpeg():
    """Proxy MJPEG multipart stream from the local MJPEG preview server."""
    upstream = 'http://127.0.0.1:8080/preview'
    req = urllib.request.Request(upstream, headers={"User-Agent": "escrime-proxy"})
    try:
        resp = urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

    def stream():
        try:
            while True:
                try:
                    chunk = resp.read(4096)
                    if not chunk:
                        break
                    yield chunk
                except EOFError:
                    # Client disconnected or stream ended
                    break
                except Exception as e:
                    # Handle incomplete reads and other issues without crashing server
                    print(f"[MJPEG Proxy] Stream read error: {e}")
                    break
        finally:
            try:
                resp.close()
            except Exception:
                pass

    ctype = resp.getheader('Content-Type') or 'multipart/x-mixed-replace; boundary=frame'
    return StreamingResponse(stream(), media_type=ctype)


if __name__ == "__main__":
    run_server(background=False)
