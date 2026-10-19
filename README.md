# WaveMascot

**English** · [Español](README.es.md) · [Português](README.pt.md)

<!-- Demo: replace docs/demo.gif with a screen recording (≈ 800 px wide, < 5 MB). -->
<p align="center">
  <img src="docs/demo.gif" alt="The mascot in its different states" width="224">
</p>

**Wave** is a pixel-art desktop mascot for Windows and macOS that lets you know when **Claude Code** finishes, needs
your permission or runs out of usage, instead of the system notification. It slides in from the edge of the screen,
tells you which chat and project the notice is about, and leaves on its own.

<p align="center">
  <a href="../../releases/latest/download/WaveMascot-Setup.exe"><b>⬇ Download for Windows</b></a>
  &nbsp;·&nbsp; <a href="../../releases/latest/download/WaveMascot-Mac-AppleSilicon.dmg"><b>⬇ Mac (Apple chip)</b></a>
  &nbsp;·&nbsp; <a href="../../releases/latest/download/WaveMascot-Mac-Intel.dmg"><b>⬇ Mac (Intel)</b></a>
  <br>
  <a href="#install">Install</a>
  &nbsp;·&nbsp; <a href="../../discussions">Questions &amp; ideas</a>
  &nbsp;·&nbsp; <a href="../../issues/new/choose">Report a problem</a>
</p>

> **Unofficial project.** It is not made, endorsed or maintained by Anthropic. It uses no logos, images, sounds or
> any other Anthropic assets: the mascot, the icon and the sounds are original and generated in code
> (see [THIRD_PARTY.md](THIRD_PARTY.md)).
>
> **Everything runs on your computer.** The mascot never connects to the internet or sends data anywhere. The summary
> of the last message is built by reading, locally, the transcript Claude Code already keeps on your disk, and it
> never leaves it.

## What it does

- **Tells you when Claude finishes** (`done`), **asks for permission**, is **thinking**, a **subagent** finished,
  you hit the **usage limit** or there was an **error**: each state has its own animation and sound.
- **Allow / Deny from the mascot** (`PermissionRequest` hook): answer without going to the terminal. If you don't
  choose in time, the usual dialog decides.
- **Shows just the right context**: chat title, project, how long it took and a short summary of the answer.
  With **several sessions at once**, each notice says which project it comes from and notices queue up instead of
  overwriting each other.
- **Doesn't get in the way**: do-not-disturb hours, nothing over full-screen apps, nothing if you're already looking
  at the terminal, a minimum duration, and quick mute from its icon (next to the clock on Windows, in the menu bar on
  Mac).
- **Companion mode**: instead of popping in and out, it stays small on the taskbar (or the Dock), wanders a bit and
  falls asleep when you run out of usage until it resets.
- **Customizable**: colors, hats, clothes and accessories, your own image (PNG/GIF), size, corner, dark/light/accent
  themes and a sound per event.
- **In your language**: English, Spanish and Portuguese. English by default; change it with the flag at the top of the
  settings.
- **Multiple monitors**: the notice shows up on the monitor where the Claude Code window is.
- **Never slows Claude Code down**: the hook returns in milliseconds, never exits with an error and, if something
  fails (no audio, broken settings, no screen), it writes it to the log and moves on.

## Install

