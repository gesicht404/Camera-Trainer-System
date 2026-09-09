from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget


class NameEntryScreen(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.setSpacing(20)
        root.setAlignment(Qt.AlignCenter)

        heading = QLabel("Enter your name to save this result")
        heading.setAlignment(Qt.AlignCenter)
        heading.setStyleSheet("font-weight:600; font-size:24px;")
        root.addWidget(heading)

        form = QVBoxLayout()
        form.setSpacing(14)
        form_wrap = QWidget()
        form_wrap.setFixedWidth(360)
        form_wrap.setLayout(form)

        name_box = QVBoxLayout()
        name_box.setSpacing(6)
        name_label = QLabel("Name")
        name_label.setStyleSheet("font-size:14px; font-weight:500;")
        name_box.addWidget(name_label)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Juan Dela Cruz")
        self.name_edit.textChanged.connect(self.controller.set_name)
        name_box.addWidget(self.name_edit)
        self.name_error = QLabel("Please enter your name.")
        self.name_error.setObjectName("nameError")
        self.name_error.hide()
        name_box.addWidget(self.name_error)
        form.addLayout(name_box)

        section_box = QVBoxLayout()
        section_box.setSpacing(6)
        section_label = QLabel("Section")
        section_label.setStyleSheet("font-size:14px; font-weight:500;")
        section_box.addWidget(section_label)
        self.section_edit = QLineEdit()
        self.section_edit.setPlaceholderText("BSET-3A")
        self.section_edit.textChanged.connect(self.controller.set_section)
        section_box.addWidget(self.section_edit)
        form.addLayout(section_box)

        root.addWidget(form_wrap)

        done_btn = QPushButton("Done")
        done_btn.setObjectName("primary")
        done_btn.setCursor(Qt.PointingHandCursor)
        done_btn.clicked.connect(self.controller.submit_name)
        root.addWidget(done_btn, alignment=Qt.AlignCenter)

    def refresh(self):
        state = self.controller.state
        if self.name_edit.text() != state["name"]:
            self.name_edit.setText(state["name"])
        if self.section_edit.text() != state["section"]:
            self.section_edit.setText(state["section"])
        self.name_error.setVisible(state["nameError"])

    def reset_fields(self):
        self.name_edit.clear()
        self.section_edit.clear()
        self.name_error.hide()
