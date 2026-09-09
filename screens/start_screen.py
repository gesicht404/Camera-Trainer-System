from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from tasks import TASKS


class StartScreen(QWidget):
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

        scenario_btn = QPushButton("Scenario")
        scenario_btn.setObjectName("textButton")
        scenario_btn.setCursor(Qt.PointingHandCursor)
        scenario_btn.clicked.connect(self.controller.open_scenario)
        root.addWidget(scenario_btn, alignment=Qt.AlignCenter)

        self.exit_btn = QPushButton("✕", self)
        self.exit_btn.setObjectName("iconButton")
        self.exit_btn.setCursor(Qt.PointingHandCursor)
        self.exit_btn.setToolTip("Exit")
        self.exit_btn.clicked.connect(self.controller.quit_app)

        self.detect_btn = QPushButton("📷", self)
        self.detect_btn.setObjectName("iconButton")
        self.detect_btn.setCursor(Qt.PointingHandCursor)
        self.detect_btn.setToolTip("Detect camera")
        self.detect_btn.clicked.connect(self._on_detect_clicked)

        self.detect_status = QLabel("", self)
        self.detect_status.setAlignment(Qt.AlignRight | Qt.AlignTop)
        self.detect_status.setWordWrap(True)
        self.detect_status.setStyleSheet("font-size:11px; color:#64748b; background:transparent;")

    def _on_detect_clicked(self):
        session = self.controller.camera_session
        session.connect()
        if session.hardware_available:
            parts = []
            for task in TASKS:
                value = session.read_current_value(task["id"])
                if value is not None:
                    parts.append(f"{task['label']}: {task['format'](value)}")
            detail = ", ".join(parts) if parts else "no readable settings"
            self.detect_status.setText(f"✓ Camera connected — {detail}")
        else:
            self.detect_status.setText("✕ No camera detected")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        margin = 16
        self.exit_btn.move(margin, margin)
        self.exit_btn.raise_()
        self.detect_btn.move(self.width() - self.detect_btn.width() - margin, margin)
        self.detect_btn.raise_()
        status_width = 220
        self.detect_status.setGeometry(
            self.width() - status_width - margin,
            margin + self.detect_btn.height() + 6,
            status_width,
            60,
        )
        self.detect_status.raise_()
