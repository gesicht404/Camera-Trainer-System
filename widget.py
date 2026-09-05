# This Python file uses the following encoding: utf-8
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from data_store import DataStore
from screens.data_log_screen import DataLogScreen
from screens.grade_screen import GradeScreen
from screens.name_entry_screen import NameEntryScreen
from screens.start_screen import StartScreen
from screens.task_capture_screen import TaskCaptureScreen
from screens.task_info_screen import TaskInfoScreen
from tasks import TASKS, compute_grade, fresh_task_state

SCREEN_INDEX = {
    "start": 0,
    "taskInfo": 1,
    "taskCapture": 2,
    "nameEntry": 3,
    "grade": 4,
    "dataLog": 5,
}


class Widget(QWidget):
    """Kiosk shell: owns app state, TASKS flow, and QStackedWidget navigation."""

    def __init__(self, parent=None, data_store: DataStore | None = None):
        super().__init__(parent)

        self.data_store = data_store or DataStore()
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

        for screen in (
            self.start_screen,
            self.task_info_screen,
            self.task_capture_screen,
            self.name_entry_screen,
            self.grade_screen,
            self.data_log_screen,
        ):
            self.stacked.addWidget(screen)

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

    def back_to_start(self):
        self.state["screen"] = "start"
        self.render()

    def open_capture(self):
        self.state["screen"] = "taskCapture"
        self.render()

    def adjust_stepper(self, delta: int):
        idx = self.state["taskIdx"]
        task = TASKS[idx]
        cur = self.state["taskState"][idx]
        options = task["options"]
        opt_idx = options.index(cur["value"])
        next_idx = min(len(options) - 1, max(0, opt_idx + delta))
        self.state["taskState"][idx] = {
            **cur,
            "value": options[next_idx],
            "checked": False,
            "correct": False,
        }
        self.render()

    def capture_or_check(self):
        idx = self.state["taskIdx"]
        task = TASKS[idx]
        cur = self.state["taskState"][idx]
        if not cur["baseline"]:
            self.state["taskState"][idx] = {**cur, "baseline": True}
        else:
            correct = cur["value"] == task["target"]
            self.state["taskState"][idx] = {
                **cur,
                "checked": True,
                "correct": correct,
                "retries": cur["retries"] if correct else cur["retries"] + 1,
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
