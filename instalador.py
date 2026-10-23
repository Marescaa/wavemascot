#!/usr/bin/env python3
"""Instalador y desinstalador de WaveMascot (solo biblioteca estándar).

    python instalador.py configurar --destino DIR [--claude-dir DIR] [--sin-inicio]
    python instalador.py desinstalar [--destino DIR] [--claude-dir DIR] [--borrar-config] [--silencioso]
    python instalador.py detener --destino DIR
    WaveMascot-Setup.exe [--destino DIR] [--claude-dir DIR] [--sin-inicio] [--silencioso]

Agrega los hooks a ~/.claude/settings.json sin tocar los que ya tenías (guarda un backup
antes de cada cambio), crea el comando /wavemascot y los accesos directos. Desinstalar revierte
eso mismo: saca solo los hooks de la mascota y deja el resto como estaba antes de instalar.

En macOS no hay Setup.exe: WaveMascot.app se instala sola la primera vez que se abre (abrir_app).
El ícono de la barra de menús arranca al iniciar sesión con un LaunchAgent, y el manifiesto vive en
~/.wavemascot porque la app firmada no se puede modificar por dentro.
"""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

try:
    import idiomas
    from idiomas import t
except ImportError:  # sin idiomas.py al lado (p. ej. un desinstalador copiado solo): textos sin traducir
    idiomas = None

    def t(texto: str, **datos) -> str:
        return texto.format(**datos) if datos else texto

VERSION = "1.2.0"
NOMBRE = "WaveMascot"
CONGELADO = getattr(sys, "frozen", False)
MAC = sys.platform == "darwin"
MANIFIESTO = "instalacion.json"   # qué se instaló y qué había antes (para desinstalar)
MARCA = "wavemascot"          # aparece en el /wavemascot que crea el instalador
EXE = "WaveMascot.exe"
APP = "WaveMascot.app"
EXE_MAC = Path("Contents") / "MacOS" / NOMBRE  # el ejecutable dentro de WaveMascot.app
BUNDLE_ID = "io.github.marescaa.wavemascot"  # el de la app y el nombre del LaunchAgent
# Evento de Claude Code -> (estado de la mascota, timeout en segundos, async)
HOOKS = {
    "Stop": ("listo", 10, False),
    "Notification": ("permiso", 10, False),
    "UserPromptSubmit": ("pensando", 10, True),   # async: no demora el envío de tus mensajes
    "SubagentStop": ("subagente", 10, False),
    "StopFailure": ("limite", 10, False),
    "PermissionRequest": ("permiso", 600, False),  # espera tu Permitir/Denegar en la mascota o en Telegram
}
ARCHIVOS_FUENTE = ("mascota.py", "ajustes.py", "bandeja.py", "sprites.py", "ventanas.py", "instalador.py",
                   "idiomas.py", "celular.py", "actualizacion.py")


class ErrorInstalacion(Exception):
    pass


# --- rutas -----------------------------------------------------------------------

def appdata() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")


def acceso_inicio() -> Path:
    if MAC:  # macOS: un LaunchAgent de la sesión del usuario
        return Path.home() / "Library" / "LaunchAgents" / f"{BUNDLE_ID}.plist"
    return appdata() / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / f"{NOMBRE}.lnk"


def ruta_manifiesto(destino: Path) -> Path:
    """Dónde se anota qué se instaló: junto al programa, salvo WaveMascot.app (tocarla por dentro
    rompería su firma), que lo anota en ~/.wavemascot."""
    if destino.suffix == ".app":
        return Path.home() / ".wavemascot" / MANIFIESTO
    return destino / MANIFIESTO


def carpeta_menu() -> Path:
    return appdata() / "Microsoft" / "Windows" / "Start Menu" / "Programs" / NOMBRE


def destino_exe_por_defecto() -> Path:
    local = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    return local / "Programs" / "WaveMascot"


def pythonw() -> str:
    exe = Path(sys.executable)
    return str(exe.with_name("pythonw.exe") if exe.with_name("pythonw.exe").exists() else exe)


def lanzador(tipo: str, destino: Path, programa: str) -> list[str]:
    """Cómo se ejecuta cada parte: "pythonw mascota.py" (fuente) o "WaveMascot.exe mascota" (exe)."""
    if tipo == "exe":
        return [str(destino / (EXE_MAC if MAC else EXE))] + ([] if programa == "mascota" else [programa])
    return [pythonw(), str(destino / f"{programa}.py")]


def linea_de_comando(partes: list[str], *args: str) -> str:
    """Rutas con barras normales (andan en bash y en cmd); entre comillas solo si hace falta."""
    citar = any(" " in p for p in partes)
    rutas = [Path(p).as_posix() if os.sep in p or "/" in p else p for p in partes]
    texto = " ".join(f'"{r}"' if citar and ("/" in r) else r for r in rutas)
    return " ".join([texto, *args])


