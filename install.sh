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
