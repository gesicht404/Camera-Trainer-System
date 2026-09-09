import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tasks import uses_remote_capture


def test_uses_remote_capture_true_for_iso():
    assert uses_remote_capture("iso") is True


def test_uses_remote_capture_false_for_other_tasks():
    assert uses_remote_capture("aperture") is False
    assert uses_remote_capture("shutter") is False
    assert uses_remote_capture("wb") is False
