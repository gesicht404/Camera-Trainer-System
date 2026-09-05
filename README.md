# Interactive Camera Trainer

A touchscreen kiosk app built with PySide6 (Qt for Python) that teaches students the fundamentals of manual camera exposure — ISO, aperture, shutter speed, and white balance — through a guided, hands-on simulation. Built for the USTP-CDO Multimedia Systems Technology program as a capstone project, targeting a Raspberry Pi 4 with a 7" HDMI touchscreen (fixed 800x480, frameless window).

## How it works

A trainee works through four camera settings in sequence. For each one they:

1. Read a short explainer on what the setting does (**Task Info** screen).
2. Capture a "baseline" exposure, then use +/- steppers to dial in the correct value while a live preview panel simulates the visual effect of their setting (darkening, brightening, grain, color tint, blur) relative to the correct target (**Task Capture** screen).
3. Get pass/fail feedback with a specific hint (e.g. "Image is too dark. Raise the ISO setting.") and retry until correct.

After all four tasks, the trainee enters their name and section, and receives a letter grade (A–D) based on total retries across all tasks, along with a per-task breakdown. Every completed session is saved to a JSON-backed data log, which can be browsed later from the **Data Log** screen by tapping any past student to review their results.

### Screen flow

```
Start → Task Info → Task Capture ─┐
  ↑           ↑___________________┘ (repeats for each of 4 tasks)
  │                                │
  │                                ▼
  │                           Name Entry → Grade Breakdown
  │                                              │
  └────────────── Data Log ←────────────────────┘
```

### Grading

Grade is determined by summed retries across all four tasks:

| Total retries | Grade |
|---|---|
| 0–6 | A |
| 7–14 | B |
| 15–24 | C |
| 25+ | D |

## Project structure

```
main.py                     Application entry point (QApplication bootstrap, fonts, stylesheet)
widget.py                   Kiosk shell: owns app state and screen navigation (QStackedWidget)
tasks.py                    Task definitions, grading, feedback messages, and exposure-overlay math
camera.py                   Live preview widget (placeholder until real camera hardware is wired in)
data_store.py                JSON-backed persistence for completed student session records
style.qss                   Application-wide Qt stylesheet
data_log.json                Generated data file of student records (seeded on first run)
screens/
  start_screen.py           Start screen: title + Start / Data Log buttons
  task_info_screen.py       Per-task explainer screen
  task_capture_screen.py    Live preview + stepper controls for adjusting a setting
  name_entry_screen.py      Name/section entry form
  grade_screen.py           Grade breakdown table (shared by session results and data log lookups)
  data_log_screen.py        List of past students; tap a row to view their grade breakdown
tests/
  test_tasks.py             Unit tests for grading, feedback messages, and overlay calculations
  test_data_store.py        Unit tests for JSON persistence
```

`widget.py` holds all application state in a single `state` dict and mirrors the logic of an approved Claude Design HTML/JS prototype ("Camera Trainer Kiosk.dc.html") — task configs, thresholds, and copy in `tasks.py` are intentionally kept in sync with that prototype.

## Hardware integration point

The live preview is currently a placeholder: `camera.py`'s `PreviewPanel` shows a static label and simulates exposure by applying dark/bright/tint/grain/blur overlays proportional to how far the trainee's setting is from the correct value (see `tasks.compute_overlay`). To wire in a real camera, feed captured frames into `PreviewPanel.set_frame(QPixmap)` from `picamera2`, `gphoto2`, or OpenCV.

## Requirements

- Python 3
- [PySide6](https://pypi.org/project/PySide6/)

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

For running tests, also install dev dependencies:

```bash
pip install -r requirements-dev.txt
```

## Running

```bash
python main.py
```

## Testing

```bash
pytest
```

Tests cover grading thresholds, per-task feedback messages, exposure-overlay math (`tests/test_tasks.py`), and JSON record persistence (`tests/test_data_store.py`).
