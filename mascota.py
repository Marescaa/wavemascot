#!/usr/bin/env python3
"""Mascota de escritorio que avisa cuando Claude Code termina o necesita algo.

Uso:
    pythonw mascota.py --estado listo|permiso|error [--mensaje TEXTO] [--detalle TEXTO]
                       [--duracion SEGUNDOS] [--esquina arriba-derecha|abajo-derecha|...]

Como hook, Claude Code le pasa el evento en JSON por stdin. Este proceso solo lee
el evento, lanza la ventana en un proceso desacoplado y sale enseguida, así nunca
bloquea a Claude Code. Si ya hay una mascota en pantalla, la nueva la reemplaza.

Los ajustes (ajustes.py) se guardan en ~/.wavemascot/config.json y se leen en
cada aviso; si el archivo no existe se usan los valores por defecto.

Con el hook PermissionRequest el proceso no se desacopla: espera a que elijas
"Permitir" o "Denegar" en la mascota y le devuelve la decisión a Claude Code.
`--compania` abre la mascota en modo compañera (queda fija en pantalla).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

import idiomas
import sprites
import ventanas
from idiomas import t

__version__ = "1.4.6"
CONGELADO = getattr(sys, "frozen", False)  # corriendo como WaveMascot.exe o WaveMascot.app (PyInstaller)
MAC = ventanas.ES_MAC
DIR = Path(__file__).resolve().parent
# Empaquetado, los assets viven en la carpeta interna de PyInstaller.
ASSETS = Path(getattr(sys, "_MEIPASS", DIR)) / "assets"

SONIDOS = ASSETS / "sonidos"
CONFIG_DIR = Path.home() / ".wavemascot"
CONFIG = CONFIG_DIR / "config.json"
LOG = CONFIG_DIR / "mascota.log"  # junto a la config: la carpeta del programa puede no ser escribible
IMAGENES = CONFIG_DIR / "imagenes"  # PNG/GIF propios subidos desde ajustes
PEDIDOS = CONFIG_DIR / "permisos"    # los pedidos de permiso que muestra la Dynamic Island (pedidos.py)
SESIONES = CONFIG_DIR / "sesiones"  # cuándo empezó la tarea de cada sesión (para la duración)
INDEFINIDO = 4_102_444_800  # 1/1/2100: "silenciada hasta que la reactive" (el botón No molestar)


def migrar_config_anterior() -> None:
    """Antes de llamarse WaveMascot la config vivía en ~/.claude-mascota: se copia una sola vez."""
    anterior = Path.home() / ".claude-mascota"
    if CONFIG_DIR.exists() or not anterior.is_dir():
        return
    try:
        shutil.copytree(anterior, CONFIG_DIR, ignore=shutil.ignore_patterns("cache", "sesiones", "*.log*"))
    except OSError:
        pass  # otro proceso la está copiando, o no se puede: se sigue con los valores por defecto


migrar_config_anterior()

ESTADOS = {
    "listo": {"mensaje": "¡Listo!", "acento": "#7BD389"},
    "permiso": {"mensaje": "Necesito tu permiso", "acento": "#FFD166"},
    "error": {"mensaje": "Algo salió mal", "acento": "#E5484D"},
    "pensando": {"mensaje": "Pensando…", "acento": "#A99CF5"},
    "subagente": {"mensaje": "Terminó un subagente", "acento": "#5BC0F8"},
    "limite": {"mensaje": "Llegué al límite de uso", "acento": "#FFA94D"},
    "idle": {"mensaje": "", "acento": "#B3A39A"},  # la compañera descansando
}
ALIAS = {
    "necesita-permiso": "permiso", "necesita_permiso": "permiso", "necesita permiso": "permiso",
    "permission": "permiso", "notification": "permiso", "stop": "listo", "done": "listo",
    "triste": "error", "thinking": "pensando", "subagent": "subagente", "limit": "limite",
    "límite": "limite", "reposo": "idle",
}
TEMAS = ("oscuro", "claro", "acento")
MODOS = ("aviso", "compania")
EVENTOS = ("Stop", "Notification", "UserPromptSubmit", "SubagentStop", "StopFailure")
NO_SE_APRUEBAN = ("AskUserQuestion", "ExitPlanMode")  # no son permisos de verdad: los responde la terminal
# Lo más que el hook PermissionRequest espera tu respuesta en Telegram: Claude Code lo corta a los 600 s
# (el timeout que pone el instalador), así que queda margen para devolver la decisión.
ESPERA_TELEGRAM_MAX = 540
ESQUINAS = ("arriba-derecha", "arriba-izquierda", "abajo-derecha", "abajo-izquierda")

PIXEL_ASSET = sprites.ESCALA  # cada pixel de arte ocupa 4x4 en los GIF dibujados
LADO_ARTE = sprites.LADO       # lado de la grilla de la mascota, en píxeles de arte
TAMANOS = (2, 5)  # px lógicos por pixel de arte: de chica a enorme
EVENTO_POR_ESTADO = {"listo": "Stop", "permiso": "Notification", "pensando": "UserPromptSubmit",
                     "subagente": "SubagentStop", "limite": "StopFailure", "error": "StopFailure"}
CONFIG_DEFECTO = {
    "esquina": "arriba-derecha",
    "duracion": 5,
    "sonido": True,
    "volumen": 60,
    "mensajes": {"Stop": "", "Notification": ""},  # vacío = el texto automático, en tu idioma
    "aspecto": dict(sprites.ASPECTO_DEFECTO),  # color y vestuario de la mascota dibujada
    "imagen": "",                              # nombre de una imagen propia; vacío = mascota dibujada
    "tamano": 3,
    "silenciado_hasta": 0,                     # hora (epoch) hasta la que no se muestran avisos
    # Qué muestra el cartel debajo del mensaje.
    "contenido": {"resumen": True, "chat": True, "proyecto": True, "duracion": True},
    # Qué eventos avisan (UserPromptSubmit = "pensando").
    "eventos": {evento: True for evento in EVENTOS},
    "no_molestar": {"activo": False, "desde": "22:00", "hasta": "08:00", "pantalla_completa": True},
    "omitir_si_enfocada": True,   # no avisar si la terminal/editor de Claude ya tiene el foco
    "umbral_segundos": 0,         # no avisar "listo" si la tarea duró menos que esto
    "permisos_desde_mascota": True,
    "espera_permiso": 30,         # segundos que la mascota espera tu respuesta antes de dejarlo a la terminal
    "boton_enfocar": True,
    "modo": "aviso",              # "aviso": aparece y se va; "compania": queda fija en pantalla
    "posicion": None,             # [x, y] si arrastraste a la compañera; None = la esquina elegida
    # Compañera: animaciones de reposo, ojos que siguen al cursor, esperar chiquita parada sobre la
    # barra de tareas y dar una caminatita de vez en cuando.
    "vida": {"idle": True, "mirada": True, "chiquita": True, "pasear": True},
    "sonidos": {"listo": "arpegio", "permiso": "doble", "pensando": "ninguno", "subagente": "pop",
                "limite": "grave", "error": "triste"},
    "tema": "oscuro",
    "idioma": idiomas.POR_DEFECTO,  # en, es o pt: la banderita de los ajustes
    # Avisos a Telegram (celular.py) por el bot oficial: la llave de esta instalación en el servidor y el
    # nombre de quien la vinculó en Telegram.
    "celular": {"activo": False, "llave": "", "conectado": False, "nombre": "", "solo_ausente": True, "minutos": 3,
                "gif": True, "estados": {"listo": True, "permiso": True, "subagente": False, "limite": True,
                                         "error": True},
                # Permitir / Denegar desde Telegram, y cuántos segundos se espera tu respuesta.
                "permisos": True, "espera_permisos": 240},
    # Buscar versiones nuevas (actualizacion.py); "ignorada": la versión a la que le dijiste "Ahora no".
    "actualizaciones": {"buscar": True, "ignorada": ""},
    # La barra de sesiones arriba al centro (barra.py): siempre a la vista (menos en pantalla completa);
    # se puede apagar desde el menú del ícono.
    # Sus opciones se eligen en los ajustes (sección Dynamic Island).
    "barra": {"activa": True,
              "pantalla_completa": True,   # esconderse si hay algo en pantalla completa
              "esconder_sin_chats": True,  # irse si ningún chat se movió en un rato (vuelve con el próximo)
              "minutos_sin_chats": 10,     # ese rato, en minutos (1 a 120)
              "abrir": "mouse",            # se estira al pasarle el mouse ("mouse") o recién al tocarla ("clic")
              "posicion": "centro",        # arriba al centro, a la izquierda o a la derecha
              "ojos": True,                # los ojos de la mascota (si no, un punto de color)
              "seguir_mouse": True,        # los ojos miran al mouse cuando anda cerca
              "tiempo": True,              # el tiempo que falta, en la pastilla
              "sesiones": True,            # cuántas sesiones hay, en la pastilla
              "uso": True,                 # el uso de 5 horas y 7 días, al pie de la isla abierta
              "filas": 5,                  # cuántas sesiones se listan como mucho (3, 5 u 8)
              "saltar": True,              # un clic en una sesión trae su ventana al frente
              "desenfoque": True,          # el vidrio desenfoca lo de atrás (Windows)
              "opacidad": 68,              # cuánto tapa el vidrio, en % (40 a 95)
              "rebote": True,              # se estira rebotando, como un líquido
              "latido": True,              # el color de la mascota late mientras Claude trabaja
              "permisos": True},           # Permitir / Denegar en la pastilla cuando Claude pide permiso
    # La sección Uso de los ajustes: el lapso que se estaba mirando (5h, hoy, 7d, 30d o 180d).
    "uso": {"lapso": "hoy"},
}
CANAL = "wavemascot-" + re.sub(r"\W", "", os.environ.get("USERNAME") or os.environ.get("USER") or "yo")


def log(texto: str) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)  # recién instalada todavía no existe
        if LOG.exists() and LOG.stat().st_size > 256_000:
            os.replace(LOG, LOG.with_suffix(".log.1"))  # se guarda el anterior, no crece sin límite
        with LOG.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} [{os.getpid()}] {texto}\n")
    except OSError:
        pass


# --- configuración y skins -------------------------------------------------------

def cargar_config(ruta: Path = CONFIG) -> dict:
    """Lee la configuración; lo que falte o sea inválido toma el valor por defecto."""
    config = json.loads(json.dumps(CONFIG_DEFECTO))  # copia profunda
    try:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return config
    except (OSError, ValueError) as e:
        log(f"no se pudo leer {ruta} ({e}); uso los valores por defecto")
        return config
    if not isinstance(datos, dict):
        return config
    if datos.get("esquina") in ESQUINAS:
        config["esquina"] = datos["esquina"]
    for clave, tipo, minimo, maximo in (("duracion", float, 1, 60), ("volumen", int, 0, 100),
                                         ("tamano", int, *TAMANOS)):
        try:
            config[clave] = min(maximo, max(minimo, tipo(datos[clave])))
        except (KeyError, TypeError, ValueError):
            pass
    if isinstance(datos.get("sonido"), bool):
        config["sonido"] = datos["sonido"]
    viejo = str(datos.get("skin") or "")  # configuraciones de la versión con skins fijos
    aspecto = datos.get("aspecto") if isinstance(datos.get("aspecto"), dict) else sprites.PRESETS.get(viejo)
    config["aspecto"] = sprites.normalizar(aspecto)
    imagen = datos.get("imagen", viejo.split(":", 1)[1] if viejo.startswith("propio:") else "")
    if isinstance(imagen, str):
        config["imagen"] = Path(imagen).name if imagen else ""
    try:
        config["silenciado_hasta"] = max(0.0, float(datos.get("silenciado_hasta", 0)))
    except (TypeError, ValueError):
        pass
    if isinstance(datos.get("mensajes"), dict):
        for evento in config["mensajes"]:
            if isinstance(datos["mensajes"].get(evento), str):
                config["mensajes"][evento] = datos["mensajes"][evento]
    for evento, texto in config["mensajes"].items():  # los de antes por defecto: ahora salen en tu idioma
        if texto.strip() in ("¡Listo! Terminé", "{mensaje}"):
            config["mensajes"][evento] = ""
    # Grupos de opciones: se copia cada valor que tenga el mismo tipo que el de por defecto.
    for grupo in ("contenido", "eventos", "no_molestar", "vida", "sonidos", "actualizaciones", "barra", "uso"):
        if isinstance(datos.get(grupo), dict):
            for clave, defecto in config[grupo].items():
                if type(datos[grupo].get(clave)) is type(defecto):
                    config[grupo][clave] = datos[grupo][clave]
    isla, isla_defecto = config["barra"], CONFIG_DEFECTO["barra"]
    for clave, validos in (("abrir", ("mouse", "clic")), ("posicion", ("centro", "izquierda", "derecha")),
                           ("filas", (3, 5, 8))):
        if isla[clave] not in validos:
            isla[clave] = isla_defecto[clave]
    isla["opacidad"] = max(40, min(95, isla["opacidad"]))
    isla["minutos_sin_chats"] = max(1, min(120, isla["minutos_sin_chats"]))
    if config["uso"]["lapso"] not in ("5h", "hoy", "7d", "30d", "180d"):  # "1d" ya no existe: pasa a "hoy"
        config["uso"]["lapso"] = CONFIG_DEFECTO["uso"]["lapso"]
    for clave in ("desde", "hasta"):
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", config["no_molestar"][clave]):
            config["no_molestar"][clave] = CONFIG_DEFECTO["no_molestar"][clave]
    for estado, sonido in config["sonidos"].items():
        if sonido != "ninguno" and sonido not in sprites.SONIDOS:
            config["sonidos"][estado] = CONFIG_DEFECTO["sonidos"][estado]
    for clave in ("omitir_si_enfocada", "permisos_desde_mascota", "boton_enfocar"):
        if isinstance(datos.get(clave), bool):
            config[clave] = datos[clave]
    for clave, minimo, maximo in (("umbral_segundos", 0, 3600), ("espera_permiso", 5, 120)):
        try:
            config[clave] = min(maximo, max(minimo, int(datos[clave])))
        except (KeyError, TypeError, ValueError):
            pass
    if datos.get("modo") in MODOS:
        config["modo"] = datos["modo"]
    if datos.get("tema") in TEMAS:
        config["tema"] = datos["tema"]
    if datos.get("idioma") in idiomas.IDIOMAS:
        config["idioma"] = datos["idioma"]
    posicion = datos.get("posicion")
    if isinstance(posicion, list) and len(posicion) == 2 and all(isinstance(v, int) for v in posicion):
        config["posicion"] = posicion
    celular = datos.get("celular")
    if isinstance(celular, dict):
        cel = config["celular"]
        for clave, defecto in cel.items():
            if clave != "estados" and type(celular.get(clave)) is type(defecto):
                cel[clave] = celular[clave]
        cel["minutos"] = min(60, max(1, cel["minutos"]))
        cel["espera_permisos"] = min(ESPERA_TELEGRAM_MAX, max(60, cel["espera_permisos"]))
        if isinstance(celular.get("estados"), dict):
            for estado in cel["estados"]:
                if isinstance(celular["estados"].get(estado), bool):
                    cel["estados"][estado] = celular["estados"][estado]
    return config


def guardar_config(config: dict, ruta: Path = CONFIG) -> None:
    """Escribe de forma atómica, así un aviso nunca lee un archivo a medio escribir."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(f"{ruta.stem}.{os.getpid()}.tmp")  # varios procesos pueden guardar
    temporal.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporal, ruta)


def silenciada(config: dict) -> bool:
    return config["silenciado_hasta"] > time.time()


def no_molestar_ahora(config: dict) -> bool:
    """El botón No molestar: silenciada sin hora de fin (el horario de No molestar de los ajustes es otra cosa)."""
    return config["silenciado_hasta"] >= INDEFINIDO


