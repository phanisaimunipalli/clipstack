import threading
import time

import pyperclip

from clipstack.appkit import frontmost_bundle_id

POLL_INTERVAL = 0.5


class Watcher:
    """Polls the clipboard on a background thread and records new text.

    Skips entries whose frontmost app bundle id is in excluded_apps.
    """

    def __init__(self, store, excluded_apps):
        self.store = store
        self.excluded_apps = set(excluded_apps)
        self._last_seen = self._read_clipboard()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _read_clipboard(self):
        try:
            return pyperclip.paste()
        except Exception:
            return None

    def _loop(self) -> None:
        while True:
            time.sleep(POLL_INTERVAL)
            text = self._read_clipboard()
            if text is None or text == self._last_seen:
                continue
            self._last_seen = text
            if frontmost_bundle_id() in self.excluded_apps:
                continue
            self.store.add(text)
