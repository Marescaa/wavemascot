# Changelog

All notable changes to this project. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [semantic versioning](https://semver.org/).

## [1.2.0] - 2026-10-19

### Added

- **macOS** (13 Ventura or newer, Apple Silicon and Intel). The same mascot, notices, companion mode, settings and
  languages as on Windows:
  - `WaveMascot-Mac-AppleSilicon.dmg` and `WaveMascot-Mac-Intel.dmg` in every release. Opening the app the first time
    installs it (and copies it to Applications if it was opened from the `.dmg`); opening it again shows the settings.
  - Wave's icon lives in the menu bar (with **Uninstall WaveMascot…**), opens at login with a LaunchAgent and has no
    Dock icon; the settings window does, like any window.
  - The notice shows up on the monitor of the Claude Code window, skips full-screen apps and the focused terminal
    (Terminal, iTerm2, VS Code, the Claude app…), and **Go to terminal** brings it to the front.
  - The mascot floats over every desktop (Space) without stealing focus from the terminal when you click it.
  - Text uses the macOS system font at the same pixel size as on Windows.
  - Hooks do nothing (instead of failing) if the app is dragged to the Trash without uninstalling.
  - `install.sh` / `uninstall.sh` to install from source (with its own Python virtual environment).
- `build-mac.sh` builds the app and the `.dmg`; the release workflow builds the Windows installer and both Mac `.dmg`
  files, with one `SHA256SUMS.txt` for all of them.
- Tests run on Windows and macOS on every push to `main` and on pull requests.

## [1.1.0] - 2026-10-18

### Added

- Languages: English, Spanish and Portuguese across the whole app (notices, buttons, settings, tray menu, installer).
  English is the default.
- Language flag at the top right of the settings window; switching rebuilds the window in place, on the same tab.
- Qt's own texts (Yes/No, Copy/Paste…) follow the chosen language.
- README in English, Spanish ([README.es.md](README.es.md)) and Portuguese ([README.pt.md](README.pt.md)).
- Test that fails if any visible text is missing a translation.

### Changed

- The default messages are now empty and use the automatic text in your language; the previous fixed Spanish
  default is migrated automatically.
- `install.ps1` / `uninstall.ps1` print in English and accept `-Destination`, `-NoStartup` and `-DeleteSettings`
  (the Spanish names still work).
- `TERCEROS.md` is now [THIRD_PARTY.md](THIRD_PARTY.md).

### Fixed

- Outfit names that don't fit on one line now wrap to a second line instead of being cut off.

## [1.0.0] - 2026-10-18

First public release of WaveMascot.

### Added

- Pixel-art mascot that replaces Claude Code's Windows notification: it slides in from the edge of the screen, shows
  the chat, project, duration and a summary of the answer, and leaves on its own or with a click.
- `done`, `permission`, `thinking`, `subagent`, `limit` and `error` states, each with its own animation and sound.
- Allow / Deny from the mascot with the `PermissionRequest` hook; button to focus the terminal.
- Companion mode: small on the taskbar, with walks, eyes that follow the cursor and a nap when you hit the usage limit.
- Settings window with a live preview, tray icon and the `/wavemascot` command.
- Outfits (colors, heads, clothes, accessories), your own image, sizes, dark / light / accent themes and a sound per
  event.
- Do not disturb by schedule, over full-screen apps and when the terminal has focus; minimum duration to notify.
- Several Claude Code sessions at once: each notice shows its project and notices from other sessions queue up.
- Multiple monitors: the notice shows up on the monitor of the Claude Code window.
- Works without `config.json` (defaults) and without an audio device; errors go to the log and never block Claude
  Code.
- `install.ps1` / `uninstall.ps1`: hook merge into `~/.claude/settings.json` with a backup first, without touching
  existing hooks; uninstalling leaves the file as it was.
- `WaveMascot-Setup.exe` installer (PyInstaller, no Python or administrator rights needed) and a GitHub Actions
  workflow that publishes it on every `v*` tag.

[1.2.0]: ../../releases/tag/v1.2.0
[1.1.0]: ../../releases/tag/v1.1.0
[1.0.0]: ../../releases/tag/v1.0.0
