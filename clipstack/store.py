import json
from pathlib import Path
from typing import Union


class Store:
    """In-memory clipboard history backed by a JSON file.

    Newest item is first. Adding an existing item moves it to the front.
    """

    def __init__(self, path: Union[str, Path], max_items: int):
        self.path = Path(path)
        self.max_items = max_items
        self._items = self._load()

    def _load(self) -> list:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
            return []
        except (json.JSONDecodeError, ValueError):
            return []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._items), encoding="utf-8")

    def add(self, text: str) -> None:
        if not text or not text.strip():
            return
        if text in self._items:
            self._items.remove(text)
        self._items.insert(0, text)
        del self._items[self.max_items:]
        self._save()

    def items(self) -> "list[str]":
        return list(self._items)
