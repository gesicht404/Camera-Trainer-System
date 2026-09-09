"""Live camera preview widget.

Displays real frames from the Nikon D3500's HDMI capture card (fed via
`set_frame(QPixmap)` - see `CameraSession` below) or a placeholder when no
camera is connected. There is no simulated exposure effect: the trainee turns
the physical camera dial and the system detects the real result.
"""

import numpy as np
import cv2
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import QLabel, QWidget

from gphoto_camera import GPhotoCamera
from vision import analyze_frame, describe_trend

PLACEHOLDER_BG = QColor("#0f172a")
PLACEHOLDER_FG = QColor("#e2e8f0")


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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.base.setGeometry(self.rect())
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

    `hardware_available` is False when no Nikon D3500 is connected (e.g. during
    development) - the app has no on-screen fallback for adjusting settings in that
    case, since the trainee is expected to turn the physical camera dial and the
    system detects the result.
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
        if self._video_capture is not None:
            self._video_capture.release()  # release any previous handle before reconnecting

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
        """Live camera-reported value for a task's setting, or None if no camera
        is connected."""
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