def comando_hook(tipo: str, destino: Path, estado: str) -> str:
    partes = lanzador(tipo, destino, "mascota")
    comando = linea_de_comando(partes, "--estado", estado)
    if MAC:  # en macOS se desinstala arrastrando a la papelera: si la app ya no está, el hook no hace nada
        return f"[ -e {shlex.quote(Path(partes[-1]).as_posix())} ] && {comando} || true"
    return comando


def comando_normalizado(hook) -> str:
    return str(hook.get("command", "")).replace("\\", "/").lower() if isinstance(hook, dict) else ""


def es_hook_nuestro(hook) -> bool:
    """Un hook de la mascota (de esta instalación o de otra versión anterior)."""
    c = comando_normalizado(hook)
    return (("/mascota.py" in c and "--estado" in c) or "wavemascot.exe" in c or "mascotaclaude.exe" in c
            or "wavemascot.app/contents/macos/wavemascot" in c)


def de_esta_instalacion(destino: Path):
    carpeta = destino.resolve().as_posix().lower().rstrip("/") + "/"
    return lambda hook: es_hook_nuestro(hook) and carpeta in comando_normalizado(hook)


# --- settings.json -----------------------------------------------------------------

def leer_json(ruta: Path) -> dict | None:
    """None si no existe. Si existe pero no es JSON válido, no se toca: se avisa y se corta."""
    if not ruta.exists():
        return None
    texto = ruta.read_text(encoding="utf-8-sig")
    if not texto.strip():
        return {}
    try:
        datos = json.loads(texto)
    except ValueError as e:
        raise ErrorInstalacion(t("{ruta} no es JSON válido ({error}); no lo modifico. Arreglalo y volvé a probar.",
                                 ruta=ruta, error=e))
    if not isinstance(datos, dict):
        raise ErrorInstalacion(t("{ruta} no tiene el formato esperado (un objeto JSON); no lo modifico.", ruta=ruta))
    return datos


