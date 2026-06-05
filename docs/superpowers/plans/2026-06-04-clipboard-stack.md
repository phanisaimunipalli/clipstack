# Clipboard Stack (clipstack) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a lightweight open source macOS clipboard history manager that lives in the menu bar, opens via a global hotkey, and pastes the selected item immediately.

**Architecture:** A single Python process runs as a PyObjC accessory app (no Dock icon) with three concerns: a background clipboard watcher (polls every 0.5s), a native `NSStatusItem` + `NSMenu` menu bar UI (rebuilds from history each time it opens, pastes on click), and a `pynput` global hotkey listener that genuinely opens the menu via `statusItem.button().performClick_()`. History and config persist as JSON under `~/.clipstack/`. Installation is one command: clone the public repo and run `./install.sh`, which pip-installs deps and registers a Launch Agent.

**Tech Stack:** Python 3, pyobjc (AppKit for the status item/menu, Quartz for paste simulation, AppKit for frontmost-app detection), pynput (hotkey), pyperclip (clipboard), pytest (tests).

---

## File Structure

```
clipstack/
├── install.sh                  # pip install + Launch Agent setup + launchctl load
├── uninstall.sh                # reverses install.sh cleanly
├── requirements.txt            # pynput, pyperclip, pyobjc (Cocoa + Quartz), pytest
├── README.md                   # setup + usage for the public repo
├── .gitignore
├── clipstack/
│   ├── __init__.py
│   ├── config.py               # loads ~/.clipstack/config.json with defaults
│   ├── store.py                # history list + read/write to history.json
│   ├── appkit.py               # frontmost-app bundle ID lookup (AppKit)
│   ├── paste.py                # write to clipboard + simulate Cmd+V (Quartz)
│   ├── watcher.py              # clipboard polling loop (background thread)
│   ├── hotkey.py               # global hotkey listener (background thread)
│   ├── menubar.py              # NSStatusItem + NSMenu, rebuild-on-open, open()
│   └── app.py                  # entry point: NSApplication run loop + wiring
├── assets/
│   └── icon.png                # 16x16 menu bar template image
├── tests/
│   ├── test_config.py
│   └── test_store.py
└── com.clipstack.plist         # Launch Agent template (KeepAlive=true)
```

**Responsibility split:**
- `config.py` and `store.py` are pure, OS-independent, and fully unit-tested.
- `appkit.py` and `paste.py` isolate single pyobjc OS calls behind small functions.
- `menubar.py` owns all AppKit status-item/menu code in one place.
- `watcher.py`, `hotkey.py`, and `app.py` wire things together. Validated by manual smoke test, not unit tests.

---

## Task 1: Project scaffolding

**Files:**
- Create: `clipstack/.gitignore`
- Create: `clipstack/requirements.txt`
- Create: `clipstack/clipstack/__init__.py`

- [ ] **Step 1: Create `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
.venv/
venv/
*.log
.DS_Store
.superpowers/
```

- [ ] **Step 2: Create `requirements.txt`**

```
pynput==1.7.7
pyperclip==1.9.0
pyobjc-framework-Cocoa==10.3.1
pyobjc-framework-Quartz==10.3.1
pytest==8.3.3
```

- [ ] **Step 3: Create empty package marker `clipstack/clipstack/__init__.py`**

```python
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore requirements.txt clipstack/__init__.py
git commit -m "chore: project scaffolding and dependencies"
```

---

## Task 2: Config module

**Files:**
- Create: `clipstack/clipstack/config.py`
- Test: `clipstack/tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd clipstack && python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError` or `AttributeError: module 'clipstack.config' has no attribute 'load'`

- [ ] **Step 3: Write minimal implementation**

```python
# clipstack/config.py
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
    """Load config, merging user values over defaults.

    Writes a default file if none exists. Falls back to defaults on
    invalid JSON.
    """
    path = Path(path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(DEFAULTS, indent=2))
        return dict(DEFAULTS)

    try:
        user = json.loads(path.read_text())
    except (json.JSONDecodeError, ValueError):
        logger.warning("Invalid config at %s; using defaults", path)
        return dict(DEFAULTS)

    merged = dict(DEFAULTS)
    merged.update(user)
    return merged
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd clipstack && python -m pytest tests/test_config.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add clipstack/config.py tests/test_config.py
git commit -m "feat: config module with defaults and fallback"
```

---

