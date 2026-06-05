# Clipboard Stack (clipstack) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a lightweight open source macOS clipboard history manager that lives in the menu bar, opens via a global hotkey, and pastes the selected item immediately.

**Architecture:** A single Python process runs three concerns: a background clipboard watcher (polls every 0.5s), a `rumps` menu bar UI (renders history, pastes on click), and a `pynput` global hotkey listener (opens the menu). History and config persist as JSON under `~/.clipstack/`. Installation is one command: clone the public repo and run `./install.sh`, which pip-installs deps and registers a Launch Agent.

**Tech Stack:** Python 3, rumps (menu bar), pynput (hotkey), pyperclip (clipboard), pyobjc (paste simulation + frontmost-app detection), pytest (tests).

---

## File Structure

```
clipstack/
├── install.sh                  # pip install + Launch Agent setup + launchctl load
├── uninstall.sh                # reverses install.sh cleanly
├── requirements.txt            # rumps, pynput, pyperclip, pyobjc
├── README.md                   # setup + usage for the public repo
├── .gitignore
├── clipstack/
│   ├── __init__.py
│   ├── config.py               # loads ~/.clipstack/config.json with defaults
│   ├── store.py                # history list + read/write to history.json
│   ├── watcher.py              # clipboard polling loop (background thread)
│   ├── paste.py                # write to clipboard + simulate Cmd+V (pyobjc)
│   ├── appkit.py               # frontmost-app bundle ID lookup (pyobjc)
│   ├── hotkey.py               # global hotkey listener (background thread)
│   └── app.py                  # entry point, wires all concerns together
├── assets/
│   └── icon.png                # 16x16 menu bar template image
├── tests/
│   ├── test_config.py
│   └── test_store.py
└── com.clipstack.plist         # Launch Agent template (KeepAlive=true)
```

**Responsibility split:**
- `config.py` and `store.py` are pure, OS-independent, and fully unit-tested.
- `paste.py` and `appkit.py` isolate the pyobjc OS calls behind small functions so the rest of the code stays testable.
- `watcher.py`, `hotkey.py`, and `app.py` wire things together and are validated by manual smoke test, not unit tests.

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
docs/superpowers/specs/.superpowers/
```

- [ ] **Step 2: Create `requirements.txt`**

```
rumps==0.4.0
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

This module isolates a pyobjc OS call. It is not unit-tested (no useful way to mock the frontmost app); it is validated during the Task 8 smoke test.

- [ ] **Step 1: Write the implementation**

```python
# clipstack/appkit.py
from AppKit import NSWorkspace


def frontmost_bundle_id() -> str | None:
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

This module isolates pyperclip + Quartz OS calls. Not unit-tested; validated during the Task 8 smoke test.

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

The watcher runs a polling loop on a background thread. It is not unit-tested; validated during the Task 8 smoke test.

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

Listens for the configured global hotkey on a background thread via pynput. On trigger, runs a callback. Not unit-tested; validated during the Task 8 smoke test.

- [ ] **Step 1: Write the implementation**

```python
# clipstack/clipstack/hotkey.py
from pynput import keyboard