def listar_imagenes() -> list[Path]:
    """Las imágenes propias subidas desde ajustes."""
    if not IMAGENES.is_dir():
        return []
    return sorted(p for p in IMAGENES.iterdir() if p.suffix.lower() in (".png", ".gif"))


def ruta_sprite(aspecto: dict, imagen: str, estado: str, mirada=None) -> tuple[Path, int | None]:
    """Archivo del sprite y tamaño de su pixel de arte (None para imágenes propias).

    Una imagen propia se usa para todos los estados; si no hay, se dibuja la mascota
    con su vestuario (queda en caché, así la próxima vez es instantáneo)."""
    if imagen:
        archivo = IMAGENES / Path(imagen).name
        if archivo.is_file():
            return archivo, None
    return sprites.gif(aspecto, estado, mirada), PIXEL_ASSET


def normalizar_estado(valor: str) -> str:
    v = ALIAS.get(valor.strip().lower(), valor.strip().lower())
    if v not in ESTADOS:
        raise argparse.ArgumentTypeError(f"estado inválido: {valor!r} (opciones: {', '.join(ESTADOS)})")
    return v


def parsear(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Mascota de escritorio para los avisos de Claude Code.")
    p.add_argument("--estado", type=normalizar_estado, default="listo", help="listo | permiso | error")
    p.add_argument("--mensaje", help="texto principal (por defecto se arma con el evento)")
    p.add_argument("--detalle", help="línea secundaria (por defecto, el título del chat o el proyecto)")
    p.add_argument("--duracion", type=float, help="segundos en pantalla (por defecto, el de la config)")
    p.add_argument("--esquina", choices=ESQUINAS, help="por defecto, la de la config")
    p.add_argument("--config", type=Path, default=CONFIG, help=f"archivo de ajustes (default {CONFIG})")
    p.add_argument("--forzar", action="store_true", help="mostrar aunque los avisos estén silenciados")
    p.add_argument("--compania", action="store_true", help="abrir la mascota en modo compañera")
    p.add_argument("--ui", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--aviso", help=argparse.SUPPRESS)  # JSON que el lanzador le pasa a la ventana
    return p.parse_args(argv)


# --- modo hook: leer el evento y lanzar la ventana desacoplada ----------------

def leer_evento(espera: float = 1.5) -> dict:
    """Lee el JSON que manda Claude Code por stdin, sin colgarse si no llega nada."""
    entrada = sys.stdin
    if entrada is None:
        return {}
    try:
        if entrada.isatty():
            return {}
    except (OSError, ValueError):
        return {}
    resultado: dict = {}

    def leer():
        datos = b""
        while True:
            trozo = entrada.buffer.read1(65536)
            if not trozo:
                break
            datos += trozo
            try:
                resultado.update(json.loads(datos.decode("utf-8")))
                return
            except ValueError:
                continue

    hilo = threading.Thread(target=leer, daemon=True)
    hilo.start()
    hilo.join(espera)
    return resultado


def traducir_notificacion(mensaje: str, tipo: str) -> str:
    m = re.search(r"needs your permission to use (.+?)\.?$", mensaje)
    if m and m.group(1) == "AskUserQuestion":
        return t("Tengo una pregunta para vos")
    if m:
        return t("Necesito permiso para usar {herramienta}", herramienta=m.group(1))
    if tipo == "idle_prompt" or "waiting for your input" in mensaje.lower():
        return t("Te estoy esperando")
    if tipo == "permission_prompt" or "needs your permission" in mensaje:
        return t("Necesito tu permiso")
    return mensaje


def mensaje_para(estado: str, evento: dict) -> str:
    nombre = evento.get("hook_event_name")
    if nombre == "Notification":
        texto = traducir_notificacion(evento.get("message") or "", evento.get("notification_type") or "")
        return texto or t(ESTADOS[estado]["mensaje"])
    if nombre == "Stop":
        return t("¡Listo! Terminé")
    if nombre == "SubagentStop" and evento.get("agent_type"):
        return t("Terminó el subagente {nombre}", nombre=evento["agent_type"])
    if nombre == "StopFailure" and estado == "error":
        return t("Error de la API ({error})", error=evento.get("error") or t("desconocido"))
    if nombre == "PermissionRequest":
        return t("¿Permitir {herramienta}?", herramienta=evento.get("tool_name") or t("esta acción"))
    return t(ESTADOS[estado]["mensaje"])


def texto_corto(texto: str, largo: int = 140) -> str:
    """Primera idea de un texto en markdown, sin formato y en una sola línea."""
    texto = re.sub(r"```.*?(```|$)", " ", texto or "", flags=re.S)       # bloques de código
    texto = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", texto)                # [texto](enlace)
    texto = re.sub(r"[*_`#>|]+", "", texto)
    texto = " ".join(texto.split())
    fin = re.search(r"(?<=[.!?:])\s", texto[:largo + 1])
    if fin and fin.start() >= 30:
        texto = texto[:fin.start()]
    return texto if len(texto) <= largo else texto[:largo - 1].rstrip() + "…"


def ultimo_mensaje_del_transcript(ruta: str) -> str:
    """Texto de la última respuesta de Claude en el transcript (si el evento no lo trae)."""
    try:
        with open(ruta, "rb") as f:
            f.seek(max(0, f.seek(0, os.SEEK_END) - 400_000))
            lineas = f.read().splitlines()
    except (OSError, TypeError):
        return ""
    for linea in reversed(lineas):
        if b'"assistant"' not in linea:
            continue
        try:
            d = json.loads(linea)
        except ValueError:
            continue
        partes = (d.get("message") or {}).get("content")
        if isinstance(partes, list):
            texto = " ".join(p.get("text", "") for p in partes if isinstance(p, dict) and p.get("type") == "text")
            if texto.strip():
                return texto
    return ""


def hora_de_reinicio(texto: str, ahora: datetime | None = None) -> float | None:
    """A qué hora se renueva el límite de uso, según el texto del error ("resets 3pm", "|1760000000")."""
    ahora = ahora or datetime.now()
    m = re.search(r"\|(\d{10})\b", texto or "")
    if m:
        return float(m.group(1))
    m = re.search(r"(?:resets?|reinicia|renueva)\D{0,12}?(\d{1,2})(?::(\d{2}))?\s*([ap]\.?\s?m\.?)?", texto or "", re.I)
    if not m:
        return None
    hora, minuto = int(m.group(1)), int(m.group(2) or 0)
    sufijo = (m.group(3) or "").lower().replace(".", "").replace(" ", "")
    if sufijo == "pm" and hora < 12:
        hora += 12
    elif sufijo == "am" and hora == 12:
        hora = 0
    if hora > 23 or minuto > 59:
        return None
    reinicio = ahora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
    if reinicio <= ahora:  # "3pm" ya pasó hoy: es mañana
        reinicio += timedelta(days=1)
    return reinicio.timestamp()


def resumen_para(evento: dict) -> str:
    nombre = evento.get("hook_event_name")
    if nombre in ("Stop", "SubagentStop"):
        return texto_corto(evento.get("last_assistant_message")
                           or ultimo_mensaje_del_transcript(evento.get("transcript_path")))
    if nombre == "StopFailure":
        return texto_corto(evento.get("last_assistant_message") or evento.get("error_details") or "")
    if nombre == "UserPromptSubmit":
        prompt = re.sub(r"<pasted_content[^>]*>.*?</pasted_content[^>]*>", "[texto pegado]",
                        evento.get("prompt") or "", flags=re.S)
        return texto_corto(prompt, 90)
    if nombre == "PermissionRequest":
        return texto_corto(detalle_permiso(evento), 120)
    return ""


def detalle_permiso(evento: dict) -> str:
    """Qué quiere hacer la herramienta: el comando, el archivo, la URL... completo (para Telegram)."""
    entrada = evento.get("tool_input") or {}
    return next((entrada[c].strip() for c in ("command", "file_path", "url", "pattern", "description", "prompt")
                 if isinstance(entrada.get(c), str) and entrada[c].strip()), "")


# --- duración de la tarea ----------------------------------------------------------

def archivo_sesion(evento: dict) -> Path | None:
    sesion = re.sub(r"[^\w-]", "", str(evento.get("session_id") or ""))
    return SESIONES / f"{sesion}.json" if sesion else None


def registrar_inicio(evento: dict, ventana: int = 0) -> None:
    """UserPromptSubmit: anota cuándo empezó la tarea (y en qué ventana corre la sesión, para que la barra
    de sesiones pueda saltar a ella) y limpia sesiones viejas."""
    archivo = archivo_sesion(evento)
    if not archivo:
        return
    try:
        SESIONES.mkdir(parents=True, exist_ok=True)
        proceso = ventanas.pid_de_ventana(ventana) if ventana and ventanas.ES_WINDOWS else 0
        archivo.write_text(json.dumps({"inicio": time.time(), "ventana": int(ventana or 0), "proceso": proceso}),
                           encoding="utf-8")
        for viejo in SESIONES.glob("*.json"):
            if time.time() - viejo.stat().st_mtime > 3 * 86400:
                viejo.unlink(missing_ok=True)
    except OSError as e:
        log(f"no se pudo anotar el inicio de la tarea: {e}")


def inicio_desde_transcript(ruta: str) -> float | None:
    """Hora del último mensaje que escribiste vos (no las respuestas de herramientas)."""
    try:
        with open(ruta, "rb") as f:
            f.seek(max(0, f.seek(0, os.SEEK_END) - 2_000_000))
            lineas = f.read().splitlines()
    except (OSError, TypeError):
        return None
    for linea in reversed(lineas):
        if b'"type":"user"' not in linea.replace(b" ", b""):
            continue
        try:
            d = json.loads(linea)
        except ValueError:
            continue
        if d.get("isMeta") or not isinstance((d.get("message") or {}).get("content"), str):
            continue  # resultados de herramientas y mensajes internos
        try:
            return datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00")).timestamp()
        except (KeyError, ValueError):
            continue
    return None


def duracion_tarea(evento: dict) -> float | None:
    """Segundos desde que mandaste el mensaje hasta ahora, o None si no se sabe."""
    archivo, inicio = archivo_sesion(evento), None
    try:
        inicio = json.loads(archivo.read_text(encoding="utf-8"))["inicio"] if archivo else None
    except (OSError, ValueError, KeyError):
        pass
    inicio = inicio or inicio_desde_transcript(evento.get("transcript_path"))
    return max(0.0, time.time() - inicio) if inicio else None


def sesiones_activas(minutos: int = 30) -> int:
    """Cuántas sesiones de Claude Code recibieron un mensaje en los últimos minutos."""
    try:
        return sum(1 for a in SESIONES.glob("*.json") if time.time() - a.stat().st_mtime < minutos * 60)
    except OSError:
        return 0


def formato_duracion(segundos: float) -> str:
    s = round(segundos)
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s // 60} min {s % 60:02d} s"
    return f"{s // 3600} h {s % 3600 // 60:02d} min"


# --- reglas de cuándo avisar ----------------------------------------------------

def en_franja(desde: str, hasta: str, ahora: datetime | None = None) -> bool:
    """¿La hora actual cae entre desde y hasta? (la franja puede cruzar la medianoche)"""
    ahora = ahora or datetime.now()
    minuto = ahora.hour * 60 + ahora.minute
    a, b = (int(h) * 60 + int(m) for h, m in (desde.split(":"), hasta.split(":")))
    return a <= minuto < b if a <= b else minuto >= a or minuto < b


def motivo_para_no_avisar(config: dict, evento: dict, estado: str, duracion: float | None,
                          anfitriona: int) -> str:
    """Devuelve por qué no hay que mostrar este aviso, o "" si hay que mostrarlo."""
    nombre = evento.get("hook_event_name") or ""
    if nombre in config["eventos"] and not config["eventos"][nombre]:
        return f"el evento {nombre} está desactivado"
    if nombre == "PermissionRequest" and not config["permisos_desde_mascota"]:
        return "aprobar permisos desde la mascota está desactivado"
    if silenciada(config):
        return f"avisos silenciados hasta {datetime.fromtimestamp(config['silenciado_hasta']):%d/%m %H:%M}"
    nm = config["no_molestar"]
    if nm["activo"] and en_franja(nm["desde"], nm["hasta"]):
        return f"no molestar ({nm['desde']}-{nm['hasta']})"
    if nm["pantalla_completa"] and ventanas.pantalla_completa():
        return "hay algo en pantalla completa"
    if config["omitir_si_enfocada"] and anfitriona and ventanas.tiene_el_foco(anfitriona):
        return "la terminal de Claude ya tiene el foco"
    if estado == "listo" and duracion is not None and duracion < config["umbral_segundos"]:
        return f"la tarea duró {duracion:.0f} s (umbral {config['umbral_segundos']} s)"
    return ""


def motivo_para_no_mandar_al_celular(config: dict, evento: dict, estado: str,
                                     inactivo: float | None = None) -> str:
    """Por qué este aviso no va a Telegram, o "" si va. inactivo: segundos sin tocar mouse ni teclado."""
    cel = config["celular"]
    if not (cel["activo"] and cel["llave"] and cel["conectado"]):
        return "Telegram no está activado"
    nombre = evento.get("hook_event_name") or ""
    if nombre in config["eventos"] and not config["eventos"][nombre]:
        return f"el evento {nombre} está desactivado"
    if not cel["estados"].get(estado):
        return f"Telegram no avisa «{estado}»"
    if silenciada(config):
        return "avisos silenciados"
    nm = config["no_molestar"]
    if nm["activo"] and en_franja(nm["desde"], nm["hasta"]):
        return f"no molestar ({nm['desde']}-{nm['hasta']})"
    if cel["solo_ausente"] and inactivo is not None and inactivo < cel["minutos"] * 60:
        return f"estás en la compu (última actividad hace {inactivo:.0f} s)"
    return ""


def mandar_al_celular(aviso: dict) -> None:
    """Lanza celular.py desacoplado: la conexión con Telegram nunca demora a Claude Code."""
    lanzar_desacoplado([str(DIR / "celular.py"), "--aviso=" + json.dumps(aviso, ensure_ascii=False)])


def aplicar_plantilla(plantilla: str, valores: dict) -> str:
    """Reemplaza {mensaje}, {proyecto} y {chat}; cualquier otra llave queda tal cual."""
    return re.sub(r"\{(mensaje|proyecto|chat)\}", lambda m: valores.get(m.group(1), ""), plantilla).strip()


def mensaje_configurado(estado: str, evento: dict, config: dict, chat: str, proy: str) -> str:
    automatico = mensaje_para(estado, evento)
    plantilla = config["mensajes"].get(evento.get("hook_event_name") or EVENTO_POR_ESTADO.get(estado), "")
    if not plantilla.strip():
        return automatico
    return aplicar_plantilla(plantilla, {"mensaje": automatico, "proyecto": proy, "chat": chat}) or automatico


def proyecto(evento: dict) -> str:
    cwd = evento.get("cwd") or ""
    return Path(cwd).name or cwd


def ultimo_titulo(datos: bytes) -> str:
    for linea in reversed(datos.splitlines()):
        if b'"customTitle"' not in linea and b'"aiTitle"' not in linea and b'"summary"' not in linea:
            continue
        try:
            d = json.loads(linea)
        except ValueError:  # p. ej. la primera línea, cortada al leer solo el final
            continue
        valor = d.get("customTitle") or d.get("aiTitle") or (d.get("summary") if d.get("type") == "summary" else "")
        if isinstance(valor, str) and valor.strip():
            return " ".join(valor.split())
    return ""


def titulo_del_chat(evento: dict) -> str:
    """El título del chat (el que muestra Claude Code), tomado del transcript.

    Se reescribe a lo largo de la sesión, así que casi siempre está cerca del final:
    se busca primero en el último MB y solo si no aparece se lee el archivo entero.
    """
    ruta = evento.get("transcript_path")
    if not ruta:
        return ""
    try:
        with open(ruta, "rb") as f:
            tam = f.seek(0, os.SEEK_END)
            for desde in dict.fromkeys((max(0, tam - 1_000_000), 0)):
                f.seek(desde)
                titulo = ultimo_titulo(f.read())
                if titulo:
                    return titulo
    except OSError:
        pass
    return ""


def bundle_app() -> Path | None:
    """macOS empaquetada: la carpeta WaveMascot.app desde la que corre este proceso."""
    if not (MAC and CONGELADO):
        return None
    return next((p for p in Path(sys.executable).resolve().parents if p.suffix == ".app"), None)


def reabrir_app() -> None:
    """macOS: abrieron WaveMascot.app estando ya abierta (ver ventanas.al_reabrir). La app vuelve a pasar
    por la apertura normal, que abre los ajustes o, si arrastraste una versión nueva, la actualiza.
    Desde el código fuente se abren los ajustes."""
    app = bundle_app()
    if not app:
        lanzar_desacoplado([str(DIR / "ajustes.py")])
        return
    subprocess.Popen(["/usr/bin/open", "-n", "-a", str(app)], start_new_session=True, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def lanzar_desacoplado(cmd: list[str], suelto: bool = False) -> None:
    """Lanza un proceso sin consola que sobrevive y no retiene a quien lo llamó.

    cmd empieza con el script (p. ej. ".../ajustes.py"); empaquetado como .exe se traduce
    a "WaveMascot.exe ajustes ..." (ver principal.py). suelto=True (macOS): el proceso queda
    sin padre, así el desinstalador puede cerrar al ícono que lo abrió."""
    exe = Path(sys.executable)
    programa = Path(cmd[0]).stem
    if MAC and programa == "ajustes" and "--ventana" not in cmd:
        cmd = [*cmd, "--ventana"]  # en macOS no hace falta el paso intermedio del lanzador
    if CONGELADO:
        cmd = [str(exe), programa, *cmd[1:]]
    else:
        if os.name == "nt" and exe.name.lower() == "python.exe" and exe.with_name("pythonw.exe").exists():
            exe = exe.with_name("pythonw.exe")  # sin ventana de consola
        cmd = [str(exe), *cmd]
    # Sin heredar stdin/stdout/stderr: Claude Code espera a que se cierren esos pipes.
    opciones = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, cwd=str(Path(sys.executable).parent if CONGELADO else DIR),
                    close_fds=True)
    app = bundle_app()
    if app and programa == "ajustes":
        # Abierta por LaunchServices, la ventana de ajustes aparece adelante y con foco (como en Windows).
        try:
            subprocess.Popen(["/usr/bin/open", "-n", "-a", str(app), "--args", *cmd[1:]], start_new_session=True,
                             **opciones)
            return
        except OSError:
            pass
    if os.name != "nt":
        if suelto:
            cmd = ["/bin/sh", "-c", '"$@" &', "sh", *cmd]
        subprocess.Popen(cmd, start_new_session=True, **opciones)
        return
    base = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        subprocess.Popen(cmd, creationflags=base | subprocess.CREATE_BREAKAWAY_FROM_JOB, **opciones)
    except OSError:  # el job de Claude Code no permite salir de él
        subprocess.Popen(cmd, creationflags=base, **opciones)


# --- instancia única -----------------------------------------------------------

class Candado:
    """Mutex con nombre (en macOS, un archivo con flock): lo tiene la mascota que está en pantalla.
    Si esa mascota se cierra de golpe, el sistema lo suelta solo."""

    def __init__(self):
        self.handle = None
        self.k32 = None
        self.archivo = None
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            self.k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self.k32.CreateMutexW.restype = wintypes.HANDLE
            self.k32.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
            self.k32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
            self.k32.WaitForSingleObject.restype = wintypes.DWORD
            self.k32.ReleaseMutex.argtypes = (wintypes.HANDLE,)
            self.k32.CloseHandle.argtypes = (wintypes.HANDLE,)

    def tomar(self) -> bool:
        if os.name != "nt":
            return self.tomar_archivo()
        if self.k32 is None:
            return True
        h = self.k32.CreateMutexW(None, False, "Local\\" + CANAL)
        if not h:
            return True  # sin mutex no se puede coordinar: mostrar igual
        if self.k32.WaitForSingleObject(h, 0) in (0x0, 0x80):  # WAIT_OBJECT_0 / WAIT_ABANDONED
            self.handle = h
            return True
        self.k32.CloseHandle(h)
        return False

    def tomar_archivo(self) -> bool:
        import fcntl

        try:  # junto a la config: los procesos que abre launchd pueden no tener la misma carpeta temporal
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            fd = os.open(CONFIG_DIR / "mascota.lock", os.O_RDWR | os.O_CREAT, 0o600)
        except OSError:
            return True  # sin candado no se puede coordinar: mostrar igual
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            return False
        self.archivo = fd
        return True

    def soltar(self) -> None:
        if self.archivo is not None:
            os.close(self.archivo)  # cerrar el archivo suelta el flock
            self.archivo = None
        if self.handle:
            self.k32.ReleaseMutex(self.handle)
            self.k32.CloseHandle(self.handle)
            self.handle = None


def escuchar(servidor, canal: str) -> bool:
    """QLocalServer.listen; en macOS, si quedó el archivo de un proceso que se cerró de golpe, se lo saca.
    Solo se llama después de comprobar que nadie responde en ese canal."""
    from PyQt6.QtNetwork import QLocalServer

    if servidor.listen(canal):
        return True
    QLocalServer.removeServer(canal)
    return servidor.listen(canal)


# --- piezas de dibujo y sonido (también las usa la vista previa de ajustes.py) ----

def fuente(puntos: int, peso=None):
    """Segoe UI en Windows. En macOS, la letra del sistema con los mismos píxeles: macOS cuenta
    72 puntos por pulgada y Windows 96, así el cartel y los ajustes quedan del mismo tamaño."""
    from PyQt6.QtGui import QFont, QFontDatabase

    if not MAC:
        return QFont("Segoe UI", puntos) if peso is None else QFont("Segoe UI", puntos, peso)
    letra = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
    letra.setPixelSize(round(puntos * 96 / 72))
    if peso is not None:
        letra.setWeight(peso)
    return letra


def sprite_de_reserva(tamano: int, dpr: float):
    from PyQt6.QtCore import QRectF, Qt
    from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPixmap

    lado = int(LADO_ARTE * tamano * dpr)
    img = QImage(lado, lado, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#D97757"))
    p.setPen(QPen(QColor("#2B1A14"), 4 * dpr))
    p.drawEllipse(QRectF(lado * 0.27, lado * 0.45, lado * 0.46, lado * 0.42))
    p.end()
    pm = QPixmap.fromImage(img)
    pm.setDevicePixelRatio(dpr)
    return pm


def cargar_cuadros(aspecto: dict, imagen: str, estado: str, tamano: int, dpr: float, mirada=None) -> list:
    """Cuadros (QPixmap, ms) del sprite. El pixel art se agranda sin suavizar."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QImageReader, QPixmap

    try:
        ruta, pixel = ruta_sprite(aspecto, imagen, estado, mirada)
    except Exception:
        log("no se pudo dibujar la mascota:\n" + traceback.format_exc())
        return [(sprite_de_reserva(tamano, dpr), 1000)]
    lector = QImageReader(str(ruta))
    caja = round(LADO_ARTE * tamano * dpr)  # lado máximo en px físicos
    rapido = Qt.TransformationMode.FastTransformation
    cuadros = []
    while len(cuadros) < 300:
        img = lector.read()
        if img.isNull():
            break
        ms = lector.nextImageDelay() or 100
        lado = max(img.width(), img.height())
        if pixel and img.width() % pixel == 0 and img.height() % pixel == 0:
            img = img.scaled(img.width() // pixel, img.height() // pixel, transformMode=rapido)
            k = max(1, round(tamano * dpr))
            img = img.scaled(img.width() * k, img.height() * k, transformMode=rapido)
        elif lado * 2 <= caja:  # imagen propia chica: seguramente pixel art
            k = caja // lado
            img = img.scaled(img.width() * k, img.height() * k, transformMode=rapido)
        else:
            img = img.scaled(caja, caja, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        pm = QPixmap.fromImage(img)
        pm.setDevicePixelRatio(dpr)
        cuadros.append((pm, max(20, ms)))
    if not cuadros:
        log(f"no se pudo leer {ruta}: {lector.errorString()}")
        cuadros = [(sprite_de_reserva(tamano, dpr), 1000)]
    return cuadros


def pintar_sombra(p, cx: float, base: float, ancho: float) -> None:
    from PyQt6.QtCore import QPointF, Qt
    from PyQt6.QtGui import QBrush, QColor, QRadialGradient

    centro, r = QPointF(cx, base - 4), ancho * 0.3
    sombra = QRadialGradient(centro, r)
    sombra.setColorAt(0, QColor(0, 0, 0, 80))
    sombra.setColorAt(1, QColor(0, 0, 0, 0))
    p.save()
    p.translate(centro)
    p.scale(1, 0.18)
    p.translate(-centro)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(sombra))
    p.drawEllipse(centro, r, r)
    p.restore()


FONDO_CARTEL = {"clasico": (30, 22, 19), "sakura": (34, 22, 28), "ninja": (22, 22, 24), "robot": (18, 25, 32),
                "hamburguesa": (32, 23, 17)}


class Cartel:
    """Mide y dibuja el cartel de vidrio debajo de la mascota: mensaje, resumen, datos y botones."""

    ANCHO_TEXTO = 236
    RELLENO = 19        # margen del texto a cada lado
    MARGEN_ARRIBA, MARGEN_ABAJO, ALTO_BOTON = 13, 16, 28
    RADIO = 22.0
    ADENTRO = RADIO * 0.2929 + 0.2  # el desenfoque es rectangular: metido esto, su esquina no asoma del redondeo
    ALFA_SOLO, ALFA_VIDRIO = 0.93, 0.76  # cuánto tapa el tinte sin desenfoque atrás y con él
    BOTONES = {"permitir": "Permitir", "denegar": "Denegar", "enfocar": "Ir a la terminal",
               "actualizar": "Actualizar", "ahora_no": "Ahora no"}

    def __init__(self):
        from PyQt6.QtGui import QFont

        self.fuente = fuente(11, QFont.Weight.DemiBold)
        self.fuente_resumen = fuente(9)
        self.fuente_meta = fuente(8)
        self.fuente_boton = fuente(9, QFont.Weight.DemiBold)
        self.mensaje = self.resumen = self.meta = ""
        self.lineas: list[str] = []
        self.lineas_resumen: list[str] = []
        self.botones: list[str] = []
        self.terminal_icono = False
        self.anchos: dict[str, float] = {}
        self.zonas: dict[str, object] = {}  # botón -> rectángulo en coordenadas del widget
        self.tema = "oscuro"
        self.estilo = "clasico"  # en el tema oscuro, el fondo toma un tinte del estilo de la mascota
        self.alfa = self.ALFA_SOLO
        self.respondido = ""     # "allow" o "deny": el borde va pasando a verde o rojo
        self.avance_borde = 0.0  # de 0 (borde de vidrio) a 1 (todo el color)
        self.ancho = self.alto = self.texto_h = self.resumen_h = self.meta_h = 0.0

    def marcar(self, decision: str) -> None:
        self.respondido, self.avance_borde = decision, 0.0

    def renglones(self, texto: str, letra, maximo: int) -> list[str]:
        """Corta el texto en renglones: por palabras, y solo parte una si no entra sola (una ruta, un token), así
        el cartel no crece hasta salirse de la ventana. Si sobra texto, el último renglón termina en "…"."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QFontMetricsF, QTextLayout, QTextOption

        texto = texto.replace("\r", "").replace("\n", " ").strip()
        if not texto:
            return []
        capa = QTextLayout(texto, letra)
        opcion = QTextOption()
        # Con una palabra que no entra en un renglón se aprovecha todo el ancho (si no, "C:" quedaba solo arriba).
        medida = QFontMetricsF(letra)
        no_entra = any(medida.horizontalAdvance(palabra) > self.ANCHO_TEXTO for palabra in texto.split())
        opcion.setWrapMode(QTextOption.WrapMode.WrapAnywhere if no_entra else QTextOption.WrapMode.WordWrap)
        capa.setTextOption(opcion)
        capa.beginLayout()
        cortes = []
        while (linea := capa.createLine()).isValid():
            linea.setLineWidth(self.ANCHO_TEXTO)
            cortes.append((linea.textStart(), linea.textLength()))
        capa.endLayout()
        crudo = texto.encode("utf-16-le")  # Qt cuenta en unidades UTF-16 (un emoji ocupa dos)
        salida = [crudo[2 * i:2 * (i + n)].decode("utf-16-le").strip() for i, n in cortes[:maximo]]
        if len(cortes) > maximo:
            resto = crudo[2 * cortes[maximo - 1][0]:].decode("utf-16-le").strip()
            salida[-1] = medida.elidedText(resto, Qt.TextElideMode.ElideRight, self.ANCHO_TEXTO)
        return salida

    def medir(self, mensaje: str, resumen: str = "", meta: str = "", botones=()) -> None:
        from PyQt6.QtGui import QFontMetricsF

        self.zonas = {}  # hasta que se dibuje lo nuevo, ningún botón responde (Permitir no aprueba algo no mostrado)
        # Un JSON puede traer medio emoji ("\ud83d"): no se puede codificar, se muestra como �.
        mensaje, resumen, meta = (re.sub("[\ud800-\udfff]", "�", x) for x in (mensaje, resumen, meta))
        self.mensaje, self.resumen, self.meta = mensaje, resumen, meta
        self.botones = [b for b in botones if b in self.BOTONES]
        self.respondido, self.avance_borde = "", 0.0
        fm = QFontMetricsF(self.fuente)
        self.lineas = self.renglones(mensaje, self.fuente, 3)
        self.texto_h = fm.lineSpacing() * len(self.lineas)
        ancho = min(max((fm.horizontalAdvance(l) for l in self.lineas), default=0.0), self.ANCHO_TEXTO)
        self.resumen_h = self.meta_h = 0.0
        self.lineas_resumen = self.renglones(resumen, self.fuente_resumen, 2)
        if self.lineas_resumen:
            fr = QFontMetricsF(self.fuente_resumen)
            self.resumen_h = fr.lineSpacing() * len(self.lineas_resumen)
            ancho = max(ancho, min(max(fr.horizontalAdvance(l) for l in self.lineas_resumen), self.ANCHO_TEXTO))
        if meta:
            fmeta = QFontMetricsF(self.fuente_meta)
            self.meta_h = fmeta.lineSpacing()
            ancho = max(ancho, min(fmeta.horizontalAdvance(meta), self.ANCHO_TEXTO))
        fb = QFontMetricsF(self.fuente_boton)
        # Todo en un renglón: al lado de otros botones, "Ir a la terminal" es solo un ícono.
        self.terminal_icono = "enfocar" in self.botones and len(self.botones) > 1
        self.anchos = {b: 34.0 if b == "enfocar" and self.terminal_icono
                       else fb.horizontalAdvance(t(self.BOTONES[b])) + 26 for b in self.botones}
        if self.botones:
            ancho = max(ancho, sum(self.anchos.values()) + 6 * (len(self.botones) - 1))
        self.ancho = max(ancho + 1, 176) + 2 * self.RELLENO
        self.alto = (self.MARGEN_ARRIBA + self.texto_h + (3 + self.resumen_h if self.lineas_resumen else 0)
                     + (2 + self.meta_h if meta else 0) + (8 + self.ALTO_BOTON if self.botones else 0)
                     + self.MARGEN_ABAJO)

    def colores(self, acento) -> dict:
        from PyQt6.QtGui import QColor

        acento = QColor(acento)
        if self.tema == "claro":
            base = {"fondo": QColor(252, 248, 242, 246), "texto": QColor(43, 26, 20), "barra": acento,
                    "borde": QColor(acento.red(), acento.green(), acento.blue(), 190), "tinta": QColor(43, 26, 20)}
        elif self.tema == "acento":
            base = {"fondo": QColor(acento.red(), acento.green(), acento.blue(), 246), "texto": QColor(28, 21, 19),
                    "barra": QColor(28, 21, 19, 120), "borde": QColor(28, 21, 19, 60), "tinta": QColor(28, 21, 19)}
        else:
            base = {"fondo": QColor(*FONDO_CARTEL.get(self.estilo, FONDO_CARTEL["clasico"]), 236),
                    "texto": QColor(255, 247, 240), "barra": acento,
                    "borde": QColor(acento.red(), acento.green(), acento.blue(), 110), "tinta": QColor(255, 247, 240)}
        base["suave"], base["tenue"], base["boton"] = (QColor(base["tinta"]), QColor(base["tinta"]),
                                                       QColor(base["tinta"]))
        base["suave"].setAlpha(190)
        base["tenue"].setAlpha(135)
        base["boton"].setAlpha(28)
        base["principal"] = QColor(28, 21, 19) if self.tema == "acento" else acento
        base["texto_principal"] = QColor(255, 247, 240) if self.tema == "acento" else QColor(28, 21, 19)
        return base

    @staticmethod
    def hueco(sprite_h: float, imagen=None) -> float:
        """Distancia de la mascota al cartel: negativa para que quede parada sobre el vidrio (los sprites
        tienen dos filas libres bajo los pies; una imagen propia puede no tenerlas)."""
        return 2.0 if imagen else 1 - sprite_h * 2 / 56

    def pintar(self, p, cx: float, y: float, acento, fraccion: float) -> None:
        """Dibuja el cartel centrado en cx; fraccion es lo que queda de la línea de tiempo."""
        from PyQt6.QtCore import QPointF, QRectF, Qt
        from PyQt6.QtGui import (QBrush, QColor, QFontMetricsF, QLinearGradient, QPainterPath, QPen, QRadialGradient,
                                 QTransform)

        def con_alfa(color, alfa: float) -> QColor:
            nuevo = QColor(color)
            nuevo.setAlphaF(max(0.0, min(1.0, alfa)))
            return nuevo

        acento = QColor(acento)
        c = self.colores(acento)
        claro, de_acento = self.tema == "claro", self.tema == "acento"
        # En el tema acento el texto es oscuro: sobre el rojo de error no se leería, va un rojo más claro.
        tinte = QColor(244, 116, 120) if de_acento and acento.name() == ESTADOS["error"]["acento"].lower() else c["fondo"]
        tinta = QColor(c["tinta"])
        caja = QRectF(cx - self.ancho / 2, y, self.ancho, self.alto)
        forma = QPainterPath()
        forma.addRoundedRect(caja, self.RADIO, self.RADIO)

        # La sombra, solo por fuera: adentro se vería a través del vidrio.
        p.save()
        afuera = QPainterPath()
        afuera.addRect(caja.adjusted(-26, -26, 26, 26))
        p.setClipPath(afuera.subtracted(forma))
        sombra = forma.translated(0, 4)
        for i in range(6, 0, -1):
            p.strokePath(sombra, QPen(QColor(0, 0, 0, 10), i * 2.7))
        p.restore()

        p.fillPath(forma, con_alfa(tinte, self.alfa))
        p.save()
        p.setClipPath(forma)
        # El canto: ahí atrás no hay desenfoque, así que el vidrio se cierra hacia el borde.
        for grosor, alfa in ((self.ADENTRO * 2.3, 0.3), (self.ADENTRO * 1.45, 0.45), (self.ADENTRO * 0.6, 0.6)):
            p.strokePath(forma, QPen(con_alfa(tinte, alfa), grosor))
        brillo = QLinearGradient(0, caja.top(), 0, caja.bottom())
        brillo.setColorAt(0.0, QColor(255, 255, 255, 120 if claro else 44))
        brillo.setColorAt(0.42, QColor(255, 255, 255, 8))
        brillo.setColorAt(1.0, QColor(0, 0, 0, 22))
        p.fillRect(caja, brillo)
        if not de_acento:  # la luz del estado, bajo los pies de la mascota (late si pide permiso)
            latido = (0.82 + 0.18 * math.sin(time.monotonic() * 2.4)
                      if acento.name() == ESTADOS["permiso"]["acento"].lower() else 1.0)
            centro = QPointF(caja.center().x(), caja.top())
            luz = QRadialGradient(centro, caja.width() * 0.62)
            luz.setColorAt(0.0, con_alfa(acento, 0.36 * latido))
            luz.setColorAt(1.0, con_alfa(acento, 0.0))
            pincel = QBrush(luz)
            pincel.setTransform(QTransform().translate(centro.x(), centro.y()).scale(1, 0.34)
                                .translate(-centro.x(), -centro.y()))
            p.fillRect(caja, pincel)
        p.restore()

        # El borde de vidrio se va apagando mientras entra el verde o el rojo de la respuesta.
        k = self.avance_borde if self.respondido else 0.0
        if k < 1:
            borde = QLinearGradient(0, caja.top(), 0, caja.bottom())
            borde.setColorAt(0.0, QColor(255, 255, 255, round((240 if claro else 165) * (1 - k))))
            borde.setColorAt(0.55, QColor(255, 255, 255, round((125 if claro else 32) * (1 - k))))
            borde.setColorAt(1.0, QColor(255, 255, 255, round((205 if claro else 78) * (1 - k))))
            p.strokePath(forma, QPen(borde, 1.1))
        if k > 0:
            color = QColor("#62d58a" if self.respondido == "allow" else "#f0555b")
            p.save()
            p.setClipPath(forma)
            p.fillPath(forma, con_alfa(color, 0.08 * k))
            p.restore()
            p.strokePath(forma, QPen(con_alfa(color, 0.16 * k), 4.0))
            p.strokePath(forma, QPen(con_alfa(color, 0.95 * k), 1.1 + 0.6 * k))

        izq, ancho = caja.left() + self.RELLENO, caja.width() - 2 * self.RELLENO
        centrado = int(Qt.AlignmentFlag.AlignHCenter)
        fila = caja.top() + self.MARGEN_ARRIBA

        def escribir(lineas: list[str], letra, color, y: float) -> None:
            alto_linea = QFontMetricsF(letra).lineSpacing()
            p.setFont(letra)
            p.setPen(color)
            for i, linea in enumerate(lineas):
                p.drawText(QRectF(izq - 1, y + i * alto_linea, ancho + 2, alto_linea),
                           centrado | int(Qt.TextFlag.TextSingleLine), linea)

        escribir(self.lineas, self.fuente, c["texto"], fila)
        fila += self.texto_h
        if self.lineas_resumen:
            fila += 3
            escribir(self.lineas_resumen, self.fuente_resumen, con_alfa(tinta, 1.0 if de_acento else 0.9), fila)
            fila += self.resumen_h
        if self.meta:
            fila += 2
            fmeta = QFontMetricsF(self.fuente_meta)
            p.setFont(self.fuente_meta)
            p.setPen(con_alfa(tinta, 1.0 if de_acento else 0.78))
            p.drawText(QRectF(izq, fila, ancho, self.meta_h), centrado,
                       fmeta.elidedText(self.meta, Qt.TextElideMode.ElideRight, ancho))
            fila += self.meta_h
        self.zonas = {}
        if self.botones:
            fila += 8
            p.setFont(self.fuente_boton)
            x = cx - (sum(self.anchos.values()) + 6 * (len(self.botones) - 1)) / 2
            for clave in self.botones:
                zona = QRectF(x, fila, self.anchos[clave], self.ALTO_BOTON)
                principal = clave in ("permitir", "actualizar")
                capsula = QPainterPath()
                capsula.addRoundedRect(zona, self.ALTO_BOTON / 2, self.ALTO_BOTON / 2)
                p.fillPath(capsula, c["principal"] if principal else con_alfa(tinta, 0.15))
                p.save()
                p.setClipPath(capsula)
                p.setPen(QPen(QColor(255, 255, 255, 135 if principal else 62), 1))
                p.drawLine(QPointF(zona.left() + 9, zona.top() + 0.6), QPointF(zona.right() - 9, zona.top() + 0.6))
                p.restore()
                if clave == "enfocar" and self.terminal_icono:  # el ícono de terminal: ">_"
                    centro_x, centro_y = zona.center().x(), zona.center().y()
                    p.setPen(QPen(c["texto"], 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                                  Qt.PenJoinStyle.RoundJoin))
                    p.drawLine(QPointF(centro_x - 6, centro_y - 4), QPointF(centro_x - 2, centro_y))
                    p.drawLine(QPointF(centro_x - 2, centro_y), QPointF(centro_x - 6, centro_y + 4))
                    p.drawLine(QPointF(centro_x, centro_y + 4.5), QPointF(centro_x + 6, centro_y + 4.5))
                else:
                    p.setPen(c["texto_principal"] if principal else c["texto"])
                    p.drawText(zona, int(Qt.AlignmentFlag.AlignCenter), t(self.BOTONES[clave]))
                self.zonas[clave] = p.transform().mapRect(zona)
                x += self.anchos[clave] + 6

        if not self.respondido:  # el tiempo que queda: una línea fina de luz
            pista = QRectF(caja.left() + 21, caja.bottom() - 7.5, caja.width() - 42, 2)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(con_alfa(tinta, 0.14))
            p.drawRoundedRect(pista, 1, 1)
            p.setBrush(QColor(28, 21, 19) if de_acento else acento)
            p.drawRoundedRect(QRectF(pista.left(), pista.top(), pista.width() * max(0.0, min(1.0, fraccion)), 2), 1, 1)

    def boton_en(self, pos) -> str | None:
        return next((clave for clave, zona in self.zonas.items() if zona.contains(pos)), None)


class Sonidos:
    """Los sonidos de assets/sonidos (ver sprites.SONIDOS), con volumen de 0 a 100."""

    def __init__(self, padre):
        self.padre = padre
        self.efectos = {}

    def tocar(self, nombre: str, volumen: int) -> None:
        if not nombre or nombre == "ninguno":
            return
        try:
            from PyQt6.QtCore import QUrl
            from PyQt6.QtMultimedia import QMediaDevices, QSoundEffect
        except ImportError as e:
            log(f"sin sonido: {e}")
            return
        if not QMediaDevices.audioOutputs():  # sin parlantes ni auriculares: se omite en silencio
            if not getattr(self, "avisado_sin_audio", False):
                log("no hay salida de audio: los avisos van sin sonido")
                self.avisado_sin_audio = True
            return
        efecto = self.efectos.get(nombre)
        if efecto is None:
            efecto = QSoundEffect(self.padre)
            efecto.statusChanged.connect(
                lambda: efecto.status() == QSoundEffect.Status.Error and log(f"no se pudo cargar {nombre}.wav"))
            efecto.setSource(QUrl.fromLocalFile(str(SONIDOS / f"{nombre}.wav")))
            self.efectos[nombre] = efecto
        # El oído percibe el volumen en escala logarítmica: al cuadrado el control se siente parejo.
        try:
            efecto.setVolume((max(0, min(100, int(volumen))) / 100) ** 2)
            efecto.stop()
            efecto.play()  # si todavía está cargando, suena apenas termine
        except Exception as e:  # el sonido nunca puede tirar abajo el aviso
            log(f"no se pudo reproducir {nombre}.wav: {e}")


def pantalla_para(ventana: int = 0, punto=None):
    """La pantalla donde mostrar: la de la terminal de Claude si se sabe; si no, la del punto
    pedido o la del mouse; y como último recurso, la principal (sirve con varios monitores)."""
    from PyQt6.QtGui import QCursor, QGuiApplication

    from PyQt6.QtCore import QPoint

    nombre = ventanas.monitor_de_ventana(ventana) if ventana else ""
    for pantalla in QGuiApplication.screens():
        if nombre and pantalla.name() == nombre:
            return pantalla
    centro = ventanas.centro_de_ventana(ventana) if ventana else None  # macOS: por la posición
    if centro and QGuiApplication.screenAt(QPoint(*centro)):
        return QGuiApplication.screenAt(QPoint(*centro))
    if punto is not None and QGuiApplication.screenAt(punto):
        return QGuiApplication.screenAt(punto)
    return QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()


# --- ventana -------------------------------------------------------------------

CLAVE_PERMISO = b"wavemascot"  # autentica la respuesta Permitir/Denegar por el pipe local


def ejecutar_ui(args: argparse.Namespace) -> int:
    import random

    from PyQt6.QtCore import (QElapsedTimer, QEasingCurve, QFileSystemWatcher, QPoint, QPointF, Qt, QTimer,
                              QVariantAnimation)
    from PyQt6.QtGui import QColor, QCursor, QGuiApplication, QPainter, QPixmap
    from PyQt6.QtNetwork import QLocalServer, QLocalSocket
    from PyQt6.QtWidgets import QApplication, QMenu, QWidget

    sys.excepthook = lambda tipo, valor, tb: log("error en la ventana:\n" + "".join(
        traceback.format_exception(tipo, valor, tb)))
    try:
        datos = json.loads(args.aviso or "{}")
    except ValueError:
        datos = {}
    datos.setdefault("estado", args.estado)
    idiomas.usar(datos.get("idioma") or cargar_config()["idioma"])

    def enviar_a_la_existente() -> bool:
        s = QLocalSocket()
        s.connectToServer(CANAL)
        if not s.waitForConnected(300):
            return False
        s.write((json.dumps(datos) + "\n").encode("utf-8"))
        s.flush()
        ok = s.waitForReadyRead(800) and bytes(s.readAll().data()).startswith(b"ok")
        s.disconnectFromServer()
        return ok

    class VidrioCartel(QWidget):
        """Ventana vacía justo debajo del cartel que desenfoca lo de atrás (Windows la desenfoca como rectángulo)."""

        def __init__(self):
            super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
                             | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus
                             | Qt.WindowType.NoDropShadowWindowHint | Qt.WindowType.WindowTransparentForInput)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            self.setWindowTitle("WaveMascot")
            self.caja = None

    class Mascota(QWidget):
        MS_BORDE = 1000      # lo que tarda el borde en pasar a verde o rojo al responder
        MS_RESPUESTA = 1900  # lo que queda el cartel después de responder: la transición y un rato para verla
        ESPERA_CLIC = 0.45   # segundos en que los botones recién aparecidos no aceptan clics (igual que la isla)
        RETRASO = 0.18   # el cartel entra un poco después que la mascota (y sale antes)
        BORDE = 14       # distancia al borde de la pantalla ya en su lugar
        HOLGURA = 18     # lugar del lado de adentro para el rebote al llegar
        MARGEN_ARRIBA = 36  # deja libres los botones de la barra de título
        ALTO_CARTEL_MAX = 230  # la compañera reserva este lugar para no saltar cuando aparece el cartel
        PIES = 54 / 56   # fila de los pies dentro del sprite: ahí se apoya sobre la barra de tareas
        RADIO_PASEO = 260  # cuánto se aleja de su lugar al caminar (px)
        ESTADOS_QUE_SIGUEN = ("pensando", "limite")  # la compañera los mantiene después del cartel

        def __init__(self, servidor, candado):
            super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                             | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus
                             | Qt.WindowType.NoDropShadowWindowHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            if MAC:  # las ventanas Tool de macOS se esconden si la app no está activa (y esta nunca lo está)
                self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
            self.setWindowTitle("WaveMascot")
            self.setCursor(Qt.CursorShape.PointingHandCursor)

            self.servidor, self.candado = servidor, candado
            self.dpr = QGuiApplication.primaryScreen().devicePixelRatio()
            self.cola: list[dict] = []  # avisos de otras sesiones esperando su turno
            self.sesion, self.conexion_permiso = "", None
            self.cartel = Cartel()
            self.sonidos = Sonidos(self)
            self.cache: dict[tuple, list[tuple[QPixmap, int]]] = {}
            self.cuadros: list[tuple[QPixmap, int]] = []
            self.cuadro = 0
            self.t = 0.0          # línea de tiempo: 0 = fuera de la pantalla, 1 = en su lugar
            self.curva = QEasingCurve(QEasingCurve.Type.OutBack)
            self.curva.setOvershoot(1.2)
            self.rebote = 1.0     # avance del "pop" al cambiar de estado
            self.restante = self.total = 5000
            self.pausada = self.saliendo = self.terminada = False
            self.base: dict = {}  # apariencia y modo del último aviso
            self.estado, self.compania, self.deslizar, self.mostrar_cartel = "idle", False, True, False
            self.mirada, self.extra = (0, 0), None
            self.respuesta, self.ventana_terminal = None, 0
            self.novedad = ""
            self.agarre = self.inicio_agarre = None
            self.arrastrada = False   # ya la moviste alguna vez (se queda donde la dejaste)
            self.arrastrando = False  # el clic actual se convirtió en arrastre
            # Compañera en segundo plano: chiquita, parada sobre la barra de tareas (salida 0), o
            # grande cuando avisa algo o le pasás el mouse (salida 1). Mira hacia donde camina (espejo).
            self.salida, self.espejo = 1.0, False
            self.chicos: list[tuple[QPixmap, int]] = []
            self.casa_x, self.caminando, self.paseo = None, False, {}
            self.despertar = None  # hora (epoch) en que se renueva el límite de uso, si se sabe

            self.timer_cuadro = QTimer(self, singleShot=True, timeout=self.siguiente_cuadro)
            self.anim_salida = QVariantAnimation(self)
            self.anim_salida.valueChanged.connect(lambda v: (setattr(self, "salida", float(v)), self.update()))
            self.timer_asomar = QTimer(self, singleShot=True, interval=250, timeout=lambda: self.mover_salida(1.0))
            self.timer_esconder = QTimer(self, singleShot=True, interval=900, timeout=self.esconder_si_corresponde)
            self.timer_paseo = QTimer(self, singleShot=True, timeout=self.empezar_paseo)
            self.timer_paso = QTimer(self, interval=50, timeout=self.dar_paso)
            self.timer_despertar = QTimer(self, singleShot=True, timeout=self.despertarse)
            # La compañera no se queda encima de un video o un juego en pantalla completa.
            self.oculta_por_pantalla = False
            self.timer_pantalla = QTimer(self, interval=1500, timeout=self.revisar_pantalla)
            self.reloj = QElapsedTimer()
            self.tic = QTimer(self, interval=30, timeout=self.avanzar_reloj)
            self.anim = QVariantAnimation(self)
            self.anim.valueChanged.connect(self.al_mover)
            self.anim.finished.connect(self.al_terminar_anim)
            # Estilos con entrada y salida propias (humo, cohetes, pétalos): cuadros que se ven mientras
            # se desliza; al salir, el cartel se va primero (k_cartel) y después la mascota.
            self.especial: list[tuple[QPixmap, int]] | None = None
            self.fase_especial, self.cuadro_especial = "", 0
            self.k_cartel = 1.0
            self.anim_cartel = QVariantAnimation(self, startValue=1.0, endValue=0.0)
            self.anim_cartel.setEasingCurve(QEasingCurve.Type.InCubic)
            self.anim_cartel.valueChanged.connect(lambda v: (setattr(self, "k_cartel", float(v)), self.update()))
            self.timer_salida = QTimer(self, singleShot=True)
            self.timer_salida.timeout.connect(
                lambda: self.animar(0.0, self.ms_desliz(self.especial[-sprites.CUADROS_DESLIZ:]) if self.especial else 480))
            self.anim_rebote = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=420)
            self.anim_rebote.valueChanged.connect(lambda v: (setattr(self, "rebote", v), self.update()))
            self.timer_mirada = QTimer(self, interval=90, timeout=self.seguir_cursor)
            # macOS: Qt no avisa cuándo entra o sale el mouse si la app no está activa (y la mascota nunca
            # lo está, para no sacarle el foco a la terminal): se mira dónde está el cursor.
            self.encima = False
            self.timer_encima = QTimer(self, interval=80, timeout=self.revisar_encima)
            self.timer_extra = QTimer(self, singleShot=True, timeout=self.extra_al_azar)
            self.timer_pensando = QTimer(self, singleShot=True, interval=600_000,
                                         timeout=lambda: self.estado == "pensando" and self.cambiar_estado("idle"))
            self.vigia = None
            self.vidrio, self.vidrio_activo, self.con_vidrio, self.vidrio_rechazado = None, False, False, False
            self.botones_desde = self.presion_en = 0.0
            self.ultimo_cuadro = time.monotonic()
            self.anim_borde = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=self.MS_BORDE)
            self.anim_borde.setEasingCurve(QEasingCurve.Type.InOutCubic)
            self.anim_borde.valueChanged.connect(lambda v: (setattr(self.cartel, "avance_borde", float(v)), self.update()))
            if servidor:
                servidor.newConnection.connect(self.nueva_conexion)

        # estado y contenido

        def aplicar(self, d: dict) -> None:
            config = CONFIG_DEFECTO
            if d.get("accion") == "salir":
                self.salir()
                return
            if d.get("idioma"):
                idiomas.usar(d["idioma"])
            estado = d["estado"] if d.get("estado") in ESTADOS else "listo"
            if self.respuesta and estado == "permiso" and not d.get("respuesta"):
                return  # el aviso genérico de Notification no pisa los botones Permitir/Denegar
            # Varias sesiones a la vez: el aviso de otra sesión espera su turno en vez de pisar al que se ve.
            otra_sesion = d.get("sesion") and self.sesion and d["sesion"] != self.sesion
            if (otra_sesion and d.get("mensaje") and not d.get("respuesta") and self.mostrar_cartel
                    and not self.saliendo and self.isVisible()):
                self.cola = [a for a in self.cola if a.get("sesion") != d["sesion"]][-4:] + [d]
                log(f"aviso de otra sesión en cola ({len(self.cola)} esperando)")
                return
            self.soltar_permiso()
            self.anim_borde.stop()
            self.con_vidrio = self.quiere_vidrio(cargar_config()) and not self.vidrio_rechazado
            self.sesion = d.get("sesion") or ""
            self.caminando, self.espejo = False, False  # un aviso se ve siempre como en la vista previa
            self.timer_paso.stop()
            if estado == "limite":
                self.despertar = d.get("despertar")
            self.base = {clave: d.get(clave, config.get(clave)) for clave in
                         ("aspecto", "imagen", "tamano", "tema", "esquina", "modo", "vida", "posicion",
                          "no_molestar")}
            self.base["aspecto"] = sprites.normalizar(self.base["aspecto"])
            self.compania = self.base["modo"] == "compania"
            self.cartel.tema = self.base["tema"] if self.base["tema"] in TEMAS else "oscuro"
            self.cartel.estilo = self.base["aspecto"]["estilo"]
            self.respuesta = d.get("respuesta")
            try:
                self.ventana_terminal = int(d.get("ventana") or 0)
            except (TypeError, ValueError):
                self.ventana_terminal = 0
            self.dpr = self.pantalla().devicePixelRatio()  # cada monitor puede tener otra escala
            self.conectar_permiso()
            self.mensaje = str(d.get("mensaje") or "")[:120]
            botones = ["permitir", "denegar"] if self.respuesta else []
            if self.ventana_terminal and d.get("boton_enfocar", True) and self.mensaje:
                botones.append("enfocar")
            self.novedad = d.get("novedad") or ""  # aviso de versión nueva: Actualizar / Ahora no
            if self.novedad:
                botones = ["actualizar", "ahora_no"]
            if botones:
                self.botones_desde = time.monotonic()  # un clic que iba para el cartel anterior no cae en este
            try:
                self.cartel.medir(self.mensaje, str(d.get("resumen") or "")[:200], str(d.get("meta") or "")[:120],
                                  botones)
            except Exception:  # nunca botones conectados a un pedido cuyo contenido no se pudo mostrar
                log("no se pudo armar el cartel:\n" + traceback.format_exc())
                self.soltar_permiso()  # decide la terminal
                self.mensaje = t(ESTADOS[estado]["mensaje"])
                try:
                    self.cartel.medir(self.mensaje)
                except Exception:  # ni eso: sale la mascota sola, sin cartel
                    self.mensaje, self.cartel.zonas = "", {}
            self.mostrar_cartel = bool(self.mensaje)
            self.cambiar_estado(estado)
            self.maquetar()
            self.total = self.restante = max(1000, int(float(d.get("duracion") or config["duracion"]) * 1000))
            self.reloj.restart()
            self.tic.start()
            if isinstance(d.get("sonido"), str):
                self.sonidos.tocar(d["sonido"], d.get("volumen", config["volumen"]))
            if self.compania and self.vigia is None:  # la compañera sigue los cambios de ajustes en vivo
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                self.vigia = QFileSystemWatcher([str(CONFIG_DIR)], self)
                self.vigia.directoryChanged.connect(lambda _: QTimer.singleShot(250, self.recargar_config))
            if not self.chiquita():
                self.anim_salida.stop()
                self.salida = 1.0
            elif not self.isVisible():  # recién abierta: chiquita, salvo que ya traiga un aviso
                self.salida = 1.0 if self.mostrar_cartel else 0.0
            elif self.mostrar_cartel:
                self.mover_salida(1.0)
            en_su_lugar = self.t >= 1.0 and self.anim.state() != QVariantAnimation.State.Running
            if self.compania:
                self.revisar_pantalla()
                self.timer_pantalla.start()
            if not self.isVisible() and not self.oculta_por_pantalla:
                self.show()
            self.saliendo = False
            self.cancelar_salida_especial()
            if en_su_lugar:
                self.anim_rebote.stop()
                self.anim_rebote.start()
            elif self.t <= 0.001 and self.con_entrada_propia():
                self.empezar_especial("entrada")
                self.animar(1.0, self.ms_desliz(self.especial[:sprites.CUADROS_DESLIZ]))
            else:
                self.animar(1.0, 650)

        def con_entrada_propia(self) -> bool:
            """Aviso que entra desde el costado con un estilo que tiene entrada y salida propias."""
            return (not self.compania and self.deslizar and not self.base.get("imagen")
                    and sprites.tiene_entrada(self.base["aspecto"]))

        def ms_desliz(self, cuadros: list) -> int:
            """Duración de la línea de tiempo para que la mascota se deslice justo mientras pasan esos cuadros."""
            return int(sum(ms for _, ms in cuadros) / (1 - self.RETRASO))

        def empezar_especial(self, fase: str) -> None:
            self.especial, self.fase_especial, self.cuadro_especial = self.cargar(fase), fase, -1
            self.timer_cuadro.stop()
            self.siguiente_cuadro()

        def cancelar_salida_especial(self) -> None:
            """Llegó otro aviso mientras se iba: vuelve con el cartel en su lugar."""
            self.timer_salida.stop()
            self.anim_cartel.stop()
            self.k_cartel = 1.0
            if self.fase_especial == "salida":
                self.especial, self.fase_especial = None, ""
                self.cuadro = -1
                self.siguiente_cuadro()

        def cambiar_estado(self, estado: str) -> None:
            self.estado, self.extra = estado, None
            self.acento = QColor(ESTADOS[estado]["acento"])
            con_mirada = (estado in sprites.CON_MIRADA and self.base.get("vida", {}).get("mirada")
                          and not self.base.get("imagen"))
            self.mirada = (0, 0)
            self.cuadros = self.cargar(estado, self.mirada if con_mirada else None)
            self.chicos = self.cargar(estado, self.mirada if con_mirada else None, chico=True) if self.chiquita() else []
            self.cuadro = -1
            self.siguiente_cuadro()
            (self.timer_mirada.start if con_mirada else self.timer_mirada.stop)()
            self.programar_extra()
            (self.timer_pensando.start if estado == "pensando" and self.compania else self.timer_pensando.stop)()
            self.timer_despertar.stop()
            if estado == "limite" and self.compania and self.despertar:
                faltan = self.despertar - time.time()
                self.timer_despertar.start(int(min(max(faltan, 1), 86_400) * 1000))

        def cargar(self, estado: str, mirada=None, chico: bool = False) -> list:
            """Cuadros del estado; chico = un tamaño menos (la compañera en reposo), nítido igual."""
            b = self.base
            tamano = int(b["tamano"] or 3) - (1 if chico else 0)
            if mirada and self.espejo:  # dibujada en espejo: los ojos tienen que mirar al revés
                mirada = (-mirada[0], mirada[1])
            clave = (json.dumps(b["aspecto"], sort_keys=True), b["imagen"], estado, max(1, tamano), mirada,
                     self.dpr)
            if clave not in self.cache:
                self.cache[clave] = cargar_cuadros(b["aspecto"], str(b["imagen"] or ""), estado,
                                                   max(1, tamano), self.dpr, mirada)
            return self.cache[clave]

        def pantalla(self):
            """Aviso: el monitor de la terminal de Claude. Compañera: donde la dejaste (o la principal)."""
            if self.compania:
                posicion = self.base.get("posicion")
                return (pantalla_para(punto=QPoint(posicion[0] + 20, posicion[1] + 20)) if posicion
                        else QGuiApplication.primaryScreen())
            return pantalla_para(self.ventana_terminal)

        def chiquita(self) -> bool:
            return self.compania and (self.base.get("vida") or {}).get("chiquita", True)

        def mover_salida(self, hasta: float) -> None:
            """Compañera: crece para avisar (1) o vuelve a quedar chiquita sobre la barra (0)."""
            if not self.chiquita() or (self.anim_salida.endValue() == hasta
                                      and self.anim_salida.state() == QVariantAnimation.State.Running):
                return
            desde = self.salida
            self.anim_salida.stop()
            self.anim_salida.setDuration(max(1, int((480 if hasta > desde else 380) * abs(hasta - desde))))
            self.anim_salida.setEasingCurve(QEasingCurve.Type.OutBack if hasta > desde else QEasingCurve.Type.InOutCubic)
            self.anim_salida.setStartValue(desde)
            self.anim_salida.setEndValue(hasta)
            self.anim_salida.start()

        def esconder_si_corresponde(self) -> None:
            if self.chiquita() and not self.mostrar_cartel and not self.mouse_encima() and self.agarre is None:
                self.mover_salida(0.0)

        def pose(self) -> tuple[float, float, float]:
            """Centro x, escala y opacidad: chiquita en reposo, grande cuando avisa."""
            if not self.chiquita() or not self.chicos:
                return self.cx, 1.0, 1.0
            s = self.salida
            k = self.chicos[0][0].width() / self.cuadros[0][0].width()
            return self.cx, k + (1 - k) * s, 0.88 + 0.12 * min(1.0, max(0.0, s))

        def maquetar(self, reubicar: bool = False) -> None:
            """Calcula el tamaño de la ventana y la ubica: el aviso en su esquina, la compañera
            parada sobre la barra de tareas (donde la dejaste, o donde quedó después de caminar)."""
            pm = self.cuadros[0][0]
            self.sprite_w, self.sprite_h = pm.width() / self.dpr, pm.height() / self.dpr
            esquina = self.base["esquina"] if self.base["esquina"] in ESQUINAS else ESQUINAS[0]
            area = self.pantalla().availableGeometry()
            if self.compania:
                self.maquetar_compania(area, esquina, reubicar)
                self.ajustar_vidrio()
                return
            arriba_extra = 4  # el "pop" crece sobre la parte transparente del sprite
            hueco = Cartel.hueco(self.sprite_h, self.base.get("imagen")) if self.mostrar_cartel else 2
            contenido = max(self.sprite_w, self.cartel.ancho)
            ancho = math.ceil(contenido + self.BORDE + self.HOLGURA)
            alto = math.ceil(arriba_extra + self.sprite_h + hueco + self.cartel.alto + 16)  # con lugar para la sombra
            derecha, abajo = esquina.endswith("derecha"), esquina.startswith("abajo")
            self.direccion = 1 if derecha else -1  # borde por el que entra y sale
            self.cx = self.cartel_cx = ancho - self.BORDE - contenido / 2 if derecha else self.BORDE + contenido / 2
            self.sprite_y = arriba_extra
            self.etiqueta_y = self.sprite_y + self.sprite_h + hueco
            # La ventana toca el borde de la pantalla: lo que se dibuja fuera de ella queda
            # recortado justo ahí, así parece que sale del costado.
            x = area.x() + area.width() - ancho if derecha else area.x()
            y = area.y() + self.MARGEN_ARRIBA if not abajo else area.y() + area.height() - alto
            self.deslizar = True
            self.espejo = False  # el aviso siempre igual que la vista previa de ajustes
            if self.arrastrada:  # una vez arrastrada se queda donde la dejaste
                x, y, self.deslizar = self.x(), self.y(), False
            self.setGeometry(int(x), int(y), ancho, alto)
            self.ajustar_vidrio()

        @staticmethod
        def quiere_vidrio(config: dict) -> bool:
            """El cartel usa la misma opción de desenfoque que la Dynamic Island."""
            return bool(ventanas.ES_WINDOWS and not os.environ.get("WAVEMASCOT_SIN_VIDRIO")
                        and config["barra"]["desenfoque"])

        def ajustar_vidrio(self) -> None:
            """Cambió el tamaño: Windows redibuja el desenfoque con atraso, así que el tinte tapa un momento."""
            if self.vidrio_activo:
                self.cartel.alfa = Cartel.ALFA_SOLO
                self.seguir_vidrio()

        def apagar_vidrio(self) -> None:
            if self.vidrio_activo:
                self.vidrio.hide()
                self.vidrio_activo = False
            self.cartel.alfa = Cartel.ALFA_SOLO

        def seguir_vidrio(self) -> None:
            """El desenfoque aparece con el cartel ya quieto: mientras entra, sale o lo arrastran, el tinte tapa
            (Windows no llega a mover el desenfoque al mismo tiempo y titilaría)."""
            quieto = (self.con_vidrio and self.mostrar_cartel and self.t >= 0.999 and not self.saliendo
                      and not self.arrastrando and self.k_cartel >= 0.999 and self.salida >= 0.999
                      and self.anim.state() != QVariantAnimation.State.Running and self.isVisible())
            if not quieto:
                self.apagar_vidrio()
                return
            if self.vidrio is None:
                self.vidrio = VidrioCartel()
            if not self.vidrio_activo:
                self.vidrio.caja = None
                self.vidrio.resize(1, 1)
                self.vidrio.show()
                self.vidrio_activo = ventanas.desenfocar_detras(int(self.vidrio.winId()))
                if not self.vidrio_activo:  # este sistema no lo da: queda el tinte solo
                    self.vidrio.hide()
                    self.con_vidrio, self.vidrio_rechazado = False, True  # no se vuelve a intentar
                    return
            d, k = Cartel.ADENTRO, self.devicePixelRatioF()
            origen = self.mapToGlobal(QPoint(0, 0))
            monitor = (self.screen() or QGuiApplication.primaryScreen()).geometry()
            izq, arriba = self.cartel_cx - self.cartel.ancho / 2 + d, self.etiqueta_y + d
            # Qt deja el origen de cada monitor en píxeles reales: solo se escala lo que está adentro de él.
            caja = (round(monitor.x() + (origen.x() - monitor.x() + izq) * k),
                    round(monitor.y() + (origen.y() - monitor.y() + arriba) * k),
                    max(1, round((self.cartel.ancho - 2 * d) * k)), max(1, round((self.cartel.alto - 2 * d) * k)))
            if caja != self.vidrio.caja:
                self.vidrio.caja = caja
                ventanas.poner_debajo(int(self.vidrio.winId()), int(self.winId()), *caja)

        def marcar_respuesta(self, decision: str) -> None:
            """El borde pasa de vidrio a verde o rojo de a poco."""
            self.cartel.marcar(decision)
            self.anim_borde.stop()
            self.anim_borde.start()
            self.total = self.restante = self.MS_RESPUESTA

        def maquetar_compania(self, area, esquina: str, reubicar: bool) -> None:
            posicion = self.base.get("posicion")
            contenido = max(self.sprite_w, self.cartel.ANCHO_TEXTO + 2 * Cartel.RELLENO)
            ancho = math.ceil(contenido + 2 * self.BORDE)
            # Tamaño fijo, con lugar arriba para el cartel: así la mascota no salta cuando avisa.
            alto = math.ceil(10 + self.ALTO_CARTEL_MAX + self.sprite_h * 0.86)
            if reubicar or not self.isVisible() or self.casa_x is None:
                x = posicion[0] if posicion else (area.x() + area.width() - ancho if esquina.endswith("derecha")
                                                  else area.x())
            else:
                x = self.x()  # se queda donde la dejó la última caminata
            x = min(max(x, area.x()), area.x() + area.width() - ancho)
            if reubicar or self.casa_x is None:
                self.casa_x = x
            derecha = x + ancho / 2 > area.center().x()
            self.direccion = 1 if derecha else -1
            self.pies_y = alto - 1  # los pies apoyan justo sobre la barra de tareas
            self.cx = ancho - self.BORDE - self.sprite_w / 2 if derecha else self.BORDE + self.sprite_w / 2
            self.cartel_cx = min(max(self.cx, self.cartel.ancho / 2 + 12), ancho - self.cartel.ancho / 2 - 12)
            self.sprite_y = self.pies_y - self.sprite_h * self.PIES
            # El cartel va por encima de los globitos de la mascota ("!", pensamiento), sin taparlos.
            self.etiqueta_y = self.pies_y - self.sprite_h * 0.82 - self.cartel.alto
            self.cartel_arriba, self.deslizar = True, False
            if not self.caminando:
                self.espejo = False  # solo se espeja mientras camina hacia la izquierda
            self.setGeometry(int(x), int(area.y() + area.height() - alto), ancho, alto)

        # paseo: cada tanto da unos pasos sobre la barra, sin alejarse mucho de su lugar

        def empezar_paseo(self) -> None:
            ocupada = (self.estado != "idle" or self.extra or self.salida > 0.01 or self.agarre is not None
                       or self.mouse_encima() or self.mostrar_cartel or self.oculta_por_pantalla)
            if ocupada:
                self.programar_extra()
                return
            area = self.pantalla().availableGeometry()
            minimo = max(area.x(), self.casa_x - self.RADIO_PASEO)
            maximo = min(area.x() + area.width() - self.width(), self.casa_x + self.RADIO_PASEO)
            direccion = random.choice((-1, 1))
            if not minimo <= self.x() + direccion * 40 <= maximo:
                direccion = -direccion
            self.paseo = {"dir": direccion, "restante": random.randint(40, 130), "limites": (minimo, maximo)}
            self.caminando, self.espejo = True, direccion < 0
            self.timer_extra.stop()
            self.cuadros = self.cargar("caminar")
            self.chicos = self.cargar("caminar", chico=True) if self.chiquita() else []
            self.cuadro = -1
            self.siguiente_cuadro()
            self.timer_paso.start()

        def dar_paso(self) -> None:
            nueva = self.x() + self.paseo["dir"] * 2
            minimo, maximo = self.paseo["limites"]
            if self.paseo["restante"] <= 0 or not minimo <= nueva <= maximo:
                self.terminar_paseo()
                return
            self.move(nueva, self.y())
            self.paseo["restante"] -= 2

        def revisar_pantalla(self) -> None:
            """Se esconde mientras haya algo en pantalla completa (si esa opción está activa)."""
            if not self.compania or self.terminada:
                return
            activa = (self.base.get("no_molestar") or {}).get("pantalla_completa", True)
            completa = activa and ventanas.pantalla_completa()
            if completa and not self.oculta_por_pantalla:
                self.oculta_por_pantalla = True
                self.terminar_paseo()
                self.hide()
                log("compañera: se esconde mientras hay algo en pantalla completa")
            elif not completa and self.oculta_por_pantalla:
                self.oculta_por_pantalla = False
                self.show()
                log("compañera: vuelve, ya no hay nada en pantalla completa")

        def despertarse(self) -> None:
            """Se renovó el límite de uso: bosteza y vuelve al reposo."""
            if self.estado != "limite":
                return
            self.despertar = None
            log("compañera: se renovó el límite, se despierta")
            self.cambiar_estado("idle")
            if not self.base.get("imagen"):
                self.hacer_extra("idle_bostezo")

        def contar_que_duerme(self) -> None:
            hasta = (t("Me despierto a las {hora}", hora=f"{datetime.fromtimestamp(self.despertar):%H:%M}")
                     if self.despertar else t("Me despierto cuando me vuelvas a escribir"))
            self.mensaje = t("Zzz… se terminó el límite de uso")
            self.cartel.medir(self.mensaje, hasta, "")
            self.mostrar_cartel = True
            self.maquetar()
            self.total = self.restante = 4000
            self.reloj.restart()
            self.tic.start()
            self.mover_salida(1.0)

        def terminar_paseo(self) -> None:
            if not self.caminando:
                return
            self.caminando, self.espejo = False, False  # al frenar vuelve a mirar de frente
            self.timer_paso.stop()
            if self.estado == "idle":
                self.cambiar_estado("idle")  # vuelve al reposo y programa lo próximo

        # vida: reposo, animaciones al azar y mirada

        def programar_extra(self) -> None:
            vida = self.base.get("vida") or {}
            if self.compania and self.estado == "idle" and vida.get("idle") and not self.base.get("imagen"):
                self.timer_extra.start(random.randint(6000, 14000))
            else:
                self.timer_extra.stop()
            if self.chiquita() and self.estado == "idle" and vida.get("pasear", True):
                if not self.timer_paseo.isActive():
                    self.timer_paseo.start(random.randint(9000, 22000))
            else:
                self.timer_paseo.stop()

        def extra_al_azar(self) -> None:
            if self.estado != "idle" or self.caminando:
                return
            self.hacer_extra(random.choice(sprites.IDLE_EXTRAS))

        def hacer_extra(self, extra: str) -> None:
            self.extra = extra
            self.cuadros = self.cargar(extra)
            self.chicos = self.cargar(extra, chico=True) if self.chiquita() else []
            self.cuadro = -1
            self.siguiente_cuadro()

        def seguir_cursor(self) -> None:
            if self.extra or self.caminando or self.estado not in sprites.CON_MIRADA:
                return
            cx, escala, _ = self.pose()
            cara_y = (self.pies_y - self.sprite_h * 0.26 * escala if self.compania
                      else self.sprite_y + self.sprite_h * 0.68)
            cara = self.mapToGlobal(QPoint(int(cx), int(cara_y)))
            dx, dy = QCursor.pos().x() - cara.x(), QCursor.pos().y() - cara.y()
            mirada = (0 if abs(dx) < 40 else (1 if dx > 0 else -1), 0 if abs(dy) < 40 else (1 if dy > 0 else -1))
            if mirada != self.mirada:
                self.mirada = mirada
                self.cuadros = self.cargar(self.estado, mirada)
                self.chicos = self.cargar(self.estado, mirada, chico=True) if self.chiquita() else []
                self.cuadro %= len(self.cuadros)
                self.update()

        def recargar_config(self) -> None:
            """Compañera: aplica en vivo lo que cambies en ajustes (o se va si elegiste modo aviso)."""
            if self.terminada:
                return
            config = cargar_config()
            if config["modo"] != "compania":
                self.salir()
                return
            self.con_vidrio = self.quiere_vidrio(config) and not self.vidrio_rechazado
            self.seguir_vidrio()  # si lo apagaste en ajustes, se va ya
            nuevo = {clave: config[clave] for clave in self.base if clave in config}
            nuevo["aspecto"] = sprites.normalizar(nuevo["aspecto"])
            if nuevo != self.base:
                reubicar = any(nuevo.get(c) != self.base.get(c) for c in ("esquina", "posicion", "tamano"))
                self.base.update(nuevo)
                self.cartel.tema = self.base["tema"]
                self.terminar_paseo()
                self.cambiar_estado(self.estado)
                self.maquetar(reubicar)
                self.update()

        # animaciones y temporizador

        def siguiente_cuadro(self) -> None:
            if self.especial:
                if self.cuadro_especial + 1 < len(self.especial):
                    self.cuadro_especial += 1
                    self.update()
                    self.timer_cuadro.start(self.especial[self.cuadro_especial][1])
                    return
                if self.fase_especial == "salida":
                    return  # queda en el último cuadro hasta que termina de irse
                self.especial, self.fase_especial = None, ""  # terminó la entrada: sigue el estado
                self.cuadro = -1
            if self.extra and self.cuadro + 1 >= len(self.cuadros):  # terminó el extra: vuelve al reposo
                self.cambiar_estado("idle")
                return
            self.cuadro = (self.cuadro + 1) % len(self.cuadros)
            self.update()
            self.timer_cuadro.start(self.cuadros[self.cuadro][1])

        def animar(self, hasta: float, ms_recorrido_completo: int) -> None:
            desde = self.t  # setEndValue puede emitir valueChanged y pisar self.t
            self.anim.stop()
            self.anim.setDuration(max(1, int(ms_recorrido_completo * abs(hasta - desde))))
            self.anim.setStartValue(desde)
            self.anim.setEndValue(hasta)
            self.anim.start()

        def al_mover(self, valor) -> None:
            self.t = float(valor)
            self.update()

        def al_terminar_anim(self) -> None:
            if self.saliendo and self.t <= 0.001:
                self.terminar()

        def avance(self, retraso: float) -> float:
            """Posición (con rebote, puede pasar de 1) de un elemento que arranca con retraso.
            Al salir la línea de tiempo corre al revés y el rebote se vuelve un amague."""
            x = min(1.0, max(0.0, (self.t - retraso) / (1 - self.RETRASO)))
            return self.curva.valueForProgress(x)

        def avanzar_reloj(self) -> None:
            transcurrido = self.reloj.restart()
            self.revisar_permiso()
            if not self.pausada and not self.saliendo:
                self.restante -= transcurrido
                if self.restante <= 0:
                    self.fin_del_aviso()
            self.update()

        def fin_del_aviso(self) -> None:
            """Aviso: se va. Compañera: guarda el cartel y vuelve a descansar (o sigue pensando)."""
            self.soltar_permiso()
            if self.cola:  # avisos de otras sesiones que esperaban su turno
                siguiente, self.sesion = self.cola.pop(0), ""
                self.aplicar(siguiente)
                return
            if not self.compania:
                self.salir()
                return
            self.tic.stop()
            self.mostrar_cartel = False
            self.cartel.zonas = {}
            if self.estado not in self.ESTADOS_QUE_SIGUEN:
                self.cambiar_estado("idle")
            self.esconder_si_corresponde()  # vuelve a asomarse chiquita desde el borde
            self.update()

        def salir(self, rapido: bool = False) -> None:
            if self.saliendo:
                return
            self.saliendo = True
            self.apagar_vidrio()
            if not rapido and self.t >= 0.999 and self.con_entrada_propia():
                # Se prepara quieta mientras el cartel se va, y después sale por el costado con su animación.
                self.empezar_especial("salida")
                quieta = sum(ms for _, ms in self.especial[:-sprites.CUADROS_DESLIZ]) or 1
                self.anim_cartel.setDuration(quieta)
                self.anim_cartel.start()
                self.timer_salida.start(quieta)
                return
            self.animar(0.0, 300 if rapido else 480)

        def terminar(self) -> None:
            self.terminada = True
            self.soltar_permiso()
            self.apagar_vidrio()
            if self.servidor:
                self.servidor.close()
            self.candado.soltar()
            self.hide()
            QApplication.quit()

        # acciones del cartel

        def accion(self, clave: str) -> None:
            if clave in ("actualizar", "ahora_no"):
                if clave == "actualizar":  # los ajustes la bajan y la instalan, mostrando el avance
                    lanzar_desacoplado([str(DIR / "ajustes.py"), "--actualizar"])
                else:
                    config = cargar_config()
                    config["actualizaciones"]["ignorada"] = self.novedad
                    guardar_config(config)
                log(f"versión nueva {self.novedad}: {clave}")
                self.restante = 0
                if not self.compania:
                    self.salir(rapido=True)
                return
            if clave == "enfocar":
                ok = ventanas.enfocar(self.ventana_terminal)
                log(f"botón 'Ir a la terminal': {'enfocada' if ok else 'no se pudo enfocar'} ({self.ventana_terminal})")
                self.restante = 0
                if not self.compania:
                    self.salir(rapido=True)
            elif clave in ("permitir", "denegar"):
                self.responder("allow" if clave == "permitir" else "deny")
                self.cartel.medir(t("Permitido") if clave == "permitir" else t("Denegado"), self.cartel.resumen)
                self.maquetar()
                self.marcar_respuesta("allow" if clave == "permitir" else "deny")
                self.update()

        def conectar_permiso(self) -> None:
            """Le avisa al hook PermissionRequest que el cartel con Permitir/Denegar ya se ve."""
            self.conexion_permiso = None
            if not self.respuesta:
                return
            try:
                from multiprocessing.connection import Client
                self.conexion_permiso = Client(self.respuesta, authkey=CLAVE_PERMISO)  # pipe o socket, según la dirección
                self.conexion_permiso.send({"mostrado": True})
            except OSError as e:
                log(f"permiso: el hook ya no estaba esperando ({e})")
                self.respuesta = None

        def responder(self, decision: str | None) -> None:
            """Le manda la decisión al hook PermissionRequest, que la está esperando."""
            conexion, self.conexion_permiso, self.respuesta = self.conexion_permiso, None, None
            if not conexion:
                return
            try:
                conexion.send({"decision": decision})
                conexion.close()
                log(f"permiso: decisión {decision or 'ninguna (decide la terminal)'}")
            except OSError as e:
                log(f"permiso: el hook ya no estaba esperando ({e})")

        def soltar_permiso(self) -> None:
            if self.respuesta:
                self.responder(None)  # que la terminal muestre su diálogo de siempre

        def revisar_permiso(self) -> None:
            """El pedido se resolvió en otro lado (Telegram) o el hook dejó de esperar: el cartel pierde los
            botones, dice qué pasó y se va."""
            conexion = self.conexion_permiso
            if not conexion:
                return
            try:
                if not conexion.poll(0):
                    return
                mensaje = conexion.recv()
            except (EOFError, OSError):
                mensaje = {}
            self.conexion_permiso, self.respuesta = None, None
            decision = mensaje.get("resuelto") if isinstance(mensaje, dict) else None
            texto = {"allow": t("Permitido desde Telegram ✓"), "deny": t("Denegado desde Telegram")}.get(decision)
            log(f"permiso: resuelto fuera de la mascota ({decision or 'sin respuesta'})")
            self.cartel.medir(texto or self.mensaje, self.cartel.resumen)
            self.maquetar()
            self.total = self.restante = 1500 if texto else 0
            if texto:
                self.marcar_respuesta(decision)
            self.update()

        def menu_compania(self, donde) -> None:
            idiomas.usar(cargar_config()["idioma"])  # pudo cambiar en los ajustes desde que se abrió
            menu = QMenu()
            menu.addAction(t("Abrir ajustes")).triggered.connect(self.abrir_ajustes)
            if self.base.get("posicion"):
                menu.addAction(t("Volver a la esquina")).triggered.connect(lambda: self.guardar_en_config(posicion=None))
            menu.addAction(t("Pasar a modo aviso")).triggered.connect(lambda: self.guardar_en_config(modo="aviso"))
            menu.addSeparator()
            no_molestar = menu.addAction(t("No molestar"))
            no_molestar.setCheckable(True)
            no_molestar.setChecked(no_molestar_ahora(cargar_config()))
            no_molestar.toggled.connect(lambda activo: self.guardar_en_config(silenciado_hasta=INDEFINIDO if activo else 0))
            menu.addAction(t("Ocultar hasta el próximo aviso")).triggered.connect(lambda: self.salir(rapido=True))
            menu.exec(donde)

        def abrir_ajustes(self) -> None:
            if ventanas.ES_WINDOWS:
                ventanas.u32.AllowSetForegroundWindow(-1)
            lanzar_desacoplado([str(DIR / "ajustes.py")])

        def guardar_en_config(self, **cambios) -> None:
            config = cargar_config()
            config.update(cambios)
            guardar_config(config)
            self.recargar_config()

        # comunicación con mascotas nuevas

        def nueva_conexion(self) -> None:
            while self.servidor.hasPendingConnections():
                s = self.servidor.nextPendingConnection()
                s.readyRead.connect(lambda s=s: self.leer_mensaje(s))
                s.disconnected.connect(s.deleteLater)

        def leer_mensaje(self, s) -> None:
            if not s.canReadLine() or self.terminada:
                return
            try:
                d = json.loads(bytes(s.readLine().data()).decode("utf-8"))
            except ValueError:
                return
            if d.get("accion") == "consultar":  # para el ícono de la bandeja (y las pruebas)
                botones = {clave: [self.x() + round(z.center().x()), self.y() + round(z.center().y())]
                           for clave, z in self.cartel.zonas.items()}  # centro de cada botón, en la pantalla
                estado = {"estado": self.estado, "mirada": self.mirada, "extra": self.extra, "modo": self.base.get("modo"),
                          "cartel": self.mostrar_cartel, "posicion": [self.x(), self.y()], "tema": self.cartel.tema,
                          "salida": round(self.salida, 2), "espejo": self.espejo, "caminando": self.caminando,
                          "despertar": self.despertar, "tamano": [self.width(), self.height()], "botones": botones}
                s.write((json.dumps(estado) + "\n").encode("utf-8"))
                s.flush()
                return
            log(f"reemplazo en pantalla: estado={d.get('estado')} mensaje={d.get('mensaje')!r}")
            self.aplicar(d)
            s.write(b"ok\n")
            s.flush()

        # interacción: click cierra (o usa un botón), arrastrar mueve, click derecho = menú de la compañera

        def mousePressEvent(self, evento) -> None:
            if evento.button() == Qt.MouseButton.RightButton:
                if self.compania:
                    self.menu_compania(evento.globalPosition().toPoint())
                return
            self.terminar_paseo()
            self.presion_en = time.monotonic()
            self.inicio_agarre = evento.globalPosition().toPoint()
            self.agarre = self.inicio_agarre - self.pos()
            self.arrastrando = False

        def mouseMoveEvent(self, evento) -> None:
            if self.agarre is None or not evento.buttons() & Qt.MouseButton.LeftButton:
                return
            if not self.arrastrando and (evento.globalPosition().toPoint() - self.inicio_agarre).manhattanLength() < 6:
                return
            if not self.arrastrando:
                self.mover_salida(1.0)  # mientras la llevás, se ve entera
            self.arrastrando = self.arrastrada = True
            self.deslizar = False
            self.move(evento.globalPosition().toPoint() - self.agarre)

        def mouseReleaseEvent(self, evento) -> None:
            if self.agarre is None:
                return
            self.agarre = None
            if self.arrastrando:  # fue un arrastre, no un clic: no toca botones ni cierra
                self.arrastrando = False
                if self.compania:  # la compañera recuerda a qué altura la dejaste (y se pega al borde)
                    self.arrastrada = False
                    area = (QGuiApplication.screenAt(self.geometry().center()) or self.pantalla()).availableGeometry()
                    x = min(max(self.x(), area.x()), area.x() + area.width() - self.width())
                    self.guardar_en_config(posicion=[x, area.y() + area.height() - self.height()])
                    self.maquetar(reubicar=True)  # vuelve a pararse sobre la barra, en ese lugar
                    self.timer_esconder.start()
                return
            clave = self.cartel.boton_en(evento.position()) if self.mostrar_cartel else None
            if clave and self.presion_en < self.botones_desde + self.ESPERA_CLIC:
                return  # el clic empezó antes de que se pudiera leer este cartel: no toca sus botones
            if clave:
                self.accion(clave)
            elif self.compania:
                if self.mostrar_cartel:
                    self.restante = 0
                elif self.estado == "limite":
                    self.contar_que_duerme()
                elif self.salida < 0.99 and self.chiquita():  # tocarla chiquita: crece y saluda
                    self.mover_salida(1.0)
                    if self.estado == "idle" and not self.base.get("imagen"):
                        self.hacer_extra("idle_saludo")
            else:
                self.salir(rapido=True)

        def showEvent(self, evento) -> None:
            super().showEvent(evento)
            if MAC:
                ventanas.ventana_flotante(int(self.winId()))
                self.timer_encima.start()

        def hideEvent(self, evento) -> None:
            self.apagar_vidrio()
            super().hideEvent(evento)

        def mouse_encima(self) -> bool:
            return self.encima if MAC else self.underMouse()

        def zona_visible(self, punto) -> bool:
            """¿El punto (de la ventana) cae sobre la mascota o el cartel? Lo transparente no cuenta,
            igual que en Windows, donde el mouse atraviesa las partes sin dibujar."""
            from PyQt6.QtCore import QRectF

            cx, escala, _ = self.pose()
            w, h = self.sprite_w * escala, self.sprite_h * escala
            base, apoyo = (self.pies_y, self.PIES) if self.compania else (self.sprite_y + self.sprite_h, 1.0)
            cuerpo = QRectF(cx - w / 2, base - h * apoyo, w, h).adjusted(w * 0.2, h * 0.3, -w * 0.2, 0)
            if cuerpo.contains(punto):
                return True
            cartel = QRectF(self.cartel_cx - self.cartel.ancho / 2, self.etiqueta_y, self.cartel.ancho, self.cartel.alto)
            return self.mostrar_cartel and cartel.contains(punto)

        def revisar_encima(self) -> None:
            if not self.isVisible() or self.t < 1.0:
                return
            adentro = self.zona_visible(QPointF(self.mapFromGlobal(QCursor.pos())))
            if adentro != self.encima:
                self.encima = adentro
                (self.enterEvent if adentro else self.leaveEvent)(None)

        def enterEvent(self, evento) -> None:
            self.pausada = True
            self.terminar_paseo()
            self.timer_esconder.stop()
            if self.chiquita() and not self.mostrar_cartel:
                self.timer_asomar.start()

        def leaveEvent(self, evento) -> None:
            self.pausada = False
            self.timer_asomar.stop()
            if self.chiquita():
                self.timer_esconder.start()

        # dibujo

        def paintEvent(self, evento) -> None:
            if self.t <= 0 or not self.cuadros:
                return
            self.seguir_vidrio()
            ahora = time.monotonic()
            if self.vidrio_activo:  # con el desenfoque ya detrás, el tinte se aclara de a poco
                paso = min(1.0, (ahora - self.ultimo_cuadro) / 0.14)
                self.cartel.alfa += (Cartel.ALFA_VIDRIO - self.cartel.alfa) * paso
            self.ultimo_cuadro = ahora
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            if self.deslizar:
                recorrido = self.width() * self.direccion  # desde afuera de la ventana
                corrida_mascota = (1 - self.avance(0.0)) * recorrido
                corrida_cartel = (1 - self.avance(self.RETRASO) * self.k_cartel) * recorrido
            else:  # lejos del borde: aparece y se va con un fundido
                p.setOpacity(min(1.0, max(0.0, self.t)))
                corrida_mascota = corrida_cartel = 0.0
            cx, escala_pose, opacidad = self.pose()
            # La compañera se apoya en los pies (sobre la barra); el aviso, en el borde del sprite.
            base, apoyo = (self.pies_y, self.PIES) if self.compania else (self.sprite_y + self.sprite_h, 1.0)
            p.save()
            p.translate(corrida_mascota, 0)
            p.setOpacity(p.opacity() * opacidad)
            pintar_sombra(p, cx, base + (3 if self.compania else 0), self.sprite_w * escala_pose)
            rebote = 1 + 0.12 * math.sin(math.pi * self.rebote) * (1 - self.rebote)
            p.translate(cx, base)
            espejo = -1 if self.espejo else 1
            if self.especial:  # entrada o salida del estilo: dibujadas llegando desde la derecha
                pm = self.especial[max(0, self.cuadro_especial) % len(self.especial)][0]
                p.scale(-rebote if self.direccion < 0 else rebote, rebote)
            elif self.chicos and self.salida < 0.02:  # quieta en el borde: cuadros chicos, nítidos
                pm = self.chicos[self.cuadro % len(self.chicos)][0]
                p.scale(espejo * rebote, rebote)
            else:
                pm = self.cuadros[self.cuadro % len(self.cuadros)][0]
                p.scale(espejo * rebote * escala_pose, rebote * escala_pose)
            w, h = pm.width() / pm.devicePixelRatio(), pm.height() / pm.devicePixelRatio()
            p.drawPixmap(QPointF(-w / 2, -h * apoyo), pm)
            p.restore()

            if self.mostrar_cartel:
                p.translate(corrida_cartel, 0)
                p.setOpacity(p.opacity() * min(1.0, max(0.0, self.salida if self.chiquita() else 1.0)))
                self.cartel.pintar(p, self.cartel_cx, self.etiqueta_y, self.acento, self.restante / max(1, self.total))
            p.end()

    if MAC:  # sin ícono en el Dock: la mascota vive en la pantalla y en la barra de menús
        os.environ["QT_MAC_DISABLE_FOREGROUND_APPLICATION_TRANSFORM"] = "1"
    app = QApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(False)
    ventanas.app_de_fondo()
    ventanas.al_reabrir(reabrir_app)
    candado = Candado()
    duena = False
    for _ in range(20):
        if candado.tomar():
            duena = True
            break
        if enviar_a_la_existente():
            log(f"mascota existente actualizada a estado={datos['estado']}")
            return 0
        time.sleep(0.1)  # la otra está arrancando o terminando de irse
    if not duena:
        log("no se pudo coordinar con la mascota existente; se muestra igual")

    servidor = None
    if duena:
        servidor = QLocalServer()
        QLocalServer.removeServer(CANAL)
        if not servidor.listen(CANAL):
            log(f"no se pudo abrir el canal local: {servidor.errorString()}")
            servidor = None
    ventana = Mascota(servidor, candado)
    ventana.aplicar(datos)
    return app.exec()


