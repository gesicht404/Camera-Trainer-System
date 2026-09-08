"""Real image analysis for the live camera feed via OpenCV.

Per the proposal's system flowchart (Ch. 3.6.3): OpenCV analyzes the captured
image for brightness, color tendency, and blur, and the system compares the
baseline and adjusted images to determine whether the student's setting
adjustment produced the expected visual change.
"""

import cv2
import numpy as np

BRIGHTNESS_EPSILON = 8.0
BLUR_EPSILON = 5.0
WARMTH_EPSILON = 3.0


def analyze_frame(frame: np.ndarray) -> dict:
    """Computes brightness, sharpness ("blur"), and color warmth for a BGR frame.

    - brightness: mean grayscale pixel value (0-255).
    - blur: variance of the Laplacian; higher means sharper/more detail, lower
      means blurrier (a flat image has near-zero variance).
    - warmth: mean red minus mean blue channel; positive skews warm/orange,
      negative skews cool/blue.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    brightness = float(np.mean(gray))
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    b_channel, _g_channel, r_channel = cv2.split(frame.astype(np.float32))
    warmth = float(np.mean(r_channel) - np.mean(b_channel))
    return {"brightness": brightness, "blur": blur, "warmth": warmth}


def describe_trend(baseline: dict, current: dict) -> dict:
    """Qualitative direction of change for each metric between two analyzed frames."""
    brightness_delta = current["brightness"] - baseline["brightness"]
    blur_delta = current["blur"] - baseline["blur"]
    warmth_delta = current["warmth"] - baseline["warmth"]

    if brightness_delta > BRIGHTNESS_EPSILON:
        brightness_trend = "brighter"
    elif brightness_delta < -BRIGHTNESS_EPSILON:
        brightness_trend = "darker"
    else:
        brightness_trend = "unchanged"

    if blur_delta > BLUR_EPSILON:
        blur_trend = "sharper"
    elif blur_delta < -BLUR_EPSILON:
        blur_trend = "blurrier"
    else:
        blur_trend = "unchanged"

    if warmth_delta > WARMTH_EPSILON:
        warmth_trend = "warmer"
    elif warmth_delta < -WARMTH_EPSILON:
        warmth_trend = "cooler"
    else:
        warmth_trend = "unchanged"

    return {"brightness": brightness_trend, "blur": blur_trend, "warmth": warmth_trend}
