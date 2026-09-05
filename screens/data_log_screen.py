from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class StudentRow(QWidget):
    def __init__(self, student: dict, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 12, 16, 12)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        name = QLabel(student["name"])
        name.setStyleSheet("font-weight:600; font-size:16px;")
        text_box.addWidget(name)
        section = QLabel(student["section"])
        section.setStyleSheet("font-size:13px; color:#64748b;")
        text_box.addWidget(section)
        row.addLayout(text_box)
        row.addStretch(1)

        retries = QLabel(f"{student['totalRetries']} retries")
        retries.setStyleSheet(
            "font-family:'Menlo','Consolas',monospace; font-size:13px; font-weight:700; color:#64748b;"
        )
        row.addWidget(retries)

        grade = QLabel(student["grade"])
        grade.setObjectName("miniGrade")
        grade.setFixedSize(32, 32)
        row.addWidget(grade)

        chevron = QLabel("›")
        chevron.setStyleSheet("font-size:18px; color:#94a3b8;")
        row.addWidget(chevron)


class DataLogScreen(QWidget):
    """SCREEN: DATA LOG - list of students, tap a row to view their grade breakdown."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller

        root = QVBoxLayout(self)
        root.setContentsMargins(44, 30, 44, 30)
        root.setSpacing(14)

        heading = QLabel("DATA LOG · Select a student")
        heading.setStyleSheet("font-weight:800; font-size:22px; letter-spacing:-0.15px;")
        root.addWidget(heading)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("border:1px solid #e2e8f0; border-radius:6px;")
        self.list_widget.setCursor(Qt.PointingHandCursor)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        root.addWidget(self.list_widget, stretch=1)

        back_btn = QPushButton("Back")
        back_btn.setObjectName("outline")
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(self.controller.back_to_start)
        root.addWidget(back_btn, alignment=Qt.AlignLeft)

    def _on_item_clicked(self, item: QListWidgetItem):
        index = item.data(Qt.UserRole)
        self.controller.open_student(index)

    def refresh(self):
        students = self.controller.state["students"]
        self.list_widget.clear()
        for i, student in enumerate(students):
            item = QListWidgetItem()
            item.setData(Qt.UserRole, i)
            item.setSizeHint(StudentRow(student).sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, StudentRow(student))
