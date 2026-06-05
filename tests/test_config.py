import json
from pathlib import Path
from clipstack import config


def test_defaults_used_when_file_missing(tmp_path):
    cfg = config.load(tmp_path / "config.json")
    assert cfg["max_items"] == 50
    assert cfg["hotkey"] == "<cmd>+<shift>+v"
    assert "com.1password.1password" in cfg["excluded_apps"]


def test_default_file_is_written_when_missing(tmp_path):
    path = tmp_path / "config.json"
    config.load(path)
    assert path.exists()
    written = json.loads(path.read_text())
    assert written["max_items"] == 50


def test_user_values_override_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"max_items": 10}))
    cfg = config.load(path)
    assert cfg["max_items"] == 10
    # missing keys fall back to defaults
    assert cfg["hotkey"] == "<cmd>+<shift>+v"


def test_invalid_json_falls_back_to_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{ not valid json")
    cfg = config.load(path)
    assert cfg["max_items"] == 50
