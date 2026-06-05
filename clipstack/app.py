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
