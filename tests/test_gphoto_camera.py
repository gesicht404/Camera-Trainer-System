import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gphoto_camera import GPhotoCamera, is_available, snap_to_options


class FakeWidget:
    def __init__(self, value):
        self._value = value

    def get_value(self):
        return self._value


class FakeConfig:
    def __init__(self, values: dict):
        self._values = values

    def get_child_by_name(self, name):
        if name not in self._values:
            raise KeyError(name)
        return FakeWidget(self._values[name])


class FakeCamera:
    """`config_values` starts as both the "true" on-camera values and the cached
    values get_config() serves. simulate_dial_change() only updates the "true"
    values, mirroring how a physical dial turn changes the camera's actual state
    but not libgphoto2's cached PTP property widgets - wait_for_event() is what
    pulls the cache back in sync, same as the real driver."""

    def __init__(self, config_values):
        self._cached_values = dict(config_values)
        self._true_values = dict(config_values)
        self.inited = False
        self.exited = False

    def init(self):
        self.inited = True

    def exit(self):
        self.exited = True

    def get_config(self):
        return FakeConfig(self._cached_values)

    def simulate_dial_change(self, new_values: dict):
        self._true_values.update(new_values)

    def wait_for_event(self, timeout_ms):
        if self._cached_values != self._true_values:
            self._cached_values = dict(self._true_values)
            return (1, None)  # GP_EVENT_UNKNOWN-ish: something changed
        return (0, None)  # GP_EVENT_TIMEOUT: nothing pending


class FakeGPhoto2Module:
    """Test double standing in for the real `gphoto2` package."""

    GP_EVENT_TIMEOUT = 0

    def __init__(self, config_values, fail_init=False):
        self._config_values = config_values
        self._fail_init = fail_init

    def Camera(self):
        if self._fail_init:
            class BadCamera:
                def init(self):
                    raise RuntimeError("no camera detected")

            return BadCamera()
        return FakeCamera(self._config_values)


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