def main() -> int:
    try:
        args = parsear(sys.argv[1:])
    except SystemExit as e:  # nunca salir con 2: en un hook Stop eso frena a Claude
        return 1 if e.code else 0
    if args.ui:
        try:
            return ejecutar_ui(args)
        except Exception:
            log("error en la ventana:\n" + traceback.format_exc())
            return 1
    try:
        evento = leer_evento()
        config = cargar_config(args.config)  # en cada aviso, así los cambios de ajustes.py valen ya
        idiomas.usar(config["idioma"])
        nombre = evento.get("hook_event_name") or "manual"
        estado = args.estado
        if nombre == "StopFailure":
            estado = "limite" if evento.get("error") == "rate_limit" else "error"
        anfitriona = ventanas.ventana_anfitriona() if evento else 0
        if nombre == "UserPromptSubmit":
            registrar_inicio(evento, anfitriona)
        if args.compania:
            lanzar_ventana({"estado": "idle", "mensaje": "", **apariencia(config), "modo": "compania",
                            "esquina": config["esquina"]})
            log("compañera abierta")
            return 0

        duracion = duracion_tarea(evento) if nombre == "Stop" else None
        motivo = "" if args.forzar else motivo_para_no_avisar(config, evento, estado, duracion, anfitriona)
        if nombre == "PermissionRequest" and evento.get("tool_name") in NO_SE_APRUEBAN:
            motivo = motivo or f"{evento.get('tool_name')} se responde en la terminal"
        compania = config["modo"] == "compania"
        # La compañera igual cambia de cara (sin sonido ni cartel), salvo eventos apagados o permisos.
        silencioso = bool(motivo) and compania and "desactivado" not in motivo and nombre != "PermissionRequest"
        # La Dynamic Island también muestra el pedido (aunque el cartel de la mascota tenga los permisos
        # apagados); si la isla lo toma, el cartel no sale.
        isla = None
        import pedidos
        if (nombre == "PermissionRequest" and config["barra"]["activa"] and config["barra"]["permisos"]
                and evento.get("tool_name") not in NO_SE_APRUEBAN and pedidos.isla_viva(PEDIDOS)
                and not motivo_para_no_avisar({**config, "permisos_desde_mascota": True}, evento, estado, None,
                                              anfitriona)):
            chat, proy = titulo_del_chat(evento) or evento.get("session_title") or "", proyecto(evento)
            isla = {"sesion": evento.get("session_id") or "", "herramienta": evento.get("tool_name") or "",
                    "etiqueta": pedidos.etiqueta(evento.get("tool_name") or "", evento.get("tool_input")),
                    # el detalle va tal cual (sin limpiarlo como markdown): es lo que se aprueba
                    "detalle": detalle_permiso(evento)[:1500], "proyecto": proy, "chat": chat,
                    "ventana": anfitriona,
                    "sonido": config["sonidos"].get("permiso", "ninguno") if config["sonido"] else ""}

        chat, proy = "", ""
        # Telegram decide aparte: aunque la mascota no se muestre (la terminal tiene el foco, una pregunta
        # que se contesta en la terminal), el celular avisa si no estás en la compu. Las pruebas no van.
        motivo_celular = ("es una prueba" if args.forzar or not evento else
                          motivo_para_no_mandar_al_celular(config, evento, estado, ventanas.segundos_inactivo()))
        # Un pedido de permiso de verdad va con los botones Permitir / Denegar (en vez del aviso común).
        telegram = None
        if (not motivo_celular and nombre == "PermissionRequest" and config["celular"]["permisos"]
                and evento.get("tool_name") not in NO_SE_APRUEBAN):
            chat, proy = titulo_del_chat(evento) or evento.get("session_title") or "", proyecto(evento)
            import celular
            telegram = {"llave": config["celular"]["llave"], "idioma": config["idioma"],
                        "espera": config["celular"]["espera_permisos"],
                        "texto": celular.texto_permiso(mensaje_para(estado, evento), detalle_permiso(evento),
                                                       " · ".join(d for d in (proy, chat if chat != proy else "") if d))}
            celular.repetido(f"{evento.get('session_id') or ''}|permiso")  # el aviso común de este permiso no va
            log(f"evento={nombre}: pedido de permiso a Telegram (espera {telegram['espera']} s)")
        elif not motivo_celular:
            chat, proy = titulo_del_chat(evento) or evento.get("session_title") or "", proyecto(evento)
            datos_cel = [formato_duracion(duracion) if duracion is not None else "", proy if proy != chat else "", chat]
            mandar_al_celular({"estado": estado, "sesion": evento.get("session_id") or "",
                               "mensaje": args.mensaje or mensaje_configurado(estado, evento, config, chat, proy),
                               "resumen": resumen_para(evento), "meta": " · ".join(d for d in datos_cel if d),
                               "aspecto": config["aspecto"], "imagen": config["imagen"],
                               "gif": config["celular"]["gif"]})
            log(f"evento={nombre} estado={estado}: mandado a Telegram")
        elif config["celular"]["activo"]:
            log(f"evento={nombre} estado={estado}: no va a Telegram porque {motivo_celular}")

        if motivo and not silencioso:
            log(f"evento={nombre} estado={estado}: no se avisa porque {motivo}")
            if telegram or isla:  # el cartel no se muestra, pero Telegram o la isla sí esperan
                responder_permiso(None, config["espera_permiso"], telegram, isla)
            return 0

        if not chat and not proy:
            chat, proy = titulo_del_chat(evento) or evento.get("session_title") or "", proyecto(evento)
        contenido = config["contenido"]
        # Del dato más corto al más largo: si no entra, se corta el título del chat y no la duración.
        varias = sesiones_activas() > 1  # con varias sesiones a la vez, el proyecto se muestra siempre
        datos = [formato_duracion(duracion) if contenido["duracion"] and duracion is not None else "",
                 proy if (contenido["proyecto"] or varias) and proy != chat else "",
                 chat if contenido["chat"] else ""]
        sonido = config["sonidos"].get(estado, "ninguno") if config["sonido"] and not silencioso else ""
        aviso = {
            "estado": estado,
            "mensaje": "" if silencioso else args.mensaje or mensaje_configurado(estado, evento, config, chat, proy),
            "resumen": resumen_para(evento) if contenido["resumen"] else "",
            "meta": args.detalle if args.detalle is not None else " · ".join(d for d in datos if d),
            "duracion": args.duracion or config["duracion"],
            "esquina": args.esquina or config["esquina"],
            "sonido": sonido,
            "ventana": anfitriona,
            "sesion": evento.get("session_id") or "",
            **apariencia(config),
        }
        if estado == "limite":  # la compañera duerme hasta que se renueve el límite
            aviso["despertar"] = hora_de_reinicio(" ".join(str(evento.get(c) or "") for c in
                                                           ("last_assistant_message", "error_details")))
        log(f"evento={nombre} estado={estado} mensaje={aviso['mensaje']!r} resumen={aviso['resumen'][:60]!r} "
            f"meta={aviso['meta']!r} aspecto={aviso['imagen'] or '-'.join(v for v in aviso['aspecto'].values() if isinstance(v, str))} "
            f"modo={aviso['modo']} tema={aviso['tema']} sonido={sonido or 'no'}"
            + (f" (silencioso: {motivo})" if silencioso else ""))
        if nombre == "PermissionRequest":
            responder_permiso(aviso, config["espera_permiso"], telegram, isla)
        else:
            lanzar_ventana(aviso)
    except Exception:
        log("error al lanzar la mascota:\n" + traceback.format_exc())
    return 0