def backup(ruta: Path) -> Path | None:
    if not ruta.exists():
        return None
    base = ruta.with_name(f"{ruta.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
    copia, n = base, 2
    while copia.exists():
        copia, n = base.with_name(f"{base.name}-{n}"), n + 1
    shutil.copy2(ruta, copia)
    return copia


def escribir_json(ruta: Path, datos: dict) -> Path | None:
    """Guarda un backup del archivo actual y lo reemplaza de forma atómica (con sus mismos saltos de línea)."""
    copia = backup(ruta)
    salto = "\r\n" if copia and b"\r\n" in copia.read_bytes() else "\n"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(f"{ruta.name}.{os.getpid()}.tmp")
    texto = json.dumps(datos, indent=2, ensure_ascii=False) + "\n"
    temporal.write_bytes(texto.replace("\n", salto).encode("utf-8"))
    os.replace(temporal, ruta)
    return copia


def separar_hooks(grupos: list, es_quitable) -> tuple[list, list]:
    """Divide los grupos de un evento en (lo que queda, lo que se saca). Los grupos sin hooks
    quitables quedan intactos; de los mixtos se saca solo lo quitable (conservando su matcher)."""
    quedan, sacados = [], []
    for grupo in grupos:
        if isinstance(grupo, dict) and isinstance(grupo.get("hooks"), list):
            ajenos = [h for h in grupo["hooks"] if not es_quitable(h)]
            if len(ajenos) == len(grupo["hooks"]):
                quedan.append(grupo)
                continue
            if ajenos:
                quedan.append({**grupo, "hooks": ajenos})
            sacados.append({**grupo, "hooks": [h for h in grupo["hooks"] if es_quitable(h)]})
        else:
            quedan.append(grupo)
    return quedan, sacados


def agregar_hooks(settings: dict, tipo: str, destino: Path, tambien=()) -> tuple[dict, dict]:
    """Devuelve (settings con los hooks, hooks de versiones anteriores de la mascota que se
    reemplazaron). Los reemplazados vuelven a su lugar al desinstalar. tambien: otras carpetas de esta
    misma instalación (WaveMascot.app que se movió de lugar), cuyos hooks no hay que reponer."""
    s = json.loads(json.dumps(settings))  # copia: el original no se toca
    if not isinstance(s.get("hooks"), dict):
        s["hooks"] = {}
    propias = [de_esta_instalacion(d) for d in (destino, *tambien)]
    reemplazados = {}
    for evento, (estado, timeout, asincrono) in HOOKS.items():
        grupos = s["hooks"].get(evento)
        grupos, sacados = separar_hooks(grupos if isinstance(grupos, list) else [], es_hook_nuestro)
        viejos = [{**g, "hooks": [h for h in g["hooks"] if not any(p(h) for p in propias)]} for g in sacados]
        if any(g["hooks"] for g in viejos):
            reemplazados[evento] = [g for g in viejos if g["hooks"]]
        hook = {"type": "command", "command": comando_hook(tipo, destino, estado), "timeout": timeout}
        if asincrono:
            hook["async"] = True
        s["hooks"][evento] = grupos + [{"hooks": [hook]}]
    return s, reemplazados


def quitar_hooks(settings: dict, manifiesto: dict, destino: Path) -> dict:
    """Saca los hooks de esta instalación y repone los de versiones anteriores que había
    reemplazado. Los eventos (y la clave "hooks") que no existían antes de instalar se borran
    si quedan vacíos; los que ya estaban se respetan aunque queden vacíos."""
    s = json.loads(json.dumps(settings))
    hooks = s.get("hooks")
    if not isinstance(hooks, dict):
        return s
    previos = set(manifiesto.get("eventos_previos") or [])
    for evento in list(hooks):
        if isinstance(hooks[evento], list):
            hooks[evento], _ = separar_hooks(hooks[evento], de_esta_instalacion(destino))
    for evento, grupos in (manifiesto.get("reemplazados") or {}).items():
        actuales = hooks.get(evento) if isinstance(hooks.get(evento), list) else []
        hooks[evento] = actuales + [g for g in grupos if g not in actuales]
    for evento in list(hooks):
        if hooks[evento] == [] and evento not in previos:
            del hooks[evento]
    if not hooks and not manifiesto.get("tenia_hooks", True):
        del s["hooks"]
    return s


# --- comando /wavemascot y accesos directos -------------------------------------------

def texto_comando(tipo: str, destino: Path) -> str:
    comando = linea_de_comando(lanzador(tipo, destino, "ajustes"))
    descripcion = t("Abre los ajustes de {nombre}", nombre=NOMBRE)
    return (f"---\ndescription: {descripcion}\nallowed-tools: Bash({comando})\n---\n"
            f"<!-- {MARCA}: created by the installer, removed on uninstall -->\n!`{comando}`\n\n"
            "The WaveMascot settings window is already open in a separate process (it does not block this "
            "session). Reply with one short line confirming it, without using any tools.\n")


def crear_comando(claude_dir: Path, tipo: str, destino: Path) -> tuple[Path | None, str]:
    ruta = claude_dir / "commands" / "wavemascot.md"
    if ruta.exists() and MARCA not in ruta.read_text(encoding="utf-8", errors="replace"):
        return None, t("ya existe un /wavemascot tuyo en {ruta}: no lo toco", ruta=ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(texto_comando(tipo, destino), encoding="utf-8")
    return ruta, t("comando /wavemascot: {ruta}", ruta=ruta)


def crear_agente_inicio(plist: Path, partes: list[str]) -> None:
    """macOS: LaunchAgent que abre el ícono de la barra de menús al iniciar sesión (se ve en
    Ajustes del Sistema → General → Ítems de inicio)."""
    datos = {"Label": BUNDLE_ID, "ProgramArguments": partes, "RunAtLoad": True, "ProcessType": "Interactive",
             "LimitLoadToSessionType": "Aqua", "AssociatedBundleIdentifiers": [BUNDLE_ID],
             "WorkingDirectory": str(Path(partes[-1]).parent if partes[-1].endswith(".py") else Path(partes[0]).parent)}
    plist.parent.mkdir(parents=True, exist_ok=True)
    temporal = plist.with_name(f"{plist.name}.{os.getpid()}.tmp")
    temporal.write_bytes(plistlib.dumps(datos))
    os.replace(temporal, plist)


def crear_acceso(lnk: Path, partes: list[str], icono: Path, descripcion: str) -> None:
    if MAC:
        crear_agente_inicio(lnk, partes)
        return
    lnk.parent.mkdir(parents=True, exist_ok=True)
    script = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:ACCESO); "
              "$s.TargetPath = $env:OBJETIVO; $s.Arguments = $env:ARGUMENTOS; "
              "$s.WorkingDirectory = $env:CARPETA; $s.IconLocation = $env:ICONO; "
              "$s.Description = $env:DESCRIPCION; $s.Save()")
    entorno = {**os.environ, "ACCESO": str(lnk), "OBJETIVO": partes[0],
               "ARGUMENTOS": " ".join(f'"{p}"' if " " in p else p for p in partes[1:]),
               "CARPETA": str(Path(partes[-1]).parent if partes[-1].endswith(".py") else Path(partes[0]).parent),
               "ICONO": str(icono), "DESCRIPCION": descripcion}
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], env=entorno, check=True,
                   timeout=60, capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def apunta_a(lnk: Path, destino: Path) -> bool:
    """Si el acceso directo abre algo de esa carpeta (ruta, argumentos o carpeta de trabajo)."""
    try:
        datos = lnk.read_bytes()
    except OSError:
        return False
    texto = " ".join(d.decode(c, errors="ignore") for d, c in
                     ((datos, "utf-16-le"), (datos[1:], "utf-16-le"), (datos, "latin-1"))).lower()
    if MAC:  # el LaunchAgent es un .plist de texto, con barras normales
        return Path(destino).as_posix().lower().rstrip("/") + "/" in texto.replace("\\", "/")
    return str(destino).lower().rstrip("\\") in texto.replace("/", "\\")


