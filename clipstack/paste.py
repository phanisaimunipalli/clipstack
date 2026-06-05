import time

import pyperclip
from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventPost,
    CGEventSetFlags,
    kCGEventFlagMaskCommand,
    kCGHIDEventTap,
)

# Virtual keycode for the 'v' key on a US keyboard.
V_KEYCODE = 9


def paste_text(text: str) -> None:
    """Put text on the clipboard, then simulate Cmd+V into the focused app."""
    pyperclip.copy(text)
    # Small delay so the clipboard write settles before the paste event.
    time.sleep(0.05)
    _press_cmd_v()


def _press_cmd_v() -> None:
    key_down = CGEventCreateKeyboardEvent(None, V_KEYCODE, True)
    CGEventSetFlags(key_down, kCGEventFlagMaskCommand)
    CGEventPost(kCGHIDEventTap, key_down)

    key_up = CGEventCreateKeyboardEvent(None, V_KEYCODE, False)
    CGEventSetFlags(key_up, kCGEventFlagMaskCommand)
    CGEventPost(kCGHIDEventTap, key_up)
