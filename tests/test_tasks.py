import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tasks import fresh_task_state, uses_remote_capture


def test_fresh_task_state_starts_capture_status_idle_with_no_error():
    state = fresh_task_state()
    assert all(task["captureStatus"] == "idle" for task in state)
    assert all(task["captureError"] is None for task in state)


def test_uses_remote_capture_true_for_iso():
    assert uses_remote_capture("iso") is True


def test_uses_remote_capture_false_for_other_tasks():
    assert uses_remote_capture("aperture") is False
    assert uses_remote_capture("shutter") is False
    assert uses_remote_capture("wb") is False
