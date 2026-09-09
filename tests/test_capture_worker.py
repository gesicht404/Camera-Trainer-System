import sys
from pathlib import Path

import numpy as np
from PySide6.QtGui import QImage

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from camera import CameraSession, CaptureWorker


class FakeGPhoto:
    def __init__(self, settings=None, captures=None, check_captures=None, raise_on_capture=False):
        self._settings = settings or {}
        self._captures = list(captures) if captures is not None else []
        self._check_captures = list(check_captures) if check_captures is not None else []
        self._raise_on_capture = raise_on_capture

    def connect(self):
        return True

    def read_settings(self):
        return self._settings

    def capture_preview_frame(self):
        return None

    def enable_viewfinder(self):
        pass

    def disable_viewfinder(self):
        pass

    def poll_physical_capture(self):
        return None

    def capture_image(self):
        if self._raise_on_capture:
            raise RuntimeError("usb error")
        captures = self._check_captures if self._check_captures else self._captures
        if not captures:
            return None
        return captures.pop(0)

    def close(self):
        pass


def solid_frame(value, size=8):
    return np.full((size, size, 3), value, dtype=np.uint8)


def make_session(tmp_path, **kwargs):
    session = CameraSession(gphoto_camera=FakeGPhoto(**kwargs), captures_dir=tmp_path)
    session.connect()
    return session


def run_worker(session, task_id, mode):
    worker = CaptureWorker(session, task_id, mode)
    results = {}
    worker.succeeded.connect(lambda image, trend: results.update(outcome="succeeded", image=image, trend=trend))
    worker.failed.connect(lambda message: results.update(outcome="failed", message=message))
    worker.run()
    return results


def test_capture_worker_emits_succeeded_with_image_on_baseline_success(tmp_path):
    session = make_session(tmp_path, settings={"iso": 800}, captures=[(solid_frame(50), b"jpeg", {"iso": 800})])

    results = run_worker(session, "iso", "baseline")

    assert results["outcome"] == "succeeded"
    assert isinstance(results["image"], QImage)
    assert results["trend"] is None


def test_capture_worker_emits_failed_when_capture_returns_no_frame(tmp_path):
    session = make_session(tmp_path, settings={"iso": 800}, captures=[])

    results = run_worker(session, "iso", "baseline")

    assert results["outcome"] == "failed"
    assert results["message"]


def test_capture_worker_emits_failed_on_exception(tmp_path):
    session = make_session(tmp_path, settings={"iso": 800}, raise_on_capture=True)

    results = run_worker(session, "iso", "baseline")

    assert results["outcome"] == "failed"
    assert "usb error" in results["message"]


def test_capture_worker_check_mode_emits_trend_on_success(tmp_path):
    session = make_session(tmp_path, settings={"iso": 800}, captures=[(solid_frame(50), b"jpeg", {"iso": 800})])
    session.capture_baseline("iso")
    session._gphoto._check_captures = [(solid_frame(60), b"jpeg2", {"iso": 800})]

    results = run_worker(session, "iso", "check")

    assert results["outcome"] == "succeeded"
    assert isinstance(results["image"], QImage)
    assert results["trend"] is not None