## Task 3: Store module

**Files:**
- Create: `clipstack/clipstack/store.py`
- Test: `clipstack/tests/test_store.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_store.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd clipstack && python -m pytest tests/test_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'clipstack.store'`

- [ ] **Step 3: Write minimal implementation**

```python
# clipstack/store.py
import json
from pathlib import Path


class Store:
    """In-memory clipboard history backed by a JSON file.

    Newest item is first. Adding an existing item moves it to the front.
    """

    def __init__(self, path, max_items: int):
        self.path = Path(path)
        self.max_items = max_items
        self._items = self._load()

    def _load(self) -> list:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text())
            if isinstance(data, list):
                return data
            return []
        except (json.JSONDecodeError, ValueError):
            return []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._items))

    def add(self, text: str) -> None:
        if not text or not text.strip():
            return
        if text in self._items:
            self._items.remove(text)
        self._items.insert(0, text)
        del self._items[self.max_items:]
        self._save()

    def items(self) -> list:
        return list(self._items)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd clipstack && python -m pytest tests/test_store.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add clipstack/store.py tests/test_store.py
git commit -m "feat: store module with history persistence and dedup"
```

---

## Task 4: AppKit helper (frontmost app detection)

**Files:**
- Create: `clipstack/clipstack/appkit.py`

This module isolates a pyobjc OS call. It is not unit-tested (no useful way to mock the frontmost app); it is validated during the Task 9 smoke test.

- [ ] **Step 1: Write the implementation**

```python
# clipstack/appkit.py
from AppKit import NSWorkspace


def frontmost_bundle_id():
    """Return the bundle identifier of the frontmost application, or None."""
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    if app is None:
        return None
    return app.bundleIdentifier()
```

- [ ] **Step 2: Verify it imports (requires deps installed)**

Run: `cd clipstack && python -c "from clipstack.appkit import frontmost_bundle_id; print(frontmost_bundle_id())"`
Expected: prints a bundle ID string like `com.apple.Terminal` (or `None`). If `ModuleNotFoundError: No module named 'AppKit'`, run `pip3 install -r requirements.txt` first.

- [ ] **Step 3: Commit**

```bash
git add clipstack/appkit.py
git commit -m "feat: frontmost app bundle id lookup"
```

---

## Task 5: Paste helper (clipboard write + Cmd+V simulation)

**Files:**
- Create: `clipstack/clipstack/paste.py`

This module isolates pyperclip + Quartz OS calls. Not unit-tested; validated during the Task 9 smoke test.

- [ ] **Step 1: Write the implementation**

```python
# clipstack/paste.py
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
```

- [ ] **Step 2: Verify it imports**

Run: `cd clipstack && python -c "from clipstack.paste import paste_text; print('ok')"`
Expected: prints `ok`. (Do not call `paste_text` here — it would fire a real paste.)

- [ ] **Step 3: Commit**

```bash
git add clipstack/paste.py
git commit -m "feat: paste helper with clipboard write and Cmd+V simulation"
```

---

## Task 6: Clipboard watcher

**Files:**
- Create: `clipstack/clipstack/watcher.py`

The watcher runs a polling loop on a background thread. It is not unit-tested; validated during the Task 9 smoke test.

- [ ] **Step 1: Write the implementation**

```python
# clipstack/clipstack/watcher.py
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
```

- [ ] **Step 2: Verify it imports**

Run: `cd clipstack && python -c "from clipstack.watcher import Watcher; print('ok')"`
Expected: prints `ok`

- [ ] **Step 3: Commit**

```bash
git add clipstack/watcher.py
git commit -m "feat: clipboard watcher with excluded-app filtering"
```

---

## Task 7: Hotkey listener

**Files:**
- Create: `clipstack/clipstack/hotkey.py`

Listens for the configured global hotkey on a background thread via pynput. On trigger, runs a callback. The callback is responsible for marshalling any UI work to the main thread (done in `app.py` via `AppHelper.callAfter`). Not unit-tested; validated during the Task 9 smoke test.

- [ ] **Step 1: Write the implementation**

```python
# clipstack/clipstack/hotkey.py
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
```

- [ ] **Step 2: Verify it imports**

Run: `cd clipstack && python -c "from clipstack.hotkey import HotkeyListener; print('ok')"`
Expected: prints `ok`

- [ ] **Step 3: Commit**

