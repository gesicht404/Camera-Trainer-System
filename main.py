# This Python file uses the following encoding: utf-8
"""QApplication bootstrap for the Interactive Camera Trainer kiosk.

Fixed 800x480, frameless, for a 7" HDMI touchscreen on Raspberry Pi 4.
"""

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from widget import Widget

BASE_DIR = Path(__file__).resolve().parent


def load_fonts():
    """Bundle Inter as an application font if present; else fall back to system sans-serif."""
    fonts_dir = BASE_DIR / "assets" / "fonts"
    if not fonts_dir.is_dir():
        return
    for font_file in fonts_dir.glob("*.[ot]tf"):
        QFontDatabase.addApplicationFont(str(font_file))


def load_stylesheet() -> str:
    qss_path = BASE_DIR / "style.qss"
    return qss_path.read_text(encoding="utf-8") if qss_path.exists() else ""

    
if __name__ == "__main__":
    app = QApplication(sys.argv)
    load_fonts()
    app.setStyleSheet(load_stylesheet())

    window = Widget()
    window.setFixedSize(800, 480)
    window.setWindowFlag(Qt.FramelessWindowHint)
    window.setWindowTitle("Interactive Camera Trainer")
    window.show()

    sys.exit(app.exec())
