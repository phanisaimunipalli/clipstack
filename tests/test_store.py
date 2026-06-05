import json
from clipstack.store import Store


def test_add_prepends_newest_first(tmp_path):
    s = Store(tmp_path / "history.json", max_items=50)
    s.add("first")
    s.add("second")
    assert s.items() == ["second", "first"]


def test_add_trims_to_max_items(tmp_path):
    s = Store(tmp_path / "history.json", max_items=2)
    s.add("a")
    s.add("b")
    s.add("c")
    assert s.items() == ["c", "b"]


def test_duplicate_moves_to_front_without_growing(tmp_path):
    s = Store(tmp_path / "history.json", max_items=50)
    s.add("a")
    s.add("b")
    s.add("a")
    assert s.items() == ["a", "b"]


def test_add_persists_to_disk(tmp_path):
    path = tmp_path / "history.json"
    s = Store(path, max_items=50)
    s.add("hello")
    assert json.loads(path.read_text()) == ["hello"]


def test_loads_existing_history_on_init(tmp_path):
    path = tmp_path / "history.json"
    path.write_text(json.dumps(["x", "y"]))
    s = Store(path, max_items=50)
    assert s.items() == ["x", "y"]


def test_corrupt_history_resets_to_empty(tmp_path):
    path = tmp_path / "history.json"
    path.write_text("{ not valid json")
    s = Store(path, max_items=50)
    assert s.items() == []


def test_blank_text_is_ignored(tmp_path):
    s = Store(tmp_path / "history.json", max_items=50)
    s.add("   ")
    s.add("")
    assert s.items() == []
