import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from camera import CameraSession
from data_store import DataStore
from widget import Widget


class FakeGPhoto:
    def __init__(self, settings=None, physical_captures=None):
        self._settings = settings or {}
        self._physical_captures = list(physical_captures) if physical_captures is not None else []
        self.viewfinder_enabled_calls = 0
        self.viewfinder_disabled_calls = 0

    def connect(self):
        return True

    def read_settings(self):
        return self._settings

    def capture_preview_frame(self):
        return None

    def capture_image(self):
        return None

    def poll_physical_capture(self):
        if not self._physical_captures:
            return None
        return self._physical_captures.pop(0)

    def enable_viewfinder(self):
        self.viewfinder_enabled_calls += 1

    def disable_viewfinder(self):
        self.viewfinder_disabled_calls += 1

    def close(self):
        pass


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
    widget, fake = make_widget(tmp_path)
    widget.start_flow()
    widget.open_capture()

    widget.proceed()
    widget.open_capture()

    assert fake.viewfinder_enabled_calls == 1


def test_check_btn_is_hidden_for_iso_and_shown_for_other_tasks(qapp, tmp_path):
    widget, fake = make_widget(tmp_path)
    widget.start_flow()
    widget.open_capture()

    assert widget.task_capture_screen.check_btn.isHidden() is True

    widget.proceed()
    widget.open_capture()

    assert widget.task_capture_screen.check_btn.isHidden() is False


def test_physical_shutter_press_records_baseline_and_shows_captured_photo(qapp, tmp_path):
    fake = FakeGPhoto(settings={"iso": 100}, physical_captures=[(solid_frame(1), b"jpeg", {"iso": 100})])
    widget, fake = make_widget(tmp_path, fake)
    widget.start_flow()
    widget.open_capture()

    widget._poll_camera()

    assert widget.state["taskState"][0]["baseline"] is True
    assert widget.task_capture_screen.result_panel.state == "success"


def test_poll_camera_on_iso_does_nothing_without_a_shutter_press(qapp, tmp_path):
    widget, fake = make_widget(tmp_path)
    widget.start_flow()
    widget.open_capture()

    widget._poll_camera()

    assert widget.state["taskState"][0]["baseline"] is False
    assert widget.task_capture_screen.result_panel.state == "idle"


def test_second_shutter_press_completes_check_adjustment(qapp, tmp_path):
    fake = FakeGPhoto(
        settings={"iso": 100},
        physical_captures=[
            (solid_frame(1), b"jpeg1", {"iso": 100}),
            (solid_frame(2), b"jpeg2", {"iso": 100}),
        ],
    )
    widget, fake = make_widget(tmp_path, fake)
    widget.start_flow()
    widget.open_capture()

    widget._poll_camera()
    assert widget.state["taskState"][0]["baseline"] is True

    widget._poll_camera()

    assert widget.state["taskState"][0]["checked"] is True


def test_poll_camera_skips_remote_capture_polling_for_non_iso_tasks(qapp, tmp_path):
    fake = FakeGPhoto(settings={"aperture": 5.6}, physical_captures=[(solid_frame(1), b"jpeg", {})])
    widget, fake = make_widget(tmp_path, fake)
    widget.start_flow()
    widget.state["taskIdx"] = 1
    widget.open_capture()

    widget._poll_camera()

    # aperture uses the original preview-panel path; the physical press should
    # update the live preview thumbnail, not the (hidden) ISO result panel or baseline state.
    assert widget.state["taskState"][1]["baseline"] is False
