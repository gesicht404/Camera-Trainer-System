import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vision import analyze_frame, describe_trend


def solid_frame(b, g, r, size=64):
    frame = np.zeros((size, size, 3), dtype=np.uint8)
    frame[:, :, 0] = b
    frame[:, :, 1] = g
    frame[:, :, 2] = r
    return frame


def checkerboard_frame(size=64, cell=4):
    frame = np.zeros((size, size, 3), dtype=np.uint8)
    for y in range(0, size, cell):
        for x in range(0, size, cell):
            if ((x // cell) + (y // cell)) % 2 == 0:
                frame[y : y + cell, x : x + cell] = 255
    return frame


def test_analyze_frame_brightness_tracks_pixel_value():
    dark = analyze_frame(solid_frame(20, 20, 20))
    bright = analyze_frame(solid_frame(220, 220, 220))
    assert dark["brightness"] < bright["brightness"]
    assert 0 <= dark["brightness"] <= 255
    assert 0 <= bright["brightness"] <= 255


def test_analyze_frame_blur_is_low_on_flat_image():
    flat = analyze_frame(solid_frame(128, 128, 128))
    assert flat["blur"] < 1.0


def test_analyze_frame_blur_is_high_on_sharp_detail():
    sharp = analyze_frame(checkerboard_frame())
    flat = analyze_frame(solid_frame(128, 128, 128))
    assert sharp["blur"] > flat["blur"]


def test_analyze_frame_warmth_positive_for_orange_tint():
    warm = analyze_frame(solid_frame(b=20, g=100, r=200))
    cool = analyze_frame(solid_frame(b=200, g=100, r=20))
    assert warm["warmth"] > 0
    assert cool["warmth"] < 0


def test_describe_trend_reports_direction():
    baseline = {"brightness": 100.0, "blur": 50.0, "warmth": 0.0}
    brighter = {"brightness": 150.0, "blur": 50.0, "warmth": 0.0}
    trend = describe_trend(baseline, brighter)
    assert trend["brightness"] == "brighter"
    assert trend["blur"] == "unchanged"
    assert trend["warmth"] == "unchanged"


def test_describe_trend_darker_and_blurrier_and_warmer():
    baseline = {"brightness": 150.0, "blur": 80.0, "warmth": 0.0}
    current = {"brightness": 90.0, "blur": 20.0, "warmth": 15.0}
    trend = describe_trend(baseline, current)
    assert trend["brightness"] == "darker"
    assert trend["blur"] == "blurrier"
    assert trend["warmth"] == "warmer"


def test_describe_trend_cooler():
    baseline = {"brightness": 100.0, "blur": 50.0, "warmth": 20.0}
    current = {"brightness": 100.0, "blur": 50.0, "warmth": -5.0}
    trend = describe_trend(baseline, current)
    assert trend["warmth"] == "cooler"
