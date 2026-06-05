#!/usr/bin/env bash
set -euo pipefail

CLIPSTACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$CLIPSTACK_DIR"

echo "Updating ClipStack in $CLIPSTACK_DIR"

OLD="$(git rev-parse HEAD)"
git pull --ff-only
NEW="$(git rev-parse HEAD)"

if [[ "$OLD" == "$NEW" ]]; then
    echo "Already up to date. Nothing to do."
    exit 0
fi

# If anything that affects installation changed (dependencies, the app bundle,
# the launch agent, or the installer itself), re-run install.sh, which rebuilds
# the bundle and reloads the launch agent. Otherwise just restart to pick up the
# new Python code.
CHANGED="$(git diff --name-only "$OLD" "$NEW")"
if echo "$CHANGED" | grep -Eq '^(install\.sh|requirements\.txt|com\.clipstack\.plist|bundle/)'; then
    echo "Install-affecting files changed; re-running install.sh"
    ./install.sh
else
    echo "Restarting ClipStack to load the new version"
    launchctl kickstart -k "gui/$(id -u)/com.clipstack"
fi

echo "ClipStack updated."
