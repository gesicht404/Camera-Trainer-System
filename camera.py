"""Live camera preview widget.

This is the real-hardware integration point: swap `PreviewPanel._base_pixmap()`
for a frame pulled from `picamera2` / `gphoto2` / OpenCV, and call
`set_frame(QPixmap)` whenever a new frame is captured. Until real hardware is
wired up, it shows a placeholder and simulates exposure by darkening/
brightening/tinting/blurring the placeholder proportional to how far the
trainee's stepper value is from the correct setting (see tasks.compute_overlay).
"""

import random

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QGraphicsBlurEffect, QGraphicsOpacityEffect, QLabel, QWidget

from gphoto_camera import GPhotoCamera
from vision import analyze_frame, describe_trend

PLACEHOLDER_BG = QColor("#0f172a")
PLACEHOLDER_FG = QColor("#e2e8f0")
TINT_COLOR = QColor("#ff8c28")


class PreviewPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(320)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background:#0f172a; border-radius:8px;")

        self._frame = None  # set via set_frame() once real hardware is attached

        self.base = QLabel("Live viewfinder\npreview", self)
        self.base.setAlignment(Qt.AlignCenter)
        self.base.setStyleSheet(f"color:{PLACEHOLDER_FG.name()}; background:transparent; font-size:13px;")
        self._blur_effect = QGraphicsBlurEffect(self.base)
        self._blur_effect.setBlurRadius(0)
        self.base.setGraphicsEffect(self._blur_effect)

        self.dark_overlay = QWidget(self)
        self.dark_overlay.setAttribute(Qt.WA_StyledBackground, True)
        self.dark_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.dark_overlay.setStyleSheet("background: rgba(0,0,0,0);")

        self.bright_overlay = QWidget(self)
        self.bright_overlay.setAttribute(Qt.WA_StyledBackground, True)
        self.bright_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.bright_overlay.setStyleSheet("background: rgba(255,255,255,0);")

        self.tint_overlay = QWidget(self)
        self.tint_overlay.setAttribute(Qt.WA_StyledBackground, True)
        self.tint_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.tint_overlay.setStyleSheet("background: rgba(255,140,40,0);")

        self.grain_overlay = QLabel(self)
        self.grain_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._grain_opacity = QGraphicsOpacityEffect(self.grain_overlay)
        self._grain_opacity.setOpacity(0)
        self.grain_overlay.setGraphicsEffect(self._grain_opacity)
        self._grain_pixmap_size = None

        self.live_chip = QWidget(self)
        self.live_chip.setAttribute(Qt.WA_StyledBackground, True)
        self.live_chip.setStyleSheet("background: rgba(0,0,0,0.45); border-radius:4px;")
        chip_label = QLabel("● LIVE", self.live_chip)
        chip_label.setStyleSheet(
            "color:#ffffff; font-family:'Menlo','Consolas',monospace; font-size:11px; "
            "font-weight:700; background:transparent;"
        )
        chip_label.move(6, 3)
        chip_label.adjustSize()
        self.live_chip.setFixedSize(chip_label.width() + 12, chip_label.height() + 6)
        self.live_chip.move(10, 10)
        self.live_chip.raise_()

    def set_frame(self, pixmap: QPixmap):
        """Hook for real camera hardware: display a captured/live frame."""
        self._frame = pixmap
        self.base.setPixmap(pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))

    def apply_overlay(self, overlay: dict):
        dark = overlay.get("dark", 0.0)
        bright = overlay.get("bright", 0.0)
        grain = overlay.get("grain", 0.0)
        tint = overlay.get("tint", 0.0)
        blur = overlay.get("blur", 0.0)

        self.dark_overlay.setStyleSheet(f"background: rgba(0,0,0,{dark});")
        self.bright_overlay.setStyleSheet(f"background: rgba(255,255,255,{bright});")
        self.tint_overlay.setStyleSheet(
            f"background: rgba({TINT_COLOR.red()},{TINT_COLOR.green()},{TINT_COLOR.blue()},{tint});"
        )
        self._grain_opacity.setOpacity(grain)
        self._blur_effect.setBlurRadius(blur)

    def _regen_grain_pixmap(self):
        size = self.size()
        if size.isEmpty() or size == self._grain_pixmap_size:
            return
        self._grain_pixmap_size = size
        pixmap = QPixmap(size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        rng = random.Random(0)
        dot_count = (size.width() * size.height()) // 12
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 140))
        for _ in range(dot_count):
            x = rng.randrange(0, max(size.width(), 1))
            y = rng.randrange(0, max(size.height(), 1))
            painter.drawRect(x, y, 1, 1)
        painter.end()
        self.grain_overlay.setPixmap(pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        rect = self.rect()
        for widget in (self.base, self.dark_overlay, self.bright_overlay, self.tint_overlay, self.grain_overlay):
            widget.setGeometry(rect)
        self._regen_grain_pixmap()
        if self._frame is not None:
            self.set_frame(self._frame)
        self.live_chip.raise_()


def frame_to_qpixmap(frame: np.ndarray) -> QPixmap:
    """Converts an OpenCV BGR frame into a QPixmap for PreviewPanel.set_frame()."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    height, width, channels = rgb.shape
    image = QImage(rgb.data, width, height, channels * width, QImage.Format_RGB888)
    return QPixmap.fromImage(image.copy())


class CameraSession:
    """Non-UI hardware controller: reads live exposure settings via gPhoto2 and
    analyzes live frames via OpenCV, per the proposal's system flowchart (Ch. 3.6.3).

    Falls back gracefully when no Nikon D3500 / HDMI capture card is attached (e.g.
    during development): `hardware_available` is False and callers should keep using
    the existing on-screen stepper + simulated overlay (tasks.compute_overlay) instead.
    """

    def __init__(self, gphoto_camera=None, video_capture_factory=None, video_index: int = 0):
        self._gphoto = gphoto_camera if gphoto_camera is not None else GPhotoCamera()
        self._video_factory = video_capture_factory or cv2.VideoCapture
        self._video_index = video_index
        self._video_capture = None

        self.settings_available = False
        self.video_available = False
        self.latest_frame = None
        self._baseline_metrics = {}

    @property
    def hardware_available(self) -> bool:
        """Whether live camera settings can be read (the signal that drives
        real-value-vs-simulated-stepper behavior in the controller layer)."""
        return self.settings_available

    def connect(self) -> bool:
        self.settings_available = self._gphoto.connect()
        self.video_available = False
        self._video_capture = None

        # Only probe for a video feed once gPhoto2 confirms the Nikon D3500 itself is
        # present. Without that, opening a capture device index would risk silently
        # grabbing an unrelated local webcam on a dev machine instead of the HDMI
        # capture card, which is only ever wired up alongside the real rig.
        if not self.settings_available:
            return False

        try:
            capture = self._video_factory(self._video_index)
            self.video_available = bool(capture.isOpened())
            self._video_capture = capture if self.video_available else None
        except Exception:
            self.video_available = False
            self._video_capture = None
        return True

    def read_current_value(self, task_id: str):
        """Live camera-reported value for a task's setting, or None if unavailable
        (caller should keep using the locally tracked/simulated value in that case)."""
        if not self.settings_available:
            return None
        return self._gphoto.read_settings().get(task_id)

    def _grab_frame(self):
        if not self.video_available or self._video_capture is None:
            return None
        ok, frame = self._video_capture.read()
        if not ok or frame is None:
            return None
        self.latest_frame = frame
        return frame

    def read_frame(self):
        """Grabs the current live frame for preview display (no analysis), or None
        if no video feed is available."""
        return self._grab_frame()

    def capture_baseline(self, task_id: str):
        """Stores the current frame's analyzed metrics as the comparison baseline
        for this task (mirrors the flowchart's "capture a baseline image")."""
        frame = self._grab_frame()
        if frame is not None:
            self._baseline_metrics[task_id] = analyze_frame(frame)

    def frame_trend(self, task_id: str):
        """Qualitative visual change (brighter/darker/sharper/blurrier/warmer/cooler)
        of the current frame relative to this task's captured baseline, or None if a
        frame or baseline isn't available yet."""
        frame = self._grab_frame()
        baseline = self._baseline_metrics.get(task_id)
        if frame is None or baseline is None:
            return None
        return describe_trend(baseline, analyze_frame(frame))

    def close(self):
        if self._video_capture is not None:
            self._video_capture.release()
            self._video_capture = None
        self._gphoto.close()