def apariencia(config: dict) -> dict:
    """Lo que la ventana de la mascota necesita de los ajustes para verse como corresponde."""
    return {clave: config[clave] for clave in ("aspecto", "imagen", "tamano", "volumen", "tema", "modo", "vida",
                                               "posicion", "boton_enfocar", "no_molestar", "idioma")}


def lanzar_ventana(aviso: dict) -> None:
    lanzar_desacoplado([str(Path(__file__).resolve()), "--ui", f"--estado={aviso['estado']}",
                        "--aviso=" + json.dumps(aviso, ensure_ascii=False)])


def direccion_permiso() -> str:
    """Dónde espera el hook PermissionRequest la respuesta: un pipe con nombre en Windows; en macOS un
    socket en la carpeta temporal del usuario (corto: macOS no acepta rutas de más de 104 caracteres)."""
    if os.name == "nt":
        return rf"\\.\pipe\{CANAL}-permiso-{os.getpid()}"
    return str(Path(tempfile.gettempdir()) / f"wavemascot-permiso-{os.getpid()}")


def responder_permiso(aviso: dict | None, espera: int, telegram: dict | None = None,
                      isla: dict | None = None) -> None:
    """PermissionRequest: espera tu respuesta en la Dynamic Island o en el cartel de la mascota (Permitir /
    Denegar) y, si no estás en la compu, también en Telegram; lo primero que llegue se le devuelve a Claude
    Code y el otro lado se entera (la isla y el cartel se cierran, el mensaje de Telegram pierde los botones).
    Si nadie responde a tiempo no se devuelve nada y decide el diálogo de siempre de la terminal.

    Si la isla toma el pedido (contesta que lo está mostrando), el cartel no sale: un solo par de botones.
    aviso: el cartel de la mascota (None si no se muestra). telegram: {"llave", "texto", "idioma", "espera"}.
    isla: lo que muestra la isla (ver main), None si no va."""
    from multiprocessing.connection import Listener

    total = max(espera, telegram["espera"]) if telegram else espera
    resultado: dict = {}
    listo, candado = threading.Event(), threading.Lock()
    vista = threading.Event()   # la isla ya muestra el pedido
    fase = ["esperando"]        # de la isla: esperando -> tomada (lo muestra) o rendida (va el cartel)
    clave = ""                  # la del pedido: la isla la devuelve en cada respuesta
    pendientes = [int(bool(aviso)) + int(bool(telegram)) + int(bool(isla))]

    def decidir(decision: str, origen: str) -> None:
        with candado:
            if not listo.is_set():
                resultado.update(decision=decision, origen=origen)
                listo.set()

    def termino() -> None:  # un lado dejó de esperar sin respuesta: si eran todos, no se espera más
        with candado:
            pendientes[0] -= 1
            if pendientes[0] <= 0:
                listo.set()

    def por_la_mascota() -> None:
        try:
            with oyente.accept() as conexion:
                resultado["mostrado"] = True
                fin = time.time() + total + 5
                while time.time() < fin and not listo.is_set():
                    if conexion.poll(0.3):
                        mensaje = conexion.recv()
                        if mensaje.get("decision") in ("allow", "deny"):
                            decidir(mensaje["decision"], "mascota")
                        elif "decision" in mensaje:  # se fue sin elegir (se venció su cartel)
                            break
                if resultado.get("origen") == "telegram":  # que el cartel diga que se resolvió en el celu
                    conexion.send({"resuelto": resultado["decision"]})
        except (OSError, EOFError):
            pass
        termino()

    def por_telegram() -> None:
        import celular
        try:
            resultado["telegram"] = celular.pedir_permiso(telegram["llave"], telegram["texto"], telegram["idioma"],
                                                          telegram["espera"])
        except celular.ErrorCelular as e:
            log(f"permiso: no se pudo mandar a Telegram ({e})")
            termino()
            return
        fin = time.time() + telegram["espera"]
        while not listo.is_set() and time.time() < fin:
            try:
                decision = celular.esperar_permiso(telegram["llave"], resultado["telegram"],
                                                   int(min(20, max(1, fin - time.time()))))
            except celular.ErrorCelular as e:  # sin conexión un momento: se reintenta
                log(f"permiso: Telegram no respondió ({e})")
                time.sleep(3)
                continue
            if decision:
                decidir(decision, "telegram")
                return
        termino()

    def por_la_isla() -> None:
        import pedidos
        fin = time.time() + espera + 3
        while not listo.is_set() and time.time() < fin:
            contestado = pedidos.respuesta(PEDIDOS, os.getpid(), clave)
            with candado:  # tomada o rendida se decide una sola vez, acá o en el hilo principal
                if fase[0] == "esperando" and contestado.get("visto"):
                    fase[0] = "tomada"
                    resultado["mostrado"] = True
                    vista.set()
                elif fase[0] == "esperando" and time.time() > inicio + 1.5:
                    fase[0] = "rendida"
                actual = fase[0]
            if actual == "rendida":  # no contestó a tiempo: va el cartel, y que una isla lenta no lo muestre
                break
            if contestado.get("decision") in ("allow", "deny"):
                decidir(contestado["decision"], "isla")
                return
            if actual == "tomada" and contestado.get("visto") is False:
                log("permiso: la isla lo soltó (se apagó o se escondió)")
                break
            if actual == "tomada" and not pedidos.isla_viva(PEDIDOS):
                log("permiso: la isla dejó de responder")
                break
            listo.wait(0.15)
        pedidos.borrar(PEDIDOS, os.getpid())
        termino()

    hilo_mascota = direccion = None
    inicio = time.time()
    if telegram:  # Telegram no espera a ver si la isla toma el pedido
        threading.Thread(target=por_telegram, daemon=True).start()
    if isla:
        import pedidos
        try:
            clave = pedidos.nueva_clave()
            pedidos.anotar(PEDIDOS, os.getpid(), {**isla, "clave": clave, "creado": inicio, "vence": inicio + espera})
            threading.Thread(target=por_la_isla, daemon=True).start()
            vista.wait(1.6)
        except OSError as e:
            log(f"permiso: no se pudo anotar el pedido para la isla ({e})")
            isla = None
            termino()
        with candado:
            if fase[0] == "esperando":
                fase[0] = "rendida"
            tomada = fase[0] == "tomada"
        if tomada:
            log("permiso: lo muestra la Dynamic Island")
            if aviso:
                aviso = None
                termino()  # el cartel no va a esperar nada
    if aviso and listo.is_set():  # Telegram ya contestó mientras se esperaba a la isla: no hace falta cartel
        aviso = None
    if aviso:
        direccion = direccion_permiso()
        oyente = Listener(direccion, authkey=CLAVE_PERMISO)
        aviso.update(respuesta=direccion, duracion=total)
        lanzar_ventana(aviso)
        hilo_mascota = threading.Thread(target=por_la_mascota, daemon=True)
        hilo_mascota.start()
    # Si en 8 s no apareció el cartel ni salió el mensaje de Telegram, no se espera: decide la terminal.
    listo.wait(8)
    if resultado.get("mostrado") or resultado.get("telegram"):
        listo.wait(total + 5)
    decision, origen = resultado.get("decision"), resultado.get("origen")
    if isla:
        import pedidos
        pedidos.borrar(PEDIDOS, os.getpid())  # la isla se cierra sola al no verlo más
    if resultado.get("telegram") and origen != "telegram":
        import celular
        try:
            celular.cerrar_permiso(telegram["llave"], resultado["telegram"], "compu" if decision else "vencido", decision)
        except celular.ErrorCelular as e:
            log(f"permiso: no se pudo cerrar el mensaje de Telegram ({e})")
    if hilo_mascota:
        hilo_mascota.join(1.5)  # le avisa al cartel si se resolvió por Telegram
    if direccion and os.name != "nt":
        try:
            os.unlink(direccion)  # el socket del permiso (os._exit no deja que lo borre multiprocessing)
        except OSError:
            pass
    if decision not in ("allow", "deny"):
        log("permiso: sin respuesta en la mascota ni en Telegram, decide la terminal")
        return
    salida = {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": decision}}}
    if decision == "deny":
        donde = {"telegram": "Telegram", "isla": "the WaveMascot Dynamic Island"}.get(origen, "WaveMascot")
        salida["hookSpecificOutput"]["decision"]["message"] = f"The user denied it from {donde}."
    if sys.stdout:
        sys.stdout.write(json.dumps(salida))
        sys.stdout.flush()
    log(f"permiso: {decision} devuelto a Claude Code (desde {origen})")


if __name__ == "__main__":
    codigo = main()
    os._exit(codigo)  # no esperar al hilo que lee stdin
