from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tasks import GRADE_LABEL


class GradeScreen(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller

        root = QVBoxLayout(self)
        root.setContentsMargins(44, 30, 44, 30)
        root.setSpacing(16)

        heading = QLabel("GRADE BREAKDOWN")
        heading.setStyleSheet("font-weight:800; font-size:24px; letter-spacing:-0.15px;")
        root.addWidget(heading)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(16)
        self.badge = QLabel()
        self.badge.setObjectName("gradeBadge")
        self.badge.setFixedSize(64, 64)
        badge_row.addWidget(self.badge)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        self.grade_label_text = QLabel()
        self.grade_label_text.setStyleSheet("font-weight:600; font-size:18px;")
        text_box.addWidget(self.grade_label_text)
        self.grade_name_text = QLabel()
        self.grade_name_text.setStyleSheet("font-size:14px; color:#64748b;")
        text_box.addWidget(self.grade_name_text)
        badge_row.addLayout(text_box)
        badge_row.addStretch(1)
        root.addLayout(badge_row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Task", "Retries", "Feedback"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setStyleSheet(
            "QHeaderView::section { background:#f1f5f9; color:#334155; font-size:13px; "
            "font-weight:600; border:none; padding:8px 14px; }"
            "QTableWidget { border:1px solid #e2e8f0; border-radius:6px; font-size:14px; }"
            "QTableWidget::item { padding:9px 14px; border-top:1px solid #e2e8f0; }"
        )
        root.addWidget(self.table, stretch=1)

        footer = QHBoxLayout()
        self.total_text = QLabel()
        self.total_text.setStyleSheet(
            "font-family:'Menlo','Consolas',monospace; font-size:14px; font-weight:700; color:#64748b;"
        )
        footer.addWidget(self.total_text)
        footer.addStretch(1)
        self.action_btn = QPushButton()
        self.action_btn.setObjectName("primary")
        self.action_btn.setCursor(Qt.PointingHandCursor)
        self.action_btn.clicked.connect(self.controller.grade_action)
        footer.addWidget(self.action_btn)
        root.addLayout(footer)

    def refresh(self):
        record = self.controller.state["currentRecord"]
        if record is None:
            return

        self.badge.setText(record["grade"])
        self.grade_label_text.setText(GRADE_LABEL[record["grade"]])
        name_text = record["name"]
        if record.get("section"):
            name_text += f" · {record['section']}"
        self.grade_name_text.setText(name_text)

        rows = record["tasks"]
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(row["label"]))
            retries_item = QTableWidgetItem(str(row["retries"]))
            retries_item.setFont(QFont("Menlo", 10))
            self.table.setItem(r, 1, retries_item)
            self.table.setItem(r, 2, QTableWidgetItem(row["feedback"]))
        self.table.resizeRowsToContents()

        self.total_text.setText(f"Total retries: {record['totalRetries']}")
        self.action_btn.setText("Done" if self.controller.state["gradeSource"] == "session" else "Back")
