import sys
from pathlib import Path

import numpy as np
import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gphoto_camera import GPhotoCamera, is_available, snap_to_options


class FakeWidget:
    def __init__(self, value, on_set=None):
        self._value = value
        self._on_set = on_set

    def get_value(self):
        return self._value

    def set_value(self, value):
        self._value = value
        if self._on_set:
            self._on_set(value)


class FakeConfig:
    def __init__(self, values: dict):
        self._values = values

    def get_child_by_name(self, name):
        if name not in self._values:
            raise KeyError(name)
        return FakeWidget(self._values[name], on_set=lambda v, n=name: self._values.__setitem__(n, v))


class FakeCamera:
    """`config_values` starts as both the "true" on-camera values and the cached
    values get_config() serves. simulate_dial_change() only updates the "true"
    values, mirroring how a physical dial turn changes the camera's actual state
    but not libgphoto2's cached PTP property widgets - wait_for_event() is what
    pulls the cache back in sync, same as the real driver."""

    def __init__(self, config_values, preview_jpeg_bytes=None, capture_jpeg_bytes=None, fail_capture=False):
        self._cached_values = dict(config_values)
        self._true_values = dict(config_values)
        self._preview_jpeg_bytes = preview_jpeg_bytes
        self._capture_jpeg_bytes = capture_jpeg_bytes
        self._fail_capture = fail_capture
        self.inited = False
        self.exited = False
        self.set_config_calls = 0
        self.deleted_paths = []

    def init(self):
        self.inited = True

    def exit(self):
        self.exited = True

    def get_config(self):
        return FakeConfig(self._cached_values)

    def set_config(self, config):
        self.set_config_calls += 1

    def capture_preview(self):
        if self._preview_jpeg_bytes is None:
            raise RuntimeError("liveview not supported")
        return FakeCameraFile(self._preview_jpeg_bytes)

    def capture(self, capture_type):
        if self._fail_capture:
            raise RuntimeError("capture failed")
        return FakeCameraFilePath("/store_00010001", "capt0001.jpg")

    def file_get(self, folder, name, file_type):
        return FakeCameraFile(self._capture_jpeg_bytes)

    def file_delete(self, folder, name):
        self.deleted_paths.append((folder, name))

    def simulate_dial_change(self, new_values: dict):
        self._true_values.update(new_values)

    def wait_for_event(self, timeout_ms):
        if self._cached_values != self._true_values:
            self._cached_values = dict(self._true_values)
            return (1, None)  # GP_EVENT_UNKNOWN-ish: something changed
        return (0, None)  # GP_EVENT_TIMEOUT: nothing pending


class FakeCameraFilePath:
    def __init__(self, folder, name):
        self.folder = folder
        self.name = name


class FakeCameraFile:
    def __init__(self, data: bytes):
        self._data = data

    def get_data_and_size(self):
        return self._data


class FakeGPhoto2Module:
    """Test double standing in for the real `gphoto2` package."""

    GP_EVENT_TIMEOUT = 0
    GP_CAPTURE_IMAGE = 0
    GP_FILE_TYPE_NORMAL = 0

    def __init__(
        self,
        config_values,
        fail_init=False,
        preview_jpeg_bytes=None,
        capture_jpeg_bytes=None,
        fail_capture=False,
    ):
        self._config_values = config_values
        self._fail_init = fail_init
        self._preview_jpeg_bytes = preview_jpeg_bytes
        self._capture_jpeg_bytes = capture_jpeg_bytes
        self._fail_capture = fail_capture

    def Camera(self):
        if self._fail_init:
            class BadCamera:
                def init(self):
                    raise RuntimeError("no camera detected")

            return BadCamera()
        return FakeCamera(
            self._config_values,
            preview_jpeg_bytes=self._preview_jpeg_bytes,
            capture_jpeg_bytes=self._capture_jpeg_bytes,
            fail_capture=self._fail_capture,
        )