You need [Claude Code](https://docs.claude.com/en/docs/claude-code) (CLI, extension or desktop app) and Windows 10 or
11, or macOS 13 (Ventura) or newer.

### Windows

#### Option A: installer (recommended, no Python needed)

1. **[Download `WaveMascot-Setup.exe`](../../releases/latest/download/WaveMascot-Setup.exe)** (always the latest
   version; it's also in [Releases](../../releases/latest)).
2. Open it and click **Yes**. It installs into `%LOCALAPPDATA%\Programs\WaveMascot`, no administrator rights needed.
3. Done: the next time Claude Code finishes, the mascot shows up. If Claude Code was already open, there's no need to
   restart it.

> Windows SmartScreen may show "Windows protected your PC". Choose **More info → Run anyway**, or use option B if you'd
> rather install from source. You can verify the file with the release's `SHA256SUMS.txt`.

#### Option B: from source (Python 3.10 or newer)

1. Get the code: [ZIP](../../archive/refs/heads/main.zip) (unzip it) or
   `git clone https://github.com/Marescaa/wavemascot.git`.
2. Open PowerShell in that folder and run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1
   ```

`install.ps1` installs PyQt6 and Pillow only if they're missing. Options: `-Python <path to python.exe>`,
`-Destination <folder>`, `-NoStartup` (no tray icon when Windows starts).

### Mac

#### Option A: the app (recommended, no Python needed)

1. Download the one for your Mac (Apple menu → **About This Mac**):
   - **Chip: Apple M1, M2, M3, M4…** → **[`WaveMascot-Mac-AppleSilicon.dmg`](../../releases/latest/download/WaveMascot-Mac-AppleSilicon.dmg)**
   - **Processor: Intel** → **[`WaveMascot-Mac-Intel.dmg`](../../releases/latest/download/WaveMascot-Mac-Intel.dmg)**
2. Open the `.dmg` and drag **WaveMascot** onto **Applications**.
3. Open WaveMascot from Applications and click **Yes**. Its icon shows up in the menu bar, and the next time Claude Code
   finishes, the mascot appears. If Claude Code was already open, there's no need to restart it.

> The app isn't notarized by Apple (that needs a paid developer account), so the first time macOS says it can't verify
> it. Open **System Settings → Privacy & Security**, scroll down and click **Open Anyway** next to WaveMascot (on
> macOS 14 or older you can also right-click the app → **Open**). It's only needed once. You can verify the file with
> the release's `SHA256SUMS.txt`, or use option B.

#### Option B: from source (Python 3.10 or newer)

```bash
git clone https://github.com/Marescaa/wavemascot.git
cd wavemascot
./install.sh
```

`install.sh` creates its own Python environment with PyQt6 and Pillow (your Python stays untouched). Options:
`--python <path to python3>`, `--destination <folder>`, `--no-startup` (no menu bar icon at login).

### What the installer does on your computer

- **Copies the program** to `%LOCALAPPDATA%\Programs\WaveMascot` (Windows) or leaves the app in **Applications** (Mac;
  if you open it straight from the `.dmg`, it copies itself there).
- **Connects Wave to Claude Code**: it adds a few lines (the *hooks*) to `~/.claude/settings.json` so Claude Code calls
  it when it finishes or needs something. What you already had in that file is left alone, and a backup is saved
  before changing it.
- **Creates the `/wavemascot` command**, which opens the settings from Claude Code.
- **Puts Wave's icon next to the clock** (Windows) or **in the menu bar** (Mac, as a login item) every time you turn
  on your computer.

It doesn't need administrator rights, and if you uninstall it, everything goes back to how it was.

## Settings

Open the settings by clicking **Wave's icon** (next to the clock on Windows, in the menu bar on Mac), with
**`/wavemascot`** in Claude Code or, on Mac, by opening WaveMascot from Applications. Changes are saved automatically
and apply from the next notice; the preview shows how it will look. The **flag** at the top right changes the
language.

<p align="center">
  <img src="docs/ajustes.png" alt="WaveMascot settings window: Outfits tab with the notice preview and the language flag" width="760">
</p>

| Tab | What you can change |
|---|---|
| Notice | Corner, time on screen, what to show in the notice (summary, chat, project, duration) and the messages |
| Behavior | Notice or companion mode (walks, idle animations, eyes), which events notify, do not disturb (hours, full screen, focused terminal), minimum duration, Allow/Deny from the mascot |
| Mascot | Color, size and your own image |
| Outfits | Head, clothes and accessories (or random) |
| Sound and style | Volume, sound for each event, dark / light / accent theme, tray / menu bar icon |

Everything is stored in `~/.wavemascot/config.json`. If the file doesn't exist or has an error, the mascot uses the
defaults. From Wave's icon you can also mute notices for an hour or until you turn them back on.

> For the mascot to replace the system notification, turn off Claude Code's own notifications (in the desktop app's
> settings or your terminal's), so you don't get two notices.

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
- **Mac: "WaveMascot can't be opened" or "Apple could not verify…"**: see the note in [Install → Mac](#mac).

## Questions, ideas and reports

- **Got a question or an idea?** Post it in [Discussions](../../discussions): chat, propose new outfits or states and
  share your setups.
- **Something doesn't work?** Open an [issue](../../issues/new/choose) with the bug template (add the last lines of
  the log, without private data).
- **Want to propose something specific?** Use the idea template in [issues](../../issues/new/choose).

English, Spanish and Portuguese are all welcome. Pull requests too: before sending one, run the tests
(`python -m unittest discover tests`).

## Development

```powershell
python -m unittest discover tests          # installer (hook merge), translation and platform tests
powershell -ExecutionPolicy Bypass -File .\build.ps1   # builds dist\WaveMascot-Setup.exe (on Windows)
./build-mac.sh                             # builds dist/WaveMascot-Mac-<chip>.dmg (on a Mac)
```

Pushing a `v*` tag (for example `v1.2.0`) makes GitHub Actions build the Windows installer and both Mac `.dmg` files
and attach them to the release. Every push to `main` runs the tests on Windows and macOS.

| File | What it is |
|---|---|
| `mascota.py` | The hook and the mascot window |
| `ajustes.py` | The settings window |
| `bandeja.py` | The tray / menu bar icon |
| `sprites.py` | The pixel art, the icons and the sounds (all generated in code) |
| `idiomas.py` | The texts in English, Spanish and Portuguese |
| `ventanas.py` | Windows and macOS windows: host terminal, focus, full screen, monitors |
| `instalador.py` | Install / uninstall (hook merge with backup); also the `.exe` installer and the Mac app's first run |
| `principal.py` | Entry point of `WaveMascot.exe` and `WaveMascot.app` |

**Adding a language**: add it to `IDIOMAS` in `idiomas.py` and one translation per text; `tests/test_idiomas.py` tells
you if any is missing.

## License

[MIT](LICENSE). The `.exe` and the Mac app include PyQt6 (GPL v3) and other libraries; see
[THIRD_PARTY.md](THIRD_PARTY.md).