```bash
git add clipstack/hotkey.py
git commit -m "feat: global hotkey listener"
```

---

## Task 8: Menu bar UI (NSStatusItem + NSMenu)

**Files:**
- Create: `clipstack/clipstack/menubar.py`
- Create: `clipstack/assets/icon.png`

This module owns all status-item and menu code. The menu is rebuilt from the
store every time it opens (via `NSMenuDelegate.menuNeedsUpdate_`), so the list
is always current without a polling timer. `open()` programmatically clicks the
status button so the hotkey can pop the menu. Not unit-tested; validated during
the Task 9 smoke test.

- [ ] **Step 1: Create a placeholder menu bar icon**

Run this to generate a simple 16x16 black template PNG (used as a template image so macOS tints it for light/dark menu bars):

```bash
cd clipstack && python3 -c "
from PIL import Image
img = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
for x in range(2, 14):
    for y in range(3, 13):
        if x in (2, 13) or y in (3, 12):
            img.putpixel((x, y), (0, 0, 0, 255))
img.save('assets/icon.png')
print('icon written')
"
```

If PIL is not installed, skip the icon: `menubar.py` falls back to a text title (handled in Step 2 — the icon is only set if the file exists). Do not block on the icon.

- [ ] **Step 2: Write the implementation**

```python
# clipstack/clipstack/menubar.py
from pathlib import Path

from AppKit import (
    NSApplication,
    NSImage,
    NSMenu,
    NSMenuItem,
    NSStatusBar,
    NSVariableStatusItemLength,
)
from Foundation import NSObject
from PyObjCTools.AppHelper import callAfter

from clipstack.paste import paste_text

ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "icon.png"
MENU_LABEL_MAX = 40


class MenuBar(NSObject):
    """Owns the NSStatusItem and its NSMenu.

    Construct with MenuBar.create(store). pyobjc subclasses of NSObject
    must not define __init__; use the create() factory plus _setup().
    """

    @classmethod
    def create(cls, store):
        self = cls.alloc().init()
        self._store = store
        self._build_status_item()
        return self

    def _build_status_item(self):
        bar = NSStatusBar.systemStatusBar()
        self._status_item = bar.statusItemWithLength_(NSVariableStatusItemLength)
        button = self._status_item.button()
        if ICON_PATH.exists():
            image = NSImage.alloc().initWithContentsOfFile_(str(ICON_PATH))
            image.setTemplate_(True)
            button.setImage_(image)
        else:
            button.setTitle_("CLIP")

        menu = NSMenu.alloc().init()
        menu.setDelegate_(self)
        self._status_item.setMenu_(menu)
        self._menu = menu

    # NSMenuDelegate: rebuild items from the store right before display.
    def menuNeedsUpdate_(self, menu):
        menu.removeAllItems()
        items = self._store.items()
        if not items:
            empty = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "(empty)", None, ""
            )
            empty.setEnabled_(False)
            menu.addItem_(empty)
        else:
            for index, text in enumerate(items):
                item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                    self._label_for(text), b"clipSelected:", ""
                )
                item.setTarget_(self)
                item.setTag_(index)
                menu.addItem_(item)
        menu.addItem_(NSMenuItem.separatorItem())
        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit ClipStack", b"terminate:", "q"
        )
        quit_item.setTarget_(NSApplication.sharedApplication())
        menu.addItem_(quit_item)

    def _label_for(self, text):
        label = " ".join(text.split())
        if len(label) > MENU_LABEL_MAX:
            label = label[:MENU_LABEL_MAX] + "…"
        return label

    # Action fired when a history item is clicked.
    def clipSelected_(self, sender):
        items = self._store.items()
        index = sender.tag()
        if 0 <= index < len(items):
            paste_text(items[index])

    def open(self):
        """Open the menu programmatically (called from the hotkey)."""
        callAfter(self._perform_click)

    def _perform_click(self):
        self._status_item.button().performClick_(None)
```

- [ ] **Step 3: Verify it imports**

Run: `cd clipstack && python -c "from clipstack.menubar import MenuBar; print('ok')"`
Expected: prints `ok`. If `ModuleNotFoundError: No module named 'AppKit'`, run `pip3 install -r requirements.txt` first.

- [ ] **Step 4: Commit**

```bash
git add clipstack/menubar.py assets/icon.png
git commit -m "feat: native NSStatusItem menu with rebuild-on-open and paste"
```

---

