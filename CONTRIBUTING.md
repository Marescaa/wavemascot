# Contributing to WaveMascot

Thanks for helping! English, Spanish and Portuguese are all welcome, in issues, discussions and pull requests.

## Questions, ideas and reports

- **Got a question or an idea?** Post it in [Discussions](../../discussions): chat, propose new outfits or states and
  share your setups.
- **Something doesn't work?** Open an [issue](../../issues/new/choose) with the bug template (add the last lines of
  the log, without private data).
- **Want to propose something specific?** Use the idea template in [issues](../../issues/new/choose).

English, Spanish and Portuguese are all welcome. Pull requests too: before sending one, run the tests
(`python -m unittest discover tests`), described below.

## Development

```powershell
python -m unittest discover tests          # installer, translations, styles, phone and update tests
powershell -ExecutionPolicy Bypass -File .\build.ps1   # builds dist\WaveMascot-Setup.exe (on Windows)
./build-mac.sh                             # builds dist/WaveMascot-Mac-<chip>.dmg (on a Mac)
python tools/capturas.py                   # redraws the screenshots and GIFs in docs/ from the real app
```

Pushing a `v*` tag (for example `v1.2.0`) makes GitHub Actions build the Windows installer and both Mac `.dmg` files
and attach them to the release, with that version's CHANGELOG section as the notes. Every push to `main` runs the
tests on Windows and macOS.

| File | What it is |
|---|---|
| `mascota.py` | The hook and the mascot window |
| `ajustes.py` | The settings window |
| `bandeja.py` | The tray / menu bar icon |
| `sprites.py` | The pixel art, the styles, the icons and the sounds (all generated in code) |
| `celular.py` | Notices and permissions on Telegram (client of the Worker) |
| `actualizacion.py` | Checks GitHub for a new version, downloads it and installs it |
| `idiomas.py` | The texts in English, Spanish and Portuguese |
| `ventanas.py` | Windows and macOS windows: host terminal, focus, full screen, monitors |
| `instalador.py` | Install / uninstall (hook merge with backup); also the `.exe` installer and the Mac app's first run |
| `principal.py` | Entry point of `WaveMascot.exe` and `WaveMascot.app` |
| `servidor/` | The Cloudflare Worker behind @WaveNotificationBot |
| `tools/capturas.py` | Makes the images in `docs/` (offscreen, without touching your settings) |

**Adding a language**: add it to `IDIOMAS` in `idiomas.py` and one translation per text; `tests/test_idiomas.py` tells
you if any is missing.
