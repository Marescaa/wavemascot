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

__version__ = "1.2.0"
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
SESIONES = CONFIG_DIR / "sesiones"  # cuándo empezó la tarea de cada sesión (para la duración)


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
    for grupo in ("contenido", "eventos", "no_molestar", "vida", "sonidos"):
        if isinstance(datos.get(grupo), dict):
            for clave, defecto in config[grupo].items():
                if type(datos[grupo].get(clave)) is type(defecto):
                    config[grupo][clave] = datos[grupo][clave]
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
    return config


def guardar_config(config: dict, ruta: Path = CONFIG) -> None:
    """Escribe de forma atómica, así un aviso nunca lee un archivo a medio escribir."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(f"{ruta.stem}.{os.getpid()}.tmp")  # varios procesos pueden guardar
    temporal.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporal, ruta)


def silenciada(config: dict) -> bool:
    return config["silenciado_hasta"] > time.time()


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
        entrada = evento.get("tool_input") or {}
        detalle = next((entrada[c] for c in ("command", "file_path", "url", "pattern", "description", "prompt")
                        if isinstance(entrada.get(c), str) and entrada[c].strip()), "")
        return texto_corto(detalle, 120)
    return ""


# --- duración de la tarea ----------------------------------------------------------

def archivo_sesion(evento: dict) -> Path | None:
    sesion = re.sub(r"[^\w-]", "", str(evento.get("session_id") or ""))
    return SESIONES / f"{sesion}.json" if sesion else None


def registrar_inicio(evento: dict) -> None:
    """UserPromptSubmit: anota cuándo empezó la tarea y limpia sesiones viejas."""
    archivo = archivo_sesion(evento)
    if not archivo:
        return
    try:
        SESIONES.mkdir(parents=True, exist_ok=True)
        archivo.write_text(json.dumps({"inicio": time.time()}), encoding="utf-8")
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


class Cartel:
    """Mide y dibuja el cartel debajo de la mascota: mensaje, resumen, datos y botones."""

    ANCHO_TEXTO = 236
    BOTONES = {"permitir": "Permitir", "denegar": "Denegar", "enfocar": "Ir a la terminal"}

    def __init__(self):
        from PyQt6.QtGui import QFont

        self.fuente = fuente(10, QFont.Weight.DemiBold)
        self.fuente_resumen = fuente(8)
        self.fuente_meta = fuente(7)
        self.fuente_boton = fuente(8, QFont.Weight.DemiBold)
        self.mensaje = self.resumen = self.meta = ""
        self.botones: list[str] = []
        self.zonas: dict[str, object] = {}  # botón -> rectángulo en coordenadas del widget
        self.tema = "oscuro"
        self.ancho = self.alto = self.texto_h = self.resumen_h = self.meta_h = 0.0

    def medir(self, mensaje: str, resumen: str = "", meta: str = "", botones=()) -> None:
        from PyQt6.QtCore import QRectF, Qt
        from PyQt6.QtGui import QFontMetricsF

        self.mensaje, self.resumen, self.meta = mensaje, resumen, meta
        self.botones = [b for b in botones if b in self.BOTONES]
        envolver = int(Qt.AlignmentFlag.AlignHCenter) | int(Qt.TextFlag.TextWordWrap)
        fm = QFontMetricsF(self.fuente)
        r = fm.boundingRect(QRectF(0, 0, self.ANCHO_TEXTO, 1000), envolver, mensaje)
        self.texto_h = min(r.height(), fm.lineSpacing() * 3)
        ancho = r.width()
        self.resumen_h = self.meta_h = 0.0
        if resumen:  # hasta dos líneas
            fr = QFontMetricsF(self.fuente_resumen)
            rr = fr.boundingRect(QRectF(0, 0, self.ANCHO_TEXTO, 1000), envolver, resumen)
            self.resumen_h = min(rr.height(), fr.lineSpacing() * 2)
            ancho = max(ancho, rr.width())
        if meta:
            fmeta = QFontMetricsF(self.fuente_meta)
            self.meta_h = fmeta.lineSpacing()
            ancho = max(ancho, min(fmeta.horizontalAdvance(meta), self.ANCHO_TEXTO))
        fb = QFontMetricsF(self.fuente_boton)
        self.anchos_boton = [fb.horizontalAdvance(t(self.BOTONES[b])) + 20 for b in self.botones]
        if self.botones:
            ancho = max(ancho, sum(self.anchos_boton) + 6 * (len(self.botones) - 1))
        self.ancho = ancho + 28
        self.alto = (9 + self.texto_h + (3 + self.resumen_h if resumen else 0) + (3 + self.meta_h if meta else 0)
                     + (10 + 24 if self.botones else 0) + 13)

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
            base = {"fondo": QColor(30, 22, 19, 236), "texto": QColor(255, 247, 240), "barra": acento,
                    "borde": QColor(acento.red(), acento.green(), acento.blue(), 110), "tinta": QColor(255, 247, 240)}
        base["suave"], base["tenue"], base["boton"] = (QColor(base["tinta"]), QColor(base["tinta"]),
                                                       QColor(base["tinta"]))
        base["suave"].setAlpha(190)
        base["tenue"].setAlpha(135)
        base["boton"].setAlpha(28)
        base["principal"] = QColor(28, 21, 19) if self.tema == "acento" else acento
        base["texto_principal"] = QColor(255, 247, 240) if self.tema == "acento" else QColor(28, 21, 19)
        return base

    def pintar(self, p, cx: float, y: float, acento, fraccion: float) -> None:
        """Dibuja el cartel centrado en cx; fraccion es lo que queda de la barra de tiempo."""
        from PyQt6.QtCore import QRectF, Qt
        from PyQt6.QtGui import QFontMetricsF, QPainterPath, QPen

        c = self.colores(acento)
        caja = QRectF(cx - self.ancho / 2, y, self.ancho, self.alto)
        forma = QPainterPath()
        forma.addRoundedRect(caja, 11, 11)
        p.fillPath(forma, c["fondo"])
        p.setPen(QPen(c["borde"], 1))
        p.drawPath(forma)
        p.save()
        p.setClipPath(forma)
        p.fillRect(QRectF(caja.left(), caja.bottom() - 3, caja.width() * max(0.0, fraccion), 3), c["barra"])
        p.restore()

        izq, ancho = caja.left() + 14, caja.width() - 28
        centrado = int(Qt.AlignmentFlag.AlignHCenter)
        envolver = centrado | int(Qt.TextFlag.TextWordWrap)
        fila = caja.top() + 9
        p.setFont(self.fuente)
        p.setPen(c["texto"])
        p.drawText(QRectF(izq, fila, ancho, self.texto_h), envolver, self.mensaje)
        fila += self.texto_h
        if self.resumen:
            fila += 3
            fr = QFontMetricsF(self.fuente_resumen)
            texto = fr.elidedText(self.resumen, Qt.TextElideMode.ElideRight, ancho * 1.85)
            p.save()
            p.setClipRect(QRectF(izq, fila, ancho, self.resumen_h))
            p.setFont(self.fuente_resumen)
            p.setPen(c["suave"])
            p.drawText(QRectF(izq, fila, ancho, self.resumen_h + 20), envolver, texto)
            p.restore()
            fila += self.resumen_h
        if self.meta:
            fila += 3
            fmeta = QFontMetricsF(self.fuente_meta)
            p.setFont(self.fuente_meta)
            p.setPen(c["tenue"])
            p.drawText(QRectF(izq, fila, ancho, self.meta_h), centrado,
                       fmeta.elidedText(self.meta, Qt.TextElideMode.ElideRight, ancho))
            fila += self.meta_h
        self.zonas = {}
        if self.botones:
            fila += 10
            x = cx - (sum(self.anchos_boton) + 6 * (len(self.botones) - 1)) / 2
            p.setFont(self.fuente_boton)
            for clave, w in zip(self.botones, self.anchos_boton):
                zona = QRectF(x, fila, w, 24)
                principal = clave == "permitir"
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(c["principal"] if principal else c["boton"])
                p.drawRoundedRect(zona, 7, 7)
                p.setPen(c["texto_principal"] if principal else c["texto"])
                p.drawText(zona, int(Qt.AlignmentFlag.AlignCenter), t(self.BOTONES[clave]))
                self.zonas[clave] = p.transform().mapRect(zona)
                x += w + 6

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

    class Mascota(QWidget):
        RETRASO = 0.18   # el cartel entra un poco después que la mascota (y sale antes)
        BORDE = 14       # distancia al borde de la pantalla ya en su lugar
        HOLGURA = 18     # lugar del lado de adentro para el rebote al llegar
        MARGEN_ARRIBA = 36  # deja libres los botones de la barra de título
        ALTO_CARTEL_MAX = 170  # la compañera reserva este lugar para no saltar cuando aparece el cartel
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
            self.agarre = self.inicio_agarre = None
            self.arrastrada = False
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
            self.respuesta = d.get("respuesta")
            self.ventana_terminal = int(d.get("ventana") or 0)
            self.dpr = self.pantalla().devicePixelRatio()  # cada monitor puede tener otra escala
            self.conectar_permiso()
            self.mensaje = (d.get("mensaje") or "")[:120]
            botones = ["permitir", "denegar"] if self.respuesta else []
            if self.ventana_terminal and d.get("boton_enfocar", True) and self.mensaje:
                botones.append("enfocar")
            self.cartel.medir(self.mensaje, (d.get("resumen") or "")[:200], (d.get("meta") or "")[:120], botones)
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
            if en_su_lugar:
                self.anim_rebote.stop()
                self.anim_rebote.start()
            else:
                self.animar(1.0, 650)

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
                return
            hueco, arriba_extra = 2, 4  # el "pop" crece sobre la parte transparente del sprite
            contenido = max(self.sprite_w, self.cartel.ancho)
            ancho = math.ceil(contenido + self.BORDE + self.HOLGURA)
            alto = math.ceil(arriba_extra + self.sprite_h + hueco + self.cartel.alto + 10)
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

        def maquetar_compania(self, area, esquina: str, reubicar: bool) -> None:
            posicion = self.base.get("posicion")
            contenido = max(self.sprite_w, self.cartel.ANCHO_TEXTO + 28)
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
            self.cartel_cx = min(max(self.cx, self.cartel.ancho / 2 + 6), ancho - self.cartel.ancho / 2 - 6)
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
            self.animar(0.0, 300 if rapido else 480)

        def terminar(self) -> None:
            self.terminada = True
            self.soltar_permiso()
            if self.servidor:
                self.servidor.close()
            self.candado.soltar()
            self.hide()
            QApplication.quit()

        # acciones del cartel

        def accion(self, clave: str) -> None:
            if clave == "enfocar":
                ok = ventanas.enfocar(self.ventana_terminal)
                log(f"botón 'Ir a la terminal': {'enfocada' if ok else 'no se pudo enfocar'} ({self.ventana_terminal})")
                self.restante = 0
                if not self.compania:
                    self.salir(rapido=True)
            elif clave in ("permitir", "denegar"):
                self.responder("allow" if clave == "permitir" else "deny")
                self.cartel.medir(t("Permitido ✓") if clave == "permitir" else t("Denegado"), self.cartel.resumen)
                self.maquetar()
                self.total = self.restante = 1200
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

        def menu_compania(self, donde) -> None:
            idiomas.usar(cargar_config()["idioma"])  # pudo cambiar en los ajustes desde que se abrió
            menu = QMenu()
            menu.addAction(t("Abrir ajustes")).triggered.connect(self.abrir_ajustes)
            if self.base.get("posicion"):
                menu.addAction(t("Volver a la esquina")).triggered.connect(lambda: self.guardar_en_config(posicion=None))
            menu.addAction(t("Pasar a modo aviso")).triggered.connect(lambda: self.guardar_en_config(modo="aviso"))
            menu.addSeparator()
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
            self.inicio_agarre = evento.globalPosition().toPoint()
            self.agarre = self.inicio_agarre - self.pos()

        def mouseMoveEvent(self, evento) -> None:
            if self.agarre is None or not evento.buttons() & Qt.MouseButton.LeftButton:
                return
            if not self.arrastrada and (evento.globalPosition().toPoint() - self.inicio_agarre).manhattanLength() < 6:
                return
            if not self.arrastrada:
                self.mover_salida(1.0)  # mientras la llevás, se ve entera
            self.arrastrada, self.deslizar = True, False
            self.move(evento.globalPosition().toPoint() - self.agarre)

        def mouseReleaseEvent(self, evento) -> None:
            if self.agarre is None:
                return
            self.agarre = None
            if self.arrastrada:
                if self.compania:  # la compañera recuerda a qué altura la dejaste (y se pega al borde)
                    self.arrastrada = False
                    area = (QGuiApplication.screenAt(self.geometry().center()) or self.pantalla()).availableGeometry()
                    x = min(max(self.x(), area.x()), area.x() + area.width() - self.width())
                    self.guardar_en_config(posicion=[x, area.y() + area.height() - self.height()])
                    self.maquetar(reubicar=True)  # vuelve a pararse sobre la barra, en ese lugar
                    self.timer_esconder.start()
                return
            clave = self.cartel.boton_en(evento.position()) if self.mostrar_cartel else None
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
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            if self.deslizar:
                recorrido = self.width() * self.direccion  # desde afuera de la ventana
                corrida_mascota = (1 - self.avance(0.0)) * recorrido
                corrida_cartel = (1 - self.avance(self.RETRASO)) * recorrido
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
            if self.chicos and self.salida < 0.02:  # quieta en el borde: cuadros chicos, nítidos
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
                self.cartel.pintar(p, self.cartel_cx, self.etiqueta_y, self.acento, self.restante / self.total)
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
        if nombre == "UserPromptSubmit":
            registrar_inicio(evento)
        apariencia = {clave: config[clave] for clave in
                      ("aspecto", "imagen", "tamano", "volumen", "tema", "modo", "vida", "posicion", "boton_enfocar",
                       "no_molestar", "idioma")}
        if args.compania:
            lanzar_ventana({"estado": "idle", "mensaje": "", **apariencia, "modo": "compania",
                            "esquina": config["esquina"]})
            log("compañera abierta")
            return 0

        duracion = duracion_tarea(evento) if nombre == "Stop" else None
        anfitriona = ventanas.ventana_anfitriona() if evento else 0
        motivo = "" if args.forzar else motivo_para_no_avisar(config, evento, estado, duracion, anfitriona)
        if nombre == "PermissionRequest" and evento.get("tool_name") in NO_SE_APRUEBAN:
            motivo = motivo or f"{evento.get('tool_name')} se responde en la terminal"
        compania = config["modo"] == "compania"
        # La compañera igual cambia de cara (sin sonido ni cartel), salvo eventos apagados o permisos.
        silencioso = bool(motivo) and compania and "desactivado" not in motivo and nombre != "PermissionRequest"
        if motivo and not silencioso:
            log(f"evento={nombre} estado={estado}: no se avisa porque {motivo}")
            return 0

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
            **apariencia,
        }
        if estado == "limite":  # la compañera duerme hasta que se renueve el límite
            aviso["despertar"] = hora_de_reinicio(" ".join(str(evento.get(c) or "") for c in
                                                           ("last_assistant_message", "error_details")))
        log(f"evento={nombre} estado={estado} mensaje={aviso['mensaje']!r} resumen={aviso['resumen'][:60]!r} "
            f"meta={aviso['meta']!r} aspecto={aviso['imagen'] or '-'.join(aviso['aspecto'].values())} "
            f"modo={aviso['modo']} tema={aviso['tema']} sonido={sonido or 'no'}"
            + (f" (silencioso: {motivo})" if silencioso else ""))
        if nombre == "PermissionRequest":
            responder_permiso(aviso, config["espera_permiso"])
        else:
            lanzar_ventana(aviso)
    except Exception:
        log("error al lanzar la mascota:\n" + traceback.format_exc())
    return 0


def lanzar_ventana(aviso: dict) -> None:
    lanzar_desacoplado([str(Path(__file__).resolve()), "--ui", f"--estado={aviso['estado']}",
                        "--aviso=" + json.dumps(aviso, ensure_ascii=False)])


def direccion_permiso() -> str:
    """Dónde espera el hook PermissionRequest la respuesta: un pipe con nombre en Windows; en macOS un
    socket en la carpeta temporal del usuario (corto: macOS no acepta rutas de más de 104 caracteres)."""
    if os.name == "nt":
        return rf"\\.\pipe\{CANAL}-permiso-{os.getpid()}"
    return str(Path(tempfile.gettempdir()) / f"wavemascot-permiso-{os.getpid()}")


def responder_permiso(aviso: dict, espera: int) -> None:
    """PermissionRequest: muestra Permitir/Denegar y espera tu click para devolverle la decisión
    a Claude Code. Si no elegís a tiempo no se devuelve nada y decide el diálogo de siempre."""
    from multiprocessing.connection import Listener

    direccion = direccion_permiso()
    oyente = Listener(direccion, authkey=CLAVE_PERMISO)
    aviso.update(respuesta=direccion, duracion=espera)
    lanzar_ventana(aviso)
    resultado: dict = {}

    def esperar():
        try:
            with oyente.accept() as conexion:
                resultado["mostrado"] = True
                fin = time.time() + espera + 5
                while time.time() < fin and conexion.poll(max(0.1, fin - time.time())):
                    mensaje = conexion.recv()
                    if "decision" in mensaje:
                        resultado.update(mensaje)
                        return
        except (OSError, EOFError):
            pass

    hilo = threading.Thread(target=esperar, daemon=True)
    hilo.start()
    hilo.join(8)  # si en 8 s la mascota no mostró el cartel, no se la espera: decide la terminal
    if resultado.get("mostrado"):
        hilo.join(espera + 5)
    if os.name != "nt":
        try:
            os.unlink(direccion)  # el socket del permiso (os._exit no deja que lo borre multiprocessing)
        except OSError:
            pass
    decision = resultado.get("decision")
    if decision not in ("allow", "deny"):
        log("permiso: sin respuesta en la mascota, decide la terminal")
        return
    salida = {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": decision}}}
    if decision == "deny":
        salida["hookSpecificOutput"]["decision"]["message"] = "The user denied it from WaveMascot."
    if sys.stdout:
        sys.stdout.write(json.dumps(salida))
        sys.stdout.flush()
    log(f"permiso: {decision} devuelto a Claude Code")


if __name__ == "__main__":
    codigo = main()
    os._exit(codigo)  # no esperar al hilo que lee stdin
