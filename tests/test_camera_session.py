import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from camera import CameraSession


class FakeGPhoto:
    def __init__(self, settings=None, connect_ok=True, preview_frames=None, captures=None):
        self._settings = settings or {}
        self._connect_ok = connect_ok
        self._preview_frames = list(preview_frames) if preview_frames is not None else []
        self._captures = list(captures) if captures is not None else []
        self.closed = False

    def connect(self):
        return self._connect_ok

    def read_settings(self):
        return self._settings

    def capture_preview_frame(self):
        if not self._preview_frames:
            return None
        return self._preview_frames.pop(0)

    def capture_image(self):
        if not self._captures:
            return None
        return self._captures.pop(0)

    def close(self):
        self.closed = True


def solid_frame(value, size=8):
    return np.full((size, size, 3), value, dtype=np.uint8)


def test_connect_reports_settings_and_video_availability():
    session = CameraSession(gphoto_camera=FakeGPhoto(settings={"iso": 800}, preview_frames=[solid_frame(100)]))
    assert session.connect() is True
    assert session.hardware_available is True
    assert session.video_available is True


def test_connect_false_when_neither_available():
    session = CameraSession(gphoto_camera=FakeGPhoto(connect_ok=False))
    assert session.connect() is False
    assert session.hardware_available is False
    assert session.video_available is False


def test_video_unavailable_when_capture_preview_returns_none():
    session = CameraSession(gphoto_camera=FakeGPhoto(preview_frames=[]))
    assert session.connect() is True
    assert session.video_available is False


def test_video_never_probed_when_gphoto_unavailable():
    calls = []

    class SpyGPhoto(FakeGPhoto):
        def capture_preview_frame(self):
            calls.append(True)
            return super().capture_preview_frame()

    session = CameraSession(gphoto_camera=SpyGPhoto(connect_ok=False, preview_frames=[solid_frame(1)]))
    session.connect()
    assert calls == []
    assert session.video_available is False


def test_video_unavailable_does_not_block_settings_readback():
    session = CameraSession(gphoto_camera=FakeGPhoto(settings={"iso": 400}, connect_ok=True, preview_frames=[]))
    session.connect()
    assert session.hardware_available is True
    assert session.read_current_value("iso") == 400


def test_read_current_value_none_when_settings_unavailable():
    session = CameraSession(gphoto_camera=FakeGPhoto(connect_ok=False))
    session.connect()
    assert session.read_current_value("iso") is None


def test_read_current_value_missing_key_returns_none():
    session = CameraSession(gphoto_camera=FakeGPhoto(settings={"iso": 400}))
    session.connect()
    assert session.read_current_value("wb") is None


def test_capture_baseline_then_frame_trend_detects_brighter(tmp_path):
    probe_frame = solid_frame(1)
    session = CameraSession(
        gphoto_camera=FakeGPhoto(
            preview_frames=[probe_frame],
            captures=[(solid_frame(50), b"jpeg-bytes-1"), (solid_frame(200), b"jpeg-bytes-2")],
        ),
        captures_dir=tmp_path,
    )
    session.connect()
    session.capture_baseline("iso")
    trend = session.frame_trend("iso")
    assert trend["brightness"] == "brighter"


def test_frame_trend_none_without_baseline(tmp_path):
    session = CameraSession(
        gphoto_camera=FakeGPhoto(preview_frames=[solid_frame(1)], captures=[(solid_frame(1), b"jpeg-bytes")]),
        captures_dir=tmp_path,
    )
    session.connect()
    assert session.frame_trend("iso") is None


def test_capture_baseline_noop_when_capture_fails(tmp_path):
    session = CameraSession(
        gphoto_camera=FakeGPhoto(preview_frames=[solid_frame(1)], captures=[]),
        captures_dir=tmp_path,
    )
    session.connect()
    session.capture_baseline("iso")
    assert session.frame_trend("iso") is None


def test_capture_baseline_saves_jpeg_to_disk(tmp_path):
    session = CameraSession(
        gphoto_camera=FakeGPhoto(preview_frames=[solid_frame(1)], captures=[(solid_frame(50), b"jpeg-bytes")]),
        captures_dir=tmp_path,
    )
    session.connect()
    session.capture_baseline("iso")
    saved = list(tmp_path.glob("iso_*.jpg"))
    assert len(saved) == 1
    assert saved[0].read_bytes() == b"jpeg-bytes"


def test_read_frame_returns_latest_frame():
    probe_frame = solid_frame(1)
    frame = solid_frame(77)
    session = CameraSession(gphoto_camera=FakeGPhoto(preview_frames=[probe_frame, frame]))
    session.connect()
    result = session.read_frame()
    assert result is not None
    assert (result == frame).all()


def test_read_frame_none_without_video():
    session = CameraSession(gphoto_camera=FakeGPhoto(preview_frames=[]))
    session.connect()
    assert session.read_frame() is None


def test_close_releases_gphoto():
    fake_gphoto = FakeGPhoto(preview_frames=[solid_frame(10)])
    session = CameraSession(gphoto_camera=fake_gphoto)
    session.connect()
    session.close()
    assert fake_gphoto.closed is True
