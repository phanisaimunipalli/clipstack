# ClipStack

A tiny, open source clipboard history manager for macOS. It lives in your menu
bar, opens with a global hotkey, and pastes the item you pick straight into
whatever app you are using.

Everything you copy is kept in a short, searchable list so you can grab
something you copied five minutes ago without copying it again.

## Requirements

macOS only. Python 3 and Git already ship with macOS, so there is nothing else
to install first.

## Install

```bash
git clone https://github.com/phanisaimunipalli/clipstack
cd clipstack
./install.sh
```

That is it. The installer builds a small `ClipStack.app`, so macOS shows the
name **ClipStack** (not "python3") in permission prompts, the Background
Activity notice, and Login Items. ClipStack starts immediately and launches
automatically on login.

On first run, macOS asks for **Accessibility** and **Input Monitoring**
permissions, which it needs to read the hotkey and paste for you. Grant them in
System Settings, Privacy & Security, then run:

```bash
launchctl kickstart -k gui/$(id -u)/com.clipstack
```

## Usage

- Copy anything as usual (`⌘C`). It is added to your history.
- Click the menu bar icon to see recent items. Click one to paste it.
- Or press the hotkey (default `⌘⇧V`) to pop the menu open from anywhere.

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

- `max_items`: how many clipboard entries to keep
- `hotkey`: pynput hotkey string (for example `<cmd>+<shift>+v`)
- `excluded_apps`: bundle IDs to ignore, so secrets from password managers are
  never recorded. Find a bundle ID with `osascript -e 'id of app "AppName"'`.

Restart after editing: `launchctl kickstart -k gui/$(id -u)/com.clipstack`

## Updating

```bash
./update.sh
```

This pulls the latest version and restarts ClipStack. If the update changed
dependencies or packaging, it re-runs the installer for you automatically.

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
