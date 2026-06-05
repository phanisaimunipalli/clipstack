# ClipStack

A tiny, open source clipboard history manager for macOS. Lives in your menu
bar, opens with a global hotkey, and pastes the item you pick straight into
whatever app you're using.

## Install

```bash
git clone https://github.com/YOURNAME/clipstack
cd clipstack
./install.sh
```

That's it. ClipStack starts immediately and launches automatically on login.

On first run, macOS will ask for **Accessibility** and **Input Monitoring**
permissions (needed to read the hotkey and paste for you). Grant them in
System Settings → Privacy & Security, then run:

```bash
launchctl kickstart -k gui/$(id -u)/com.clipstack
```

## Usage

- Copy anything as usual (`⌘C`). It's added to your history.
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

- `max_items` — how many clipboard entries to keep
- `hotkey` — pynput hotkey string (e.g. `<cmd>+<shift>+v`)
- `excluded_apps` — bundle IDs to ignore (find one with
  `osascript -e 'id of app "AppName"'`)

Restart after editing: `launchctl kickstart -k gui/$(id -u)/com.clipstack`

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