def _encode_test_jpeg():
    frame = np.full((4, 4, 3), 120, dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", frame)
    assert ok
    return buf.tobytes()


def test_snap_to_options_exact_match():
    assert snap_to_options(800, [100, 200, 400, 800, 1600]) == 800


def test_snap_to_options_nearest_match():
    assert snap_to_options(750, [100, 200, 400, 800, 1600]) == 800
    assert snap_to_options(150, [100, 200, 400, 800, 1600]) == 100


def test_connect_success():
    fake_module = FakeGPhoto2Module({"iso": "800", "f-number": "5.6", "shutterspeed": "1/60", "whitebalance": "Auto"})
    camera = GPhotoCamera(gphoto2_module=fake_module)
    assert camera.connect() is True
    assert camera.is_connected() is True


def test_connect_failure_when_no_device():
    fake_module = FakeGPhoto2Module({}, fail_init=True)
    camera = GPhotoCamera(gphoto2_module=fake_module)
    assert camera.connect() is False
    assert camera.is_connected() is False


def test_reconnect_releases_previous_handle_first():
    """Regression guard for the 'Detect Camera' button: calling connect() again
    while already connected must exit() the old handle before claiming a new one,
    or repeated clicks would double-claim the USB device."""
    fake_module = FakeGPhoto2Module({"iso": "400"})
    camera = GPhotoCamera(gphoto2_module=fake_module)
    camera.connect()
    first_camera = camera._camera
    camera.connect()
    assert first_camera.exited is True
    assert camera.is_connected() is True


def test_read_settings_parses_and_snaps_all_fields():
    fake_module = FakeGPhoto2Module(
        {"iso": "790", "f-number": "f/5.6", "shutterspeed": "1/58", "whitebalance": "Fluorescent"}
    )
    camera = GPhotoCamera(gphoto2_module=fake_module)
    camera.connect()
    settings = camera.read_settings()
    assert settings == {"iso": 800, "aperture": 5.6, "shutter": 60, "wb": "Fluorescent"}


def test_read_settings_returns_empty_when_not_connected():
    camera = GPhotoCamera(gphoto2_module=FakeGPhoto2Module({}))
    assert camera.read_settings() == {}


def test_read_settings_reflects_dial_change_in_realtime():
    """Regression guard: libgphoto2 caches PTP property values and only refreshes
    them once pending events are drained via wait_for_event() (see
    gphoto/libgphoto2#677). Turning the camera's physical dial changes the
    camera's actual state, but read_settings() must drain events before reading
    config or it will keep reporting the value from before the dial turn."""
    fake_module = FakeGPhoto2Module({"iso": "400"})
    camera = GPhotoCamera(gphoto2_module=fake_module)
    camera.connect()
    assert camera.read_settings()["iso"] == 400

    camera._camera.simulate_dial_change({"iso": "800"})
    assert camera.read_settings()["iso"] == 800


def test_read_settings_omits_unreadable_field():
    fake_module = FakeGPhoto2Module({"iso": "400", "f-number": "8"})  # shutter/wb missing
    camera = GPhotoCamera(gphoto2_module=fake_module)
    camera.connect()
    settings = camera.read_settings()
    assert settings == {"iso": 400, "aperture": 8.0}


def test_close_marks_disconnected():
    fake_module = FakeGPhoto2Module({"iso": "100"})
    camera = GPhotoCamera(gphoto2_module=fake_module)
    camera.connect()
    camera.close()
    assert camera.is_connected() is False


def test_is_available_false_without_native_library():
    # On this dev machine libgphoto2 isn't installed, so the real import must fail
    # gracefully rather than raising.
    assert is_available() is False


def test_connect_enables_viewfinder_when_supported():
    """USB live view must be turned on before capture_preview() will return
    frames on many Nikon bodies (config widget 'viewfinder' -> 1)."""
    fake_module = FakeGPhoto2Module({"iso": "800", "viewfinder": 0})
    camera = GPhotoCamera(gphoto2_module=fake_module)
    camera.connect()
    assert camera._camera._cached_values["viewfinder"] == 1
    assert camera._camera.set_config_calls == 1


def test_connect_succeeds_when_viewfinder_unsupported():
    """Regression guard: a body/firmware without a 'viewfinder' config widget must
    not break connect() - the toggle is best-effort."""
    fake_module = FakeGPhoto2Module({"iso": "800"})
    camera = GPhotoCamera(gphoto2_module=fake_module)
    assert camera.connect() is True


def test_capture_preview_frame_returns_decoded_frame():
    jpeg_bytes = _encode_test_jpeg()
    fake_module = FakeGPhoto2Module({"iso": "800"}, preview_jpeg_bytes=jpeg_bytes)
    camera = GPhotoCamera(gphoto2_module=fake_module)
    camera.connect()
    frame = camera.capture_preview_frame()
    assert frame is not None
    assert frame.shape == (4, 4, 3)


def test_capture_preview_frame_none_when_not_connected():
    camera = GPhotoCamera(gphoto2_module=FakeGPhoto2Module({}))
    assert camera.capture_preview_frame() is None


def test_capture_preview_frame_none_when_liveview_unsupported():
    fake_module = FakeGPhoto2Module({"iso": "800"})  # no preview_jpeg_bytes configured
    camera = GPhotoCamera(gphoto2_module=fake_module)
    camera.connect()
    assert camera.capture_preview_frame() is None


def test_capture_image_returns_decoded_frame_and_bytes():
    jpeg_bytes = _encode_test_jpeg()
    fake_module = FakeGPhoto2Module({"iso": "800"}, capture_jpeg_bytes=jpeg_bytes)
    camera = GPhotoCamera(gphoto2_module=fake_module)
    camera.connect()
    frame, raw_bytes = camera.capture_image()
    assert frame is not None
    assert frame.shape == (4, 4, 3)
    assert raw_bytes == jpeg_bytes


def test_capture_image_deletes_file_from_camera_after_download():
    jpeg_bytes = _encode_test_jpeg()
    fake_module = FakeGPhoto2Module({"iso": "800"}, capture_jpeg_bytes=jpeg_bytes)
    camera = GPhotoCamera(gphoto2_module=fake_module)
    camera.connect()
    camera.capture_image()
    assert camera._camera.deleted_paths == [("/store_00010001", "capt0001.jpg")]


def test_capture_image_none_when_not_connected():
    camera = GPhotoCamera(gphoto2_module=FakeGPhoto2Module({}))
    assert camera.capture_image() is None


def test_capture_image_none_on_capture_failure():
    fake_module = FakeGPhoto2Module({"iso": "800"}, fail_capture=True)
    camera = GPhotoCamera(gphoto2_module=fake_module)
    camera.connect()
    assert camera.capture_image() is None
