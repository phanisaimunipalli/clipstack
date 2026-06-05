#!/usr/bin/env bash
set -euo pipefail

CLIPSTACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_DST="$HOME/Library/LaunchAgents/com.clipstack.plist"

echo "Uninstalling ClipStack"

launchctl unload "$PLIST_DST" 2>/dev/null || true
rm -f "$PLIST_DST"
rm -rf "$CLIPSTACK_DIR/ClipStack.app"

read -r -p "Also delete history and config at ~/.clipstack? [y/N] " ans
if [[ "$ans" == "y" || "$ans" == "Y" ]]; then
    rm -rf "$HOME/.clipstack"
    echo "Removed ~/.clipstack"
fi

echo "ClipStack uninstalled."
echo "If macOS still lists an old \"python3\" entry under Privacy & Security,"
echo "you can remove it there by hand."
