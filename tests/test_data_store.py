import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data_store import DataStore, SEED_STUDENTS


def test_seeds_on_first_load(tmp_path):
    store = DataStore(tmp_path / "data_log.json")
    assert len(store.students) == len(SEED_STUDENTS)
    assert (tmp_path / "data_log.json").exists()


def test_add_record_persists(tmp_path):
    path = tmp_path / "data_log.json"
    store = DataStore(path)
    record = {"name": "Ana Reyes", "section": "BSET-3C", "grade": "B", "totalRetries": 10, "tasks": []}
    store.add_record(record)

    reloaded = DataStore(path)
    assert reloaded.students[-1] == record
    assert len(reloaded.students) == len(SEED_STUDENTS) + 1
