from AppKit import NSWorkspace


def frontmost_bundle_id():
    """Return the bundle identifier of the frontmost application, or None."""
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    if app is None:
        return None
    return app.bundleIdentifier()
