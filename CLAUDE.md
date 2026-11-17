# WaveMascot

Mascota de escritorio en pixel art (PyQt6) que avisa cuando Claude Code termina o necesita algo. Windows y macOS.
El código, los comentarios y los commits van en español rioplatense. Los tests se corren con
`python -m unittest discover -s tests`.

## Pendiente para la próxima sesión en la PC (Windows)

> Si esta sesión corre en la PC del usuario (Windows, no en un contenedor en la nube), **avisale apenas empiece** que
> esto quedó pendiente y ofrecé hacerlo. Si corre en la nube, solo mencionalo: las capturas tienen que salir de
> Windows, con el vidrio y el desenfoque de verdad. Cuando esté hecho, borrá esta sección.

**Regenerar las capturas del README y de la galería** (`docs/capturas/{en,es,pt}`, `docs/README*.md`). El texto de
los README ya describe la 1.4.0, pero las imágenes siguen siendo las de las 6 pestañas viejas
(`ajustes-1-aviso.png`, `ajustes-2-comportamiento.png`, `ajustes-4-vestuario.png`…), que ya no existen.

1. Actualizar `tools/capturas.py`:
   - Ya recorre `ajustes.PAGINAS`, así que saca las 7 secciones (avisos, mascota, celular, isla, dashboard, uso,
     general). Los nombres de archivo cambian: `ajustes-1-avisos.png` … `ajustes-7-general.png`.
   - Dashboard y Uso salen vacíos porque el script usa una carpeta de usuario temporal: hay que escribir transcripts de
     ejemplo en `<casa temporal>/.claude/projects/<proyecto>/<sesion>.jsonl` (líneas `user` / `assistant` con
     `message.usage`, `model` y `timestamp`, y un `system` con `subtype: stop_hook_summary` al final de cada turno;
     ver `tests/test_estadisticas.py`) y esperar unos segundos a que el análisis termine antes de capturar.
   - Sumar la **Dynamic Island**: `barra.Barra(seguimiento.Monitor(None, carpeta), leer=False)`, cargar sesiones de
     ejemplo en `b.lector.foto = (time.time(), sesiones)` y el uso en `b.lector.uso = {"5h":…, "7d":…, "serie":[…]}`
     (ver `tests/test_ojos.py`, `OpcionesDeLaIsla`). Capturas: la pastilla chica, la isla abierta y, si se puede, un GIF
     corto abriéndose. En Windows, encima de un fondo de escritorio para que se vea el desenfoque.
   - Sumar el estilo **Hamburguesa** (beta) a la galería de estilos y a `docs/estilos.gif` si corresponde.
2. Correr `python tools/capturas.py` en Windows y revisar las imágenes.
3. Actualizar las referencias a las capturas en `README.md`, `README.es.md`, `README.pt.md` (la imagen de Ajustes) y en
   `docs/README.md`, `docs/README.es.md`, `docs/README.pt.md` (la tabla de pestañas pasa a secciones; agregar Dynamic
   Island, Dashboard y Uso).
4. Borrar las capturas viejas que ya no se usen.

**Revisar también antes del release 1.4.0:** el CHANGELOG no menciona lo del PR #3 (barra lateral, tabla de eventos,
probador, animaciones con resortes, 9 sonidos nuevos), y la isla nunca se probó a mano en macOS.
