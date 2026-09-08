# Interactive Camera Trainer

A touchscreen kiosk app built with PySide6 (Qt for Python) that teaches students the fundamentals of manual camera exposure — ISO, aperture, shutter speed, and white balance — using a real Nikon D3500. Built for the USTP-CDO Multimedia Systems Technology program as a capstone project, targeting a Raspberry Pi 4 with a 7" HDMI touchscreen (fixed 800x480, frameless window).

## How it works

A trainee works through four camera settings in sequence. For each one they:

1. Read a short explainer on what the setting does (**Task Info** screen).
2. Tap **Capture Baseline**, then turn the *physical* camera dial to adjust the setting — the app detects the camera's live ISO/aperture/shutter/white-balance over USB (`gphoto2`) and shows it on screen in real time, alongside the live HDMI preview feed (**Task Capture** screen). There is no on-screen +/- control: the real camera is the input device.
3. Tap **Check Adjustment** to get pass/fail feedback with a specific hint (e.g. "Image is too dark. Raise the ISO setting.") and retry until correct.

After all four tasks, the trainee enters their name and section, and receives a letter grade (A–D) based on total retries across all tasks, along with a per-task breakdown. Every completed session is saved to a SQLite-backed data log, which can be browsed later from the **Data Log** screen by tapping any past student to review their results.

Every screen is an unmodified implementation of an approved Claude Design UI prototype (layout, copy, grading), wired up to the real hardware/software architecture specified in the capstone proposal ("Design and Development of an Interactive Camera Trainer System...") — a Nikon D3500 read over USB via `gphoto2`, live video analyzed with OpenCV, and SQLite persistence.

**Without a camera connected** (e.g. this dev machine), the Task Capture screen shows "No camera detected" and the setting display reads "—" — there is deliberately no simulated/fake value to interact with, so a task can't be completed until real hardware is attached. See [Deploying to Raspberry Pi 4](#deploying-to-raspberry-pi-4) below.

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
widget.py                   Kiosk shell: owns app state, screen navigation, and camera/hardware wiring
tasks.py                    Task definitions, grading, and feedback messages
camera.py                   PreviewPanel (live preview widget, UI) + CameraSession (hardware controller)
gphoto_camera.py            gPhoto2 wrapper: reads live ISO/aperture/shutter/WB from a Nikon D3500 over USB
vision.py                   OpenCV frame analysis: brightness, sharpness, and color-warmth metrics
data_store.py               SQLite-backed persistence for completed student session records
style.qss                   Application-wide Qt stylesheet
data_log.db                 Generated SQLite database of student records (seeded on first run)
screens/
  start_screen.py           Start screen: title + Start / Data Log buttons
  task_info_screen.py       Per-task explainer screen
  task_capture_screen.py    Live preview + live-detected camera setting (no on-screen stepper)
  name_entry_screen.py      Name/section entry form
  grade_screen.py           Grade breakdown table (shared by session results and data log lookups)
  data_log_screen.py        List of past students; tap a row to view their grade breakdown
tests/
  test_tasks.py             Unit tests for grading and feedback messages
  test_data_store.py        Unit tests for SQLite persistence
  test_vision.py            Unit tests for OpenCV brightness/blur/warmth analysis (synthetic frames)
  test_gphoto_camera.py     Unit tests for the gPhoto2 wrapper (mocked hardware)
  test_camera_session.py    Unit tests for the camera controller (mocked hardware)
