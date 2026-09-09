import io

import numpy as np
import cv2
from PIL import Image

from tasks import TASKS

CONFIG_NAMES = {"iso": "iso", "aperture": "f-number", "shutter": "shutterspeed", "wb": "whitebalance"}

_TASK_OPTIONS = {t["id"]: t["options"] for t in TASKS}

_EXIF_IFD_TAG = 0x8769
_EXIF_ISO_TAG = 0x8827
_EXIF_FNUMBER_TAG = 0x829D
_EXIF_EXPOSURE_TIME_TAG = 0x829A


def snap_to_options(value, options: list):
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


def _extract_exif_settings(jpeg_bytes: bytes) -> dict:
    try:
        exif_ifd = Image.open(io.BytesIO(jpeg_bytes)).getexif().get_ifd(_EXIF_IFD_TAG)
    except Exception:
        return {}

    result = {}
    if _EXIF_ISO_TAG in exif_ifd:
        try:
            result["iso"] = snap_to_options(int(exif_ifd[_EXIF_ISO_TAG]), _TASK_OPTIONS["iso"])
        except (TypeError, ValueError):
            pass
    if _EXIF_FNUMBER_TAG in exif_ifd:
        try:
            result["aperture"] = snap_to_options(float(exif_ifd[_EXIF_FNUMBER_TAG]), _TASK_OPTIONS["aperture"])
        except (TypeError, ValueError):
            pass
    if _EXIF_EXPOSURE_TIME_TAG in exif_ifd:
        try:
            exposure_time = float(exif_ifd[_EXIF_EXPOSURE_TIME_TAG])
            shutter_denominator = int(round(1 / exposure_time))
            result["shutter"] = snap_to_options(shutter_denominator, _TASK_OPTIONS["shutter"])
        except (TypeError, ValueError, ZeroDivisionError):
            pass
    return result


class GPhotoCamera:
    def __init__(self, gphoto2_module=None):
        self._gp = gphoto2_module
        self._camera = None

    def connect(self) -> bool:
        self.close()
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
        try:
            config = self._camera.get_config()
            widget = config.get_child_by_name("viewfinder")
            widget.set_value(1)
            self._camera.set_config(config)
        except Exception:
            pass

    def capture_image(self):
        if self._camera is None:
            return None
        try:
            file_path = self._camera.capture(self._gp.GP_CAPTURE_IMAGE)
        except Exception:
            return None
        return self._download_and_delete(file_path)

    def _download_and_delete(self, file_path):
        try:
            camera_file = self._camera.file_get(file_path.folder, file_path.name, self._gp.GP_FILE_TYPE_NORMAL)
            jpeg_bytes = bytes(camera_file.get_data_and_size())
            buf = np.frombuffer(jpeg_bytes, dtype=np.uint8)
            frame = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        except Exception:
            return None
        try:
            self._camera.file_delete(file_path.folder, file_path.name)
        except Exception:
            pass
        return frame, jpeg_bytes, _extract_exif_settings(jpeg_bytes)

    def poll_physical_capture(self, timeout_ms: int = 20, max_events: int = 5):
        """Check for a photo taken with the camera's own shutter button."""
        if self._camera is None or self._gp is None or not hasattr(self._camera, "wait_for_event"):
            return None
        for _ in range(max_events):
            try:
                event_type, event_data = self._camera.wait_for_event(timeout_ms)
            except Exception:
                return None
            if event_type == self._gp.GP_EVENT_TIMEOUT:
                return None
            if event_type == self._gp.GP_EVENT_FILE_ADDED:
                return self._download_and_delete(event_data)
        return None

    def capture_preview_frame(self):
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

    def close(self):
        if self._camera is not None:
            try:
                self._camera.exit()
            except Exception:
                pass
            self._camera = None

    def _drain_events(self, timeout_ms: int = 20, max_events: int = 5):
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
