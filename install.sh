#!/usr/bin/env bash
set -euo pipefail

CLIPSTACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$(command -v python3)"
PLIST_SRC="$CLIPSTACK_DIR/com.clipstack.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.clipstack.plist"
APP="$CLIPSTACK_DIR/ClipStack.app"
APP_EXEC="$APP/Contents/MacOS/ClipStack"

echo "Installing ClipStack from $CLIPSTACK_DIR"

# 1. Dependencies
"$PYTHON" -m pip install --user -r "$CLIPSTACK_DIR/requirements.txt"

# 2. Config dir
mkdir -p "$HOME/.clipstack"

# 3. Build ClipStack.app so macOS shows the app name (not "python3") in
#    permission prompts, Background Activity, and Login Items.
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp "$CLIPSTACK_DIR/bundle/Info.plist" "$APP/Contents/Info.plist"
sed -e "s|__PYTHON__|$PYTHON|g" \
    -e "s|__CLIPSTACK_DIR__|$CLIPSTACK_DIR|g" \
    "$CLIPSTACK_DIR/bundle/launcher" > "$APP_EXEC"
chmod +x "$APP_EXEC"

# Ad-hoc sign so the bundle has a stable identity. This is what lets macOS
# remember the permission grants and label the prompts as "ClipStack".
codesign --force --deep --sign - "$APP"

# 4. Launch Agent (points at the app bundle's executable)
mkdir -p "$HOME/Library/LaunchAgents"
sed -e "s|__APP_EXEC__|$APP_EXEC|g" \
    -e "s|__CLIPSTACK_DIR__|$CLIPSTACK_DIR|g" \
    -e "s|__HOME__|$HOME|g" \
    "$PLIST_SRC" > "$PLIST_DST"

# 5. Load (reload if already loaded)
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"

echo ""
echo "ClipStack installed and running."
echo "Grant Accessibility + Input Monitoring permissions when macOS prompts"
echo "(the prompt now says \"ClipStack\"), then run:"
echo "  launchctl kickstart -k gui/$(id -u)/com.clipstack"
echo "Edit settings at: ~/.clipstack/config.json"
