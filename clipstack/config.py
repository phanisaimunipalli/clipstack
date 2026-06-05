import json
import logging
from pathlib import Path

logger = logging.getLogger("clipstack")

DEFAULTS = {
    "max_items": 50,
    "hotkey": "<cmd>+<shift>+v",
    "excluded_apps": [
        "com.1password.1password",
        "com.agilebits.onepassword7",
    ],
}


def load(path: Path) -> dict:
    """Load config, with user values overriding defaults key by key.

    Top-level keys present in the file replace the corresponding default
    (e.g. a user ``excluded_apps`` list replaces the default list rather
    than merging into it); missing keys fall back to defaults. Writes a
    default file if none exists. Falls back to defaults on invalid JSON.
    """
    path = Path(path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(DEFAULTS, indent=2), encoding="utf-8")
        return dict(DEFAULTS)

    try:
        user = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        logger.warning("Invalid config at %s; using defaults", path)
        return dict(DEFAULTS)

    merged = dict(DEFAULTS)
    merged.update(user)
    return merged
