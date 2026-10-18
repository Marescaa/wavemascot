# Assets y software de terceros

## Sprites, ícono y sonidos: todos originales

No hay imágenes, sonidos, fuentes ni logos de Anthropic ni de nadie más en este repositorio.

| Asset | Origen |
|---|---|
| Mascota (todos los estados, vestuario y accesorios) | Pixel art original dibujado como matrices de píxeles en [`sprites.py`](sprites.py). Los GIF se generan en tu equipo la primera vez que hacen falta (`~/.wavemascot/cache`). |
| `assets/icono.ico` | Generado por `sprites.py` (`icono_bandeja`) a partir del mismo pixel art. |
| `assets/sonidos/*.wav` | Sintetizados por `sprites.py` (ondas senoidales con armónicos y envolvente); no son grabaciones ni samples. Se regeneran con `python sprites.py`. |
| `assets/ui/flecha-*.svg` | Flechas de las listas desplegables, escritas a mano (un solo `path`). |
| Tipografía | Segoe UI, la fuente del sistema de Windows; no se incluye en el repositorio ni en el `.exe`. |

Atribuciones requeridas por los assets: **ninguna**. Todo se publica bajo la [licencia MIT](LICENSE) del proyecto.

## Software de terceros

El código fuente del proyecto es MIT. Para correr desde el código fuente se instalan aparte:

| Paquete | Licencia | Uso |
|---|---|---|
| [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) | GPL v3 | Ventanas, animación, sonido |
| [Pillow](https://python-pillow.github.io/) | MIT-CMU (HPND) | Generar los GIF de la mascota |

### Qué incluye el `.exe`

`WaveMascot-Setup.exe` se arma con [PyInstaller](https://pyinstaller.org) e incluye:

| Componente | Licencia |
|---|---|
| Python | PSF License |
| PyQt6 | GPL v3 |
| Qt 6 (Core, Gui, Widgets, Network, Multimedia, Svg) | LGPL v3 |
| FFmpeg (backend de Qt Multimedia) | LGPL v2.1 o posterior |
| Pillow | MIT-CMU (HPND) |
| OpenSSL (`libcrypto`, usado por `hashlib` de Python) | Apache 2.0 |
| libffi | MIT |
| Bootloader de PyInstaller | GPL v2 o posterior, con excepción para el bootloader |
| Microsoft Visual C++ Runtime | Redistribuible de Microsoft |

Como el ejecutable incluye PyQt6 (GPL v3), **el `.exe` en conjunto se distribuye bajo los términos de la GPL v3**. El
código fuente completo y las instrucciones para construirlo (`build.ps1`) están en este repositorio. El código propio
sigue siendo MIT, que es compatible con la GPL v3. Los textos de las licencias van junto al programa instalado, en
la carpeta `licencias`.
