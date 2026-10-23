# Installation guide

[← Back to the README](../README.md) · **English** · [Español](install.es.md) · [Português](install.pt.md)

You need [Claude Code](https://docs.claude.com/en/docs/claude-code) (CLI, extension or desktop app) and Windows 10 or
11, or macOS 13 (Ventura) or newer.

## Windows

### Option A: installer (recommended, no Python needed)

1. **[Download `WaveMascot-Setup.exe`](../../../releases/latest/download/WaveMascot-Setup.exe)** (always the latest
   version; it's also in [Releases](../../../releases/latest)).
2. Open it and click **Yes**. It installs into `%LOCALAPPDATA%\Programs\WaveMascot`, no administrator rights needed.
3. Done: the next time Claude Code finishes, the mascot shows up. If Claude Code was already open, there's no need to
   restart it.

> Windows SmartScreen may show "Windows protected your PC". Choose **More info → Run anyway**, or use option B if you'd
> rather install from source. You can verify the file with the release's `SHA256SUMS.txt`.

### Option B: from source (Python 3.10 or newer)

1. Get the code: [ZIP](../../../archive/refs/heads/main.zip) (unzip it) or
   `git clone https://github.com/Marescaa/wavemascot.git`.
2. Open PowerShell in that folder and run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1
   ```

`install.ps1` installs PyQt6 and Pillow only if they're missing. Options: `-Python <path to python.exe>`,
`-Destination <folder>`, `-NoStartup` (no tray icon when Windows starts).

## Mac

### Option A: the app (recommended, no Python needed)

You need macOS 13 (Ventura) or newer, on any Mac.

1. **Download the file for your Mac.** To know which one: Apple menu → **About This Mac**.
   - It says **Chip: Apple M1, M2, M3, M4…** → **[`WaveMascot-Mac-AppleSilicon.dmg`](../../../releases/latest/download/WaveMascot-Mac-AppleSilicon.dmg)**
   - It says **Processor: Intel** → **[`WaveMascot-Mac-Intel.dmg`](../../../releases/latest/download/WaveMascot-Mac-Intel.dmg)**
2. **Open the `.dmg`** (double-click it in Downloads). A window shows WaveMascot and the Applications folder:
   **drag WaveMascot onto Applications**. You can then eject the WaveMascot disk in the Finder sidebar.
3. **Open WaveMascot** from Applications (or with Spotlight: <kbd>⌘</kbd> <kbd>Space</kbd>, type *WaveMascot*).
   The first time, macOS blocks it because the app isn't notarized by Apple (that needs a paid developer account):
   - **macOS 15 (Sequoia) or newer**: a window says *"Apple could not verify 'WaveMascot' is free of malware…"*.
     Click **Done**, open **System Settings → Privacy & Security**, scroll down to **Security** and click
     **Open Anyway** next to *"WaveMascot was blocked…"*. Confirm with **Open Anyway** and your password or Touch ID.
   - **macOS 13 or 14**: right-click (or <kbd>Control</kbd>-click) WaveMascot in Applications → **Open**, and
     **Open** again.

   It's only needed once; updates and the hooks don't ask again.
4. WaveMascot asks **"Install WaveMascot?"**: click **Yes**. It connects to Claude Code and tells you what it did.
5. Done: Wave's icon appears in the **menu bar** (top right). Click it → **Test notice** to see it. From now on it shows
   up whenever Claude Code finishes or needs something, in the terminal, VS Code or the Claude app. If Claude Code was
   already open, there's no need to restart it. To see it in Spanish or Portuguese, open the settings and pick the
   flag.

Good to know:

- **It doesn't ask for any permission** (no Accessibility, no Screen Recording, no notifications).
- If you open it straight from the `.dmg` without dragging it, it copies itself to Applications.
- **Settings**: menu bar icon → **Open settings**, `/wavemascot` in Claude Code, or open WaveMascot again from
  Applications.
- **Update**: download the new `.dmg`, drag WaveMascot onto Applications (**Replace**) and open it once.
- macOS shows *"Background Items Added"* the first time: that's the menu bar icon opening at login. You can turn it
  off in WaveMascot's settings or in **System Settings → General → Login Items**.
- To check the download: `shasum -a 256 ~/Downloads/WaveMascot-Mac-*.dmg` must match the release's
  `SHA256SUMS.txt`.

### Option B: from source (Python 3.10 or newer)

```bash
git clone https://github.com/Marescaa/wavemascot.git
cd wavemascot
./install.sh
```

`install.sh` creates its own Python environment with PyQt6 and Pillow (your Python stays untouched). Options:
`--python <path to python3>`, `--destination <folder>`, `--no-startup` (no menu bar icon at login).

## What the installer does on your computer

- **Copies the program** to `%LOCALAPPDATA%\Programs\WaveMascot` (Windows) or leaves the app in **Applications** (Mac;
  if you open it straight from the `.dmg`, it copies itself there).
- **Connects Wave to Claude Code**: it adds a few lines (the *hooks*) to `~/.claude/settings.json` so Claude Code calls
  it when it finishes or needs something. What you already had in that file is left alone, and a backup is saved
  before changing it.
- **Creates the `/wavemascot` command**, which opens the settings from Claude Code.
- **Puts Wave's icon next to the clock** (Windows) or **in the menu bar** (Mac, as a login item) every time you turn
  on your computer.

It doesn't need administrator rights, and if you uninstall it, everything goes back to how it was.

## Uninstall

- **Windows, installed with the `.exe`**: Start menu → *WaveMascot* → **Uninstall WaveMascot**.
- **Windows, installed with `install.ps1`** (or either way):

  ```powershell
  powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
  ```

- **Mac**: Wave's icon in the menu bar → **Uninstall WaveMascot…** (or `./uninstall.sh`, either way). If you just drag
  the app to the Trash, Claude Code keeps working normally: its hooks do nothing while the app isn't there.

Uninstalling closes the mascot, removes **only its hooks** from `~/.claude/settings.json` (with a backup first; yours
stay exactly as they were), and deletes `/wavemascot`, the shortcuts and the program. Your settings in `~/.wavemascot`
are kept; to delete them too: `uninstall.ps1 -DeleteSettings` or `uninstall.sh --delete-settings`.

## Troubleshooting

- **It doesn't show up**: check `~/.wavemascot/mascota.log`; each event says whether it notified or why not (full
  screen, do not disturb, focused terminal, event turned off...). Wave's icon → *Test notice* forces one.
- **The hooks don't run**: check with `/hooks` in Claude Code that the mascot's hooks are there.
- **Allow/Deny**: in the desktop app its own dialog still appears; the first answer wins.
- **Mac: "WaveMascot can't be opened" or "Apple could not verify…"**: see step 3 of [Install → Mac](#mac).
- **Mac: I don't see the icon in the menu bar**: on Macs with a notch, icons that don't fit are hidden; close a few
  other menu bar apps or open the settings with `/wavemascot`. If you quit it, open WaveMascot from Applications.
- **Mac: two notices**: turn off the notifications of your terminal or of the Claude app in **System Settings →
  Notifications**, so only Wave tells you.
- **Telegram: nothing arrives**: by default notices only go to the phone when you've been away for 3 minutes; turn
  off "Only when I'm not using the computer" to test it. If you blocked the bot or sent `/stop`, connect again from
  the **Phone** tab.
