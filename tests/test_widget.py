import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PySide6.QtWidgets import QApplication

from data_store import DataStore
from widget import Widget


class FakeCameraSession:
    hardware_available = False

    def connect(self):
        return False

    def read_current_value(self, task_id):
        return None

    def read_frame(self):
        return None

    def capture_baseline(self, task_id):
        pass

    def frame_trend(self, task_id):
        return None

    def close(self):
        pass


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def widget(app, tmp_path):
    store = DataStore(tmp_path / "data_log.db")
    w = Widget(data_store=store, camera_session=FakeCameraSession())
    yield w
    store.close()


def test_go_back_from_task_capture_returns_to_task_info_same_task(widget):
    widget.start_flow()
    widget.state["taskIdx"] = 2
    widget.open_capture()
    assert widget.state["screen"] == "taskCapture"

    widget.go_back()

    assert widget.state["screen"] == "taskInfo"
    assert widget.state["taskIdx"] == 2


def test_go_back_from_task_info_goes_to_previous_task_capture(widget):
    widget.start_flow()
    widget.state["taskIdx"] = 2
    widget.state["screen"] = "taskInfo"

    widget.go_back()

    assert widget.state["screen"] == "taskCapture"
    assert widget.state["taskIdx"] == 1


def test_go_back_from_first_task_info_goes_to_start(widget):
    widget.start_flow()
    assert widget.state["taskIdx"] == 0
    assert widget.state["screen"] == "taskInfo"

    widget.go_back()

    assert widget.state["screen"] == "start"


def test_go_back_never_touches_task_state(widget):
    widget.start_flow()
    widget.state["taskIdx"] = 1
    widget.open_capture()

    # simulate progress on task 0 and task 1 that must survive navigation
    widget.state["taskState"][0]["retries"] = 3
    widget.state["taskState"][0]["checked"] = True
    widget.state["taskState"][0]["correct"] = True
    widget.state["taskState"][1]["retries"] = 5
    widget.state["taskState"][1]["baseline"] = True
    before = [dict(t) for t in widget.state["taskState"]]

    widget.go_back()  # taskCapture(1) -> taskInfo(1)
    widget.go_back()  # taskInfo(1) -> taskCapture(0)

    assert widget.state["taskState"] == before
