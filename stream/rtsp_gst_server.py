"""Simple RTSP server using GStreamer's GstRtspServer.

This module exposes `start_server()` and `push_frame(frame)`.

Requirements (system):
- GStreamer and gst-rtsp-server (libgstrtspserver-1.0)
- Python bindings: PyGObject (python3-gi) and gir1.2-gst-rtsp-server-1.0

If imports fail, the module will raise an ImportError when started and callers
should fallback to another preview method.
"""
import threading
import time

# Lazy-loaded GStreamer bindings
_gi_available = False
_Gst = None
_GObject = None
_GstRtspServer = None
_appsrc = None
_loop = None


def _ensure_gi():
    """Lazy import of PyGObject and GStreamer — raises ImportError if missing."""
    global _gi_available, _Gst, _GObject, _GstRtspServer
    if _gi_available:
        return
    try:
        import gi
        gi.require_version('Gst', '1.0')
        gi.require_version('GstRtspServer', '1.0')
        from gi.repository import Gst, GObject, GstRtspServer
        _Gst = Gst
        _GObject = GObject
        _GstRtspServer = GstRtspServer
        _Gst.init(None)
        _gi_available = True
    except Exception as e:
        raise ImportError("GStreamer/PyGObject not available") from e


class SensorFactory:
    """Factory that creates media pipeline dynamically.

    The factory uses a hardware encoder pipeline when `use_hw=True` (Jetson).
    """
    def __init__(self, width, height, fps, use_hw=False):
        _ensure_gi()

        class _Factory(_GstRtspServer.RTSPMediaFactory):
            def __init__(self, width, height, fps, use_hw):
                super().__init__()
                self.width = width
                self.height = height
                self.fps = fps
                self.use_hw = use_hw

            def do_create_element(self, url):
                if self.use_hw:
                    # Jetson hardware encoder pipeline (nvvidconv + nvv4l2h264enc)
                    launch = (
                        'appsrc name=mysrc is-live=true block=true format=time '
                        'caps=video/x-raw,format=BGR,width={w},height={h},framerate={f}/1 '
                        '! videoconvert '
                        '! video/x-raw,format=I420 '
                        '! nvvidconv '
                        '! nvv4l2h264enc bitrate=4000000 '
                        '! h264parse '
                        '! rtph264pay name=pay0 pt=96'
                    ).format(w=self.width, h=self.height, f=self.fps)
                else:
                    # software fallback using x264
                    launch = (
                        'appsrc name=mysrc is-live=true block=true format=time '
                        'caps=video/x-raw,format=BGR,width={w},height={h},framerate={f}/1 '
                        '! videoconvert '
                        '! x264enc speed-preset=ultrafast tune=zerolatency bitrate=2000 '
                        '! rtph264pay name=pay0 pt=96'
                    ).format(w=self.width, h=self.height, f=self.fps)
                return _Gst.parse_launch(launch)

            def do_configure(self, rtsp_media):
                global _appsrc
                pipeline = rtsp_media.get_pipeline()
                appsrc = pipeline.get_by_name('mysrc')
                _appsrc = appsrc

        self._factory = _Factory(width, height, fps, use_hw)

    def set_shared(self, v):
        self._factory.set_shared(v)

    def get_factory(self):
        return self._factory


def _main_loop(port=8554, width=1280, height=720, fps=30, use_hw=False):
    global _loop
    _ensure_gi()
    server = _GstRtspServer.RTSPServer()
    server.props.service = str(port)

    factory_wrapper = SensorFactory(width, height, fps, use_hw)
    factory = factory_wrapper.get_factory()
    factory.set_shared(True)

    mounts = server.get_mount_points()
    mounts.add_factory('/live', factory)

    server.attach(None)

    _loop = _GObject.MainLoop()
    try:
        _loop.run()
    except Exception:
        pass


def start_server(background=True, port=8554, width=1280, height=720, fps=30, use_hw=False):
    """Start RTSP server. If `use_hw=True` attempts to use Jetson hardware encoder.

    Raises ImportError if PyGObject/GStreamer are not installed.
    """
    # ensure gi is available (will raise ImportError otherwise)
    _ensure_gi()
    if background:
        t = threading.Thread(target=_main_loop, args=(port, width, height, fps, use_hw), daemon=True)
        t.start()
        # give time for server to start
        time.sleep(0.5)
    else:
        _main_loop(port, width, height, fps, use_hw)


def push_frame(frame):
    """Push a numpy BGR frame into the appsrc as Gst.Buffer.

    Returns True on success, False otherwise.
    """
    global _appsrc
    if _appsrc is None:
        return False

    try:
        import numpy as np

        if not _gi_available or _Gst is None:
            return False

        h, w = frame.shape[:2]
        data = frame.tobytes()
        buf = _Gst.Buffer.new_allocate(None, len(data), None)
        buf.fill(0, data)
        # timestamping (optional)
        duration = _Gst.util_uint64_scale_int(1, _Gst.SECOND, 30)
        buf.duration = duration
        _appsrc.emit('push-buffer', buf)
        return True
    except Exception:
        return False
