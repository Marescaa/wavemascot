# WaveMascot gallery

Every image here is drawn from the app itself by [`tools/capturas.py`](../tools/capturas.py): the real pixel art, the
real notice card and the real settings window, rendered offscreen. The only exception is `telegram.gif`, an
illustration of the Telegram chat (Telegram's look is recreated; Wave's GIF and the texts are the real ones).

To redraw everything after changing the art or the interface:

```bash
python tools/capturas.py
```

## The mascot

| | |
|---|---|
| [`estados.gif`](estados.gif) | The six states: done, permission, thinking, sub-agent, usage limit, error |
| [`estilos.gif`](estilos.gif) | The four styles celebrating: Classic, Sakura, Ninja, Robot |
| [`estilos/`](estilos) | Each style slides in, celebrates and leaves |
| [`vestuario.gif`](vestuario.gif) | Six outfit combinations |

<p align="center">
  <img src="estados.gif" alt="The six states" width="760"><br>
  <img src="estilos.gif" alt="The four styles" width="760"><br>
  <img src="vestuario.gif" alt="Outfits" width="760">
</p>

## Notices and settings, in each language

[English](capturas/en) · [Español](capturas/es) · [Português](capturas/pt)

| File | What it shows |
|---|---|
| `aviso-<state>.gif` | The notice for each state (`listo`, `permiso`, `pensando`, `subagente`, `limite`, `error`) |
| `ajustes-1-aviso.png` … `ajustes-6-celular.png` | Each tab of the settings window |
| `telegram.gif` | Illustration: a notice and a permission approved from Telegram |

| | | |
|---|---|---|
| <img src="capturas/en/aviso-listo.gif" width="250" alt="Done"> | <img src="capturas/en/aviso-permiso.gif" width="250" alt="Permission"> | <img src="capturas/en/aviso-pensando.gif" width="250" alt="Thinking"> |
| <img src="capturas/en/aviso-subagente.gif" width="250" alt="Sub-agent"> | <img src="capturas/en/aviso-limite.gif" width="250" alt="Usage limit"> | <img src="capturas/en/aviso-error.gif" width="250" alt="Error"> |

| | |
|---|---|
| <img src="capturas/en/ajustes-1-aviso.png" width="380" alt="Notice tab"> | <img src="capturas/en/ajustes-2-comportamiento.png" width="380" alt="Behavior tab"> |
| <img src="capturas/en/ajustes-3-mascota.png" width="380" alt="Mascot tab"> | <img src="capturas/en/ajustes-4-vestuario.png" width="380" alt="Outfits tab"> |
| <img src="capturas/en/ajustes-5-sonido.png" width="380" alt="Sound and style tab"> | <img src="capturas/en/ajustes-6-celular.png" width="380" alt="Phone tab"> |

<p align="center"><img src="capturas/en/telegram.gif" width="320" alt="Telegram illustration"></p>

`mac-instalar.es.png` is a screenshot of the macOS first run (the "Install WaveMascot?" dialog and the menu bar icon).
