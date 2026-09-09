import logging

from PySide6.QtCore import QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from camera import CameraSession, CaptureWorker, frame_to_qpixmap
from data_store import DataStore
from screens.data_log_screen import DataLogScreen
from screens.grade_screen import GradeScreen
from screens.name_entry_screen import NameEntryScreen
from screens.scenario_screen import ScenarioScreen
from screens.start_screen import StartScreen
from screens.task_capture_screen import TaskCaptureScreen
from screens.task_info_screen import TaskInfoScreen
from tasks import TASKS, compute_grade, fresh_task_state, uses_remote_capture

logger = logging.getLogger(__name__)

CAMERA_POLL_INTERVAL_MS = 400
CAPTURE_SHUTDOWN_TIMEOUT_MS = 5000

SCREEN_INDEX = {
    "start": 0,
    "taskInfo": 1,
    "taskCapture": 2,
    "nameEntry": 3,
    "grade": 4,
    "dataLog": 5,
    "scenario": 6,
}


class Widget(QWidget):
    def __init__(self, parent=None, data_store: DataStore | None = None, camera_session: CameraSession | None = None):
        super().__init__(parent)

        self.data_store = data_store or DataStore()

        self.camera_session = camera_session or CameraSession()
        self.camera_session.connect()
        self._capture_worker = None
        self._live_preview_task_id = None

        self.state = {
            "screen": "start",
            "taskIdx": 0,
            "taskState": fresh_task_state(),
            "name": "",
            "section": "",
            "nameError": False,
            "students": self.data_store.students,
            "currentRecord": None,
            "gradeSource": "session",
        }

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.stacked = QStackedWidget(self)
        layout.addWidget(self.stacked)

        self.start_screen = StartScreen(self)
        self.task_info_screen = TaskInfoScreen(self)
        self.task_capture_screen = TaskCaptureScreen(self)
        self.name_entry_screen = NameEntryScreen(self)
        self.grade_screen = GradeScreen(self)
        self.data_log_screen = DataLogScreen(self)
        self.scenario_screen = ScenarioScreen(self)

        for screen in (
            self.start_screen,
            self.task_info_screen,
            self.task_capture_screen,
            self.name_entry_screen,
            self.grade_screen,
            self.data_log_screen,
            self.scenario_screen,
        ):
            self.stacked.addWidget(screen)

        self._camera_timer = QTimer(self)
        self._camera_timer.timeout.connect(self._poll_camera)
        self._camera_timer.start(CAMERA_POLL_INTERVAL_MS)

        self.render()

    def closeEvent(self, event):
        self._camera_timer.stop()
        if self._capture_worker is not None and not self._capture_worker.wait(CAPTURE_SHUTDOWN_TIMEOUT_MS):
            logger.warning(
                "Capture worker did not finish within %dms of app close; closing anyway.",
                CAPTURE_SHUTDOWN_TIMEOUT_MS,
            )
        self.camera_session.close()
        self.data_store.close()
        super().closeEvent(event)

    def _poll_camera(self):
        if self.state["screen"] != "taskCapture":
            return
        if self._capture_worker is not None:
            return

        idx = self.state["taskIdx"]
        task = TASKS[idx]

        if not uses_remote_capture(task["id"]):
            physical_frame = None
            if self.camera_session.hardware_available:
                physical_frame = self.camera_session.poll_physical_capture(task["id"])

            frame = physical_frame if physical_frame is not None else self.camera_session.read_frame()
            if frame is not None:
                self.task_capture_screen.preview.set_frame(frame_to_qpixmap(frame))

        if not self.camera_session.hardware_available:
            return

        live_value = self.camera_session.read_current_value(task["id"])
        cur = self.state["taskState"][idx]
        if live_value is not None and live_value != cur["value"]:
            self.state["taskState"][idx] = {
                **cur,
                "value": live_value,
                "checked": False,
                "correct": False,
            }
            self.render()

    def go_start(self):
        self.state.update(
            screen="start",
            taskIdx=0,
            taskState=fresh_task_state(),
            name="",
            section="",
            nameError=False,
            currentRecord=None,
        )
        self.name_entry_screen.reset_fields()
        self.render()

    def start_flow(self):
        self.state.update(
            screen="taskInfo",
            taskIdx=0,
            taskState=fresh_task_state(),
            name="",
            section="",
            nameError=False,
            currentRecord=None,
        )
        self.name_entry_screen.reset_fields()
        self.render()

    def open_data_log(self):
        self.state["screen"] = "dataLog"
        self.render()

    def open_scenario(self):
        self.state["screen"] = "scenario"
        self.render()

    def quit_app(self):
        self.window().close()

    def back_to_start(self):
        self.state["screen"] = "start"
        self.render()

    def open_capture(self):
        self.state["screen"] = "taskCapture"
        self.render()

    def _update_live_preview_for_active_task(self):
        task_id = TASKS[self.state["taskIdx"]]["id"]
        if task_id == self._live_preview_task_id:
            return
        self._live_preview_task_id = task_id
        self.camera_session.set_live_preview_enabled(not uses_remote_capture(task_id))

    def go_back(self):
        screen = self.state["screen"]
        if screen == "taskCapture":
            self.state["screen"] = "taskInfo"
        elif screen == "taskInfo":
            if self.state["taskIdx"] > 0:
                self.state["taskIdx"] -= 1
                self.state["screen"] = "taskCapture"
            else:
                self.state["screen"] = "start"
        self.render()

    def capture_or_check(self):
        idx = self.state["taskIdx"]
        task = TASKS[idx]
        if uses_remote_capture(task["id"]):
            self._start_iso_capture()
            return

        cur = self.state["taskState"][idx]
        if not cur["baseline"]:
            self.camera_session.capture_baseline(task["id"])
            self.state["taskState"][idx] = {**cur, "baseline": True}
        else:
            trend = self.camera_session.frame_trend(task["id"])
            correct = cur["value"] == task["target"]
            self.state["taskState"][idx] = {
                **cur,
                "checked": True,
                "correct": correct,
                "retries": cur["retries"] if correct else cur["retries"] + 1,
                "trend": trend,
            }
        self.render()

    def _start_iso_capture(self):
        if self._capture_worker is not None:
            return

        idx = self.state["taskIdx"]
        task = TASKS[idx]
        cur = self.state["taskState"][idx]
        mode = "check" if cur["baseline"] else "baseline"

        self.state["taskState"][idx] = {**cur, "captureStatus": "capturing", "captureError": None}
        self.render()

        worker = CaptureWorker(self.camera_session, task["id"], mode)
        worker.task_idx = idx
        worker.succeeded.connect(self._on_iso_capture_succeeded)
        worker.failed.connect(self._on_iso_capture_failed)
        worker.finished.connect(self._on_iso_capture_finished)
        self._capture_worker = worker
        worker.start()

    def _on_iso_capture_succeeded(self, image, trend):
        worker = self.sender()
        idx = worker.task_idx
        task = TASKS[idx]
        cur = self.state["taskState"][idx]
        if worker.mode == "baseline":
            updated = {**cur, "baseline": True, "captureStatus": "success", "captureError": None}
        else:
            correct = cur["value"] == task["target"]
            updated = {
                **cur,
                "checked": True,
                "correct": correct,
                "retries": cur["retries"] if correct else cur["retries"] + 1,
                "trend": trend,
                "captureStatus": "success",
                "captureError": None,
            }
        self.state["taskState"][idx] = updated
        self.task_capture_screen.result_panel.show_result(QPixmap.fromImage(image))
        self.render()

    def _on_iso_capture_failed(self, message):
        worker = self.sender()
        idx = worker.task_idx
        cur = self.state["taskState"][idx]
        self.state["taskState"][idx] = {**cur, "captureStatus": "error", "captureError": message}
        self.render()

    def _on_iso_capture_finished(self):
        worker = self._capture_worker
        self._capture_worker = None
        if worker is not None:
            worker.deleteLater()

    def proceed(self):
        if self.state["taskIdx"] < len(TASKS) - 1:
            self.state["taskIdx"] += 1
            self.state["screen"] = "taskInfo"
        else:
            self.state["screen"] = "nameEntry"
        self.render()

    def set_name(self, value: str):
        self.state["name"] = value
        self.state["nameError"] = False

    def set_section(self, value: str):
        self.state["section"] = value

    def submit_name(self):
        name = self.state["name"].strip()
        if not name:
            self.state["nameError"] = True
            self.render()
            return

        total_retries = sum(t["retries"] for t in self.state["taskState"])
        grade = compute_grade(total_retries)
        record = {
            "name": name,
            "section": self.state["section"].strip(),
            "grade": grade,
            "totalRetries": total_retries,
            "tasks": [
                {"label": t["label"], "retries": ts["retries"], "feedback": t["final_feedback"]}
                for t, ts in zip(TASKS, self.state["taskState"])
            ],
        }
        self.data_store.add_record(record)
        self.state["students"] = self.data_store.students
        self.state["currentRecord"] = record
        self.state["gradeSource"] = "session"
        self.state["screen"] = "grade"
        self.render()

    def grade_action(self):
        if self.state["gradeSource"] == "session":
            self.go_start()
        else:
            self.state["screen"] = "dataLog"
            self.render()

    def open_student(self, index: int):
        self.state["currentRecord"] = self.state["students"][index]
        self.state["gradeSource"] = "log"
        self.state["screen"] = "grade"
        self.render()

    def render(self):
        screen = self.state["screen"]
        self.stacked.setCurrentIndex(SCREEN_INDEX[screen])

        if screen == "taskInfo":
            self.task_info_screen.refresh()
        elif screen == "taskCapture":
            self._update_live_preview_for_active_task()
            self.task_capture_screen.refresh()
        elif screen == "nameEntry":
            self.name_entry_screen.refresh()
        elif screen == "grade":
            self.grade_screen.refresh()
        elif screen == "dataLog":
            self.data_log_screen.refresh()
