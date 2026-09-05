"""JSON-backed persistence for completed training session records."""

import json
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent / "data_log.json"

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


class DataStore:
    """Loads/persists student session records to a JSON file next to the app."""

    def __init__(self, path: Path = DEFAULT_PATH):
        self.path = Path(path)
        self.students = self._load()

    def _load(self):
        if not self.path.exists():
            self._write(SEED_STUDENTS)
            return [dict(s) for s in SEED_STUDENTS]
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, students):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(students, f, indent=2)

    def add_record(self, record: dict):
        self.students.append(record)
        self._write(self.students)
