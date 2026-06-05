# Clipboard Stack (clipstack) — Design Spec

**Date:** 2026-06-04
**Status:** Approved

---

## Overview

A lightweight, open source macOS clipboard history manager. Lives in the menu bar, triggered by a global hotkey, pastes immediately on selection. One-command setup from a public git repo.

---

## Goals

- Keep a rolling history of clipboard items (text only)
- Surface history via a menu bar icon and a global hotkey
- Paste selected item immediately into the focused app
- Configurable cap, hotkey, and excluded apps via a JSON config file
- Anyone can set it up with: `git clone <repo> && cd clipstack && ./install.sh`

---

## Non-Goals

- Image or file clipboard support (text only)
- Cloud sync or cross-device history
- GUI settings panel (config file is the settings UI)
- Windows or Linux support (macOS only)

---

## Stack

| Concern | Library |
|---|---|
| Menu bar UI (status item + native menu) | `pyobjc` (AppKit) |
| Global hotkey | `pynput` |
| Clipboard read/write | `pyperclip` |
| Paste simulation + excluded app detection | `pyobjc` (Quartz + AppKit) |
| Config + history persistence | stdlib (`json`, `pathlib`) |
| Tests | `pytest` |

Python 3 and Git are both pre-installed on macOS — no prerequisites beyond cloning the repo.

---

## Architecture

The process runs as a PyObjC accessory app (no Dock icon). Three concerns:

1. **Clipboard Watcher** — background thread, polls clipboard every 0.5s. On change, checks excluded apps, then calls `store.add()`.
2. **Menu Bar UI** — a raw `NSStatusItem` with a native `NSMenu`, owned on the main thread. The menu is rebuilt fresh from the store each time it opens (via `NSMenuDelegate.menuNeedsUpdate_`), so no polling timer is needed. Clicking an item pastes it immediately.
3. **Hotkey Listener** — background thread via `pynput`. Default `⌘⇧V` genuinely opens the menu by calling `statusItem.button().performClick_(None)` on the main thread (marshalled via `PyObjCTools.AppHelper.callAfter`).

**Why raw PyObjC instead of `rumps`:** `rumps` does not expose a public API to open its menu programmatically, so a hotkey could only nudge the user to click. A raw `NSStatusItem` lets the hotkey truly pop the menu open, fully satisfying the hotkey requirement, while staying native and small.

---

## File Structure

```
clipstack/
├── install.sh                  # pip install + Launch Agent setup + launchctl load
├── uninstall.sh                # reverses install.sh cleanly
├── requirements.txt            # pynput, pyperclip, pyobjc (Cocoa + Quartz)
├── clipstack/
│   ├── app.py                  # entry point: NSApplication run loop + wiring
│   ├── menubar.py              # NSStatusItem + NSMenu, rebuild-on-open, open()
│   ├── watcher.py              # clipboard polling loop (background thread)
│   ├── hotkey.py               # global hotkey listener (background thread)
│   ├── paste.py                # clipboard write + Cmd+V simulation (Quartz)
│   ├── appkit.py               # frontmost-app bundle id lookup (AppKit)
│   ├── store.py                # history list + read/write to history.json
│   └── config.py               # loads ~/.clipstack/config.json with defaults
├── assets/
│   └── icon.png                # 16x16 menu bar template image
├── tests/
│   ├── test_store.py
│   └── test_config.py
└── com.clipstack.plist         # Launch Agent template (KeepAlive=true)
```

---

## Data Flow

### Clipboard Capture

1. `watcher.py` reads clipboard every 0.5s via `pyperclip.paste()`
2. If content is unchanged from last read, skip
3. Get frontmost app bundle ID via `NSWorkspace.sharedWorkspace().frontmostApplication().bundleIdentifier()`
4. If bundle ID is in `config.excluded_apps`, skip silently
5. Call `store.add(text)` — prepend to list, trim to `max_items`, write to `~/.clipstack/history.json`

### Opening the Menu

1. **Via icon:** user clicks the `NSStatusItem` button → the attached `NSMenu` opens automatically.
2. **Via hotkey:** `pynput` fires the callback on its listener thread → `AppHelper.callAfter` marshals to the main thread → `statusItem.button().performClick_(None)` opens the same menu.
3. Either path triggers `menuNeedsUpdate_`, which rebuilds the menu items from `store.items()` so the list is always current.

### Paste on Selection

1. User clicks a history item in the menu (or selects via hotkey + menu)
2. `pyperclip.copy(text)` writes item back to clipboard
3. `pyobjc` fires `CGEvent` keyboard event simulating `⌘V`
4. Focused app receives the paste

### History Persistence

- On startup: `store.py` loads `~/.clipstack/history.json` (survives restarts)
- On each new item: list is written back to `history.json`

---

## Config

Default config written to `~/.clipstack/config.json` on first run:

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

---

## install.sh Behavior

1. `pip3 install -r requirements.txt`
2. Resolve absolute path to `app.py`
3. Copy `com.clipstack.plist` to `~/Library/LaunchAgents/com.clipstack.plist` with path substituted
4. `launchctl load ~/Library/LaunchAgents/com.clipstack.plist`

The Launch Agent has `KeepAlive = true` so the process auto-restarts on crash.

## uninstall.sh Behavior

1. `launchctl unload ~/Library/LaunchAgents/com.clipstack.plist`
2. Remove plist from `~/Library/LaunchAgents/`
3. Optionally remove `~/.clipstack/` (prompts user)

---

## Error Handling

| Scenario | Behavior |
|---|---|
| `history.json` corrupt on load | Reset to empty list, overwrite file |
| Clipboard read returns non-text (image, file) | Skip poll cycle silently |
| `config.json` invalid JSON | Fall back to defaults, log warning to `~/.clipstack/clipstack.log` |
| Process crash | Launch Agent restarts it automatically |

---

## Testing

- `tests/test_store.py` — add, trim, dedup logic
- `tests/test_config.py` — default fallback behavior when config is missing or invalid
- Run with: `python -m pytest`
- No mocking of OS APIs (AppKit/Quartz/pynput) — those are validated by manual smoke test, not unit tests

---

## Open Questions

None — all decisions made during design session.
