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
