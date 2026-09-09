import json
import sqlite3
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent / "data_log.db"

SEED_STUDENTS = [
    {
        "name": "Juan Dela Cruz",
        "section": "BSET-3A",
        "grade": "A",
        "totalRetries": 5,
        "tasks": [
            {"label": "ISO", "retries": 2, "feedback": "Good brightness and clear image."},
            {"label": "Aperture", "retries": 1, "feedback": "Image is clear with good background."},
            {"label": "Shutter Speed", "retries": 1, "feedback": "Image is sharp and clear."},
            {"label": "White Balance", "retries": 1, "feedback": "Colors look natural."},
        ],
    },
    {
        "name": "Maria Santos",
        "section": "BSET-3B",
        "grade": "C",
        "totalRetries": 23,
        "tasks": [
            {"label": "ISO", "retries": 8, "feedback": "Good brightness and clear image."},
            {"label": "Aperture", "retries": 3, "feedback": "Image is clear with good background."},
            {"label": "Shutter Speed", "retries": 9, "feedback": "Image is sharp and clear."},
            {"label": "White Balance", "retries": 3, "feedback": "Colors look natural."},
        ],
    },
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    section TEXT NOT NULL,
    grade TEXT NOT NULL,
    total_retries INTEGER NOT NULL,
    tasks_json TEXT NOT NULL
);
"""


class DataStore:
    def __init__(self, path: Path = DEFAULT_PATH):
        self.path = Path(path)
        is_new = not self.path.exists()
        self._conn = sqlite3.connect(self.path)
        self._conn.execute(_SCHEMA)
        self._conn.commit()
        if is_new:
            for student in SEED_STUDENTS:
                self._insert(student)
        self.students = self._load_all()

    def _row_to_record(self, row) -> dict:
        _id, name, section, grade, total_retries, tasks_json = row
        return {
            "name": name,
            "section": section,
            "grade": grade,
            "totalRetries": total_retries,
            "tasks": json.loads(tasks_json),
        }

    def _load_all(self):
        cursor = self._conn.execute(
            "SELECT id, name, section, grade, total_retries, tasks_json FROM students ORDER BY id"
        )
        return [self._row_to_record(row) for row in cursor.fetchall()]

    def _insert(self, record: dict):
        self._conn.execute(
            "INSERT INTO students (name, section, grade, total_retries, tasks_json) VALUES (?, ?, ?, ?, ?)",
            (
                record["name"],
                record["section"],
                record["grade"],
                record["totalRetries"],
                json.dumps(record["tasks"]),
            ),
        )
        self._conn.commit()

    def add_record(self, record: dict):
        self._insert(record)
        self.students.append(record)

    def close(self):
        self._conn.close()
