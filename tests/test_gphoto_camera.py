import io
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gphoto_camera import GPhotoCamera, _extract_exif_settings


class FakeCameraFilePath:
    def __init__(self, folder, name):
        self.folder = folder
        self.name = name


class FakeCameraFile:
    def __init__(self, data: bytes):
        self._data = data

    def get_data_and_size(self):
        return self._data


class FakeConfigWidget:
    def __init__(self):
        self.value = None

    def set_value(self, value):
        self.value = value


class FakeConfig:
    def __init__(self):
        self.viewfinder = FakeConfigWidget()

    def get_child_by_name(self, name):
        if name == "viewfinder":
            return self.viewfinder
        raise KeyError(name)


class FakeCamera:
    def __init__(self, capture_jpeg_bytes, events=None):
        self._capture_jpeg_bytes = capture_jpeg_bytes
        self._events = list(events) if events is not None else []
        self.deleted_paths = []
        self.config = FakeConfig()
        self.get_config_calls = 0
        self.set_config_calls = 0

    def init(self):
        pass

    def exit(self):
        pass

    def capture(self, capture_type):
        return FakeCameraFilePath("/store_00010001", "capt0001.jpg")

    def file_get(self, folder, name, file_type):
        return FakeCameraFile(self._capture_jpeg_bytes)

    def file_delete(self, folder, name):
        self.deleted_paths.append((folder, name))

    def wait_for_event(self, timeout_ms):
        if not self._events:
            return (FakeGPhoto2Module.GP_EVENT_TIMEOUT, None)
        return self._events.pop(0)

    def get_config(self):
        self.get_config_calls += 1
        return self.config

    def set_config(self, config):
        self.set_config_calls += 1


class FakeGPhoto2Module:
    GP_CAPTURE_IMAGE = 0
    GP_FILE_TYPE_NORMAL = 0
    GP_EVENT_TIMEOUT = 1
    GP_EVENT_FILE_ADDED = 2

    def __init__(self, capture_jpeg_bytes, events=None):
        self._capture_jpeg_bytes = capture_jpeg_bytes
        self._events = events

    def Camera(self):
        return FakeCamera(self._capture_jpeg_bytes, events=self._events)


def _build_exif_bytes(iso=None, fnumber=None, exposure_time=None):
    image = Image.new("RGB", (4, 4))
    exif = image.getexif()
    exif_ifd = exif.get_ifd(0x8769)
    if iso is not None:
        exif_ifd[0x8827] = iso
    if fnumber is not None:
        exif_ifd[0x829D] = fnumber
    if exposure_time is not None:
        exif_ifd[0x829A] = exposure_time
    return exif.tobytes()