## Task 9: App entry point (wiring + run loop)

**Files:**
- Create: `clipstack/clipstack/app.py`

`app.py` sets the app to accessory mode (no Dock icon), wires config, store,
watcher, hotkey, and the menu bar together, and runs the AppKit event loop.

- [ ] **Step 1: Write the implementation**

```python
# clipstack/clipstack/app.py
from pathlib import Path

from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
)
from PyObjCTools import AppHelper

from clipstack import config
from clipstack.store import Store
from clipstack.watcher import Watcher
from clipstack.hotkey import HotkeyListener
from clipstack.menubar import MenuBar

HOME = Path.home()
CONFIG_PATH = HOME / ".clipstack" / "config.json"
HISTORY_PATH = HOME / ".clipstack" / "history.json"


def main():
    cfg = config.load(CONFIG_PATH)
    store = Store(HISTORY_PATH, max_items=cfg["max_items"])

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    menubar = MenuBar.create(store)

    watcher = Watcher(store, cfg["excluded_apps"])
    watcher.start()

    hotkey = HotkeyListener(cfg["hotkey"], menubar.open)
    hotkey.start()

    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test the whole app manually**

Run: `cd clipstack && pip3 install -r requirements.txt && python -m clipstack.app`

Expected behavior:
1. A menu bar icon (or `CLIP` text) appears. No Dock icon.
2. Copy some text in another app (`⌘C`). Open the menu from the icon → the new item is at the top.
3. Click a menu item → it pastes into the focused app.
4. Press the hotkey (`⌘⇧V`) → the menu pops open without clicking the icon.
5. Copy text while a password manager (a bundle id in `excluded_apps`) is frontmost → it does NOT appear.
6. Quit via the menu's "Quit ClipStack".

macOS will prompt for **Accessibility** and **Input Monitoring** permissions on first run (needed for hotkey + paste simulation). Grant them in System Settings → Privacy & Security, then relaunch.

- [ ] **Step 3: Commit**

```bash
git add clipstack/app.py
git commit -m "feat: app entry point wiring accessory app, watcher, hotkey, menu"
```

---

## Task 10: Launch Agent + install/uninstall scripts

**Files:**
- Create: `clipstack/com.clipstack.plist`
- Create: `clipstack/install.sh`
- Create: `clipstack/uninstall.sh`

- [ ] **Step 1: Create the Launch Agent template**

`__CLIPSTACK_DIR__`, `__PYTHON__`, and `__HOME__` are placeholders that `install.sh` substitutes.

```xml
<!-- com.clipstack.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.clipstack</string>
    <key>ProgramArguments</key>
    <array>
        <string>__PYTHON__</string>
        <string>-m</string>
        <string>clipstack.app</string>
    </array>
    <key>WorkingDirectory</key>
    <string>__CLIPSTACK_DIR__</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>__HOME__/.clipstack/clipstack.log</string>
    <key>StandardErrorPath</key>
    <string>__HOME__/.clipstack/clipstack.log</string>
</dict>
</plist>
```

- [ ] **Step 2: Create `install.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

CLIPSTACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$(command -v python3)"
PLIST_SRC="$CLIPSTACK_DIR/com.clipstack.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.clipstack.plist"

echo "Installing ClipStack from $CLIPSTACK_DIR"

# 1. Dependencies
"$PYTHON" -m pip install --user -r "$CLIPSTACK_DIR/requirements.txt"

# 2. Config dir
mkdir -p "$HOME/.clipstack"

# 3. Launch Agent
mkdir -p "$HOME/Library/LaunchAgents"
sed -e "s|__PYTHON__|$PYTHON|g" \
    -e "s|__CLIPSTACK_DIR__|$CLIPSTACK_DIR|g" \
    -e "s|__HOME__|$HOME|g" \
    "$PLIST_SRC" > "$PLIST_DST"

# 4. Load (reload if already loaded)
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"

echo ""
echo "ClipStack installed and running."
echo "Grant Accessibility + Input Monitoring permissions when macOS prompts,"
echo "then run: launchctl kickstart -k gui/$(id -u)/com.clipstack"
echo "Edit settings at: ~/.clipstack/config.json"
```

- [ ] **Step 3: Create `uninstall.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

PLIST_DST="$HOME/Library/LaunchAgents/com.clipstack.plist"

echo "Uninstalling ClipStack"

launchctl unload "$PLIST_DST" 2>/dev/null || true
rm -f "$PLIST_DST"

