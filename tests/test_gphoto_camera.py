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


class FakeCamera:
    def __init__(self, capture_jpeg_bytes):
        self._capture_jpeg_bytes = capture_jpeg_bytes
        self.deleted_paths = []

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


class FakeGPhoto2Module:
    GP_CAPTURE_IMAGE = 0
    GP_FILE_TYPE_NORMAL = 0

    def __init__(self, capture_jpeg_bytes):
        self._capture_jpeg_bytes = capture_jpeg_bytes

    def Camera(self):
        return FakeCamera(self._capture_jpeg_bytes)


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
