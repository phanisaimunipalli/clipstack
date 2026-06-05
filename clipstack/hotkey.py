from pynput import keyboard


class HotkeyListener:
    """Global hotkey listener. Calls `on_trigger` when the hotkey fires.

    `hotkey` uses pynput's GlobalHotKeys format, e.g. "<cmd>+<shift>+v".
    The callback runs on pynput's listener thread, so callers that touch
    AppKit must marshal to the main thread themselves.
    """

    def __init__(self, hotkey: str, on_trigger):
        self._listener = keyboard.GlobalHotKeys({hotkey: on_trigger})

    def start(self) -> None:
        self._listener.start()
