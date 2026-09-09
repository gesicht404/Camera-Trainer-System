import logging
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import cv2
from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import QLabel, QWidget

from gphoto_camera import GPhotoCamera
from vision import analyze_frame, describe_trend

logger = logging.getLogger(__name__)

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


class CaptureResultPanel(QWidget):
    """Shows the result of a remote-triggered DSLR capture: idle / capturing / success / error."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(320)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background:#0f172a; border-radius:8px;")

        self.state = "idle"
        self._pixmap = None

        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.hide()

        self.message_label = QLabel(self)
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet(
            f"color:{PLACEHOLDER_FG.name()}; background:transparent; font-size:13px; padding:16px;"
        )

        self.show_idle()

    def show_idle(self):
        self.state = "idle"
        self._pixmap = None
        self.image_label.hide()
        self.message_label.setText("Ready to capture\nPosition your document using the DSLR")
        self.message_label.show()

    def show_capturing(self):
        self.state = "capturing"
        self._pixmap = None
        self.image_label.hide()
        self.message_label.setText("Capturing...\nTransferring image from the DSLR")
        self.message_label.show()

    def show_result(self, pixmap: QPixmap):
        self.state = "success"
        self._pixmap = pixmap
        self.message_label.hide()
        self._render_pixmap()
        self.image_label.show()

    def show_error(self, message: str):
        self.state = "error"
        self._pixmap = None
        self.image_label.hide()
        self.message_label.setText(f"Capture failed\n{message}\nClick the button to retry.")
        self.message_label.show()

    def _render_pixmap(self):
        if self._pixmap is not None:
            self.image_label.setPixmap(
                self._pixmap.scaled(
                    self.image_label.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
                )
            )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.image_label.setGeometry(self.rect())
        self.message_label.setGeometry(self.rect())
        self._render_pixmap()


def frame_to_qimage(frame: np.ndarray) -> QImage:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    height, width, channels = rgb.shape
    image = QImage(rgb.data, width, height, channels * width, QImage.Format_RGB888)
    return image.copy()


def frame_to_qpixmap(frame: np.ndarray) -> QPixmap:
    return QPixmap.fromImage(frame_to_qimage(frame))


PREVIEW_HOLD_SECONDS = 3.0


class CameraSession:
    def __init__(self, gphoto_camera=None, captures_dir="captures", clock=time.monotonic):
        self._gphoto = gphoto_camera if gphoto_camera is not None else GPhotoCamera()
        self._captures_dir = Path(captures_dir)
        self._clock = clock

        self.settings_available = False
        self.video_available = False
        self.latest_frame = None
        self.last_exif_settings = {}
        self._baseline_metrics = {}
        self._hold_until = 0.0

    @property
    def hardware_available(self) -> bool:
        return self.settings_available

    def connect(self) -> bool:
        self.settings_available = self._gphoto.connect()
        self.video_available = False
        return self.settings_available

    def set_live_preview_enabled(self, enabled: bool):
        if not self.settings_available:
            return
        if enabled:
            self._gphoto.enable_viewfinder()
            frame = self._gphoto.capture_preview_frame()
            self.video_available = frame is not None
            if self.video_available:
                self.latest_frame = frame
        else:
            self._gphoto.disable_viewfinder()
            self.video_available = False

    def read_current_value(self, task_id: str):
        if not self.settings_available:
            return None
        return self._gphoto.read_settings().get(task_id)

    def _grab_frame(self):
        if self._clock() < self._hold_until:
            return self.latest_frame
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
        return self._store_capture(task_id, self._gphoto.capture_image())

    def poll_physical_capture(self, task_id: str):
        if not self.settings_available:
            return None
        return self._store_capture(task_id, self._gphoto.poll_physical_capture())

    def _store_capture(self, task_id: str, result):
        if result is None:
            return None
        frame, jpeg_bytes, exif_settings = result
        if frame is None:
            return None
        self._captures_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{task_id}_{datetime.now():%Y%m%d_%H%M%S}.jpg"
        (self._captures_dir / filename).write_bytes(jpeg_bytes)
        self.latest_frame = frame
        self.last_exif_settings = exif_settings
        self._hold_until = self._clock() + PREVIEW_HOLD_SECONDS
        self._warn_on_settings_mismatch(task_id, exif_settings)
        return frame

    def _warn_on_settings_mismatch(self, task_id: str, exif_settings: dict):
        exif_value = exif_settings.get(task_id)
        live_value = self._gphoto.read_settings().get(task_id)
        if exif_value is not None and live_value is not None and exif_value != live_value:
            logger.warning(
                "Captured-image EXIF disagrees with live camera config for %s: config=%s exif=%s",
                task_id,
                live_value,
                exif_value,
            )

    def capture_baseline(self, task_id: str) -> bool:
        frame = self._capture_real_frame(task_id)
        if frame is None:
            return False
        self._baseline_metrics[task_id] = analyze_frame(frame)
        return True

    def frame_trend(self, task_id: str):
        frame = self._capture_real_frame(task_id)
        baseline = self._baseline_metrics.get(task_id)
        if frame is None or baseline is None:
            return None
        return describe_trend(baseline, analyze_frame(frame))

    def close(self):
        self._gphoto.close()


class CaptureWorker(QThread):
    """Runs a real DSLR capture (shutter fire + USB transfer) off the UI thread."""

    succeeded = Signal(QImage, object)
    failed = Signal(str)

    def __init__(self, camera_session: CameraSession, task_id: str, mode: str, parent=None):
        super().__init__(parent)
        self.camera_session = camera_session
        self.task_id = task_id
        self.mode = mode

    def run(self):
        trend = None
        try:
            if self.mode == "baseline":
                ok = self.camera_session.capture_baseline(self.task_id)
            else:
                trend = self.camera_session.frame_trend(self.task_id)
                ok = trend is not None
        except Exception as exc:
            self.failed.emit(str(exc))
            return

        if ok:
            self.succeeded.emit(frame_to_qimage(self.camera_session.latest_frame), trend)
        else:
            self.failed.emit("The DSLR did not return an image. Check the connection and try again.")
