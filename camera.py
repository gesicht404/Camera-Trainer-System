from datetime import datetime
from pathlib import Path

import numpy as np
import cv2
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import QLabel, QWidget

from gphoto_camera import GPhotoCamera
from vision import analyze_frame, describe_trend

PLACEHOLDER_FG = QColor("#e2e8f0")


class PreviewPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(320)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background:#0f172a; border-radius:8px;")

        self._frame = None

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
        self._frame = pixmap
        self.base.setPixmap(pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.base.setGeometry(self.rect())
        if self._frame is not None:
            self.set_frame(self._frame)
        self.live_chip.raise_()


def frame_to_qpixmap(frame: np.ndarray) -> QPixmap:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    height, width, channels = rgb.shape
    image = QImage(rgb.data, width, height, channels * width, QImage.Format_RGB888)
    return QPixmap.fromImage(image.copy())


class CameraSession:
    def __init__(self, gphoto_camera=None, captures_dir="captures"):
        self._gphoto = gphoto_camera if gphoto_camera is not None else GPhotoCamera()
        self._captures_dir = Path(captures_dir)

        self.settings_available = False
        self.video_available = False
        self.latest_frame = None
        self._baseline_metrics = {}

    @property
    def hardware_available(self) -> bool:
        return self.settings_available

    def connect(self) -> bool:
        self.settings_available = self._gphoto.connect()
        self.video_available = False

        if not self.settings_available:
            return False

        frame = self._gphoto.capture_preview_frame()
        self.video_available = frame is not None
        if self.video_available:
            self.latest_frame = frame
        return True

    def read_current_value(self, task_id: str):
        if not self.settings_available:
            return None
        return self._gphoto.read_settings().get(task_id)

    def _grab_frame(self):
        if not self.video_available:
            return None
        frame = self._gphoto.capture_preview_frame()
        if frame is None:
            return None
        self.latest_frame = frame
        return frame

    def read_frame(self):
        return self._grab_frame()

    def _capture_real_frame(self, task_id: str):
        if not self.settings_available:
            return None
        result = self._gphoto.capture_image()
        if result is None:
            return None
        frame, jpeg_bytes = result
        if frame is None:
            return None
        self._captures_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{task_id}_{datetime.now():%Y%m%d_%H%M%S}.jpg"
        (self._captures_dir / filename).write_bytes(jpeg_bytes)
        self.latest_frame = frame
        return frame

    def capture_baseline(self, task_id: str):
        frame = self._capture_real_frame(task_id)
        if frame is not None:
            self._baseline_metrics[task_id] = analyze_frame(frame)

    def frame_trend(self, task_id: str):
        frame = self._capture_real_frame(task_id)
        baseline = self._baseline_metrics.get(task_id)
        if frame is None or baseline is None:
            return None
        return describe_trend(baseline, analyze_frame(frame))

    def close(self):
        self._gphoto.close()
