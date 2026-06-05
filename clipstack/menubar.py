from pathlib import Path

import objc
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
# SF Symbol shown in the menu bar. Crisp at any size and adapts to light/dark.
# Swap for another symbol name to taste, e.g. "doc.on.clipboard" or
# "square.stack.3d.up" (all available on macOS 11+).
ICON_SYMBOL = "square.stack"
MENU_LABEL_MAX = 64
# Number the most recent items so the list reads like a ranked history.
NUMBERED_ITEMS = 9


class MenuBar(NSObject):
    """Owns the NSStatusItem and its NSMenu.

    Construct with MenuBar.create(store). pyobjc subclasses of NSObject
    must not define __init__; use the create() factory plus _setup().
    """

    @objc.python_method
    @classmethod
    def create(cls, store):
        self = cls.alloc().init()
        self._store = store
        self._build_status_item()
        return self

    @objc.python_method
    def _build_status_item(self):
        bar = NSStatusBar.systemStatusBar()
        self._status_item = bar.statusItemWithLength_(NSVariableStatusItemLength)
        button = self._status_item.button()
        image = self._status_image()
        if image is not None:
            image.setTemplate_(True)
            button.setImage_(image)
        else:
            button.setTitle_("ClipStack")

        menu = NSMenu.alloc().init()
        menu.setDelegate_(self)
        self._status_item.setMenu_(menu)
        self._menu = menu

    @objc.python_method
    def _status_image(self):
        """Prefer a crisp SF Symbol; fall back to the bundled PNG, then text."""
        try:
            image = NSImage.imageWithSystemSymbolName_accessibilityDescription_(
                ICON_SYMBOL, "ClipStack"
            )
        except Exception:
            image = None
        if image is not None:
            return image
        if ICON_PATH.exists():
            return NSImage.alloc().initWithContentsOfFile_(str(ICON_PATH))
        return None

    # NSMenuDelegate: rebuild items from the store right before display.
    def menuNeedsUpdate_(self, menu):
        menu.removeAllItems()
        items = self._store.items()
        if not items:
            empty = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "No clips yet", None, ""
            )
            empty.setEnabled_(False)
            menu.addItem_(empty)
        else:
            for position, text in enumerate(items, start=1):
                item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                    self._label_for(position, text), b"clipSelected:", ""
                )
                item.setTarget_(self)
                # Attach the full text to the item itself rather than an index,
                # so a background clipboard write while the menu is open can't
                # shift indices and paste the wrong entry.
                item.setRepresentedObject_(text)
                menu.addItem_(item)
        menu.addItem_(NSMenuItem.separatorItem())
        if items:
            clear_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Clear History", b"clearHistory:", ""
            )
            clear_item.setTarget_(self)
            menu.addItem_(clear_item)
        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit ClipStack", b"terminate:", "q"
        )
        quit_item.setTarget_(NSApplication.sharedApplication())
        menu.addItem_(quit_item)

    @objc.python_method
    def _label_for(self, position, text):
        label = " ".join(text.split())
        if len(label) > MENU_LABEL_MAX:
            label = label[:MENU_LABEL_MAX] + "…"
        if position <= NUMBERED_ITEMS:
            return "{}.  {}".format(position, label)
        return label

    # Action fired when a history item is clicked.
    def clipSelected_(self, sender):
        text = sender.representedObject()
        if text:
            paste_text(text)

    # Action fired by the "Clear History" item.
    def clearHistory_(self, sender):
        self._store.clear()

    @objc.python_method
    def open(self):
        """Open the menu programmatically (called from the hotkey)."""
        callAfter(self._perform_click)

    @objc.python_method
    def _perform_click(self):
        self._status_item.button().performClick_(None)