def detener_procesos_mac(destino: Path) -> None:
    """macOS: lo mismo con ps y señales. Solo procesos de Python o de WaveMascot.app que corren desde
    esa carpeta, nunca este ni los que lo lanzaron."""
    carpeta = destino.resolve().as_posix().lower().rstrip("/") + "/"

    def ps(campos: str) -> dict[int, str]:
        salida = subprocess.run(["/bin/ps", "-axww", "-o", campos], capture_output=True, text=True, timeout=30).stdout
        filas = (linea.strip().split(None, 1) for linea in salida.splitlines())
        return {int(f[0]): f[1] if len(f) > 1 else "" for f in filas if f and f[0].isdigit()}

    padres = {pid: int(texto) for pid, texto in ps("pid=,ppid=").items() if texto.strip().isdigit()}
    ejecutables, comandos = ps("pid=,comm="), ps("pid=,args=")
    no, actual = set(), os.getpid()
    while actual and actual not in no:
        no.add(actual)
        actual = padres.get(actual, 0)
    elegidos = [pid for pid, exe in ejecutables.items()
                if pid not in no and re.fullmatch(r"(python[\d.]*|wavemascot)", Path(exe).name, re.I)
                and carpeta in comandos.get(pid, "").lower()]
    for senal, espera in ((signal.SIGTERM, 3.0), (signal.SIGKILL, 1.0)):
        vivos = []
        for pid in elegidos:
            try:
                os.kill(pid, senal)
                vivos.append(pid)
            except OSError:
                pass
        fin = time.time() + espera
        while vivos and time.time() < fin:
            time.sleep(0.1)
            vivos = [pid for pid in vivos if _vive(pid)]
        elegidos = vivos


def _vive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def detener_procesos(destino: Path) -> None:
    """Cierra la mascota, el ícono y los ajustes que estén corriendo desde esa carpeta."""
    if MAC:
        detener_procesos_mac(destino)
        return
    if os.name != "nt":
        return
    # Nunca este proceso ni sus padres (la consola o el .exe que lanzó el desinstalador).
    script = ("$t = Get-CimInstance Win32_Process; $id = @{}; foreach ($p in $t) { $id[[int]$p.ProcessId] = $p }; "
              "$no = @{}; $i = [int]$env:PROPIO; "
              "while ($i -and $id.ContainsKey($i) -and -not $no.ContainsKey($i)) { $no[$i] = 1; "
              "$i = [int]$id[$i].ParentProcessId }; "
              "$t | Where-Object { -not $no.ContainsKey([int]$_.ProcessId) -and "
              "$_.Name -match '^(pythonw?|WaveMascot)\\.exe$' -and $_.CommandLine -and "
              "$_.CommandLine.ToLower().Replace('\\', '/').Contains($env:CARPETA) } | "
              "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
    entorno = {**os.environ, "PROPIO": str(os.getpid()),
               "CARPETA": destino.resolve().as_posix().lower().rstrip("/") + "/"}
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], env=entorno, timeout=60,
                   capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


# --- instalar / desinstalar -----------------------------------------------------------

