from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from camera import CaptureResultPanel, PreviewPanel
from tasks import DEFAULTS, TASKS, correct_message, incorrect_message, uses_remote_capture

ACTIVE_COLOR = "#ffffff"
MUTED_COLOR = "#94a3b8"


class TaskCaptureScreen(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller

        root = QHBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(20)

        self.preview = PreviewPanel(self)
        root.addWidget(self.preview)

        self.result_panel = CaptureResultPanel(self)
        root.addWidget(self.result_panel)

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

        detected_box = QVBoxLayout()
        detected_box.setSpacing(6)
        self.camera_status = QLabel()
        self.camera_status.setStyleSheet("font-size:12px; font-weight:600;")
        detected_box.addWidget(self.camera_status)

        self.detected_value = QLabel()
        self.detected_value.setObjectName("detectedValue")
        self.detected_value.setAlignment(Qt.AlignCenter)
        detected_box.addWidget(self.detected_value)

        self.detected_hint = QLabel()
        self.detected_hint.setWordWrap(True)
        self.detected_hint.setStyleSheet("font-size:12px; color:#94a3b8;")
        detected_box.addWidget(self.detected_hint)
        controls.addLayout(detected_box)

        check_row = QHBoxLayout()
        self.back_btn = QPushButton("Back")
        self.back_btn.setObjectName("outline")
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self.controller.go_back)
        check_row.addWidget(self.back_btn)

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

        is_iso = uses_remote_capture(task["id"])
        self.preview.setVisible(not is_iso)
        self.result_panel.setVisible(is_iso)
        if is_iso and not cur["baseline"]:
            self.result_panel.show_idle()
        # once a baseline exists, leave whatever the controller already pushed into the
        # panel showing (the most recent shutter-press photo) rather than resetting it here.

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

        if self.controller.camera_session.hardware_available:
            self.camera_status.setText("● Camera connected")
            self.camera_status.setStyleSheet("font-size:12px; font-weight:600; color:#15803d;")
            self.detected_value.setText(task["format"](cur["value"]))
            self.detected_hint.setText("Turn the camera's dial to change this setting.")
        else:
            self.camera_status.setText("● No camera detected")
            self.camera_status.setStyleSheet("font-size:12px; font-weight:600; color:#b91c1c;")
            self.detected_value.setText("—")
            self.detected_hint.setText("Connect the Nikon D3500 (gPhoto2) to detect its live settings.")

        self.check_btn.setVisible(not is_iso)
        self.check_btn.setText("Check Adjustment" if cur["baseline"] else "Capture Baseline")
        self.retries_label.setText(f"Retries: {cur['retries']}")

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
