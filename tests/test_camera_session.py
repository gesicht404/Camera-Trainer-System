import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from camera import CameraSession


class FakeGPhoto:
    def __init__(self, settings=None, connect_ok=True):
        self._settings = settings or {}
        self._connect_ok = connect_ok
        self.closed = False

    def connect(self):
        return self._connect_ok

    def read_settings(self):
        return self._settings

    def close(self):
        self.closed = True


class FakeVideoCapture:
    def __init__(self, frames=None, opened=True):
        self._frames = list(frames or [])
        self._opened = opened
        self.released = False

    def isOpened(self):
        return self._opened

    def read(self):
        if not self._frames:
            return False, None
        return True, self._frames.pop(0)

    def release(self):
        self.released = True


def solid_frame(value, size=8):
    return np.full((size, size, 3), value, dtype=np.uint8)


def test_connect_reports_settings_and_video_availability():
    session = CameraSession(
        gphoto_camera=FakeGPhoto(settings={"iso": 800}),
        video_capture_factory=lambda index: FakeVideoCapture(frames=[solid_frame(100)]),
    )
    assert session.connect() is True
    assert session.hardware_available is True
    assert session.video_available is True


def test_connect_false_when_neither_available():
    session = CameraSession(
        gphoto_camera=FakeGPhoto(connect_ok=False),
        video_capture_factory=lambda index: FakeVideoCapture(opened=False),
    )
    assert session.connect() is False
    assert session.hardware_available is False
    assert session.video_available is False


def test_video_never_probed_when_gphoto_unavailable():
    """Regression guard: without a confirmed Nikon D3500 (gphoto2 connected), the
    video device must never be probed at all, so a dev machine's own webcam is never
    silently opened in place of the HDMI capture card."""
    factory_calls = []

    def spy_factory(index):
        factory_calls.append(index)
        return FakeVideoCapture(opened=True)

    session = CameraSession(gphoto_camera=FakeGPhoto(connect_ok=False), video_capture_factory=spy_factory)
    session.connect()
    assert factory_calls == []
    assert session.video_available is False


def test_video_unavailable_does_not_block_settings_readback():
    session = CameraSession(
        gphoto_camera=FakeGPhoto(settings={"iso": 400}, connect_ok=True),
        video_capture_factory=lambda index: FakeVideoCapture(opened=False),
    )
    session.connect()
    assert session.hardware_available is True
    assert session.read_current_value("iso") == 400


def test_read_current_value_none_when_settings_unavailable():
    session = CameraSession(
        gphoto_camera=FakeGPhoto(connect_ok=False),
        video_capture_factory=lambda index: FakeVideoCapture(frames=[solid_frame(50)]),
    )
    session.connect()
    assert session.read_current_value("iso") is None


def test_read_current_value_missing_key_returns_none():
    session = CameraSession(
        gphoto_camera=FakeGPhoto(settings={"iso": 400}),
        video_capture_factory=lambda index: FakeVideoCapture(),
    )
    session.connect()
    assert session.read_current_value("wb") is None


def test_capture_baseline_then_frame_trend_detects_brighter():
    frames = [solid_frame(50), solid_frame(200)]
    session = CameraSession(
        gphoto_camera=FakeGPhoto(),
        video_capture_factory=lambda index: FakeVideoCapture(frames=frames),
    )
    session.connect()
    session.capture_baseline("iso")
    trend = session.frame_trend("iso")
    assert trend["brightness"] == "brighter"


def test_frame_trend_none_without_baseline():
    session = CameraSession(
        gphoto_camera=FakeGPhoto(),
        video_capture_factory=lambda index: FakeVideoCapture(frames=[solid_frame(100)]),
    )
    session.connect()
    assert session.frame_trend("iso") is None


def test_read_frame_returns_latest_frame():
    frame = solid_frame(77)
    session = CameraSession(
        gphoto_camera=FakeGPhoto(),
        video_capture_factory=lambda index: FakeVideoCapture(frames=[frame]),
    )
    session.connect()
    result = session.read_frame()
    assert result is not None
    assert (result == frame).all()


def test_read_frame_none_without_video():
    session = CameraSession(
        gphoto_camera=FakeGPhoto(),
        video_capture_factory=lambda index: FakeVideoCapture(opened=False),
    )
    session.connect()
    assert session.read_frame() is None


def test_close_releases_video_and_gphoto():
    fake_gphoto = FakeGPhoto()
    fake_video = FakeVideoCapture(frames=[solid_frame(10)])
    session = CameraSession(gphoto_camera=fake_gphoto, video_capture_factory=lambda index: fake_video)
    session.connect()
    session.close()
    assert fake_video.released is True
    assert fake_gphoto.closed is True
