# Changelog

All notable changes to this project. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [semantic versioning](https://semver.org/).

## [Unreleased]

### Changed

- The settings window opens a little wider (980 px) so every tab fits with the PRO badge.
- The Windows build keeps `libssl`/`libcrypto` (needed for HTTPS to Telegram and GitHub).

### Added

- **WaveMascot Pro**: Telegram notifications and Allow/Deny from the phone are now part of Pro, with a 7-day free
  trial that starts when you connect. Everything else stays free and open source.
  - A **PRO** badge on the Phone tab and a plan card at the top of it. Tapping either opens a guide: what Pro
    includes, what stays free, and three steps to unlock it (connect Telegram, pick a plan, pay with Telegram Stars).
    It detects the payment by itself and celebrates with confetti.
  - Plans: monthly (Telegram renews it; cancel anytime with `/pro`) or lifetime. One Pro covers every computer
    linked to the same Telegram account.
  - Without Pro, the mascot keeps notifying on screen and permission requests go back to the terminal; the bot
    explains it once and reminds you a day before the trial ends.
  - New bot commands: `/pro`, `/paysupport`, `/terms`. The server decides who is Pro; `COBRAR = "no"` turns billing
    off.
- **Mascot styles (beta)**: Classic, Sakura, Ninja and Robot, in the **Mascot** tab. A style changes the mascot's
  face and how it shows up, celebrates and leaves; the settings window only takes its colors.
  - **Sakura**: big shiny eyes with lashes, a cherry blossom on the antenna, a heart-shaped shine and a flower clip.
    Floats in on a gust of petals and celebrates with hearts.
  - **Ninja**: mask with a red headband and determined brows, plus a skin tone of your choice. Rolls in hidden in a
    smoke cloud that bursts into a guard pose, and throws a shuriken when a task is done.
  - **Robot**: visor with light-up eyes, speaker mouth and bolts. Flies in on rocket boots, lands and boots up, and
    takes off when it leaves.
  - Every style still slides in from the edge; Classic looks and moves exactly as before.
  - Each style keeps its own color, and the outfit works with all of them. Five new colors (Shadow, Steel, Crimson,
    Forest, Night); the swatches are now sorted by hue, with the neutrals on their own row.
  - The settings preview now shows the whole notice: it slides in, shows the card for the chosen duration and leaves.

- **Notifications on your phone through Telegram**, with Wave animated (a GIF of each state), from the official bot
  **@WaveNotificationBot**. New **Phone** tab in the settings: tap **Connect Telegram**, Telegram opens with a one-time
  code and you tap **Start**. Nothing to create or paste.
  - By default it only sends when you're away from the computer (no mouse or keyboard for 3 minutes, adjustable), so
    you don't get everything twice. Mute and Do Not Disturb apply too.
  - Pick which notices go to the phone (done, needs something, sub-agent, usage limit, API error) and whether they
    include the GIF. A custom image is sent instead of the drawn mascot.
  - Sent from a separate process, so the network never slows down Claude Code; a permission request that arrives as
    two events is sent once. Send /stop to the bot or tap **Disconnect** to stop.
  - **Allow or deny permissions from Telegram**: when Claude asks for permission and you're away, the message shows
    the full command with **Allow** and **Deny** buttons, and your answer goes straight back to Claude Code. Whatever
    comes first wins (the phone, Wave's buttons or the terminal) and the other side updates itself. Waits up to
    9 minutes (adjustable); the permission hook timeout is now 600 s.
  - The bot's token lives only on a small Cloudflare Worker (`servidor/`); each installation gets its own key that can
    only message the chat it linked. Messages are relayed, not stored.

- **Update notice**: WaveMascot checks GitHub at most once a day. When there's a new version, Wave says so once
  (with **Update** and **Not now**), a small "⬇ version" pill appears next to the language flag in the settings and
  the tray menu offers **Update to version…**. On Windows, **Update** downloads the installer, checks it against
  `SHA256SUMS.txt` and installs it silently, keeping your settings; on macOS it opens the download page. Releases now
  include this version's CHANGELOG section, which the app shows as "what's new".

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
