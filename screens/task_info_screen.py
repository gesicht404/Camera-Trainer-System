from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from tasks import TASKS


class TaskInfoScreen(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller

        root = QVBoxLayout(self)
        root.setContentsMargins(44, 36, 44, 36)
        root.setSpacing(20)

        self.eyebrow = QLabel()
        self.eyebrow.setObjectName("eyebrow")
        root.addWidget(self.eyebrow)

        center = QVBoxLayout()
        center.setSpacing(16)
        root.addLayout(center, stretch=1)

        self.title_label = QLabel()
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("font-weight:600; font-size:28px; letter-spacing:-0.2px;")
        center.addWidget(self.title_label)

        self.body_label = QLabel()
        self.body_label.setWordWrap(True)
        self.body_label.setMaximumWidth(620)
        self.body_label.setStyleSheet("font-weight:400; font-size:18px; color:#475569;")
        center.addWidget(self.body_label)
        center.addStretch(1)

        footer = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.setObjectName("outline")
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(self.controller.go_back)
        footer.addWidget(back_btn)
        footer.addStretch(1)
        next_btn = QPushButton("Next")
        next_btn.setObjectName("primary")
        next_btn.setCursor(Qt.PointingHandCursor)
        next_btn.clicked.connect(self.controller.open_capture)
        footer.addWidget(next_btn)
        root.addLayout(footer)

    def refresh(self):
        idx = self.controller.state["taskIdx"]
        task = TASKS[idx]
        self.eyebrow.setText(f"TASK {idx + 1} OF {len(TASKS)}")
        self.title_label.setText(task["title"])
        self.body_label.setText(task["info"])
