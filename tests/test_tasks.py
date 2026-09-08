import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tasks import (
    NEUTRAL_OVERLAY,
    TASKS,
    compute_grade,
    compute_overlay,
    correct_message,
    fresh_task_state,
    incorrect_message,
    is_hardware_mode,
    set_hardware_mode,
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
    assert compute_grade(5) == "A"  # Juan Dela Cruz
    assert compute_grade(23) == "C"  # Maria Santos


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


def test_overlay_at_target_is_neutral():
    for task in TASKS:
        overlay = compute_overlay(task, task["target"])
        assert overlay["dark"] == 0
        assert overlay["bright"] == 0
        assert overlay["tint"] == 0


def test_overlay_iso_too_low_darkens():
    task = TASKS[0]
    overlay = compute_overlay(task, task["options"][0])
    assert overlay["dark"] > 0
    assert overlay["bright"] == 0


def test_overlay_iso_too_high_brightens_and_adds_grain():
    task = TASKS[0]
    overlay = compute_overlay(task, task["options"][-1])
    assert overlay["bright"] > 0
    assert overlay["grain"] > 0


def test_overlay_wb_mismatch_tints():
    task = TASKS[3]
    overlay = compute_overlay(task, "Auto")
    assert overlay["tint"] == 0.32


def test_hardware_mode_defaults_off():
    assert is_hardware_mode() is False


def test_hardware_mode_forces_neutral_overlay():
    task = TASKS[0]
    try:
        set_hardware_mode(True)
        overlay = compute_overlay(task, task["options"][-1])  # would normally darken/grain
        assert overlay == NEUTRAL_OVERLAY
    finally:
        set_hardware_mode(False)


def test_hardware_mode_off_keeps_simulated_overlay():
    set_hardware_mode(False)
    task = TASKS[0]
    overlay = compute_overlay(task, task["options"][-1])
    assert overlay != NEUTRAL_OVERLAY