read -r -p "Also delete history and config at ~/.clipstack? [y/N] " ans
if [[ "$ans" == "y" || "$ans" == "Y" ]]; then
    rm -rf "$HOME/.clipstack"
    echo "Removed ~/.clipstack"
fi

echo "ClipStack uninstalled."
```

- [ ] **Step 4: Make scripts executable**

Run: `cd clipstack && chmod +x install.sh uninstall.sh`

- [ ] **Step 5: Verify scripts parse without executing**

Run: `cd clipstack && bash -n install.sh && bash -n uninstall.sh && echo "syntax ok"`
Expected: prints `syntax ok`

- [ ] **Step 6: Commit**

```bash
git add com.clipstack.plist install.sh uninstall.sh
git commit -m "feat: Launch Agent and install/uninstall scripts"
```

---

## Task 11: README

**Files:**
- Create: `clipstack/README.md`

- [ ] **Step 1: Write the README**

````markdown
# ClipStack

A tiny, open source clipboard history manager for macOS. Lives in your menu
bar, opens with a global hotkey, and pastes the item you pick straight into
whatever app you're using.

## Install

```bash
git clone https://github.com/YOURNAME/clipstack
cd clipstack
./install.sh
```

That's it. ClipStack starts immediately and launches automatically on login.

On first run, macOS will ask for **Accessibility** and **Input Monitoring**
permissions (needed to read the hotkey and paste for you). Grant them in
System Settings → Privacy & Security, then run:

```bash
launchctl kickstart -k gui/$(id -u)/com.clipstack
```

## Usage

- Copy anything as usual (`⌘C`). It's added to your history.
- Click the menu bar icon to see recent items. Click one to paste it.
- Or press the hotkey (default `⌘⇧V`) to pop the menu open from anywhere.

## Configuration

Edit `~/.clipstack/config.json`:

```json
{
  "max_items": 50,
  "hotkey": "<cmd>+<shift>+v",
  "excluded_apps": [
    "com.1password.1password",
    "com.agilebits.onepassword7"
  ]
}
```

- `max_items` — how many clipboard entries to keep
- `hotkey` — pynput hotkey string (e.g. `<cmd>+<shift>+v`)
- `excluded_apps` — bundle IDs to ignore (find one with
  `osascript -e 'id of app "AppName"'`)

Restart after editing: `launchctl kickstart -k gui/$(id -u)/com.clipstack`

## Uninstall

```bash
./uninstall.sh
```

## Development

```bash
pip3 install -r requirements.txt
python -m pytest        # run unit tests
python -m clipstack.app # run in foreground
```

## License

MIT
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README with install, usage, and config"
```

---

## Self-Review Notes

**Spec coverage:**
- Menu bar trigger → Task 8 (NSStatusItem + NSMenu). ✓
- Global hotkey truly opens the menu → Task 7 + Task 8 `open()`/`performClick_`, wired in Task 9. ✓
- Configurable cap/hotkey/exclusions → Task 2 (config). ✓
- Paste immediately on selection → Task 5 + Task 8 `clipSelected_`. ✓
- Excluded apps via frontmost bundle id → Task 4 + Task 6. ✓
- History persistence + corrupt-file reset → Task 3. ✓
- One-command install + Launch Agent + KeepAlive → Task 10. ✓
- Error handling (corrupt config/history, non-text clipboard) → Tasks 2, 3, 6. ✓
- Tests for store + config → Tasks 2, 3. ✓
- No Dock icon (accessory app) → Task 9. ✓

**Threading note:** the hotkey callback runs on pynput's thread. `MenuBar.open()` uses `AppHelper.callAfter` to marshal `performClick_` onto the main thread, which is required for AppKit calls. This is implemented in Task 8, not left as an exercise.

**pyobjc subclass note:** `MenuBar` subclasses `NSObject`, so it uses a `create()` factory + `alloc().init()` instead of `__init__` (pyobjc convention). Flagged so the implementer doesn't "fix" it into a normal constructor.

**Type consistency:** `Store(path, max_items)`, `store.items()`, `store.add(text)`, `config.load(path)`, `paste_text(text)`, `frontmost_bundle_id()`, `Watcher(store, excluded_apps)`, `HotkeyListener(hotkey, on_trigger)`, `MenuBar.create(store)`, `menubar.open` — all consistent across tasks.
