# Guía de instalación

[← Volver al README](../README.es.md) · [English](install.md) · **Español** · [Português](install.pt.md)

Necesitás [Claude Code](https://docs.claude.com/en/docs/claude-code) (CLI, extensión o app de escritorio) y Windows
10 u 11, o macOS 13 (Ventura) o superior.

## Windows

### Opción A: instalador (recomendada, no necesita Python)

1. **[Descargá `WaveMascot-Setup.exe`](../../../releases/latest/download/WaveMascot-Setup.exe)** (siempre la
   última versión; también está en [Releases](../../../releases/latest)).
2. Abrilo y tocá **Sí**. Se instala en `%LOCALAPPDATA%\Programs\WaveMascot`, sin permisos de administrador.
3. Listo: la próxima vez que Claude Code termine, aparece la mascota. Si ya tenías Claude Code abierto, no hace falta
   reiniciarlo. Para verla en español, abrí los ajustes y elegí la banderita.

> Windows SmartScreen puede mostrar «Windows protegió su PC». Elegí **Más información → Ejecutar de todas formas**,
> o usá la opción B si preferís instalar desde el código. Podés verificar el archivo con el `SHA256SUMS.txt` del
> release.

### Opción B: desde el código fuente (Python 3.10 o superior)

1. Descargá el código: [ZIP](../../../archive/refs/heads/main.zip) (descomprimilo) o
   `git clone https://github.com/Marescaa/wavemascot.git`.
2. Abrí PowerShell en esa carpeta y corré:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1
   ```

`install.ps1` instala PyQt6 y Pillow solo si faltan. Opciones: `-Python <ruta a python.exe>`, `-Destino <carpeta>`,
`-SinInicio` (sin ícono al iniciar Windows).

## Mac

### Opción A: la app (recomendada, no necesita Python)

Necesitás macOS 13 (Ventura) o más nuevo, en cualquier Mac.

1. **Descargá el archivo de tu Mac.** Para saber cuál: menú Apple → **Acerca de esta Mac**.
   - Dice **Chip: Apple M1, M2, M3, M4…** → **[`WaveMascot-Mac-AppleSilicon.dmg`](../../../releases/latest/download/WaveMascot-Mac-AppleSilicon.dmg)**
   - Dice **Procesador: Intel** → **[`WaveMascot-Mac-Intel.dmg`](../../../releases/latest/download/WaveMascot-Mac-Intel.dmg)**
2. **Abrí el `.dmg`** (doble click en Descargas). Se abre una ventana con WaveMascot y la carpeta Aplicaciones:
   **arrastrá WaveMascot sobre Aplicaciones**. Después podés expulsar el disco WaveMascot desde el costado del Finder.
3. **Abrí WaveMascot** desde Aplicaciones (o con Spotlight: <kbd>⌘</kbd> <kbd>Espacio</kbd> y escribí *WaveMascot*).
   La primera vez macOS la bloquea porque la app no está notarizada por Apple (eso requiere una cuenta paga de
   desarrollador):
   - **macOS 15 (Sequoia) o más nuevo**: aparece *«Apple no pudo verificar que "WaveMascot" esté libre de malware…»*.
     Tocá **OK**, abrí **Ajustes del Sistema → Privacidad y seguridad**, bajá hasta **Seguridad** y tocá
     **Abrir de todos modos** al lado de *«Se bloqueó "WaveMascot"…»*. Confirmá con **Abrir de todos modos** y tu
     contraseña o Touch ID.
   - **macOS 13 o 14**: click derecho (o <kbd>Control</kbd> + click) en WaveMascot dentro de Aplicaciones → **Abrir**,
     y otra vez **Abrir**.

   Hace falta una sola vez; las actualizaciones y los hooks no lo vuelven a pedir.
4. WaveMascot pregunta **«¿Instalar WaveMascot?»**: tocá **Sí**. Se conecta con Claude Code y te cuenta qué hizo.
5. Listo: el ícono de Wave aparece en la **barra de menús** (arriba a la derecha). Tocalo → **Probar aviso** para
   verla. Desde ahora aparece cada vez que Claude Code termina o necesita algo, en la terminal, en VS Code o en la app
   de Claude. Si ya tenías Claude Code abierto, no hace falta reiniciarlo. Para verla en español, abrí los ajustes y
   elegí la banderita.

<p align="center">
  <img src="mac-instalar.es.png" alt="WaveMascot en macOS: el cuadro «¿Instalar WaveMascot 1.2.0?» y el menú del ícono en la barra de menús" width="760">
</p>

Bueno saber:

- **No pide ningún permiso** (ni Accesibilidad, ni Grabación de pantalla, ni notificaciones).
- Si la abrís directo desde el `.dmg` sin arrastrarla, se copia sola a Aplicaciones.
- **Ajustes**: ícono de la barra de menús → **Abrir ajustes**, `/wavemascot` en Claude Code, o abriendo WaveMascot
  otra vez desde Aplicaciones.
- **Actualizar**: descargá el `.dmg` nuevo, arrastrá WaveMascot sobre Aplicaciones (**Reemplazar**) y abrila una vez.
- La primera vez macOS muestra *«Ítems en segundo plano añadidos»*: es el ícono de la barra de menús que se abre al
  iniciar sesión. Se apaga en los ajustes de WaveMascot o en **Ajustes del Sistema → General → Ítems de inicio**.
- Para verificar la descarga: `shasum -a 256 ~/Downloads/WaveMascot-Mac-*.dmg` tiene que coincidir con el
  `SHA256SUMS.txt` del release.

### Opción B: desde el código fuente (Python 3.10 o superior)

```bash
git clone https://github.com/Marescaa/wavemascot.git
cd wavemascot
./install.sh
```

`install.sh` crea su propio entorno de Python con PyQt6 y Pillow (tu Python no se toca). Opciones:
`--python <ruta a python3>`, `--destination <carpeta>`, `--no-startup` (sin ícono en la barra de menús al iniciar
sesión).

## Qué hace el instalador en tu compu

- **Copia el programa** a `%LOCALAPPDATA%\Programs\WaveMascot` (Windows) o deja la app en **Aplicaciones** (Mac; si
  la abrís directo desde el `.dmg`, se copia sola ahí).
- **Conecta a Wave con Claude Code**: agrega unas líneas (los *hooks*) a `~/.claude/settings.json` para que Claude
  Code la llame cuando termina o necesita algo. Lo que ya tenías en ese archivo no se toca, y antes de cambiarlo se
  guarda una copia de seguridad.
- **Crea el comando `/wavemascot`**, que abre los ajustes desde Claude Code.
- **Pone el ícono de Wave junto al reloj** (Windows) o **en la barra de menús** (Mac, como ítem de inicio) cada vez
  que prendés la compu.

No pide permisos de administrador, y si la desinstalás, todo vuelve a quedar como estaba.

## Desinstalación

- **Windows, instalada con el `.exe`**: menú Inicio → *WaveMascot* → **Desinstalar WaveMascot**.
- **Windows, instalada con `install.ps1`** (o cualquiera de las dos):

  ```powershell
  powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
  ```

- **Mac**: ícono de Wave en la barra de menús → **Desinstalar WaveMascot…** (o `./uninstall.sh`, de cualquiera de las
  dos formas). Si solo arrastrás la app a la papelera, Claude Code sigue andando normal: sus hooks no hacen nada
  mientras la app no esté.

La desinstalación cierra la mascota, quita **solo sus hooks** de `~/.claude/settings.json` (con backup previo; los
tuyos quedan exactamente como estaban), borra `/wavemascot`, los accesos directos y el programa. Tu configuración en
`~/.wavemascot` se conserva; para borrarla también: `uninstall.ps1 -BorrarConfig` o `uninstall.sh --delete-settings`.

## Problemas frecuentes

- **No aparece**: mirá `~/.wavemascot/mascota.log`; cada evento dice si se avisó o por qué no (pantalla completa,
  no molestar, terminal enfocada, evento apagado...). Con el ícono de Wave → *Probar aviso* se fuerza uno.
- **Los hooks no corren**: revisá en Claude Code con `/hooks` que estén los de la mascota.
- **Permitir/Denegar**: en la app de escritorio el diálogo propio sigue apareciendo; vale la primera respuesta.
- **Mac: «No se puede abrir WaveMascot» o «Apple no pudo verificar…»**: mirá el paso 3 de
  [Instalación → Mac](#mac).
- **Mac: no veo el ícono en la barra de menús**: en las Mac con notch, los íconos que no entran se esconden; cerrá
  alguna otra app de la barra o abrí los ajustes con `/wavemascot`. Si lo cerraste, abrí WaveMascot desde Aplicaciones.
- **Mac: me llegan dos avisos**: apagá las notificaciones de tu terminal o de la app de Claude en **Ajustes del
  Sistema → Notificaciones**, así te avisa solo Wave.
- **Telegram: no llega nada**: por defecto los avisos solo van al celular si hace 3 minutos que no usás la compu;
  apagá «Solo si no estoy usando la compu» para probar. Si bloqueaste el bot o le mandaste `/stop`, volvé a conectar
  desde la pestaña **Celular**.