def configurar(tipo: str, destino: Path, claude_dir: Path, sin_inicio: bool = False) -> list[str]:
    """Hooks, /wavemascot, accesos directos y manifiesto (los archivos ya tienen que estar en destino)."""
    destino, claude_dir = destino.resolve(), claude_dir.resolve()
    ruta_settings = claude_dir / "settings.json"
    previo = leer_json(ruta_settings)
    base = previo or {}
    anterior = leer_json(ruta_manifiesto(destino)) or {}  # reinstalar conserva lo que había ANTES de la 1.ª vez
    # macOS: si la app estaba instalada en otro lugar, sus hooks y su LaunchAgent son de esta misma instalación.
    otra = Path(anterior["destino"]) if anterior.get("destino") and anterior.get("tipo") == tipo else None
    otras = [otra] if otra and otra != destino else []
    manifiesto = {
        "version": VERSION, "tipo": tipo, "destino": str(destino), "claude_dir": str(claude_dir),
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "creado_settings": anterior.get("creado_settings", previo is None),
        "tenia_hooks": anterior.get("tenia_hooks", isinstance(base.get("hooks"), dict)),
        "eventos_previos": anterior.get("eventos_previos", list(base.get("hooks") or {})
                                        if isinstance(base.get("hooks"), dict) else []),
        "comando": None, "accesos": [],
    }
    informe = [t("{nombre} {version} ({tipo}) en {destino}", nombre=NOMBRE, version=VERSION, destino=destino,
                 tipo=t("ejecutable") if tipo == "exe" else t("código fuente"))]
    nuevo, reemplazados = agregar_hooks(base, tipo, destino, otras)
    manifiesto["reemplazados"] = {**(anterior.get("reemplazados") or {}), **reemplazados}
    copia = escribir_json(ruta_settings, nuevo)
    informe.append(t("hooks agregados a {ruta} (backup: {copia})", ruta=ruta_settings, copia=copia.name) if copia
                   else t("hooks agregados a {ruta} (archivo nuevo)", ruta=ruta_settings))
    if reemplazados:
        informe.append(t("reemplazados los hooks de una versión anterior de la mascota ({eventos}); "
                         "vuelven a su lugar si desinstalás", eventos=", ".join(reemplazados)))
    comando, texto = crear_comando(claude_dir, tipo, destino)
    manifiesto["comando"] = str(comando) if comando else None
    informe.append(texto)
    icono = (destino / "_internal" / "assets" / "icono.ico") if tipo == "exe" else destino / "assets" / "icono.ico"
    manifiesto["accesos_previos"] = anterior.get("accesos_previos") or {}
    if not sin_inicio:
        if (acceso_inicio().exists() and not apunta_a(acceso_inicio(), destino)
                and not any(apunta_a(acceso_inicio(), o) for o in otras)):
            # Un acceso con el mismo nombre de otra instalación: se guarda y vuelve al desinstalar.
            respaldo = ruta_manifiesto(destino).parent / "respaldo" / acceso_inicio().name
            respaldo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(acceso_inicio(), respaldo)
            manifiesto["accesos_previos"][str(acceso_inicio())] = str(respaldo)
        crear_acceso(acceso_inicio(), lanzador(tipo, destino, "bandeja"), icono, t("{nombre} (ícono junto al reloj)", nombre=NOMBRE))
        manifiesto["accesos"].append(str(acceso_inicio()))
        informe.append(t("ícono en la barra de menús al iniciar sesión") if MAC
                       else t("ícono junto al reloj al iniciar Windows"))
    if tipo == "exe" and not MAC:  # en macOS la app ya está en Aplicaciones (y en Launchpad)
        for nombre, programa in ((t("Ajustes de {nombre}", nombre=NOMBRE), "ajustes"),
                                 (t("Desinstalar {nombre}", nombre=NOMBRE), "desinstalar")):
            lnk = carpeta_menu() / f"{nombre}.lnk"
            crear_acceso(lnk, lanzador(tipo, destino, programa), icono, nombre)
            manifiesto["accesos"].append(str(lnk))
        informe.append(t("accesos en el menú Inicio: {carpeta}", carpeta=carpeta_menu()))
    ruta_manifiesto(destino).parent.mkdir(parents=True, exist_ok=True)
    ruta_manifiesto(destino).write_text(json.dumps(manifiesto, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return informe


def desinstalar(destino: Path, claude_dir: Path | None = None, borrar_config: bool = False) -> list[str]:
    destino = destino.resolve()
    manifiesto = leer_json(ruta_manifiesto(destino)) or {}
    if destino.suffix == ".app" and manifiesto.get("destino") not in (None, str(destino)):
        manifiesto = {}  # el manifiesto de ~/.wavemascot es de otra copia de la app
    claude_dir = (claude_dir or Path(manifiesto.get("claude_dir") or Path.home() / ".claude")).resolve()
    informe = [t("desinstalando {nombre} de {destino}", nombre=NOMBRE, destino=destino)]
    detener_procesos(destino)
    ruta_settings = claude_dir / "settings.json"
    actual = leer_json(ruta_settings)
    if actual is not None:
        limpio = quitar_hooks(actual, manifiesto, destino)
        if limpio != actual or (not limpio and manifiesto.get("creado_settings")):
            if not limpio and manifiesto.get("creado_settings"):  # lo había creado el instalador
                copia = backup(ruta_settings)
                ruta_settings.unlink()
                informe.append(t("{ruta} borrado (lo había creado el instalador; backup: {copia})",
                                 ruta=ruta_settings, copia=copia.name))
            else:
                copia = escribir_json(ruta_settings, limpio)
                informe.append(t("hooks de la mascota quitados de {ruta} (backup: {copia})",
                                 ruta=ruta_settings, copia=copia.name))
    comando = claude_dir / "commands" / "wavemascot.md"
    if comando.exists() and MARCA in comando.read_text(encoding="utf-8", errors="replace"):
        comando.unlink()
        informe.append(t("comando /wavemascot borrado"))
        try:
            comando.parent.rmdir()  # solo si quedó vacía
        except OSError:
            pass
    for lnk in {acceso_inicio(), *(Path(a) for a in manifiesto.get("accesos") or [])}:
        if lnk.exists() and apunta_a(lnk, destino):  # nunca uno de otra instalación
            lnk.unlink()
            if MAC:  # si launchd lo tiene cargado desde que se inició la sesión, que lo olvide
                try:
                    subprocess.run(["/bin/launchctl", "remove", BUNDLE_ID], capture_output=True, timeout=30)
                except (OSError, subprocess.SubprocessError):
                    pass
    for lnk, respaldo in (manifiesto.get("accesos_previos") or {}).items():
        if Path(respaldo).exists() and not Path(lnk).exists():
            shutil.copy2(respaldo, lnk)
            informe.append(t("repuesto el acceso directo que había antes: {nombre}", nombre=Path(lnk).name))
    if not MAC and carpeta_menu().exists() and not any(carpeta_menu().iterdir()):
        carpeta_menu().rmdir()
    informe.append(t("acceso de inicio borrado") if MAC else t("accesos directos borrados"))
    if borrar_config:
        shutil.rmtree(Path.home() / ".wavemascot", ignore_errors=True)
        informe.append(t("configuración borrada (~/.wavemascot)"))
    else:
        informe.append(t("tu configuración queda en ~/.wavemascot (borrala a mano si no la querés)"))
    informe.append(borrar_programa(destino, manifiesto))
    if destino.suffix == ".app" and manifiesto:  # lo que la app anotó en ~/.wavemascot
        ruta_manifiesto(destino).unlink(missing_ok=True)
        shutil.rmtree(ruta_manifiesto(destino).parent / "respaldo", ignore_errors=True)
    return informe


def borrar_programa(destino: Path, manifiesto: dict) -> str:
    """Borra la carpeta instalada, solo si la creó el instalador (y nunca un repositorio)."""
    if destino.suffix == ".app":  # macOS: el manifiesto está en ~/.wavemascot y dice qué app es
        instalada = bool(manifiesto) and manifiesto.get("destino") == str(destino)
    else:
        instalada = bool(manifiesto) and (destino / MANIFIESTO).exists()
    if not instalada or (destino / ".git").exists():
        return t("la carpeta {destino} no la creó el instalador: no la borro", destino=destino)
    os.chdir(Path.home())
    if CONGELADO and Path(sys.executable).resolve().is_relative_to(destino):
        if MAC:  # la app no se borra a sí misma mientras corre: lo hace sh apenas termine
            subprocess.Popen(["/bin/sh", "-c", 'sleep 2; rm -rf "$1"', "sh", str(destino)], start_new_session=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return t("la carpeta {destino} se borra en unos segundos", destino=destino)
        # El .exe no puede borrarse a sí mismo mientras corre: lo borra cmd apenas termine.
        subprocess.Popen(f'cmd /c ping 127.0.0.1 -n 3 > nul & rmdir /s /q "{destino}"', shell=True,
                         creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS)
        return t("la carpeta {destino} se borra en unos segundos", destino=destino)
    shutil.rmtree(destino, ignore_errors=True)
    return t("carpeta {destino} borrada", destino=destino)


def instalar_exe(destino: Path, claude_dir: Path, sin_inicio: bool) -> list[str]:
    """Instalador .exe: desempaqueta la app (app.zip, dentro del instalador) y la configura."""
    paquete = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "app.zip"
    if not paquete.exists():
        raise ErrorInstalacion(t("al instalador le falta app.zip (se arma con build.ps1)"))
    destino.mkdir(parents=True, exist_ok=True)
    detener_procesos(destino)
    for viejo in (destino / EXE, destino / "_internal"):  # se reemplaza la versión anterior
        if viejo.is_dir():
            shutil.rmtree(viejo)
        elif viejo.exists():
            viejo.unlink()
    with zipfile.ZipFile(paquete) as z:
        z.extractall(destino)
    informe = configurar("exe", destino, claude_dir, sin_inicio)
    if not sin_inicio:
        subprocess.Popen([str(destino / EXE), "bandeja"], cwd=destino,
                         creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    return informe


# --- macOS: WaveMascot.app se instala sola ------------------------------------------------

def app_actual() -> Path | None:
    """La WaveMascot.app desde la que corre este proceso (None si no es la app empaquetada)."""
    if not (MAC and CONGELADO):
        return None
    return next((p for p in Path(sys.executable).resolve().parents if p.suffix == ".app"), None)


def carpetas_aplicaciones() -> tuple[Path, Path]:
    return Path("/Applications"), Path.home() / "Applications"


def en_aplicaciones(app: Path) -> bool:
    """Fuera de Aplicaciones (el .dmg, Descargas o la copia temporal que hace macOS de las apps
    descargadas) la app no puede quedar conectada a Claude Code: esa ruta puede desaparecer."""
    return app.parent in carpetas_aplicaciones()


def destino_app_por_defecto() -> Path:
    sistema, usuario = carpetas_aplicaciones()
    return (sistema if os.access(sistema, os.W_OK) else usuario) / APP


def copiar_app(origen: Path, destino: Path) -> None:
    """Copia WaveMascot.app a Aplicaciones (reemplaza una versión anterior)."""
    if destino.exists():
        detener_procesos(destino)
        try:
            shutil.rmtree(destino)
        except OSError as e:
            raise ErrorInstalacion(t("No pude reemplazar {destino} ({error}). Arrastrá {nombre} a Aplicaciones "
                                     "desde el Finder y abrila desde ahí.", destino=destino, error=e, nombre=NOMBRE))
    destino.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["/usr/bin/ditto", str(origen), str(destino)], check=True, capture_output=True, timeout=600)
    # Ya autorizaste abrir esta app: la copia instalada no vuelve a pedirlo (lo mismo que hace el Finder
    # cuando la arrastrás desde el .dmg).
    subprocess.run(["/usr/bin/xattr", "-dr", "com.apple.quarantine", str(destino)], capture_output=True, timeout=120)


def abrir_programa(app: Path, programa: str) -> None:
    """Abre una parte de la app instalada, desacoplada de este proceso."""
    exe = app / EXE_MAC
    # Los ajustes van por LaunchServices para que la ventana aparezca adelante y con foco.
    cmd = (["/usr/bin/open", "-n", "-a", str(app), "--args", "ajustes", "--ventana"] if programa == "ajustes"
           else [str(exe), programa])
    subprocess.Popen(cmd, cwd=str(exe.parent), start_new_session=True, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def instalar_app(origen: Path, claude_dir: Path, sin_inicio: bool, preguntar=None,
                 destino: Path | None = None) -> list[str] | None:
    """macOS: deja WaveMascot.app en Aplicaciones (si se abrió desde el .dmg o desde Descargas), la
    conecta a Claude Code y abre el ícono. preguntar(destino) -> bool confirma antes; None si se canceló."""
    destino = (destino or (origen if en_aplicaciones(origen) else destino_app_por_defecto())).resolve()
    if preguntar and not preguntar(destino):
        return None
    if destino != origen.resolve():
        copiar_app(origen, destino)
    else:
        detener_procesos(destino)  # una versión anterior que siga abierta (el ícono, la compañera)
    informe = configurar("exe", destino, claude_dir, sin_inicio)
    if not sin_inicio:
        abrir_programa(destino, "bandeja")
    return informe


def abrir_app() -> int:
    """Doble click en WaveMascot.app: la primera vez la instala (o la actualiza, si arrastraste una
    versión nueva); después abre los ajustes y el ícono de la barra de menús."""
    if idiomas:
        idiomas.usar(idioma_guardado())
    origen = app_actual()
    if origen is None:
        return 0
    try:
        manifiesto = leer_json(ruta_manifiesto(origen)) or {}
    except ErrorInstalacion:
        manifiesto = {}
    instalada = en_aplicaciones(origen) and manifiesto.get("destino") == str(origen)
    try:
        if instalada and manifiesto.get("version") == VERSION:
            abrir_programa(origen, "bandeja")  # si ya está abierto, el nuevo se cierra solo
            abrir_programa(origen, "ajustes")
            return 0

        # Actualizar la misma app (arrastraste una versión nueva encima) no pregunta.
        preguntar = (lambda destino: True) if instalada else confirmar_instalacion
        informe = instalar_app(origen, Path.home() / ".claude", False, preguntar)
        if informe is None:
            return 0
    except (ErrorInstalacion, OSError, subprocess.SubprocessError) as e:
        mensaje(t("No se pudo completar:\n\n{error}", error=e), f"{NOMBRE}: error")
        return 1
    mensaje(t("Listo.") + "\n\n" + "\n".join(f"• {linea}" for linea in informe))
    return 0


# --- interfaz ------------------------------------------------------------------------

def idioma_guardado() -> str:
    try:
        return json.loads((Path.home() / ".wavemascot" / "config.json").read_text(encoding="utf-8"))["idioma"]
    except (OSError, ValueError, KeyError, TypeError):
        return idiomas.POR_DEFECTO if idiomas else "en"


def confirmar_instalacion(destino: Path) -> bool:
    return mensaje(t("¿Instalar {nombre} {version}?\n\nSe instala en {destino} y se agregan sus hooks a "
                     "~/.claude/settings.json sin tocar los que ya tengas (antes se guarda un backup).",
                     nombre=NOMBRE, version=VERSION, destino=destino), pregunta=True)


def mensaje(texto: str, titulo: str = NOMBRE, pregunta: bool = False) -> bool:
    """Cuadro de diálogo de Windows (el .exe no tiene consola). Devuelve True si se aceptó."""
    if MAC:
        return dialogo_mac(texto, titulo, pregunta)
    if os.name != "nt":
        print(texto)
        return True
    import ctypes
    flags = (0x4 | 0x20) if pregunta else 0x40  # MB_YESNO|MB_ICONQUESTION o MB_ICONINFORMATION
    return ctypes.windll.user32.MessageBoxW(None, texto, titulo, flags | 0x10000) in (1, 6)  # MB_SETFOREGROUND


def dialogo_mac(texto: str, titulo: str, pregunta: bool) -> bool:
    """El cuadro de diálogo de macOS (con osascript, sin dependencias), con el ícono de la mascota."""
    icono = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "assets" / "icono.icns"
    botones = [t("No"), t("Sí")] if pregunta else ["OK"]
    script = "\n".join([
        "on run argv",
        "activate",
        "set opciones to items 4 thru -1 of argv",
        "set r to display dialog (item 1 of argv) with title (item 2 of argv) buttons opciones "
        f"default button {len(botones)}" + (" cancel button 1" if pregunta else "")
        + (" with icon (POSIX file (item 3 of argv))" if icono.exists() else " with icon note"),
        "return button returned of r",
        "end run"])
    try:
        r = subprocess.run(["/usr/bin/osascript", "-e", script, texto, titulo, str(icono), *botones],
                           capture_output=True, text=True, timeout=3600)
    except (OSError, subprocess.SubprocessError):
        print(texto)
        return not pregunta
    return r.returncode == 0 and r.stdout.strip() == botones[-1]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    p = argparse.ArgumentParser(description=f"Instalador de {NOMBRE}")
    p.add_argument("accion", nargs="?", choices=("instalar", "configurar", "desinstalar", "detener"), default="instalar")
    p.add_argument("--tipo", choices=("fuente", "exe"), default="exe" if CONGELADO else "fuente")
    p.add_argument("--destino", type=Path)
    p.add_argument("--claude-dir", type=Path, help="carpeta de Claude Code (por defecto ~/.claude)")
    p.add_argument("--sin-inicio", action="store_true", help="sin ícono al iniciar Windows ni accesos del menú")
    p.add_argument("--borrar-config", action="store_true", help="al desinstalar, borrar también ~/.wavemascot")
    p.add_argument("--silencioso", action="store_true", help="sin cuadros de diálogo")
    p.add_argument("--dialogos", action="store_true", help=argparse.SUPPRESS)  # con cuadros aunque sea el código
    a = p.parse_args(argv)
    if idiomas:  # el idioma elegido en los ajustes; si todavía no hay, inglés
        idiomas.usar(idioma_guardado())
    interactivo = (CONGELADO or a.dialogos) and not a.silencioso
    try:
        if a.accion == "detener":
            detener_procesos(a.destino)
            return 0
        if a.accion == "configurar":
            informe = configurar(a.tipo, a.destino or Path(__file__).resolve().parent,
                                 a.claude_dir or Path.home() / ".claude", a.sin_inicio)
        elif a.accion == "desinstalar":
            destino = a.destino or app_actual() or (Path(sys.executable).parent if CONGELADO
                                                    else Path(__file__).resolve().parent)
            if interactivo and not mensaje(t("¿Desinstalar {nombre}?\n\nSe quitan solo sus hooks de "
                                             "~/.claude/settings.json (con backup); los tuyos quedan como estaban.",
                                             nombre=NOMBRE), pregunta=True):
                return 0
            informe = desinstalar(destino, a.claude_dir, a.borrar_config)
        elif MAC:  # instalar WaveMascot.app (lo mismo que abrirla, con opciones)
            if app_actual() is None:
                raise ErrorInstalacion(t("desde el código fuente se instala con install.sh"))
            informe = instalar_app(app_actual(), a.claude_dir or Path.home() / ".claude", a.sin_inicio,
                                   confirmar_instalacion if interactivo else None, a.destino)
            if informe is None:
                return 0
        else:  # instalar (el .exe)
            destino = a.destino or destino_exe_por_defecto()
            if interactivo and not confirmar_instalacion(destino):
                return 0
            informe = instalar_exe(destino, a.claude_dir or Path.home() / ".claude", a.sin_inicio)
    except (ErrorInstalacion, OSError, subprocess.SubprocessError) as e:
        if interactivo:
            mensaje(t("No se pudo completar:\n\n{error}", error=e), f"{NOMBRE}: error")
        print(f"ERROR: {e}", file=sys.stderr if sys.stderr else None)
        return 1
    if interactivo:
        mensaje(t("Listo.") + "\n\n" + "\n".join(f"• {linea}" for linea in informe))
    elif sys.stdout:
        print("\n".join(informe))
    return 0


if __name__ == "__main__":
    sys.exit(main())
