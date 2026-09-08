import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data_store import DataStore, SEED_STUDENTS


def test_seeds_on_first_load(tmp_path):
    store = DataStore(tmp_path / "data_log.db")
    assert len(store.students) == len(SEED_STUDENTS)
    assert (tmp_path / "data_log.db").exists()


def test_add_record_persists(tmp_path):
    path = tmp_path / "data_log.db"
    store = DataStore(path)
    record = {
        "name": "Ana Reyes",
        "section": "BSET-3C",
        "grade": "B",
        "totalRetries": 10,
        "tasks": [{"label": "ISO", "retries": 3, "feedback": "Good brightness and clear image."}],
    }
    store.add_record(record)

    assert store.students[-1] == record

    reloaded = DataStore(path)
    assert reloaded.students[-1] == record
    assert len(reloaded.students) == len(SEED_STUDENTS) + 1


def test_reopening_does_not_reseed(tmp_path):
    path = tmp_path / "data_log.db"
    DataStore(path)
    second = DataStore(path)
    assert len(second.students) == len(SEED_STUDENTS)


def test_students_ordered_by_insertion(tmp_path):
    path = tmp_path / "data_log.db"
    store = DataStore(path)
    for i in range(3):
        store.add_record(
            {"name": f"Student {i}", "section": "X", "grade": "A", "totalRetries": 0, "tasks": []}
        )
    names = [s["name"] for s in store.students]
    assert names == ["Juan Dela Cruz", "Maria Santos", "Student 0", "Student 1", "Student 2"]