```

`widget.py` holds all application state in a single `state` dict. Every screen file is an implementation of an approved Claude Design UI prototype ("Camera Trainer Kiosk.dc.html") — copy, layout, and grading thresholds in `tasks.py` are intentionally kept in sync with that prototype, except `task_capture_screen.py`, whose on-screen +/- stepper (from the original prototype's simulated-value demo) was removed in favor of live camera detection.

## Hardware integration (per the capstone proposal)

The proposal's system flowchart (Ch. 3.6.3) specifies: a Nikon D3500 connected via HDMI capture card for live video, `gphoto2` reading the camera's actual settings over USB, and OpenCV analyzing the video feed — comparing both the setting direction and the resulting image effect against a captured baseline. `camera.py`'s `CameraSession` implements exactly this, with no simulated fallback:

- **Camera connected**: `gphoto_camera.GPhotoCamera` reads live ISO/aperture/shutter/white-balance over USB every 400ms, driving the on-screen readout directly from the physical dial — the trainee never touches the screen to change a value. `vision.analyze_frame`/`describe_trend` (real OpenCV) measure brightness/sharpness/warmth against a captured baseline frame.
- **No camera connected** (e.g. this dev machine): the Task Capture screen shows "No camera detected" and the value reads "—". Nothing on screen can change the value, and `Check Adjustment` will not report a task as correct — this is intentional per the capstone's real-hardware requirement, not a bug.

`CameraSession.connect()` only probes for a video device *after* `gphoto2` confirms the Nikon is actually present — this deliberately avoids a dev machine's own webcam ever being opened in its place.

`python-gphoto2` requires the native `libgphoto2` C library (Linux-only — see `requirements-pi.txt`), so it can't be installed or tested on Windows/macOS; `gphoto_camera.py` and `camera.CameraSession` are unit-tested against a mocked `gphoto2` module instead (`tests/test_gphoto_camera.py`, `tests/test_camera_session.py`). Real end-to-end hardware testing must happen on the deployed Raspberry Pi rig.

## Requirements

- Python 3
- [PySide6](https://pypi.org/project/PySide6/), OpenCV, NumPy (`requirements.txt`)
- On the deployed Raspberry Pi only: `gphoto2` (`requirements-pi.txt`) — needs `libgphoto2` installed at the OS level

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

On the Raspberry Pi, install the hardware extras instead (after `sudo apt install libgphoto2-dev`):

```bash
pip install -r requirements-pi.txt
```

## Deploying to Raspberry Pi 4

The app is written to run on the Pi, but the following has only been verified through unit tests and mocked hardware on a Windows dev machine — it has **not** been exercised on a physical Pi + Nikon D3500 + capture card yet. Verify each step on the real rig, since some details (device paths, exact package versions) can only be confirmed there.

1. **Use Raspberry Pi OS Bookworm, 64-bit.** PySide6 has no wheel for 32-bit ARM at all — only `aarch64`. Check with `uname -m` (must print `aarch64`, not `armv7l`).

2. **Install PySide6 via `requirements-pi.txt`, not `requirements.txt`.** PySide6 releases from 6.8 onward ship Linux aarch64 wheels requiring `glibc >= 2.39`; Raspberry Pi OS Bookworm has `glibc 2.36`. Installing an unpinned `PySide6` on the Pi would find no compatible wheel and fall back to compiling from source (hours-long, frequently OOMs on a Pi 4). `requirements-pi.txt` pins `PySide6==6.7.3`, whose aarch64 wheel only needs `glibc >= 2.31` and supports Python 3.9–3.12 (Bookworm's default `python3` is 3.11). If a future Raspberry Pi OS ships newer glibc, this pin can be revisited.

3. **Install `libgphoto2` before `pip install -r requirements-pi.txt`:**
   ```bash
   sudo apt update
   sudo apt install libgphoto2-dev
   ```
   `python-gphoto2` compiles a C extension against this at install time — there's no prebuilt wheel for it.

4. **Kill the desktop's automatic camera-mounting service before running the app**, or `gphoto2`/the app will fail to claim the USB device (`Could not claim the USB device`) because Raspberry Pi OS Desktop's file manager auto-mounts any connected camera as a media device:
   ```bash
   sudo systemctl mask --now gvfs-gphoto2-volume-monitor 2>/dev/null || killall gvfs-gphoto2-volume-monitor
   ```

5. **Confirm the HDMI capture card's video device index.** OpenCV opens it via `cv2.VideoCapture(index)`, defaulting to index `0`, but the actual `/dev/videoN` number depends on what else is attached. Check with `v4l2-ctl --list-devices` (`sudo apt install v4l-utils` if needed) and, if it's not `0`, set:
   ```bash
   export CAMERA_VIDEO_INDEX=1   # whatever v4l2-ctl reports
   ```

6. **Verify gPhoto2 sees the camera independently first**, before debugging the app:
   ```bash
   gphoto2 --auto-detect
   ```
   If this doesn't list the Nikon D3500, the app's hardware mode won't activate either (it'll just fall back to simulation mode silently) — fix the USB/driver issue at this level first.

7. Use USB 3.0 ports (blue) for both the camera and the capture card, as the proposal specifies, for stable throughput.

If `gphoto2 --auto-detect` finds the camera but the app still doesn't pick it up, that's the first thing to report back — it likely means one of the `gphoto2` config widget names in `gphoto_camera.py`'s `CONFIG_NAMES` doesn't match what this particular Nikon firmware exposes (these can vary slightly by camera/firmware version), which `gphoto2 --get-config iso` (etc.) can confirm directly on the device.

## Running

```bash
python main.py
```

## Testing

```bash
pytest
```

38 tests cover grading thresholds and feedback messages (`test_tasks.py`), SQLite persistence (`test_data_store.py`), OpenCV frame analysis (`test_vision.py`), and the gPhoto2 wrapper + camera controller against mocked hardware (`test_gphoto_camera.py`, `test_camera_session.py`). None require a physical camera.
