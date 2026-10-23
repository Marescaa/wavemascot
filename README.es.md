<div align="center">

[English](README.md) · **Español** · [Português](README.pt.md)

<br>

<img src="docs/capturas/es/portada.gif" alt="Wave pidiendo permiso en la compu, y el mismo pedido aprobado desde Telegram" width="780">

# WaveMascot

**Una mascota de escritorio en pixel art que te avisa cuando Claude Code termina, o te necesita.**

[![Latest release](https://img.shields.io/github/v/release/Marescaa/wavemascot?style=flat-square&label=release&color=d97757)](../../releases/latest)
[![Downloads](https://img.shields.io/github/downloads/Marescaa/wavemascot/total?style=flat-square&color=4c8bf5)](../../releases)
![Windows | macOS](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-5b6470?style=flat-square)
[![License](https://img.shields.io/github/license/Marescaa/wavemascot?style=flat-square&color=5b6470)](LICENSE)

<a href="../../releases/latest/download/WaveMascot-Setup.exe"><img src="https://img.shields.io/badge/Descargar-Windows-0a66c2?style=for-the-badge" alt="Descargar para Windows"></a>
<a href="../../releases/latest/download/WaveMascot-Mac-AppleSilicon.dmg"><img src="https://img.shields.io/badge/Descargar-Mac%20(chip%20Apple)-1f1f1f?style=for-the-badge" alt="Descargar para Mac con chip Apple"></a>
<a href="../../releases/latest/download/WaveMascot-Mac-Intel.dmg"><img src="https://img.shields.io/badge/Descargar-Mac%20(Intel)-1f1f1f?style=for-the-badge" alt="Descargar para Mac con Intel"></a>

</div>

<br>

Wave aparece desde el borde de la pantalla cuando **Claude Code** termina, pide permiso o se queda sin uso, te dice de
qué chat y proyecto se trata, y se va sola. Si no estás en la compu, te escribe al celular por Telegram y desde ahí
podés **permitir o denegar**.

## Qué hace

- **Un aviso para cada momento**: terminó, necesita permiso, está pensando, terminó un subagente, límite de uso y
  errores de la API, cada uno con su animación y su sonido.
- **Permitir o denegar sin ir a la terminal**, desde los botones de Wave o desde el celular.
- **El contexto justo**: chat, proyecto, cuánto tardó y un resumen de una línea. Los avisos de varias sesiones se encolan.
- **No molesta**: horario de no molestar, nada sobre apps en pantalla completa ni si ya estás mirando la terminal.
- **A tu gusto**: cuatro estilos (Clásico, Sakura, Ninja, Robot), colores, vestuario, tu propia imagen y sonidos.
- **Modo compañera**: Wave vive chiquita sobre la barra de tareas o el Dock, pasea y se duerme cuando llegás al límite.
- **Inglés, español y portugués**, varios monitores y actualizaciones automáticas en Windows.

<p align="center">
  <img src="docs/estilos.gif" alt="Los cuatro estilos festejando: Clásico, Sakura, Ninja y Robot" width="640">
  <br>
  <a href="docs/README.es.md"><b>Ver la galería →</b></a>
</p>

## Instalación

Necesitás [Claude Code](https://docs.claude.com/en/docs/claude-code) (CLI, extensión o app de escritorio).

**Windows 10 / 11**: bajá [`WaveMascot-Setup.exe`](../../releases/latest/download/WaveMascot-Setup.exe), abrilo y
hacé click en **Sí**. No necesita permisos de administrador ni Python. Si aparece SmartScreen, elegí
**Más información → Ejecutar de todas formas**.

**macOS 13 o superior**: bajá el `.dmg` de tu Mac
([chip Apple](../../releases/latest/download/WaveMascot-Mac-AppleSilicon.dmg) ·
[Intel](../../releases/latest/download/WaveMascot-Mac-Intel.dmg)), arrastrá WaveMascot a Aplicaciones y abrilo. La
primera vez macOS te pide confirmar porque la app no está notarizada: [así se hace](docs/install.es.md#mac).

Listo: la próxima vez que Claude Code termine, aparece Wave. No hace falta reiniciar nada.

La [guía de instalación](docs/install.es.md) explica cómo instalar desde el código, qué cambia el instalador, cómo
desinstalar y los problemas frecuentes.

## Ajustes

Hacé click en el **ícono de Wave** (junto al reloj en Windows, en la barra de menús en Mac) o escribí
**`/wavemascot`** en Claude Code. Los cambios se guardan solos y la vista previa muestra el aviso tal cual se va a ver.

<p align="center">
  <img src="docs/capturas/es/ajustes-3-mascota.png" alt="Ventana de ajustes, pestaña Mascota, con la vista previa" width="720">
</p>

<details>
<summary><b>Qué tiene cada pestaña</b></summary>

| Pestaña | Qué cambiás |
|---|---|
| Notificación | Esquina, tiempo en pantalla, qué muestra el aviso y sus mensajes |
| Comportamiento | Modo aviso o compañera, qué eventos avisan, no molestar, duración mínima, Permitir/Denegar |
| Mascota | Estilo, color, tono de piel, tamaño y tu propia imagen |
| Vestuario | Cabeza, ropa y accesorios |
| Sonido y estilo | Volumen, sonido por evento, tema, ícono junto al reloj, actualizaciones |
| Celular | Telegram: cuándo mandar, qué avisos, Permitir/Denegar desde el celular |

Todo se guarda en `~/.wavemascot/config.json`. Consejo: apagá las notificaciones propias de Claude Code para que no
te lleguen dos.

</details>

## En tu celular

Abrí la pestaña **Celular**, tocá **Conectar con Telegram** y después **Iniciar** en el chat con
[@WaveNotificationBot](https://t.me/WaveNotificationBot). No hay nada que crear ni pegar.

Por defecto solo te escribe si hace 3 minutos que no estás en la compu. Los pedidos de permiso llegan con
**Permitir** y **Denegar**, y gana la primera respuesta: el celular, Wave o la terminal.

## Privacidad

Todo corre en tu compu. El resumen se lee localmente del transcript que Claude Code ya guarda en tu disco. WaveMascot
solo se conecta a internet para buscar en GitHub si hay una versión nueva (como mucho una vez por día) y, si lo
conectás, para mandar avisos a Telegram. Las dos cosas se pueden apagar.

Para Telegram, la clave del bot vive solo en un pequeño [Worker de Cloudflare](servidor/) que pasa cada mensaje sin
guardarlo, y cada instalación tiene su propia llave, que solo puede escribirle al chat que vinculó. Se manda lo que
muestra el aviso (mensaje, resumen, proyecto, título del chat, comando a aprobar). Mandale `/stop` al bot o tocá
**Desconectar** para cortarlo.

## Colaborar

Las preguntas e ideas van a [Discussions](../../discussions) y los errores a [Issues](../../issues/new/choose). Los
pull requests son bienvenidos, en español, inglés o portugués: mirá [CONTRIBUTING.md](CONTRIBUTING.md).

## Licencia

[MIT](LICENSE). Los instaladores incluyen PyQt6 (GPL v3) y otras bibliotecas; ver [THIRD_PARTY.md](THIRD_PARTY.md).

<sub>WaveMascot es un proyecto no oficial: no está hecho, avalado ni mantenido por Anthropic. La mascota, el ícono y
los sonidos son originales y se generan por código.</sub>
