from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class ScenarioScreen(QWidget):

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.setAlignment(Qt.AlignCenter)
        root.setSpacing(24)

        heading = QLabel("Scenario")
        heading.setAlignment(Qt.AlignCenter)
        heading.setStyleSheet("font-weight:600; font-size:24px;")
        root.addWidget(heading)

        back_btn = QPushButton("Back")
        back_btn.setObjectName("outline")
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(self.controller.back_to_start)
        root.addWidget(back_btn, alignment=Qt.AlignCenter)
