# This Python file uses the following encoding: utf-8
import os

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from camera import CameraSession, frame_to_qpixmap
from data_store import DataStore
from screens.data_log_screen import DataLogScreen
from screens.grade_screen import GradeScreen
from screens.name_entry_screen import NameEntryScreen
from screens.scenario_screen import ScenarioScreen
from screens.start_screen import StartScreen
from screens.task_capture_screen import TaskCaptureScreen
from screens.task_info_screen import TaskInfoScreen
from tasks import TASKS, compute_grade, fresh_task_state

CAMERA_POLL_INTERVAL_MS = 400

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
    """Kiosk shell: owns app state, TASKS flow, and QStackedWidget navigation."""

    def __init__(self, parent=None, data_store: DataStore | None = None, camera_session: CameraSession | None = None):
        super().__init__(parent)

        self.data_store = data_store or DataStore()

        # Real hardware integration (Ch. 3.6.3 of the proposal): gPhoto2 reads the
        # Nikon D3500's live settings over USB, OpenCV analyzes the HDMI capture
        # card's video feed. There is no on-screen simulation of these values -
        # the trainee turns the physical camera dial and the system detects it.
        # The HDMI capture card's video device index varies by Pi (e.g. /dev/video1
        # instead of /dev/video0 if another video device is present) — override with
        # the CAMERA_VIDEO_INDEX env var rather than editing code.
        video_index = int(os.environ.get("CAMERA_VIDEO_INDEX", "0"))
        self.camera_session = camera_session or CameraSession(video_index=video_index)
        self.camera_session.connect()

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
        self.camera_session.close()
        self.data_store.close()
        super().closeEvent(event)

    def _poll_camera(self):
        """Live hardware polling while on the Task Capture screen: feeds real
        frames into the (unchanged) preview widget and keeps the on-screen
        readout tracking the physical camera dial, per Ch. 3.6.3 of the proposal."""
        if self.state["screen"] != "taskCapture":
            return

        frame = self.camera_session.read_frame()
        if frame is not None:
            self.task_capture_screen.preview.set_frame(frame_to_qpixmap(frame))

        if not self.camera_session.hardware_available:
            return

        idx = self.state["taskIdx"]
        task = TASKS[idx]
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

    # -- navigation / state transitions (mirrors the approved design's Component logic) --

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

    def back_to_start(self):
        self.state["screen"] = "start"
        self.render()

    def open_capture(self):
        self.state["screen"] = "taskCapture"
        self.render()

    def go_back(self):
        """Steps back one screen within the task flow without touching taskState -
        every task's captured retries/values/checked status is preserved."""
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
        cur = self.state["taskState"][idx]
        if not cur["baseline"]:
            self.camera_session.capture_baseline(task["id"])
            self.state["taskState"][idx] = {**cur, "baseline": True}
        else:
            # Per Ch. 3.6.3: the system compares both the setting direction (checked
            # against the target above) and the resulting image effect. The measured
            # visual trend is recorded for internal fidelity even though correctness
            # itself is still whether the live-detected setting hit the target.
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

    # -- rendering --

    def render(self):
        screen = self.state["screen"]
        self.stacked.setCurrentIndex(SCREEN_INDEX[screen])

        if screen == "taskInfo":
            self.task_info_screen.refresh()
        elif screen == "taskCapture":
            self.task_capture_screen.refresh()
        elif screen == "nameEntry":
            self.name_entry_screen.refresh()
        elif screen == "grade":
            self.grade_screen.refresh()
        elif screen == "dataLog":
            self.data_log_screen.refresh()
