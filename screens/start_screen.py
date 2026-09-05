from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class StartScreen(QWidget):
    """SCREEN: START - kiosk title, subtitle, Start / Data Log buttons."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.setSpacing(28)
        root.setAlignment(Qt.AlignCenter)

        title_box = QVBoxLayout()
        title_box.setSpacing(10)
        title_box.setAlignment(Qt.AlignCenter)

        title = QLabel("INTERACTIVE\nCAMERA TRAINER")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-weight:800; font-size:34px; letter-spacing:-0.3px;")
        title_box.addWidget(title)

        subtitle = QLabel("USTP-CDO · Multimedia Systems Technology")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("font-weight:500; font-size:14px; color:#64748b;")
        title_box.addWidget(subtitle)

        root.addLayout(title_box)

        buttons = QHBoxLayout()
        buttons.setSpacing(16)
        buttons.setAlignment(Qt.AlignCenter)

        start_btn = QPushButton("Start")
        start_btn.setObjectName("primary")
        start_btn.setCursor(Qt.PointingHandCursor)
        start_btn.clicked.connect(self.controller.start_flow)
        buttons.addWidget(start_btn)

        data_log_btn = QPushButton("Data Log")
        data_log_btn.setObjectName("outline")
        data_log_btn.setCursor(Qt.PointingHandCursor)
        data_log_btn.clicked.connect(self.controller.open_data_log)
        buttons.addWidget(data_log_btn)

        root.addLayout(buttons)
