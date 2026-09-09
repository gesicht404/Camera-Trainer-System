import logging
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from camera import CameraSession


class FakeGPhoto:
    def __init__(
        self,
        settings=None,
        connect_ok=True,
        preview_frames=None,
        captures=None,
        physical_captures=None,
    ):
        self._settings = settings or {}
        self._connect_ok = connect_ok
        self._preview_frames = list(preview_frames) if preview_frames is not None else []
        self._captures = list(captures) if captures is not None else []
        self._physical_captures = list(physical_captures) if physical_captures is not None else []
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

    def poll_physical_capture(self):
        if not self._physical_captures:
            return None
        return self._physical_captures.pop(0)

    def close(self):
        self.closed = True


def solid_frame(value, size=8):
    return np.full((size, size, 3), value, dtype=np.uint8)


def test_capture_baseline_stores_exif_settings(tmp_path):
    session = CameraSession(
        gphoto_camera=FakeGPhoto(
            settings={"iso": 800},
            preview_frames=[solid_frame(1)],
            captures=[(solid_frame(50), b"jpeg-bytes", {"iso": 800, "aperture": 5.6})],
        ),
        captures_dir=tmp_path,
    )
    session.connect()
    session.capture_baseline("iso")
    assert session.last_exif_settings == {"iso": 800, "aperture": 5.6}


def test_capture_real_frame_logs_warning_on_exif_config_mismatch(tmp_path, caplog):
    session = CameraSession(
        gphoto_camera=FakeGPhoto(
            settings={"iso": 400},
            preview_frames=[solid_frame(1)],
            captures=[(solid_frame(50), b"jpeg-bytes", {"iso": 800})],
        ),
        captures_dir=tmp_path,
    )
    session.connect()
    with caplog.at_level(logging.WARNING):
        session.capture_baseline("iso")
    assert any("iso" in record.message for record in caplog.records)


def test_capture_real_frame_no_warning_when_exif_matches_config(tmp_path, caplog):
    session = CameraSession(
        gphoto_camera=FakeGPhoto(
            settings={"iso": 800},
            preview_frames=[solid_frame(1)],
            captures=[(solid_frame(50), b"jpeg-bytes", {"iso": 800})],
        ),
        captures_dir=tmp_path,
    )
    session.connect()
    with caplog.at_level(logging.WARNING):
        session.capture_baseline("iso")
    assert caplog.records == []


def test_capture_real_frame_no_warning_when_exif_missing_field(tmp_path, caplog):
    session = CameraSession(
        gphoto_camera=FakeGPhoto(
            settings={"iso": 800},
            preview_frames=[solid_frame(1)],
            captures=[(solid_frame(50), b"jpeg-bytes", {})],
        ),
        captures_dir=tmp_path,
    )
    session.connect()
    with caplog.at_level(logging.WARNING):
        session.capture_baseline("iso")
    assert caplog.records == []


def test_poll_physical_capture_returns_none_when_no_shutter_press(tmp_path):
    session = CameraSession(
        gphoto_camera=FakeGPhoto(settings={"iso": 800}, preview_frames=[solid_frame(1)]),
        captures_dir=tmp_path,
    )
    session.connect()
    assert session.poll_physical_capture("iso") is None


def test_poll_physical_capture_updates_latest_frame_and_saves_file(tmp_path):
    session = CameraSession(
        gphoto_camera=FakeGPhoto(
            settings={"iso": 800},
            preview_frames=[solid_frame(1)],
            physical_captures=[(solid_frame(77), b"jpeg-bytes", {"iso": 800})],
        ),
        captures_dir=tmp_path,
    )
    session.connect()

    frame = session.poll_physical_capture("iso")

    assert frame is not None
    assert np.array_equal(session.latest_frame, frame)
    assert session.last_exif_settings == {"iso": 800}
    saved_files = list(tmp_path.glob("iso_*.jpg"))
    assert len(saved_files) == 1
    assert saved_files[0].read_bytes() == b"jpeg-bytes"


def test_poll_physical_capture_warns_on_exif_config_mismatch(tmp_path, caplog):
    session = CameraSession(
        gphoto_camera=FakeGPhoto(
            settings={"iso": 400},
            preview_frames=[solid_frame(1)],
            physical_captures=[(solid_frame(77), b"jpeg-bytes", {"iso": 800})],
        ),
        captures_dir=tmp_path,
    )
    session.connect()
    with caplog.at_level(logging.WARNING):
        session.poll_physical_capture("iso")
    assert any("iso" in record.message for record in caplog.records)


def test_poll_physical_capture_returns_none_when_hardware_unavailable(tmp_path):
    session = CameraSession(
        gphoto_camera=FakeGPhoto(connect_ok=False),
        captures_dir=tmp_path,
    )
    session.connect()
    assert session.poll_physical_capture("iso") is None
