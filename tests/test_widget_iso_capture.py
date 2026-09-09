import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import QCoreApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from camera import CameraSession
from data_store import DataStore
from widget import Widget


class FakeGPhoto:
    def __init__(self, settings=None, captures=None):
        self._settings = settings or {}
        self._captures = list(captures) if captures is not None else []
        self.viewfinder_enabled_calls = 0
        self.viewfinder_disabled_calls = 0
        self.closed = False

    def connect(self):
        return True

    def read_settings(self):
        return self._settings

    def capture_preview_frame(self):
        return None

    def capture_image(self):
        if not self._captures:
            return None
        return self._captures.pop(0)

    def poll_physical_capture(self):
        return None

    def enable_viewfinder(self):
        self.viewfinder_enabled_calls += 1

    def disable_viewfinder(self):
        self.viewfinder_disabled_calls += 1

    def close(self):
        self.closed = True


def solid_frame(value, size=8):
    return np.full((size, size, 3), value, dtype=np.uint8)


def make_widget(tmp_path, fake_gphoto=None):
    fake_gphoto = fake_gphoto or FakeGPhoto(settings={"iso": 100})
    session = CameraSession(gphoto_camera=fake_gphoto, captures_dir=tmp_path / "captures")
    data_store = DataStore(tmp_path / "test.db")
    widget = Widget(data_store=data_store, camera_session=session)
    return widget, fake_gphoto


def test_entering_iso_task_screen_keeps_live_preview_disabled(qapp, tmp_path):
    widget, fake = make_widget(tmp_path)
    widget.start_flow()

    widget.open_capture()

    assert fake.viewfinder_enabled_calls == 0


def test_proceeding_to_aperture_task_enables_live_preview(qapp, tmp_path):
    fake = FakeGPhoto(settings={"iso": 100})
    widget, fake = make_widget(tmp_path, fake)
    widget.start_flow()
    widget.open_capture()

    widget.proceed()
    widget.open_capture()

    assert fake.viewfinder_enabled_calls == 1


def test_capture_or_check_on_iso_starts_worker_and_disables_button(qapp, tmp_path):
    fake = FakeGPhoto(settings={"iso": 100}, captures=[(solid_frame(1), b"jpeg", {"iso": 100})])
    widget, fake = make_widget(tmp_path, fake)
    widget.start_flow()
    widget.open_capture()

    widget.capture_or_check()

    assert widget.state["taskState"][0]["captureStatus"] == "capturing"
    assert widget.task_capture_screen.check_btn.isEnabled() is False
    assert widget._capture_worker is not None

    widget._capture_worker.wait()
    QCoreApplication.processEvents()

    assert widget.state["taskState"][0]["captureStatus"] == "success"
    assert widget.state["taskState"][0]["baseline"] is True
    assert widget._capture_worker is None
    assert widget.task_capture_screen.check_btn.isEnabled() is True


def test_capture_or_check_ignores_duplicate_click_while_capturing(qapp, tmp_path):
    fake = FakeGPhoto(settings={"iso": 100}, captures=[(solid_frame(1), b"jpeg", {"iso": 100})])
    widget, fake = make_widget(tmp_path, fake)
    widget.start_flow()
    widget.open_capture()

    widget.capture_or_check()
    first_worker = widget._capture_worker
    widget.capture_or_check()

    assert widget._capture_worker is first_worker

    widget._capture_worker.wait()
    QCoreApplication.processEvents()


def test_close_event_waits_for_in_flight_capture_before_closing_camera(qapp, tmp_path):
    fake = FakeGPhoto(settings={"iso": 100}, captures=[(solid_frame(1), b"jpeg", {"iso": 100})])
    widget, fake = make_widget(tmp_path, fake)
    widget.start_flow()
    widget.open_capture()

    widget.capture_or_check()
    assert widget._capture_worker is not None

    widget.close()

    assert fake.closed is True


def test_capture_or_check_on_iso_shows_error_on_failed_capture(qapp, tmp_path):
    fake = FakeGPhoto(settings={"iso": 100}, captures=[])
    widget, fake = make_widget(tmp_path, fake)
    widget.start_flow()
    widget.open_capture()

    widget.capture_or_check()
    widget._capture_worker.wait()
    QCoreApplication.processEvents()

    assert widget.state["taskState"][0]["captureStatus"] == "error"
    assert widget.state["taskState"][0]["captureError"]
    assert widget.task_capture_screen.check_btn.isEnabled() is True
