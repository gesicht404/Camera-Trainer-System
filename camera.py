"""Live camera preview widget.

This is the real-hardware integration point: swap `PreviewPanel._base_pixmap()`
for a frame pulled from `picamera2` / `gphoto2` / OpenCV, and call
`set_frame(QPixmap)` whenever a new frame is captured. Until real hardware is
wired up, it shows a placeholder and simulates exposure by darkening/
brightening/tinting/blurring the placeholder proportional to how far the
trainee's stepper value is from the correct setting (see tasks.compute_overlay).
"""

import random

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QGraphicsBlurEffect, QGraphicsOpacityEffect, QLabel, QWidget

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
