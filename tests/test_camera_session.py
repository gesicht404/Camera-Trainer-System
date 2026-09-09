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
        self.preview_frame_calls = 0
        self.viewfinder_enabled_calls = 0
        self.viewfinder_disabled_calls = 0

    def connect(self):
        return self._connect_ok

    def read_settings(self):
        return self._settings

    def capture_preview_frame(self):
        self.preview_frame_calls += 1
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

    def enable_viewfinder(self):
        self.viewfinder_enabled_calls += 1

    def disable_viewfinder(self):
        self.viewfinder_disabled_calls += 1

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


def test_record_physical_baseline_returns_true_and_stores_metrics_on_shutter_press(tmp_path):
    session = CameraSession(
        gphoto_camera=FakeGPhoto(
            settings={"iso": 800},
            physical_captures=[(solid_frame(50), b"jpeg-bytes", {"iso": 800})],
        ),
        captures_dir=tmp_path,
    )
    session.connect()

    assert session.record_physical_baseline("iso") is True
    assert np.array_equal(session.latest_frame, solid_frame(50))


def test_record_physical_baseline_returns_false_when_no_shutter_press(tmp_path):
    session = CameraSession(
        gphoto_camera=FakeGPhoto(settings={"iso": 800}),
        captures_dir=tmp_path,
    )
    session.connect()

    assert session.record_physical_baseline("iso") is False


def test_physical_capture_trend_returns_none_without_a_recorded_baseline(tmp_path):
    session = CameraSession(
        gphoto_camera=FakeGPhoto(
            settings={"iso": 800},
            physical_captures=[(solid_frame(60), b"jpeg-bytes", {"iso": 800})],
        ),
        captures_dir=tmp_path,
    )
    session.connect()

    assert session.physical_capture_trend("iso") is None


def test_physical_capture_trend_compares_new_shutter_press_against_baseline(tmp_path):
    session = CameraSession(
        gphoto_camera=FakeGPhoto(
            settings={"iso": 800},
            physical_captures=[
                (solid_frame(50), b"jpeg-bytes-1", {"iso": 800}),
                (solid_frame(120), b"jpeg-bytes-2", {"iso": 800}),
            ],
        ),
        captures_dir=tmp_path,
    )
    session.connect()
    session.record_physical_baseline("iso")

    trend = session.physical_capture_trend("iso")

    assert trend is not None
    assert np.array_equal(session.latest_frame, solid_frame(120))


def test_read_frame_holds_captured_frame_instead_of_reverting_to_live_view(tmp_path):
    clock_values = iter([0.0, 0.0, 1.0])

    def fake_clock():
        return next(clock_values)

    captured = solid_frame(50)
    session = CameraSession(
        gphoto_camera=FakeGPhoto(
            settings={"iso": 800},
            preview_frames=[solid_frame(1), solid_frame(2)],
            captures=[(captured, b"jpeg-bytes", {"iso": 800})],
        ),
        captures_dir=tmp_path,
        clock=fake_clock,
    )
    session.connect()
    session.set_live_preview_enabled(True)

    session.capture_baseline("iso")
    frame = session.read_frame()

    assert np.array_equal(frame, captured)


def test_connect_does_not_probe_preview_frame(tmp_path):
    gphoto = FakeGPhoto(settings={"iso": 800}, preview_frames=[solid_frame(1)])
    session = CameraSession(gphoto_camera=gphoto, captures_dir=tmp_path)

    session.connect()

    assert gphoto.preview_frame_calls == 0
    assert session.video_available is False


def test_set_live_preview_enabled_true_enables_viewfinder_and_fetches_frame(tmp_path):
    gphoto = FakeGPhoto(settings={"iso": 800}, preview_frames=[solid_frame(9)])
    session = CameraSession(gphoto_camera=gphoto, captures_dir=tmp_path)
    session.connect()

    session.set_live_preview_enabled(True)

    assert gphoto.viewfinder_enabled_calls == 1
    assert session.video_available is True
    assert np.array_equal(session.latest_frame, solid_frame(9))


def test_set_live_preview_enabled_false_disables_viewfinder_and_video_unavailable(tmp_path):
    gphoto = FakeGPhoto(settings={"iso": 800}, preview_frames=[solid_frame(9)])
    session = CameraSession(gphoto_camera=gphoto, captures_dir=tmp_path)
    session.connect()
    session.set_live_preview_enabled(True)

    session.set_live_preview_enabled(False)

    assert gphoto.viewfinder_disabled_calls == 1
    assert session.video_available is False


def test_set_live_preview_enabled_noop_when_hardware_unavailable(tmp_path):
    gphoto = FakeGPhoto(connect_ok=False)
    session = CameraSession(gphoto_camera=gphoto, captures_dir=tmp_path)
    session.connect()

    session.set_live_preview_enabled(True)

    assert gphoto.viewfinder_enabled_calls == 0


def test_capture_baseline_returns_true_on_success(tmp_path):
    session = CameraSession(
        gphoto_camera=FakeGPhoto(
            settings={"iso": 800},
            captures=[(solid_frame(50), b"jpeg-bytes", {"iso": 800})],
        ),
        captures_dir=tmp_path,
    )
    session.connect()

    assert session.capture_baseline("iso") is True


def test_capture_baseline_returns_false_when_capture_fails(tmp_path):
    session = CameraSession(
        gphoto_camera=FakeGPhoto(settings={"iso": 800}, captures=[]),
        captures_dir=tmp_path,
    )
    session.connect()

    assert session.capture_baseline("iso") is False


def test_read_frame_resumes_live_view_after_hold_expires(tmp_path):
    clock_values = iter([0.0, 0.0, 10.0])

    def fake_clock():
        return next(clock_values)

    live_frame = solid_frame(2)
    session = CameraSession(
        gphoto_camera=FakeGPhoto(
            settings={"iso": 800},
            preview_frames=[solid_frame(1), live_frame],
            captures=[(solid_frame(50), b"jpeg-bytes", {"iso": 800})],
        ),
        captures_dir=tmp_path,
        clock=fake_clock,
    )
    session.connect()
    session.set_live_preview_enabled(True)

    session.capture_baseline("iso")
    session.read_frame()  # still within the hold window
    frame = session.read_frame()  # hold has now expired

    assert np.array_equal(frame, live_frame)
