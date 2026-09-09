import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tasks import (
    TASKS,
    compute_grade,
    correct_message,
    fresh_task_state,
    incorrect_message,
)


def test_compute_grade_thresholds():
    assert compute_grade(0) == "A"
    assert compute_grade(6) == "A"
    assert compute_grade(7) == "B"
    assert compute_grade(14) == "B"
    assert compute_grade(15) == "C"
    assert compute_grade(24) == "C"
    assert compute_grade(25) == "D"


def test_seed_students_grades_match_thresholds():
    assert compute_grade(5) == "A"
    assert compute_grade(23) == "C"


def test_fresh_task_state_matches_start_values():
    state = fresh_task_state()
    assert [s["value"] for s in state] == [100, 11, 500, "Auto"]
    assert all(s == {"value": s["value"], "baseline": False, "checked": False, "correct": False, "retries": 0} for s in state)


def test_iso_messages():
    task = TASKS[0]
    options = task["options"]
    target_idx = options.index(task["target"])
    assert incorrect_message(task, 0, target_idx) == "Image is too dark. Raise the ISO setting."
    assert incorrect_message(task, len(options) - 1, target_idx) == "Image is too bright! Lower the ISO setting."
    assert correct_message(task) == "Good ISO setting, image brightness is balanced."


def test_aperture_messages():
    task = TASKS[1]
    assert incorrect_message(task, 3, 0) == "Image is too dark. Use a lower f-number to open the aperture."
    assert correct_message(task) == "Good aperture setting, exposure looks balanced."


def test_shutter_messages():
    task = TASKS[2]
    options = task["options"]
    target_idx = options.index(task["target"])
    assert incorrect_message(task, target_idx + 1, target_idx) == "Image is too dark. Use a slower shutter speed."
    assert incorrect_message(task, target_idx - 1, target_idx) == "Image looks blurry. Use a faster shutter speed."
    assert correct_message(task) == "Good shutter speed, exposure and sharpness look balanced."


def test_wb_messages():
    task = TASKS[3]
    assert incorrect_message(task, 0, 3) == "Image still looks too warm/orange. Select the Tungsten preset to match the lighting."
    assert correct_message(task) == "Good white balance, colors look natural."


