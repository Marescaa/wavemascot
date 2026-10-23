#!/usr/bin/env python3
"""¿Hay una versión nueva de WaveMascot? La busca en los releases de GitHub, la baja y la instala.

El ícono del reloj (bandeja.py) pregunta como mucho una vez cada 20 horas; si hay una más nueva, Wave
avisa una sola vez con su cartel (botones Actualizar / Ahora no) y los ajustes muestran una franja.
En Windows, con la app instalada, "Actualizar" baja WaveMascot-Setup.exe, lo comprueba con
SHA256SUMS.txt y lo corre sin preguntas (la config se mantiene). En macOS o desde el código fuente
se abre la página del release.

WAVEMASCOT_RELEASE=<archivo.json> reemplaza la respuesta de GitHub (para probar sin publicar nada).
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mascota as m  # noqa: E402

REPO = "Marescaa/wavemascot"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
PAGINA = f"https://github.com/{REPO}/releases/latest"
ESTADO = m.CONFIG_DIR / "actualizacion.json"  # cuándo se buscó, lo último encontrado y qué versión ya se avisó
CADA = 20 * 3600


class ErrorActualizacion(Exception):
    pass


def version_tupla(texto: str) -> tuple[int, ...]:
    numeros = [int(n) for n in re.findall(r"\d+", texto or "")[:3]]
    return tuple(numeros + [0] * (3 - len(numeros)))


def es_mas_nueva(version: str, actual: str = m.__version__) -> bool:
    return version_tupla(version) > version_tupla(actual)


def limpiar(texto: str) -> str:
    texto = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", texto)  # [texto](enlace)
    texto = re.sub(r"[*_`]+", "", texto)
    return " ".join(texto.split())


def novedades(cuerpo: str, cantidad: int = 4, largo: int = 110) -> list[str]:
    """Las novedades del release: los puntos principales de "What's new" (sale del CHANGELOG), cortos."""
    m_seccion = re.search(r"(?ims)^#+\s*(what's new|novedades|added)\b.*?$(.*?)(?=^#+\s|\Z)", cuerpo or "")
    if not m_seccion:
        return []
    puntos, actual = [], None
    for linea in m_seccion.group(2).splitlines():
        if linea.startswith("- "):  # punto principal (los "  - " son detalles)
            actual = [linea[2:]]
            puntos.append(actual)
        elif actual is not None and linea.startswith("  ") and not linea.lstrip().startswith("-"):
            actual.append(linea)  # el mismo punto, que sigue en otra línea
        else:
            actual = None
    salida = []
    for partes in puntos[:cantidad]:
        texto = limpiar(" ".join(partes))
        corte = re.search(r"(?<=[.:;])\s|,\s(?=with|con|com)", texto[:largo + 1])  # primera idea
        if corte and corte.start() >= 25:
            texto = texto[:corte.start()].rstrip(".,:;")
        texto = texto.rstrip(".")
        salida.append(texto if len(texto) <= largo else texto[:largo - 1].rstrip() + "…")
    return salida


def archivo_para_esta_compu(nombres: list[str]) -> str:
    """El instalador que corresponde a esta compu, entre los archivos del release."""
    if m.MAC:
        chip = "AppleSilicon" if platform.machine().lower() in ("arm64", "aarch64") else "Intel"
        return next((n for n in nombres if chip in n and n.endswith(".dmg")), "")
    return "WaveMascot-Setup.exe" if "WaveMascot-Setup.exe" in nombres else ""


def leer_release(datos: dict) -> dict:
    archivos = {a.get("name", ""): a.get("browser_download_url", "") for a in datos.get("assets") or []}
    instalador = archivo_para_esta_compu(list(archivos))
    return {"version": str(datos.get("tag_name") or "").lstrip("vV"),
            "novedades": novedades(datos.get("body") or ""),
            "pagina": datos.get("html_url") or PAGINA,
            "instalador": instalador, "url": archivos.get(instalador, ""),
            "sumas": archivos.get("SHA256SUMS.txt", "")}


def bajar(url: str, espera: float = 20) -> bytes:
    pedido = urllib.request.Request(url, headers={"User-Agent": f"WaveMascot/{m.__version__}",
                                                  "Accept": "application/vnd.github+json"})
    import celular  # el mismo contexto SSL (en macOS, los certificados del sistema)
    with urllib.request.urlopen(pedido, timeout=espera, context=celular.contexto_ssl()) as respuesta:
        return respuesta.read()


def ultimo_release() -> dict:
    prueba = os.environ.get("WAVEMASCOT_RELEASE")
    try:
        datos = json.loads(Path(prueba).read_text(encoding="utf-8") if prueba else bajar(API).decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError) as e:
        raise ErrorActualizacion(f"no se pudo consultar GitHub ({getattr(e, 'reason', e)})") from e
    return leer_release(datos)


def leer_estado() -> dict:
    try:
        datos = json.loads(ESTADO.read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def guardar_estado(datos: dict) -> None:
    try:
        ESTADO.parent.mkdir(parents=True, exist_ok=True)
        temporal = ESTADO.with_name(f"{ESTADO.stem}.{os.getpid()}.tmp")
        temporal.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        os.replace(temporal, ESTADO)
    except OSError:
        pass


def buscar(forzar: bool = False) -> dict | None:
    """La versión nueva ({"version", "novedades", "pagina", "url"...}) o None si estás al día.

    Sin forzar, usa lo que se encontró en las últimas 20 horas (GitHub limita las consultas)."""
    estado = leer_estado()
    if forzar or os.environ.get("WAVEMASCOT_RELEASE") or time.time() - estado.get("comprobado", 0) > CADA:
        estado.update(comprobado=time.time(), ultima=ultimo_release())
        guardar_estado(estado)
        m.log(f"[actualización] último release: {estado['ultima']['version']} (esta es la {m.__version__})")
    ultima = estado.get("ultima") or {}
    return ultima if es_mas_nueva(ultima.get("version", "")) else None


def ya_avisada(version: str) -> bool:
    return leer_estado().get("avisada") == version


def marcar_avisada(version: str) -> None:
    estado = leer_estado()
    estado["avisada"] = version
    guardar_estado(estado)


def se_instala_sola(info: dict) -> bool:
    """Windows con la app instalada (el .exe): se baja y se instala sin pasar por el navegador."""
    return os.name == "nt" and m.CONGELADO and bool(info.get("url"))


def descargar(info: dict, progreso=None) -> Path:
    """Baja el instalador a una carpeta temporal y lo comprueba con SHA256SUMS.txt."""
    destino = Path(tempfile.mkdtemp(prefix="wavemascot-")) / info["instalador"]
    pedido = urllib.request.Request(info["url"], headers={"User-Agent": f"WaveMascot/{m.__version__}"})
    import celular
    suma = hashlib.sha256()
    try:
        with urllib.request.urlopen(pedido, timeout=60, context=celular.contexto_ssl()) as respuesta, \
                destino.open("wb") as archivo:
            total, hecho = int(respuesta.headers.get("Content-Length") or 0), 0
            while trozo := respuesta.read(256 * 1024):
                archivo.write(trozo)
                suma.update(trozo)
                hecho += len(trozo)
                if progreso and total:
                    progreso(hecho / total)
        if info.get("sumas"):
            sumas = bajar(info["sumas"]).decode("utf-8", "replace")
            esperada = next((linea.split()[0] for linea in sumas.splitlines()
                             if linea.strip().endswith(info["instalador"])), "")
            if esperada and esperada.lower() != suma.hexdigest():
                destino.unlink(missing_ok=True)
                raise ErrorActualizacion("el archivo bajado no coincide con SHA256SUMS.txt")
    except (OSError, urllib.error.URLError) as e:
        raise ErrorActualizacion(f"no se pudo bajar ({getattr(e, 'reason', e)})") from e
    return destino


def instalar(ruta: Path) -> None:
    """Corre el instalador sin preguntas: cierra WaveMascot, la reemplaza y vuelve a abrir el ícono."""
    m.log(f"[actualización] instalando {ruta}")
    opciones = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
    if os.name == "nt":
        base = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        try:
            subprocess.Popen([str(ruta), "--silencioso"], creationflags=base | subprocess.CREATE_BREAKAWAY_FROM_JOB,
                             **opciones)
        except OSError:
            subprocess.Popen([str(ruta), "--silencioso"], creationflags=base, **opciones)
    else:
        subprocess.Popen(["/usr/bin/open", str(ruta)], start_new_session=True, **opciones)


def aviso_de_version(info: dict, config: dict) -> dict:
    """El cartel de Wave para una versión nueva (sin sonido: no es urgente)."""
    from idiomas import t

    lineas = info.get("novedades") or []
    return {"estado": "listo", "mensaje": t("¡Hay una versión nueva de WaveMascot!"),
            "resumen": t("Versión {version}", version=info["version"]) + (f": {lineas[0]}" if lineas else ""),
            "meta": t("Tenés la {version}", version=m.__version__), "duracion": 30, "esquina": config["esquina"],
            "sonido": "", "novedad": info["version"], **m.apariencia(config)}


def revisar_y_avisar(forzar: bool = False) -> dict | None:
    """Lo que hace el ícono del reloj de vez en cuando: si hay versión nueva y no se avisó, Wave avisa una vez.
    Devuelve la versión nueva (o None) para que el menú del ícono ofrezca actualizar."""
    import idiomas
    import ventanas

    config = m.cargar_config()
    if not config["actualizaciones"]["buscar"] and not forzar:
        return None
    info = buscar(forzar)
    if not info:
        return None
    version = info["version"]
    if version == config["actualizaciones"]["ignorada"] or ya_avisada(version):
        return info
    nm = config["no_molestar"]
    if m.silenciada(config) or (nm["activo"] and m.en_franja(nm["desde"], nm["hasta"])) or ventanas.pantalla_completa():
        return info  # se avisa en la próxima vuelta
    idiomas.usar(config["idioma"])
    m.lanzar_ventana(aviso_de_version(info, config))
    marcar_avisada(version)
    m.log(f"[actualización] Wave avisó de la versión {version}")
    return info
