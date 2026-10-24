#!/usr/bin/env python3
"""Avisos al celular por Telegram, con Wave animada, a través del bot oficial @WaveNotificationBot.

La clave del bot vive en el servidor de WaveMascot (servidor/worker.js), no en la app: cada instalación
se registra y recibe una llave propia, que solo sirve para mandarle avisos al chat que vinculó. Para
vincular, la app muestra un código de 6 letras y la persona se lo manda al bot (o toca el botón que
abre el bot con el código ya cargado). Sin librerías extra: es HTTPS común (urllib).

El hook lo lanza desacoplado ("celular.py --aviso=JSON"), así la red nunca demora a Claude Code.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import ssl
import sys
import time
import traceback
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import idiomas  # noqa: E402
import mascota as m  # noqa: E402
import sprites  # noqa: E402

SERVIDOR = os.environ.get("WAVEMASCOT_SERVIDOR", "https://wavemascot.wavemascot.workers.dev").rstrip("/")
BOT = "WaveNotificationBot"
ULTIMOS = m.CONFIG_DIR / "celular-ultimos.json"  # cuándo se mandó cada aviso (para no repetir)
FONDO = (0x1C, 0x15, 0x13)  # el mismo marrón oscuro de los ajustes


class ErrorCelular(Exception):
    """El servidor contestó con un error o no hubo conexión."""

    def __init__(self, texto: str, estado: int = 0, datos: dict | None = None):
        super().__init__(texto)
        self.estado, self.datos = estado, datos or {}


def contexto_ssl() -> ssl.SSLContext:
    contexto = ssl.create_default_context()
    if m.MAC and Path("/etc/ssl/cert.pem").is_file():
        # La app empaquetada no trae los certificados de Python.org: se usan los del sistema.
        contexto.load_verify_locations("/etc/ssl/cert.pem")
    return contexto


def pedir(metodo: str, ruta: str, llave: str = "", datos: dict | None = None,
          archivo: tuple[str, Path] | None = None, espera: float = 20) -> dict:
    """Llama al servidor y devuelve su respuesta (JSON). Un error del servidor o de red es ErrorCelular."""
    cabeceras = {"User-Agent": f"WaveMascot/{m.__version__}"}
    if llave:
        cabeceras["Authorization"] = f"Bearer {llave}"
    cuerpo = None
    if archivo:  # multipart a mano: un archivo y unos pocos campos de texto
        limite = uuid.uuid4().hex
        partes = [f'--{limite}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
                  for k, v in (datos or {}).items()]
        campo, ruta_archivo = archivo
        partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="{campo}"; filename="{ruta_archivo.name}"\r\n'
                      f'Content-Type: application/octet-stream\r\n\r\n'.encode() + ruta_archivo.read_bytes() + b"\r\n")
        partes.append(f"--{limite}--\r\n".encode())
        cuerpo = b"".join(partes)
        cabeceras["Content-Type"] = f"multipart/form-data; boundary={limite}"
    elif datos is not None:
        cuerpo = json.dumps(datos).encode()
        cabeceras["Content-Type"] = "application/json"
    pedido = urllib.request.Request(SERVIDOR + ruta, data=cuerpo, headers=cabeceras, method=metodo)
    try:
        with urllib.request.urlopen(pedido, timeout=espera, context=contexto_ssl()) as respuesta:
            return json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError as e:  # el servidor explica el error en el cuerpo
        try:
            respuesta = json.loads(e.read().decode("utf-8"))
        except ValueError:
            respuesta = {}
        raise ErrorCelular(respuesta.get("error") or f"HTTP {e.code}", e.code, respuesta) from e
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise ErrorCelular(f"sin conexión ({getattr(e, 'reason', e)})") from e


# --- conectar (lo usan los ajustes) ---------------------------------------------------

def registrar() -> dict:
    """Nueva instalación: {"llave", "codigo", "bot"}. La llave se guarda; el código se le muestra a la persona."""
    return pedir("POST", "/v1/registro", datos={})


def nuevo_codigo(llave: str) -> dict:
    return pedir("POST", "/v1/codigo", llave, datos={})


def estado(llave: str) -> dict:
    """{"conectado": bool, "nombre": nombre en Telegram, "plan": {...} o None, "precios", "dias_prueba"}."""
    return pedir("GET", "/v1/estado", llave)


def desconectar(llave: str) -> None:
    pedir("DELETE", "/v1/registro", llave)


# --- WaveMascot Pro ------------------------------------------------------------------
# Los avisos y los permisos por Telegram son de Pro (con días de prueba). Lo decide siempre el servidor,
# según la cuenta de Telegram vinculada: acá solo se muestra.

PRECIOS = {"mensual": 100, "vitalicio": 1500}  # en Telegram Stars; los de verdad los manda el servidor
DIAS_PRUEBA = 7


def planes() -> dict:
    """Precios y días de prueba (sin llave): {"cobrando", "precios", "dias_prueba"}."""
    return pedir("GET", "/v1/planes", espera=10)


def enlace_pro(plan: str = "", bot: str = BOT) -> str:
    """Abre el bot con los planes; con "mensual" o "vitalicio", ese plan primero."""
    return f"https://t.me/{bot}?start=pro" + (f"_{plan}" if plan in PRECIOS else "")


def precio(stars: int, idioma: str | None = None) -> str:
    """100 -> "US$ 1,99": lo que salen esas Stars en la tienda de Telegram (100 = 1,99; 1.500 = 29,99)."""
    valor = f"{stars * 0.02 - 0.01:.2f}"
    return "US$ " + (valor if (idioma or idiomas.actual()) == "en" else valor.replace(".", ","))


def estrellas(stars: int, idioma: str | None = None) -> str:
    """1500 -> "1.500" (o "1,500" en inglés)."""
    numero = f"{stars:,}"
    return numero if (idioma or idiomas.actual()) == "en" else numero.replace(",", ".")


def sin_pro(error: ErrorCelular) -> bool:
    """¿El servidor frenó el aviso porque hace falta Pro (terminó la prueba)?"""
    return error.estado == 402


# --- permisos (Permitir / Denegar desde Telegram) --------------------------------------

def texto_permiso(mensaje: str, detalle: str, meta: str) -> str:
    """El pedido en HTML de Telegram: qué quiere hacer Claude, el comando o archivo completo y el proyecto."""
    lineas = [f"🔐 <b>{html.escape(mensaje)}</b>"]
    if detalle:
        lineas.append(f"<pre>{html.escape(detalle[:3000])}</pre>")
    if meta:
        lineas.append(f"<i>{html.escape(meta)}</i>")
    return "\n".join(lineas)


def pedir_permiso(llave: str, texto: str, idioma: str, espera: int) -> str:
    """Manda el pedido con los botones; devuelve su id."""
    respuesta = pedir("POST", "/v1/permiso", llave, datos={"texto": texto, "idioma": idioma, "espera": espera})
    if not respuesta.get("ok") or not respuesta.get("id"):
        raise ErrorCelular(respuesta.get("error") or "no se pudo mandar el pedido", 0, respuesta)
    return respuesta["id"]


def esperar_permiso(llave: str, id_permiso: str, segundos: int = 20) -> str | None:
    """Espera hasta `segundos` a que toques un botón: "allow", "deny" o None (todavía nada, o ya se cerró)."""
    respuesta = pedir("GET", f"/v1/permiso/{id_permiso}?segundos={segundos}", llave, espera=segundos + 15)
    return respuesta.get("decision") if respuesta.get("decision") in ("allow", "deny") else None


def cerrar_permiso(llave: str, id_permiso: str, motivo: str, decision: str | None = None) -> None:
    """La compu lo resolvió ("compu", con la decisión si la hubo) o se venció: el mensaje pierde los botones."""
    pedir("POST", f"/v1/permiso/{id_permiso}/cerrar", llave, datos={"motivo": motivo, "decision": decision}, espera=10)


def codigo_visible(codigo: str) -> str:
    """ENRHPK -> ENR-HPK, más fácil de leer y de escribir."""
    return f"{codigo[:3]}-{codigo[3:]}" if len(codigo) == 6 else codigo


def enlace_bot(codigo: str = "", bot: str = BOT) -> str:
    """Abre el chat con el bot; con el código, al tocar «Iniciar» queda vinculado solo."""
    return f"https://t.me/{bot}" + (f"?start={codigo}" if codigo else "")


# --- mandar un aviso ----------------------------------------------------------------

def leer_json(ruta: Path) -> dict:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def escribir_json(ruta: Path, datos: dict) -> None:
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = ruta.with_name(f"{ruta.stem}.{os.getpid()}.tmp")
        temporal.write_text(json.dumps(datos), encoding="utf-8")
        os.replace(temporal, ruta)
    except OSError:
        pass


def repetido(clave: str, segundos: float = 90) -> bool:
    """¿Ya se mandó este mismo aviso hace poco? (un pedido de permiso llega como dos eventos)."""
    ahora, ultimos = time.time(), leer_json(ULTIMOS)
    ultimos = {k: v for k, v in ultimos.items() if isinstance(v, (int, float)) and ahora - v < 3600}
    if ahora - ultimos.get(clave, 0) < segundos:
        return True
    ultimos[clave] = ahora
    escribir_json(ULTIMOS, ultimos)
    return False


def texto(aviso: dict) -> str:
    """El mensaje en HTML de Telegram: el aviso en negrita, el resumen y los datos en cursiva."""
    lineas = [f"<b>{html.escape(aviso.get('mensaje') or '')}</b>"]
    if aviso.get("resumen"):
        lineas.append(html.escape(aviso["resumen"]))
    if aviso.get("meta"):
        lineas.append(f"<i>{html.escape(aviso['meta'])}</i>")
    return "\n".join(lineas)[:1024]  # lo máximo que Telegram acepta debajo de un GIF


def animacion(aviso: dict) -> tuple[str, str, Path] | None:
    """(tipo, clave, archivo) de la imagen del aviso, o None si va solo texto.

    La clave identifica al archivo en el servidor, que lo sube a Telegram una sola vez: los GIF de la
    mascota dibujada son iguales para todos; una imagen propia se identifica por su contenido."""
    if not aviso.get("gif", True):
        return None
    if aviso.get("imagen"):
        propia = m.IMAGENES / Path(aviso["imagen"]).name
        if propia.is_file():
            tipo = "animation" if propia.suffix.lower() == ".gif" else "photo"
            return tipo, "propia/" + hashlib.sha256(propia.read_bytes()).hexdigest()[:32], propia
    estado_aviso = aviso.get("estado") if aviso.get("estado") in sprites.ESTADOS else "listo"
    ruta = sprites.gif_celular(aviso.get("aspecto") or {}, estado_aviso, FONDO)
    return "animation", f"{ruta.parent.name}/{ruta.stem}", ruta


def enviar(llave: str, aviso: dict) -> None:
    """Manda el aviso. El GIF va por su clave; si el servidor todavía no lo tiene, se sube una vez."""
    datos = {"texto": texto(aviso)}
    imagen = animacion(aviso)
    if imagen:
        tipo, clave, ruta = imagen
        datos.update(gif=clave, tipo=tipo)
        respuesta = pedir("POST", "/v1/aviso", llave, datos=datos)
        if respuesta.get("falta_gif"):
            respuesta = pedir("POST", "/v1/aviso", llave, datos=datos, archivo=("archivo", ruta), espera=40)
    else:
        respuesta = pedir("POST", "/v1/aviso", llave, datos=datos)
    if not respuesta.get("ok"):
        raise ErrorCelular(respuesta.get("error") or "no se pudo mandar", 0, respuesta)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Manda un aviso de WaveMascot a Telegram.")
    p.add_argument("--aviso", required=True, help="JSON con mensaje, resumen, meta, estado y aspecto")
    try:
        args = p.parse_args(argv)
        aviso = json.loads(args.aviso)
    except (SystemExit, ValueError):
        return 0
    cel = m.cargar_config()["celular"]
    if not cel["llave"]:
        return 0
    if aviso.get("estado") == "permiso" and repetido(f"{aviso.get('sesion')}|permiso"):
        m.log("[celular] el pedido de permiso ya se mandó hace un momento")
        return 0
    try:
        enviar(cel["llave"], aviso)
        m.log(f"[celular] aviso «{aviso.get('estado')}» mandado a Telegram")
    except ErrorCelular as e:
        if sin_pro(e):  # el bot ya le explicó a la persona qué pasó (una sola vez)
            m.log("[celular] no va a Telegram: hace falta WaveMascot Pro (terminó la prueba)")
        else:
            m.log(f"[celular] no se pudo mandar a Telegram: {e}")
    return 0


if __name__ == "__main__":
    try:
        codigo = main(sys.argv[1:])
    except Exception:
        m.log("[celular] error:\n" + traceback.format_exc())
        codigo = 0
    os._exit(codigo)