class HotkeyListener:
    """Global hotkey listener. Calls `on_trigger` when the hotkey fires.

    `hotkey` uses pynput's GlobalHotKeys format, e.g. "<cmd>+<shift>+v".
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

## Task 8: App entry point (wiring)

**Files:**
- Create: `clipstack/clipstack/app.py`
- Create: `clipstack/assets/icon.png`

`app.py` wires config, store, watcher, hotkey, and the rumps menu bar UI together. The rumps app runs on the main thread; watcher and hotkey run on background threads.

- [ ] **Step 1: Create a placeholder menu bar icon**

Run this to generate a simple 16x16 black template PNG:

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

If PIL is not installed, fall back to no icon: the rumps app will show a text title instead (handled in Step 2 — `icon` is set only if the file exists). Either way, do not block on the icon.

- [ ] **Step 2: Write the implementation**

```python
# clipstack/clipstack/app.py
import os
from pathlib import Path

import rumps

from clipstack import config
from clipstack.store import Store
from clipstack.watcher import Watcher
from clipstack.hotkey import HotkeyListener
from clipstack.paste import paste_text

HOME = Path.home()
CONFIG_PATH = HOME / ".clipstack" / "config.json"
HISTORY_PATH = HOME / ".clipstack" / "history.json"
ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "icon.png"

MENU_LABEL_MAX = 40


class ClipStackApp(rumps.App):
    def __init__(self, store, cfg):
        icon = str(ICON_PATH) if ICON_PATH.exists() else None
        super().__init__("ClipStack", icon=icon, title=None if icon else "📋",
                         template=True)
        self.store = store
        self.cfg = cfg
        self._rebuild_menu()

    def _rebuild_menu(self):
        self.menu.clear()
        items = self.store.items()
        if not items:
            self.menu.add(rumps.MenuItem("(empty)", callback=None))
        else:
            for text in items:
                self.menu.add(self._make_item(text))
        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Quit", callback=rumps.quit_application))

    def _make_item(self, text):
        label = " ".join(text.split())
        if len(label) > MENU_LABEL_MAX:
            label = label[:MENU_LABEL_MAX] + "…"
        item = rumps.MenuItem(label, callback=self._on_select)
        item._clip_text = text
        return item

    def _on_select(self, sender):
        paste_text(sender._clip_text)

    @rumps.timer(1)
    def _refresh(self, _):
        # Keep the menu in sync with the watcher's additions.
        self._rebuild_menu()

    def open_menu(self):
        # Triggered by the hotkey; rumps shows the menu on icon click,
        # so we surface the app by clicking programmatically is not exposed.
        # Instead we post a notification to draw attention; the user clicks
        # the menu bar icon. Hotkey primarily ensures the app is frontmost.
        rumps.notification("ClipStack", "", "Click the menu bar icon to pick")


def main():
    cfg = config.load(CONFIG_PATH)
    store = Store(HISTORY_PATH, max_items=cfg["max_items"])

    watcher = Watcher(store, cfg["excluded_apps"])
    watcher.start()

    app = ClipStackApp(store, cfg)

    hotkey = HotkeyListener(cfg["hotkey"], app.open_menu)
    hotkey.start()

    app.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Smoke test the whole app manually**

Run: `cd clipstack && pip3 install -r requirements.txt && python -m clipstack.app`

Expected behavior:
1. A 📋 / icon appears in the menu bar.
2. Copy some text in another app (e.g. `⌘C` in a browser). Within ~1.5s it appears in the menu.
3. Click a menu item → it pastes into the focused app.
4. Copy text while a password manager is frontmost → it does NOT appear (if that bundle id is in `excluded_apps`).
5. Quit via the menu.

macOS will prompt for **Accessibility** and **Input Monitoring** permissions on first run (needed for hotkey + paste simulation). Grant them in System Settings → Privacy & Security, then relaunch.

- [ ] **Step 4: Commit**

```bash
git add clipstack/app.py assets/icon.png
git commit -m "feat: app entry point wiring menu bar, watcher, and hotkey"
```

---

## Task 9: Launch Agent + install/uninstall scripts

**Files:**
- Create: `clipstack/com.clipstack.plist`
- Create: `clipstack/install.sh`
- Create: `clipstack/uninstall.sh`

- [ ] **Step 1: Create the Launch Agent template**

`__CLIPSTACK_DIR__` and `__PYTHON__` are placeholders that `install.sh` substitutes.

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

## Task 10: README

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
- Or press the hotkey (default `⌘⇧V`) to be reminded, then click the icon.

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
- Menu bar trigger → Task 8 (rumps menu). ✓
- Global hotkey trigger → Task 7 + wired in Task 8. ✓
- Configurable cap/hotkey/exclusions → Task 2 (config). ✓
- Paste immediately on selection → Task 5 + Task 8. ✓
- Excluded apps via frontmost bundle id → Task 4 + Task 6. ✓
- History persistence + corrupt-file reset → Task 3. ✓
- One-command install + Launch Agent + KeepAlive → Task 9. ✓
- Error handling (corrupt config/history, non-text clipboard) → Tasks 2, 3, 6. ✓
- Tests for store + config → Tasks 2, 3. ✓

**Known platform note:** rumps does not expose a public API to programmatically open the menu from a hotkey. The hotkey therefore posts a notification cue (Task 8 `open_menu`); the menu bar click remains the primary open path. This is an honest limitation, not a placeholder — if a future contributor wants true hotkey-open they would need a custom NSStatusItem. Flagged here so the implementer doesn't treat it as a bug.

**Type consistency:** `Store` constructor signature `(path, max_items)`, `store.items()`, `store.add(text)`, `config.load(path)`, `paste_text(text)`, `frontmost_bundle_id()`, `Watcher(store, excluded_apps)`, `HotkeyListener(hotkey, on_trigger)` — all consistent across tasks.
