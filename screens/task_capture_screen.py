from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from camera import PreviewPanel
from tasks import DEFAULTS, TASKS, compute_overlay, correct_message, incorrect_message

ACTIVE_COLOR = "#ffffff"
MUTED_COLOR = "#94a3b8"


class TaskCaptureScreen(QWidget):
    """SCREEN: TASK CAPTURE - live preview + stepper controls, re-populated per task."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller

        root = QHBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(20)

        self.preview = PreviewPanel(self)
        root.addWidget(self.preview)

        controls = QVBoxLayout()
        controls.setSpacing(12)
        root.addLayout(controls, stretch=1)

        header = QVBoxLayout()
        header.setSpacing(2)
        self.eyebrow = QLabel()
        self.eyebrow.setObjectName("eyebrow")
        header.addWidget(self.eyebrow)
        self.instruction = QLabel()
        self.instruction.setWordWrap(True)
        self.instruction.setStyleSheet("font-size:15px; color:#0f172a;")
        header.addWidget(self.instruction)
        controls.addLayout(header)

        self.readout = QLabel()
        self.readout.setObjectName("readout")
        controls.addWidget(self.readout)

        stepper_row = QHBoxLayout()
        stepper_row.setSpacing(10)
        self.minus_btn = QPushButton("−")
        self.minus_btn.setObjectName("stepperBtn")
        self.minus_btn.setCursor(Qt.PointingHandCursor)
        self.minus_btn.clicked.connect(lambda: self.controller.adjust_stepper(-1))
        stepper_row.addWidget(self.minus_btn)

        self.stepper_value = QLabel()
        self.stepper_value.setObjectName("stepperValue")
        self.stepper_value.setAlignment(Qt.AlignCenter)
        stepper_row.addWidget(self.stepper_value, stretch=1)

        self.plus_btn = QPushButton("+")
        self.plus_btn.setObjectName("stepperBtn")
        self.plus_btn.setCursor(Qt.PointingHandCursor)
        self.plus_btn.clicked.connect(lambda: self.controller.adjust_stepper(1))
        stepper_row.addWidget(self.plus_btn)
        controls.addLayout(stepper_row)

        check_row = QHBoxLayout()
        self.check_btn = QPushButton()
        self.check_btn.setObjectName("primary")
        self.check_btn.setCursor(Qt.PointingHandCursor)
        self.check_btn.clicked.connect(self.controller.capture_or_check)
        check_row.addWidget(self.check_btn)
        check_row.addStretch(1)
        self.retries_label = QLabel()
        self.retries_label.setStyleSheet(
            "font-family:'Menlo','Consolas',monospace; font-size:13px; font-weight:700; color:#64748b;"
        )
        check_row.addWidget(self.retries_label)
        controls.addLayout(check_row)

        self.banner = QLabel()
        self.banner.setWordWrap(True)
        self.banner.setContentsMargins(14, 12, 14, 12)
        self.banner.hide()
        controls.addWidget(self.banner)

        controls.addStretch(1)

        proceed_row = QHBoxLayout()
        proceed_row.addStretch(1)
        self.proceed_btn = QPushButton("Proceed")
        self.proceed_btn.setObjectName("primary")
        self.proceed_btn.setCursor(Qt.PointingHandCursor)
        self.proceed_btn.clicked.connect(self.controller.proceed)
        proceed_row.addWidget(self.proceed_btn)
        controls.addLayout(proceed_row)

    def refresh(self):
        state = self.controller.state
        idx = state["taskIdx"]
        task = TASKS[idx]
        cur = state["taskState"][idx]
        options = task["options"]
        opt_idx = options.index(cur["value"])
        target_idx = options.index(task["target"])

        self.eyebrow.setText(f"TASK {idx + 1} OF {len(TASKS)} · {task['label'].upper()}")
        self.instruction.setText(task["instruction"])

        iso_val = cur["value"] if task["id"] == "iso" else DEFAULTS["iso"]
        ap_val = cur["value"] if task["id"] == "aperture" else DEFAULTS["aperture"]
        sh_val = cur["value"] if task["id"] == "shutter" else DEFAULTS["shutter"]
        wb_val = cur["value"] if task["id"] == "wb" else DEFAULTS["wb"]

        def color_for(task_id):
            return ACTIVE_COLOR if task["id"] == task_id else MUTED_COLOR

        self.readout.setText(
            f'<span style="color:{color_for("iso")}">ISO {iso_val}</span>&nbsp;&nbsp;&nbsp;'
            f'<span style="color:{color_for("aperture")}">f/{ap_val}</span>&nbsp;&nbsp;&nbsp;'
            f'<span style="color:{color_for("shutter")}">1/{sh_val}</span>&nbsp;&nbsp;&nbsp;'
            f'<span style="color:{color_for("wb")}">WB {wb_val}</span>'
        )

        self.stepper_value.setText(task["format"](cur["value"]))
        self.minus_btn.setEnabled(opt_idx > 0)
        self.plus_btn.setEnabled(opt_idx < len(options) - 1)

        self.check_btn.setText("Check Adjustment" if cur["baseline"] else "Capture Baseline")
        self.retries_label.setText(f"Retries: {cur['retries']}")

        overlay = compute_overlay(task, cur["value"])
        self.preview.apply_overlay(overlay)

        if not cur["checked"]:
            self.banner.hide()
        elif cur["correct"]:
            self._set_banner_style("bannerCorrect")
            self.banner.setText(f"✓  {correct_message(task)}")
            self.banner.show()
        else:
            self._set_banner_style("bannerIncorrect")
            self.banner.setText(f"⚠  {incorrect_message(task, opt_idx, target_idx)}")
            self.banner.show()

        self.proceed_btn.setVisible(cur["checked"] and cur["correct"])

    def _set_banner_style(self, object_name: str):
        self.banner.setObjectName(object_name)
        style = self.banner.style()
        style.unpolish(self.banner)
        style.polish(self.banner)
