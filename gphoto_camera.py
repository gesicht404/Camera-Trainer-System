"""Thin wrapper around python-gphoto2 for reading Nikon D3500 exposure settings over USB.

Per the proposal's system flowchart (Ch. 3.6.3): "gPhoto2 reads the current camera
values through USB, such as ISO, shutter speed, aperture, and white balance when
supported by the Nikon D3500."

`python-gphoto2` depends on the native `libgphoto2` library, which is only available
on Linux (i.e. the deployed Raspberry Pi OS target). `is_available()` reports whether
it can be used on the current machine; callers should fall back to a simulated camera
controller when it returns False (e.g. during development on a machine with no
camera/capture card attached).
"""

import numpy as np
import cv2

from tasks import TASKS

# gphoto2 config widget names for a Nikon D3500 body, keyed by our task ids.
CONFIG_NAMES = {"iso": "iso", "aperture": "f-number", "shutter": "shutterspeed", "wb": "whitebalance"}

_TASK_OPTIONS = {t["id"]: t["options"] for t in TASKS}


def is_available() -> bool:
    """Whether the native gphoto2 bindings can be imported on this machine."""
    try:
        import gphoto2  # noqa: F401
    except ImportError:
        return False
    return True


def snap_to_options(value, options: list):
    """Maps a raw camera-reported value onto the nearest matching entry in a task's
    discrete `options` list (the camera's real dial may report values with more
    precision or different formatting than the curriculum's fixed option set)."""
    if value in options:
        return value
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return options[0]
    return min(options, key=lambda opt: abs(float(opt) - numeric_value))


def _parse_iso(raw: str):
    return int(str(raw).strip())


def _parse_aperture(raw: str):
    text = str(raw).strip().lower().lstrip("f").lstrip("/")
    return float(text)


def _parse_shutter(raw: str):
    text = str(raw).strip()
    if "/" in text:
        return int(round(float(text.split("/")[1])))
    return int(round(1 / float(text))) if float(text) < 1 else int(round(float(text)))


def _parse_wb(raw: str):
    text = str(raw).strip().lower()
    mapping = {
        "auto": "Auto",
        "daylight": "Daylight",
        "cloudy": "Cloudy",
        "tungsten": "Tungsten",
        "incandescent": "Tungsten",
        "fluorescent": "Fluorescent",
    }
    for key, label in mapping.items():
        if key in text:
            return label
    return "Auto"


_PARSERS = {"iso": _parse_iso, "aperture": _parse_aperture, "shutter": _parse_shutter, "wb": _parse_wb}


class GPhotoCamera:
    """Talks to a Nikon D3500 (or gphoto2-compatible body) over USB."""

    def __init__(self, gphoto2_module=None):
        """`gphoto2_module` can be injected (e.g. a test double); defaults to importing
        the real `gphoto2` package lazily, only when `connect()` is called."""
        self._gp = gphoto2_module
        self._camera = None

    def connect(self) -> bool:
        self.close()  # release any previous handle before reconnecting (e.g. re-detect)
        if self._gp is None:
            try:
                import gphoto2 as gp
            except ImportError:
                return False
            self._gp = gp
        try:
            camera = self._gp.Camera()
            camera.init()
        except Exception:
            self._camera = None
            return False
        self._camera = camera
        self._enable_viewfinder()
        return True

    def _enable_viewfinder(self):
        """Best-effort: many Nikon bodies only feed capture_preview() once USB live
        view is switched on via the 'viewfinder' config widget. Not every body/
        firmware exposes it, so any failure here is silently ignored."""
        try:
            config = self._camera.get_config()
            widget = config.get_child_by_name("viewfinder")
            widget.set_value(1)
            self._camera.set_config(config)
        except Exception:
            pass

    def capture_preview_frame(self):
        """Grabs one live-view frame over USB via gphoto2's capture_preview(), or
        None if not connected or the camera doesn't support/allow it right now."""
        if self._camera is None:
            return None
        try:
            camera_file = self._camera.capture_preview()
            data = camera_file.get_data_and_size()
            buf = np.frombuffer(bytes(data), dtype=np.uint8)
            frame = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        except Exception:
            return None
        return frame

    def is_connected(self) -> bool:
        return self._camera is not None

    def close(self):
        if self._camera is not None:
            try:
                self._camera.exit()
            except Exception:
                pass
            self._camera = None

    def _drain_events(self, timeout_ms: int = 20, max_events: int = 5):
        """Processes pending PTP property-changed events before reading config.

        libgphoto2 serves get_config() from a cached widget tree that's only
        refreshed once the driver processes a device property-changed event
        (see gphoto/libgphoto2#677) - without draining events first, settings
        changed via the camera's physical dial keep reading as stale."""
        if self._gp is None or not hasattr(self._camera, "wait_for_event"):
            return
        for _ in range(max_events):
            try:
                event_type, _ = self._camera.wait_for_event(timeout_ms)
            except Exception:
                return
            if event_type == self._gp.GP_EVENT_TIMEOUT:
                return

    def read_settings(self) -> dict:
        """Reads the camera's live config and returns values snapped onto each task's
        discrete option set, e.g. {"iso": 800, "aperture": 5.6, "shutter": 60, "wb": "Auto"}.
        Missing/unreadable fields are simply omitted from the result.
        """
        if self._camera is None:
            return {}
        self._drain_events()
        config = self._camera.get_config()
        result = {}
        for task_id, widget_name in CONFIG_NAMES.items():
            try:
                widget = config.get_child_by_name(widget_name)
                raw_value = widget.get_value()
            except Exception:
                continue
            try:
                parsed = _PARSERS[task_id](raw_value)
            except (TypeError, ValueError):
                continue
            result[task_id] = snap_to_options(parsed, _TASK_OPTIONS[task_id])
        return result
