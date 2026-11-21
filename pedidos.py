"""Pedidos de permiso que espera la Dynamic Island.

El hook PermissionRequest (mascota.py) anota cada pedido en un archivito, <pid>.json, dentro de
~/.wavemascot/permisos, con una clave al azar. La isla (barra.py, en el proceso del ícono) lo ve y contesta en
<pid>.isla.json, siempre con esa misma clave: {"clave", "visto": true} al mostrarlo, {"clave", "visto": true,
"decision": "allow" | "deny"} al tocar un botón y {"clave", "visto": false} si lo suelta (se apagó o se
escondió). El hook solo hace caso a respuestas con su clave: un archivo viejo que haya quedado de otro pedido
(Windows reusa los pid enseguida) nunca aprueba nada.

Mientras la isla puede mostrar pedidos toca el archivo "isla-viva" cada par de segundos; si está viejo, el
hook ni la espera y va directo al cartel de la mascota.

El hook borra sus archivos al terminar. Si murió (Claude Code lo corta a los 600 s, o se cerró la terminal)
quedan huérfanos: la isla los descarta por la hora de vencimiento o porque su proceso ya no existe, y barre
las respuestas sueltas y los temporales viejos.

Todo se escribe de forma atómica (un temporal y os.replace), así nadie lee un archivo a medio escribir. En
Windows reemplazar o borrar falla si el otro proceso justo lo está leyendo: se reintenta un momento.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shlex
import time
from pathlib import Path
from urllib.parse import urlparse

from idiomas import t

SUFIJO_RESPUESTA = ".isla.json"
VIVA = "isla-viva"
LATIDO = 2.0        # cada cuánto toca la isla su archivo
VIVA_HASTA = 6.0    # más viejo que esto: la isla no está (el ícono cerrado o colgado)


def _reintentar(accion, veces: int = 8):
    for intento in range(veces):
        try:
            return accion()
        except FileNotFoundError:
            raise
        except PermissionError:  # el otro proceso lo tiene abierto un instante
            if intento == veces - 1:
                raise
            time.sleep(0.02)


def _escribir(ruta: Path, datos: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(f"{ruta.name}.{os.getpid()}.tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    try:
        _reintentar(lambda: os.replace(temporal, ruta))
    except OSError:
        try:
            temporal.unlink()
        except OSError:
            pass
        raise


def _leer(ruta: Path) -> dict | None:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return datos if isinstance(datos, dict) else None


def _borrar(ruta: Path) -> None:
    try:
        _reintentar(ruta.unlink)
    except OSError:
        pass


def nueva_clave() -> str:
    return secrets.token_hex(8)


def anotar(carpeta: Path, pid: int, datos: dict) -> None:
    """El hook: deja el pedido a la vista de la isla (datos trae su "clave")."""
    _borrar(carpeta / f"{pid}{SUFIJO_RESPUESTA}")  # una respuesta vieja de otro proceso con el mismo pid
    _escribir(carpeta / f"{pid}.json", {**datos, "pid": pid})


def borrar(carpeta: Path, pid: int) -> None:
    for ruta in (carpeta / f"{pid}.json", carpeta / f"{pid}{SUFIJO_RESPUESTA}"):
        _borrar(ruta)


def contestar(carpeta: Path, pedido: dict, **datos) -> None:
    """La isla: visto=True al mostrarlo, decision=... al tocar un botón, visto=False si lo suelta."""
    _escribir(carpeta / f"{pedido['pid']}{SUFIJO_RESPUESTA}", {**datos, "clave": pedido.get("clave")})


def respuesta(carpeta: Path, pid: int, clave: str) -> dict:
    """El hook: lo que contestó la isla a este pedido (vacío si nada, o si la respuesta no es de este pedido)."""
    datos = _leer(carpeta / f"{pid}{SUFIJO_RESPUESTA}") or {}
    return datos if clave and datos.get("clave") == clave else {}


def latir(carpeta: Path) -> None:
    """La isla: "estoy y puedo mostrar pedidos"."""
    ruta = carpeta / VIVA
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.touch()
    except OSError:
        pass


def callar(carpeta: Path) -> None:
    """La isla: se apagó, se escondió o no muestra pedidos."""
    _borrar(carpeta / VIVA)


def isla_viva(carpeta: Path, ahora: float | None = None) -> bool:
    try:
        return (time.time() if ahora is None else ahora) - (carpeta / VIVA).stat().st_mtime < VIVA_HASTA
    except OSError:
        return False


def proceso_vivo(pid: int) -> bool:
    if not isinstance(pid, int) or not 0 < pid < 2 ** 31:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        k32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        manija = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not manija:
            return ctypes.get_last_error() == 5  # sin acceso: existe, pero es de otro usuario
        try:
            codigo = wintypes.DWORD()
            return bool(k32.GetExitCodeProcess(manija, ctypes.byref(codigo))) and codigo.value == 259  # STILL_ACTIVE
        finally:
            k32.CloseHandle(manija)
    try:
        os.kill(pid, 0)  # (en Windows esto lo mataría: por eso va solo en macOS / Linux)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def pendientes(carpeta: Path, ahora: float, vivo=proceso_vivo) -> list[dict]:
    """Los pedidos que siguen esperando, del más viejo al más nuevo. Los de hooks muertos se borran, y también
    las respuestas sin pedido y los temporales viejos."""
    try:
        entradas = list(os.scandir(carpeta))
    except OSError:
        return []
    pedidos_vivos = {e.name for e in entradas if e.name.endswith(".json") and not e.name.endswith(SUFIJO_RESPUESTA)}
    lista = []
    for entrada in entradas:
        nombre = entrada.name
        if nombre.endswith(SUFIJO_RESPUESTA) or nombre.endswith(".tmp"):
            pedido = nombre[:-len(SUFIJO_RESPUESTA)] + ".json" if nombre.endswith(SUFIJO_RESPUESTA) else ""
            try:
                viejo = ahora - entrada.stat().st_mtime > 60
            except OSError:
                continue
            if viejo and pedido not in pedidos_vivos:
                _borrar(Path(entrada.path))
            continue
        if nombre not in pedidos_vivos:
            continue
        datos = _leer(Path(entrada.path))
        pid = datos.get("pid") if datos else None
        if not isinstance(pid, int):
            continue
        if not vivo(pid):  # el hook murió sin poder borrarlo
            borrar(carpeta, pid)
            continue
        if not datos.get("clave"):
            continue
        vence = datos.get("vence")
        if not isinstance(vence, (int, float)) or vence <= ahora:
            continue  # se le pasó el tiempo a la isla; el hook lo borra al terminar (quizás espera a Telegram)
        lista.append(datos)
    return sorted(lista, key=lambda d: (d.get("creado") or 0, d["pid"]))


# --- la etiqueta: el permiso en una o dos palabras ----------------------------------

PREFIJOS = ("sudo", "env", "time", "nohup", "exec", "command", "&", "!", "(", "{", "call")
CAMBIAR_CARPETA = ("cd", "set-location", "pushd", "sl", "chdir")
SIN_SUBCOMANDO = ("echo", "printf", "cat", "ls", "rm", "cp", "mv", "mkdir", "touch", "write-host", "write-output",
                  "head", "tail", "grep", "find", "sleep", "start-sleep", "chmod", "chown")


def _palabras(tramo: str) -> list[str]:
    """Las palabras de un comando, respetando comillas (y las barras de Windows tal cual)."""
    try:
        lexer = shlex.shlex(tramo, posix=True)
        lexer.whitespace_split = True
        lexer.escape = ""  # C:\Program Files\... no son escapes
        return list(lexer)
    except ValueError:  # comillas sin cerrar
        return tramo.split()


def _tramos(comando: str) -> list[str]:
    """Los comandos de una cadena, cortando en && || ; | & y saltos de línea fuera de las comillas. Lo que va
    dentro de $(...) o `...` es otro comando más: se suma al final como un tramo "…"."""
    tramos, actual, comilla, i, adentro = [], [], "", 0, 0
    while i < len(comando):
        c = comando[i]
        if comilla:
            if c == comilla:
                comilla = ""
            elif comilla == '"' and (c == "`" or comando.startswith("$(", i)):
                adentro += 1  # algo se ejecuta adentro de las comillas dobles
            actual.append(c)
        elif c in "\"'":
            comilla = c
            actual.append(c)
        elif c == "`" or comando.startswith("$(", i):
            adentro += 1
            actual.append(c)
        elif c in ";|&\n":
            tramos.append("".join(actual))
            actual = []
            while i + 1 < len(comando) and comando[i + 1] in "|&":  # && y ||
                i += 1
        else:
            actual.append(c)
        i += 1
    tramos.append("".join(actual))
    return tramos + ["…"] * adentro


def renglones(comando: str) -> list[str]:
    """El comando para leerlo desplegado: un renglón por cada comando encadenado, con su operador al final
    ("git status &&", "git push --force"). Lo que está entre comillas no se corta."""
    lineas, actual, comilla, i = [], "", "", 0
    while i < len(comando):
        c = comando[i]
        if comilla:
            comilla = "" if c == comilla else comilla
            actual += c
        elif c in "\"'":
            comilla = c
            actual += c
        elif c == "\n":
            lineas.append(actual)
            actual = ""
        elif c == "&" and (actual.endswith(">") or comando[i + 1:i + 2] == ">"):
            actual += c  # redirección (2>&1, &>archivo), no otro comando
        elif c in ";|&":
            operador = comando[i:i + 2] if comando[i:i + 2] in ("&&", "||") else c
            i += len(operador) - 1
            lineas.append(actual.rstrip() + (";" if operador == ";" else f" {operador}"))
            actual = ""
        else:
            actual += c
        i += 1
    lineas.append(actual)
    return [" ".join(linea.split()) for linea in lineas if linea.strip()]


def _programas(comando: str) -> list[str]:
    """Cada comando de una cadena ("cd app && FOO=1 sudo npm install x; git push") como "npm install",
    "git push"; sin los cd. Lo que corre adentro de $(...) cuenta como "…"."""
    encontrados = []
    for tramo in _tramos(comando):
        if tramo == "…":
            encontrados.append(tramo)
            continue
        palabras = _palabras(re.sub(r"^(?:\$\(|[({`\s])+", "", tramo).strip())  # ($(cmd), `cmd`, (cd x
        while palabras:
            primera = palabras[0]
            if re.fullmatch(r"(\$env:)?\w+=.*", primera) or primera in PREFIJOS:
                palabras.pop(0)
                if primera == "sudo":  # sus opciones: sudo -u root npm
                    while palabras and palabras[0].startswith("-"):
                        opcion = palabras.pop(0)
                        if opcion in ("-u", "-g", "-C", "-D", "-h", "-p", "-U") and palabras:
                            palabras.pop(0)
            else:
                break
        if not palabras or palabras[0].lower() in CAMBIAR_CARPETA:
            continue
        nombre = re.split(r"[\\/]", palabras[0])[-1].rstrip(")}`")
        nombre = re.sub(r"\.(exe|cmd|bat|ps1|com)$", "", nombre, flags=re.I) or palabras[0]
        if (len(palabras) > 1 and nombre.lower() not in SIN_SUBCOMANDO
                and re.fullmatch(r"[a-z][\w:-]{0,15}", palabras[1])):
            encontrados.append(f"{nombre} {palabras[1]}")  # git push, npm install, docker compose
        else:
            encontrados.append(nombre)
    return encontrados


def etiqueta(herramienta: str, entrada: dict | None) -> str:
    """El permiso en una o dos palabras, para la isla: "git push", "Editar barra.py", "github.com".
    Si el comando encadena varios, va el primero con "…": el detalle completo se ve al pasarle el mouse."""
    entrada = entrada if isinstance(entrada, dict) else {}
    herramienta = herramienta or ""

    def texto(clave: str) -> str:
        valor = entrada.get(clave)
        return valor.strip() if isinstance(valor, str) else ""

    if herramienta in ("Bash", "PowerShell"):
        programas = _programas(texto("command"))
        if not programas or programas[0] == "…":
            return herramienta + (" …" if programas else "")
        return programas[0] + (" …" if len(programas) > 1 else "")
    archivo = texto("file_path") or texto("notebook_path")
    if archivo:
        nombre = re.split(r"[\\/]", archivo)[-1] or archivo
        editar = t("Editar {archivo}", archivo=nombre)
        return {"Edit": editar, "MultiEdit": editar, "NotebookEdit": editar,
                "Write": t("Escribir {archivo}", archivo=nombre),
                "Read": t("Leer {archivo}", archivo=nombre)}.get(herramienta, nombre)
    if herramienta == "WebFetch" and texto("url"):
        try:
            dominio = urlparse(texto("url")).hostname or ""  # sin usuario, clave ni puerto
        except ValueError:
            dominio = ""
        dominio = dominio[4:] if dominio.startswith("www.") else dominio
        return dominio or "WebFetch"
    if herramienta == "WebSearch":
        return t("Buscar en la web")
    if herramienta in ("Task", "Agent"):
        return texto("subagent_type") or t("Un agente")
    if herramienta.startswith("mcp__"):  # mcp__servidor__herramienta: lo que hace, sin el servidor
        return herramienta.split("__")[-1] or herramienta
    return herramienta or t("Un permiso")
