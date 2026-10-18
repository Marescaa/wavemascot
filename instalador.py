#!/usr/bin/env python3
"""Instalador y desinstalador de WaveMascot (solo biblioteca estándar).

    python instalador.py configurar --destino DIR [--claude-dir DIR] [--sin-inicio]
    python instalador.py desinstalar [--destino DIR] [--claude-dir DIR] [--borrar-config] [--silencioso]
    python instalador.py detener --destino DIR
    WaveMascot-Setup.exe [--destino DIR] [--claude-dir DIR] [--sin-inicio] [--silencioso]

Agrega los hooks a ~/.claude/settings.json sin tocar los que ya tenías (guarda un backup
antes de cada cambio), crea el comando /wavemascot y los accesos directos. Desinstalar revierte
eso mismo: saca solo los hooks de la mascota y deja el resto como estaba antes de instalar.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

VERSION = "1.0.0"
NOMBRE = "WaveMascot"
CONGELADO = getattr(sys, "frozen", False)
MANIFIESTO = "instalacion.json"   # qué se instaló y qué había antes (para desinstalar)
MARCA = "wavemascot"          # aparece en el /wavemascot que crea el instalador
EXE = "WaveMascot.exe"
# Evento de Claude Code -> (estado de la mascota, timeout en segundos, async)
HOOKS = {
    "Stop": ("listo", 10, False),
    "Notification": ("permiso", 10, False),
    "UserPromptSubmit": ("pensando", 10, True),   # async: no demora el envío de tus mensajes
    "SubagentStop": ("subagente", 10, False),
    "StopFailure": ("limite", 10, False),
    "PermissionRequest": ("permiso", 150, False),  # espera tu Permitir/Denegar en la mascota
}
ARCHIVOS_FUENTE = ("mascota.py", "ajustes.py", "bandeja.py", "sprites.py", "ventanas.py", "instalador.py")


class ErrorInstalacion(Exception):
    pass


# --- rutas -----------------------------------------------------------------------

def appdata() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")


def acceso_inicio() -> Path:
    return appdata() / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / f"{NOMBRE}.lnk"


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
        return [str(destino / EXE)] + ([] if programa == "mascota" else [programa])
    return [pythonw(), str(destino / f"{programa}.py")]


def linea_de_comando(partes: list[str], *args: str) -> str:
    """Rutas con barras normales (andan en bash y en cmd); entre comillas solo si hace falta."""
    citar = any(" " in p for p in partes)
    rutas = [Path(p).as_posix() if os.sep in p or "/" in p else p for p in partes]
    texto = " ".join(f'"{r}"' if citar and ("/" in r) else r for r in rutas)
    return " ".join([texto, *args])


def comando_normalizado(hook) -> str:
    return str(hook.get("command", "")).replace("\\", "/").lower() if isinstance(hook, dict) else ""


def es_hook_nuestro(hook) -> bool:
    """Un hook de la mascota (de esta instalación o de otra versión anterior)."""
    c = comando_normalizado(hook)
    return ("/mascota.py" in c and "--estado" in c) or "wavemascot.exe" in c or "mascotaclaude.exe" in c


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
        raise ErrorInstalacion(f"{ruta} no es JSON válido ({e}); no lo modifico. Arreglalo y volvé a probar.")
    if not isinstance(datos, dict):
        raise ErrorInstalacion(f"{ruta} no tiene el formato esperado (un objeto JSON); no lo modifico.")
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


def agregar_hooks(settings: dict, tipo: str, destino: Path) -> tuple[dict, dict]:
    """Devuelve (settings con los hooks, hooks de versiones anteriores de la mascota que se
    reemplazaron). Los reemplazados vuelven a su lugar al desinstalar."""
    s = json.loads(json.dumps(settings))  # copia: el original no se toca
    if not isinstance(s.get("hooks"), dict):
        s["hooks"] = {}
    propia = de_esta_instalacion(destino)
    reemplazados = {}
    for evento, (estado, timeout, asincrono) in HOOKS.items():
        grupos = s["hooks"].get(evento)
        grupos, sacados = separar_hooks(grupos if isinstance(grupos, list) else [], es_hook_nuestro)
        viejos = [{**g, "hooks": [h for h in g["hooks"] if not propia(h)]} for g in sacados]
        if any(g["hooks"] for g in viejos):
            reemplazados[evento] = [g for g in viejos if g["hooks"]]
        hook = {"type": "command", "command": linea_de_comando(lanzador(tipo, destino, "mascota"), "--estado", estado),
                "timeout": timeout}
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
    return (f"---\ndescription: Abre los ajustes de {NOMBRE}\nallowed-tools: Bash({comando})\n---\n"
            f"<!-- {MARCA}: lo creó el instalador y se borra al desinstalar -->\n!`{comando}`\n\n"
            "La ventana de ajustes de la mascota ya se abrió en un proceso aparte (no bloquea esta sesión). "
            "Respondé solo con una línea breve confirmándolo, sin usar herramientas.\n")


def crear_comando(claude_dir: Path, tipo: str, destino: Path) -> tuple[Path | None, str]:
    ruta = claude_dir / "commands" / "wavemascot.md"
    if ruta.exists() and MARCA not in ruta.read_text(encoding="utf-8", errors="replace"):
        return None, f"ya existe un /wavemascot tuyo en {ruta}: no lo toco"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(texto_comando(tipo, destino), encoding="utf-8")
    return ruta, f"comando /wavemascot: {ruta}"


def crear_acceso(lnk: Path, partes: list[str], icono: Path, descripcion: str) -> None:
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
    return str(destino).lower().rstrip("\\") in texto.replace("/", "\\")


def detener_procesos(destino: Path) -> None:
    """Cierra la mascota, el ícono y los ajustes que estén corriendo desde esa carpeta."""
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
    anterior = leer_json(destino / MANIFIESTO) or {}  # reinstalar conserva lo que había ANTES de la 1.ª vez
    manifiesto = {
        "version": VERSION, "tipo": tipo, "destino": str(destino), "claude_dir": str(claude_dir),
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "creado_settings": anterior.get("creado_settings", previo is None),
        "tenia_hooks": anterior.get("tenia_hooks", isinstance(base.get("hooks"), dict)),
        "eventos_previos": anterior.get("eventos_previos", list(base.get("hooks") or {})
                                        if isinstance(base.get("hooks"), dict) else []),
        "comando": None, "accesos": [],
    }
    informe = [f"{NOMBRE} {VERSION} ({'ejecutable' if tipo == 'exe' else 'código fuente'}) en {destino}"]
    nuevo, reemplazados = agregar_hooks(base, tipo, destino)
    manifiesto["reemplazados"] = {**(anterior.get("reemplazados") or {}), **reemplazados}
    copia = escribir_json(ruta_settings, nuevo)
    informe.append(f"hooks agregados a {ruta_settings}" + (f" (backup: {copia.name})" if copia else " (archivo nuevo)"))
    if reemplazados:
        informe.append(f"reemplazados los hooks de una versión anterior de la mascota ({', '.join(reemplazados)}); "
                       "vuelven a su lugar si desinstalás")
    comando, texto = crear_comando(claude_dir, tipo, destino)
    manifiesto["comando"] = str(comando) if comando else None
    informe.append(texto)
    icono = (destino / "_internal" / "assets" / "icono.ico") if tipo == "exe" else destino / "assets" / "icono.ico"
    manifiesto["accesos_previos"] = anterior.get("accesos_previos") or {}
    if not sin_inicio:
        if acceso_inicio().exists() and not apunta_a(acceso_inicio(), destino):
            # Un acceso con el mismo nombre de otra instalación: se guarda y vuelve al desinstalar.
            respaldo = destino / "respaldo" / acceso_inicio().name
            respaldo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(acceso_inicio(), respaldo)
            manifiesto["accesos_previos"][str(acceso_inicio())] = str(respaldo)
        crear_acceso(acceso_inicio(), lanzador(tipo, destino, "bandeja"), icono, f"{NOMBRE} (ícono junto al reloj)")
        manifiesto["accesos"].append(str(acceso_inicio()))
        informe.append("ícono junto al reloj al iniciar Windows")
    if tipo == "exe":
        for nombre, programa in ((f"Ajustes de {NOMBRE}", "ajustes"), (f"Desinstalar {NOMBRE}", "desinstalar")):
            lnk = carpeta_menu() / f"{nombre}.lnk"
            crear_acceso(lnk, lanzador(tipo, destino, programa), icono, nombre)
            manifiesto["accesos"].append(str(lnk))
        informe.append(f"accesos en el menú Inicio: {carpeta_menu()}")
    (destino / MANIFIESTO).write_text(json.dumps(manifiesto, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return informe


def desinstalar(destino: Path, claude_dir: Path | None = None, borrar_config: bool = False) -> list[str]:
    destino = destino.resolve()
    manifiesto = leer_json(destino / MANIFIESTO) or {}
    claude_dir = (claude_dir or Path(manifiesto.get("claude_dir") or Path.home() / ".claude")).resolve()
    informe = [f"desinstalando {NOMBRE} de {destino}"]
    detener_procesos(destino)
    ruta_settings = claude_dir / "settings.json"
    actual = leer_json(ruta_settings)
    if actual is not None:
        limpio = quitar_hooks(actual, manifiesto, destino)
        if limpio != actual or (not limpio and manifiesto.get("creado_settings")):
            if not limpio and manifiesto.get("creado_settings"):  # lo había creado el instalador
                copia = backup(ruta_settings)
                ruta_settings.unlink()
                informe.append(f"{ruta_settings} borrado (lo había creado el instalador; backup: {copia.name})")
            else:
                copia = escribir_json(ruta_settings, limpio)
                informe.append(f"hooks de la mascota quitados de {ruta_settings} (backup: {copia.name})")
    comando = claude_dir / "commands" / "wavemascot.md"
    if comando.exists() and MARCA in comando.read_text(encoding="utf-8", errors="replace"):
        comando.unlink()
        informe.append("comando /wavemascot borrado")
        try:
            comando.parent.rmdir()  # solo si quedó vacía
        except OSError:
            pass
    for lnk in {acceso_inicio(), *(Path(a) for a in manifiesto.get("accesos") or [])}:
        if lnk.exists() and apunta_a(lnk, destino):  # nunca uno de otra instalación
            lnk.unlink()
    for lnk, respaldo in (manifiesto.get("accesos_previos") or {}).items():
        if Path(respaldo).exists() and not Path(lnk).exists():
            shutil.copy2(respaldo, lnk)
            informe.append(f"repuesto el acceso directo que había antes: {Path(lnk).name}")
    if carpeta_menu().exists() and not any(carpeta_menu().iterdir()):
        carpeta_menu().rmdir()
    informe.append("accesos directos borrados")
    if borrar_config:
        shutil.rmtree(Path.home() / ".wavemascot", ignore_errors=True)
        informe.append("configuración borrada (~/.wavemascot)")
    else:
        informe.append("tu configuración queda en ~/.wavemascot (borrala a mano si no la querés)")
    informe.append(borrar_programa(destino, manifiesto))
    return informe


def borrar_programa(destino: Path, manifiesto: dict) -> str:
    """Borra la carpeta instalada, solo si la creó el instalador (y nunca un repositorio)."""
    if not manifiesto or not (destino / MANIFIESTO).exists() or (destino / ".git").exists():
        return f"la carpeta {destino} no la creó el instalador: no la borro"
    os.chdir(Path.home())
    if CONGELADO and Path(sys.executable).resolve().is_relative_to(destino):
        # El .exe no puede borrarse a sí mismo mientras corre: lo borra cmd apenas termine.
        subprocess.Popen(f'cmd /c ping 127.0.0.1 -n 3 > nul & rmdir /s /q "{destino}"', shell=True,
                         creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS)
        return f"la carpeta {destino} se borra en unos segundos"
    shutil.rmtree(destino, ignore_errors=True)
    return f"carpeta {destino} borrada"


def instalar_exe(destino: Path, claude_dir: Path, sin_inicio: bool) -> list[str]:
    """Instalador .exe: desempaqueta la app (app.zip, dentro del instalador) y la configura."""
    paquete = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "app.zip"
    if not paquete.exists():
        raise ErrorInstalacion("al instalador le falta app.zip (se arma con build.ps1)")
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


# --- interfaz ------------------------------------------------------------------------

def mensaje(texto: str, titulo: str = NOMBRE, pregunta: bool = False) -> bool:
    """Cuadro de diálogo de Windows (el .exe no tiene consola). Devuelve True si se aceptó."""
    if os.name != "nt":
        print(texto)
        return True
    import ctypes
    flags = (0x4 | 0x20) if pregunta else 0x40  # MB_YESNO|MB_ICONQUESTION o MB_ICONINFORMATION
    return ctypes.windll.user32.MessageBoxW(None, texto, titulo, flags | 0x10000) in (1, 6)  # MB_SETFOREGROUND


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
    a = p.parse_args(argv)
    interactivo = CONGELADO and not a.silencioso
    try:
        if a.accion == "detener":
            detener_procesos(a.destino)
            return 0
        if a.accion == "configurar":
            informe = configurar(a.tipo, a.destino or Path(__file__).resolve().parent,
                                 a.claude_dir or Path.home() / ".claude", a.sin_inicio)
        elif a.accion == "desinstalar":
            destino = a.destino or (Path(sys.executable).parent if CONGELADO else Path(__file__).resolve().parent)
            if interactivo and not mensaje(f"¿Desinstalar {NOMBRE}?\n\nSe quitan solo sus hooks de "
                                           f"~/.claude/settings.json (con backup); los tuyos quedan como estaban.",
                                           pregunta=True):
                return 0
            informe = desinstalar(destino, a.claude_dir, a.borrar_config)
        else:  # instalar (el .exe)
            destino = a.destino or destino_exe_por_defecto()
            if interactivo and not mensaje(
                    f"¿Instalar {NOMBRE} {VERSION}?\n\nSe instala en {destino} y se agregan sus hooks a "
                    f"~/.claude/settings.json sin tocar los que ya tengas (antes se guarda un backup).",
                    pregunta=True):
                return 0
            informe = instalar_exe(destino, a.claude_dir or Path.home() / ".claude", a.sin_inicio)
    except (ErrorInstalacion, OSError, subprocess.SubprocessError) as e:
        if interactivo:
            mensaje(f"No se pudo completar:\n\n{e}", f"{NOMBRE}: error")
        print(f"ERROR: {e}", file=sys.stderr if sys.stderr else None)
        return 1
    if interactivo:
        mensaje("Listo.\n\n" + "\n".join(f"• {linea}" for linea in informe))
    elif sys.stdout:
        print("\n".join(informe))
    return 0


if __name__ == "__main__":
    sys.exit(main())