def _encode_test_jpeg(exif_bytes=None):
    frame = np.full((4, 4, 3), 120, dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", frame)
    assert ok
    if exif_bytes is None:
        return buf.tobytes()
    image = Image.open(io.BytesIO(buf.tobytes()))
    out = io.BytesIO()
    image.save(out, format="JPEG", exif=exif_bytes)
    return out.getvalue()


def test_extract_exif_settings_parses_and_snaps_known_fields():
    exif_bytes = _build_exif_bytes(iso=790, fnumber=5.6, exposure_time=1 / 58)
    jpeg_bytes = _encode_test_jpeg(exif_bytes)
    assert _extract_exif_settings(jpeg_bytes) == {"iso": 800, "aperture": 5.6, "shutter": 60}


def test_extract_exif_settings_omits_unreadable_field():
    exif_bytes = _build_exif_bytes(iso=400)
    jpeg_bytes = _encode_test_jpeg(exif_bytes)
    assert _extract_exif_settings(jpeg_bytes) == {"iso": 400}


def test_extract_exif_settings_empty_when_no_exif():
    jpeg_bytes = _encode_test_jpeg()
    assert _extract_exif_settings(jpeg_bytes) == {}


def test_extract_exif_settings_empty_on_garbage_bytes():
    assert _extract_exif_settings(b"not a jpeg") == {}


def test_capture_image_returns_frame_bytes_and_exif_settings():
    exif_bytes = _build_exif_bytes(iso=800, fnumber=8, exposure_time=1 / 125)
    jpeg_bytes = _encode_test_jpeg(exif_bytes)
    fake_module = FakeGPhoto2Module(jpeg_bytes)
    camera = GPhotoCamera(gphoto2_module=fake_module)
    camera.connect()

    frame, raw_bytes, exif_settings = camera.capture_image()

    assert frame is not None
    assert raw_bytes == jpeg_bytes
    assert exif_settings == {"iso": 800, "aperture": 8.0, "shutter": 125}


def test_capture_image_exif_settings_empty_when_capture_has_no_exif():
    jpeg_bytes = _encode_test_jpeg()
    fake_module = FakeGPhoto2Module(jpeg_bytes)
    camera = GPhotoCamera(gphoto2_module=fake_module)
    camera.connect()

    _frame, _raw_bytes, exif_settings = camera.capture_image()

    assert exif_settings == {}


def test_poll_physical_capture_returns_none_on_timeout():
    jpeg_bytes = _encode_test_jpeg()
    fake_module = FakeGPhoto2Module(jpeg_bytes, events=[])
    camera = GPhotoCamera(gphoto2_module=fake_module)
    camera.connect()

    assert camera.poll_physical_capture() is None


def test_poll_physical_capture_downloads_file_on_shutter_press():
    exif_bytes = _build_exif_bytes(iso=800, fnumber=8, exposure_time=1 / 125)
    jpeg_bytes = _encode_test_jpeg(exif_bytes)
    file_path = FakeCameraFilePath("/store_00010001", "dsc_0001.jpg")
    events = [(FakeGPhoto2Module.GP_EVENT_FILE_ADDED, file_path)]
    fake_module = FakeGPhoto2Module(jpeg_bytes, events=events)
    camera = GPhotoCamera(gphoto2_module=fake_module)
    camera.connect()

    result = camera.poll_physical_capture()

    assert result is not None
    frame, raw_bytes, exif_settings = result
    assert frame is not None
    assert raw_bytes == jpeg_bytes
    assert exif_settings == {"iso": 800, "aperture": 8.0, "shutter": 125}


def test_poll_physical_capture_deletes_file_from_camera_after_download():
    jpeg_bytes = _encode_test_jpeg()
    file_path = FakeCameraFilePath("/store_00010001", "dsc_0002.jpg")
    events = [(FakeGPhoto2Module.GP_EVENT_FILE_ADDED, file_path)]
    fake_module = FakeGPhoto2Module(jpeg_bytes, events=events)
    camera = GPhotoCamera(gphoto2_module=fake_module)
    camera.connect()

    camera.poll_physical_capture()

    assert ("/store_00010001", "dsc_0002.jpg") in camera._camera.deleted_paths


def test_poll_physical_capture_ignores_unrelated_events_then_finds_capture():
    jpeg_bytes = _encode_test_jpeg()
    file_path = FakeCameraFilePath("/store_00010001", "dsc_0003.jpg")
    events = [
        (99, None),
        (FakeGPhoto2Module.GP_EVENT_FILE_ADDED, file_path),
    ]
    fake_module = FakeGPhoto2Module(jpeg_bytes, events=events)
    camera = GPhotoCamera(gphoto2_module=fake_module)
    camera.connect()

    result = camera.poll_physical_capture()

    assert result is not None


def test_poll_physical_capture_returns_none_when_not_connected():
    fake_module = FakeGPhoto2Module(b"")
    camera = GPhotoCamera(gphoto2_module=fake_module)

    assert camera.poll_physical_capture() is None


def test_connect_does_not_enable_viewfinder():
    fake_module = FakeGPhoto2Module(b"")
    camera = GPhotoCamera(gphoto2_module=fake_module)

    camera.connect()

    assert camera._camera.get_config_calls == 0
    assert camera._camera.set_config_calls == 0


def test_enable_viewfinder_sets_config_value_to_one():
    fake_module = FakeGPhoto2Module(b"")
    camera = GPhotoCamera(gphoto2_module=fake_module)
    camera.connect()

    camera.enable_viewfinder()

    assert camera._camera.config.viewfinder.value == 1
    assert camera._camera.set_config_calls == 1


def test_disable_viewfinder_sets_config_value_to_zero():
    fake_module = FakeGPhoto2Module(b"")
    camera = GPhotoCamera(gphoto2_module=fake_module)
    camera.connect()

    camera.disable_viewfinder()

    assert camera._camera.config.viewfinder.value == 0
    assert camera._camera.set_config_calls == 1
