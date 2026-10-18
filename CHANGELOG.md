# Changelog

Todos los cambios importantes del proyecto. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el proyecto usa [versionado semántico](https://semver.org/lang/es/).

## [1.0.0] - 2026-10-18

Primera versión pública de WaveMascot.

### Agregado

- Mascota en pixel art que reemplaza la notificación de Windows de Claude Code: entra desde el borde de la pantalla,
  muestra el chat, el proyecto, la duración y un resumen de la respuesta, y se va sola o con un click.
- Estados `listo`, `permiso`, `pensando`, `subagente`, `limite` y `error`, con animación y sonido propios.
- Permitir / Denegar desde la mascota con el hook `PermissionRequest`; botón para enfocar la terminal.
- Modo compañera: chiquita sobre la barra de tareas, con paseos, mirada que sigue al cursor y siesta al llegar al
  límite de uso.
- Centro de ajustes con vista previa en vivo, ícono junto al reloj y comando `/wavemascot`.
- Vestuario (colores, cabezas, ropa, accesorios), imagen propia, tamaños, temas oscuro / claro / acento y sonido por
  evento.
- No molestar por horario, en pantalla completa y con la terminal enfocada; duración mínima para avisar.
- Varias sesiones de Claude Code a la vez: cada aviso muestra su proyecto y los avisos de otras sesiones se encolan.
- Varios monitores: el aviso sale en el monitor de la ventana de Claude Code.
- Funciona sin `config.json` (valores por defecto) y sin dispositivo de audio; los errores van al log y nunca
  bloquean a Claude Code.
- `install.ps1` / `uninstall.ps1`: merge de hooks en `~/.claude/settings.json` con backup previo, sin tocar los
  existentes; la desinstalación deja el archivo como estaba.
- Instalador `WaveMascot-Setup.exe` (PyInstaller, sin Python ni permisos de administrador) y workflow de
  GitHub Actions que lo publica en cada tag `v*`.

[1.0.0]: ../../releases/tag/v1.0.0
