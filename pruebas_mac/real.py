"""Prueba real de WaveMascot.app en una Mac de GitHub Actions (temporal, solo para la rama mac).

Instala la app desde el .dmg, dispara los hooks como lo hace Claude Code, saca capturas de pantalla,
prueba la compañera, los ajustes, la terminal anfitriona, la pantalla completa y desinstala.
Todo queda en resultados/ (resumen.txt, capturas y logs).
"""

from __future__ import annotations

import ctypes
import glob
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RES = RAIZ / "resultados"
RES.mkdir(exist_ok=True)
HOME = Path.home()
APP = Path("/Applications/WaveMascot.app")
EXE = APP / "Contents" / "MacOS" / "WaveMascot"
CONFIG = HOME / ".wavemascot" / "config.json"
LOG = HOME / ".wavemascot" / "mascota.log"
SETTINGS = HOME / ".claude" / "settings.json"
PY = sys.executable  # el python del build (tiene PyQt6)
CANAL = "wavemascot-" + re.sub(r"\W", "", os.environ.get("USER") or "yo")
resumen: list[str] = []
fallas = 0


def anotar(texto: str) -> None:
    print(texto, flush=True)
    resumen.append(texto)
    (RES / "resumen.txt").write_text("\n".join(resumen) + "\n", encoding="utf-8")


def paso(nombre: str, ok: bool, detalle: str = "") -> bool:
    global fallas
    fallas += 0 if ok else 1
    anotar(f"[{'OK' if ok else 'FALLA'}] {nombre}" + (f": {detalle}" if detalle else ""))
    return ok


def correr(cmd, **opciones) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **opciones)


def captura(nombre: str) -> None:
    correr(["/usr/sbin/screencapture", "-x", "-C", str(RES / f"{nombre}.png")])


def log_nuevo(desde: int) -> str:
    try:
        return LOG.read_text(encoding="utf-8")[desde:]
    except OSError:
        return ""


def largo_log() -> int:
    try:
        return len(LOG.read_text(encoding="utf-8"))
    except OSError:
        return 0


def procesos(patron: str) -> list[str]:
    salida = correr(["/bin/ps", "-axww", "-o", "pid=,args="]).stdout
    return [l.strip() for l in salida.splitlines() if patron in l and "pruebas_mac" not in l and "/bin/ps" not in l]


def consultar() -> dict:
    s = socket.socket(socket.AF_UNIX)
    s.settimeout(3)
    s.connect(os.path.join(tempfile.gettempdir(), CANAL))
    s.sendall(b'{"accion": "consultar"}\n')
    datos = b""
    while not datos.endswith(b"\n"):
        trozo = s.recv(65536)
        if not trozo:
            break
        datos += trozo
    s.close()
    return json.loads(datos)


def config(**cambios) -> None:
    datos = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}
    datos.update(cambios)
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")


def comando_hook(evento: str) -> str:
    datos = json.loads(SETTINGS.read_text(encoding="utf-8"))
    return next(h["command"] for g in datos["hooks"][evento] for h in g["hooks"] if "WaveMascot" in h["command"])


PROYECTO = HOME / "proyectos" / "mi-app"
TRANSCRIPT = HOME / ".claude" / "projects" / "mi-app" / "sesion-1.jsonl"


def preparar_transcript() -> None:
    TRANSCRIPT.parent.mkdir(parents=True, exist_ok=True)
    PROYECTO.mkdir(parents=True, exist_ok=True)
    hace = datetime.now(timezone.utc).timestamp() - 83
    lineas = [
        {"type": "user", "message": {"role": "user", "content": "Arreglá el login que no valida el mail"},
         "timestamp": datetime.fromtimestamp(hace, timezone.utc).isoformat().replace("+00:00", "Z")},
        {"type": "assistant", "message": {"content": [{"type": "text", "text":
            "Listo: agregué la validación del mail en el formulario y los tests pasan. También corregí el "
            "mensaje de error."}]}},
        {"type": "custom-title", "customTitle": "Validación del login"},
    ]
    TRANSCRIPT.write_text("\n".join(json.dumps(l, ensure_ascii=False) for l in lineas) + "\n", encoding="utf-8")


def evento(nombre: str, **extra) -> dict:
    return {"session_id": "sesion-1", "transcript_path": str(TRANSCRIPT), "cwd": str(PROYECTO),
            "hook_event_name": nombre, **extra}


def disparar(nombre: str, esperar: bool = True, **extra):
    """Corre el hook como Claude Code: sh -c "<comando>" con el evento por stdin."""
    datos = json.dumps(evento(nombre, **extra), ensure_ascii=False)
    inicio = time.time()
    p = subprocess.Popen(["/bin/sh", "-c", comando_hook(nombre)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, cwd=PROYECTO)
    if not esperar:
        p.stdin.write(datos)
        p.stdin.close()
        return p, inicio
    salida, error = p.communicate(datos, timeout=200)
    return p.returncode, salida, error, time.time() - inicio


class Punto(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


CG = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
CG.CGEventCreateMouseEvent.restype = ctypes.c_void_p
CG.CGEventCreateMouseEvent.argtypes = (ctypes.c_void_p, ctypes.c_uint32, Punto, ctypes.c_uint32)
CG.CGEventPost.argtypes = (ctypes.c_uint32, ctypes.c_void_p)
CG.CGWarpMouseCursorPosition.argtypes = (Punto,)
AS = ctypes.CDLL("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
AS.AXIsProcessTrusted.restype = ctypes.c_bool


def mover(x: float, y: float) -> None:
    ev = CG.CGEventCreateMouseEvent(None, 5, Punto(x, y), 0)  # kCGEventMouseMoved
    CG.CGEventPost(0, ev)
    CG.CGWarpMouseCursorPosition(Punto(x, y))


CG.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
CG.CGEventCreateKeyboardEvent.argtypes = (ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool)


def tecla(codigo: int) -> None:
    """Una tecla (códigos de macOS: 36 Return, 53 Escape, 2 D)."""
    for abajo in (True, False):
        CG.CGEventPost(0, CG.CGEventCreateKeyboardEvent(None, codigo, abajo))
        time.sleep(0.06)


def click(x: float, y: float) -> None:
    mover(x, y)
    time.sleep(0.15)
    for tipo in (1, 2):  # kCGEventLeftMouseDown, kCGEventLeftMouseUp
        CG.CGEventPost(0, CG.CGEventCreateMouseEvent(None, tipo, Punto(x, y), 0))
        time.sleep(0.08)


def en_python(codigo: str) -> str:
    """Corre código con los módulos del repo en un proceso nuevo (como el hook: sin loop de Cocoa)."""
    r = correr([PY, "-c", f"import sys; sys.path.insert(0, {str(RAIZ)!r}); {codigo}"], timeout=60)
    return (r.stdout + r.stderr).strip()


# ----------------------------------------------------------------------------------------------

def informacion() -> None:
    anotar("== Sistema ==")
    anotar(correr(["/usr/bin/sw_vers"]).stdout.strip().replace("\n", " | "))
    anotar("chip: " + correr(["/usr/bin/uname", "-m"]).stdout.strip())
    anotar("pantallas: " + en_python("import ventanas; print(ventanas._pantallas_mac())"))
    anotar("accesibilidad (para clicks simulados): " + str(AS.AXIsProcessTrusted()))
    dmg = glob.glob(str(RAIZ / "dist" / "*.dmg"))
    anotar(f"dmg: {[Path(d).name for d in dmg]} {[os.path.getsize(d) // 1_000_000 for d in dmg]} MB")
    app = RAIZ / "build" / "dist-mac" / "WaveMascot.app"
    anotar("tamaño app: " + correr(["/usr/bin/du", "-sh", str(app)]).stdout.split()[0])
    anotar("codesign: " + correr(["/usr/bin/codesign", "-dv", str(app)]).stderr.replace("\n", " | ")[:400])
    anotar("spctl (Gatekeeper): " + (correr(["/usr/sbin/spctl", "-a", "-vv", "-t", "exec", str(app)]).stderr.strip()
                                     .replace("\n", " | ")))
    plist = correr(["/usr/bin/plutil", "-p", str(app / "Contents" / "Info.plist")]).stdout
    (RES / "Info.plist.txt").write_text(plist, encoding="utf-8")
    anotar("LSMinimumSystemVersion: " + (re.search(r'"LSMinimumSystemVersion" => "([^"]+)"', plist) or [None, "?"])[1])


def instalar() -> None:
    anotar("== Instalación desde el .dmg ==")
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    original = {"model": "opus", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo mio"}]}]}}
    SETTINGS.write_text(json.dumps(original, indent=2), encoding="utf-8")
    (RES / "settings-original.json").write_text(json.dumps(original, indent=2), encoding="utf-8")
    config(idioma="es", sonido=False, espera_permiso=10, omitir_si_enfocada=False)

    dmg = glob.glob(str(RAIZ / "dist" / "*.dmg"))[0]
    montaje = Path("/tmp/wm-dmg")
    r = correr(["/usr/bin/hdiutil", "attach", dmg, "-nobrowse", "-mountpoint", str(montaje)])
    paso("montar el .dmg", r.returncode == 0, r.stderr.strip()[:200])
    anotar("contenido del .dmg: " + str(sorted(p.name for p in montaje.iterdir())))

    # Abrir la app sin instalar: tiene que preguntar (el cuadro de diálogo). Se captura y se cancela.
    dialogo = subprocess.Popen([str(montaje / "WaveMascot.app" / "Contents" / "MacOS" / "WaveMascot")],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(6)
    captura("00-pregunta-instalar")
    hay_dialogo = bool(procesos("osascript"))
    paso("al abrir la app sin instalar aparece el cuadro '¿Instalar?'", hay_dialogo)
    correr(["/usr/bin/pkill", "-f", "osascript"])
    try:
        dialogo.wait(10)
    except subprocess.TimeoutExpired:
        dialogo.kill()
    paso("cancelar no instala nada", not APP.exists() and "WaveMascot" not in SETTINGS.read_text(encoding="utf-8"))

    inicio = time.time()
    r = correr([str(montaje / "WaveMascot.app" / "Contents" / "MacOS" / "WaveMascot"), "instalar", "--silencioso"],
               timeout=300)
    anotar(r.stdout.strip())
    paso("instalar desde el .dmg (copia a Aplicaciones)", r.returncode == 0 and APP.exists(),
         f"{time.time() - inicio:.1f} s {r.stderr.strip()[:300]}")
    correr(["/usr/bin/hdiutil", "detach", str(montaje)])
    anotar("xattr de la app instalada: " + (correr(["/usr/bin/xattr", "-l", str(EXE)]).stdout.strip() or "(ninguno)"))
    paso("firma válida después de copiarla", correr(["/usr/bin/codesign", "--verify", "--deep", "--strict",
                                                     str(APP)]).returncode == 0)

    datos = json.loads(SETTINGS.read_text(encoding="utf-8"))
    (RES / "settings-instalado.json").write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
    eventos = ("Stop", "Notification", "UserPromptSubmit", "SubagentStop", "StopFailure", "PermissionRequest")
    paso("hooks agregados", all(any("WaveMascot.app" in h["command"] for g in datos["hooks"].get(e, [])
                                    for h in g["hooks"]) for e in eventos))
    paso("tus hooks y ajustes quedan", datos["model"] == "opus" and "echo mio" in json.dumps(datos))
    agente = HOME / "Library" / "LaunchAgents" / "io.github.marescaa.wavemascot.plist"
    paso("LaunchAgent de inicio", agente.exists())
    if agente.exists():
        (RES / "launchagent.plist").write_text(correr(["/usr/bin/plutil", "-p", str(agente)]).stdout)
    comando = HOME / ".claude" / "commands" / "wavemascot.md"
    paso("comando /wavemascot", comando.exists())
    if comando.exists():
        (RES / "wavemascot.md").write_text(comando.read_text(encoding="utf-8"), encoding="utf-8")
    paso("manifiesto en ~/.wavemascot", (HOME / ".wavemascot" / "instalacion.json").exists())
    time.sleep(4)
    paso("ícono de la barra de menús corriendo", bool(procesos("WaveMascot bandeja")), str(procesos("WaveMascot")))
    captura("01-instalada-barra-de-menus")


def avisos() -> None:
    anotar("== Avisos ==")
    preparar_transcript()
    disparar("UserPromptSubmit", prompt="Arreglá el login")  # anota el inicio de la tarea
    time.sleep(3)
    correr(["/usr/bin/pkill", "-f", "WaveMascot mascota"])
    time.sleep(1)

    desde = largo_log()
    codigo, salida, error, segundos = disparar("Stop", last_assistant_message=None)
    paso("hook Stop sale con 0 y rápido", codigo == 0 and segundos < 3, f"{segundos:.2f} s, salida={salida!r} "
                                                                       f"error={error[:200]!r}")
    inicio, visible = time.time() - segundos, None
    while time.time() - inicio < 10 and visible is None:
        try:
            visible = consultar() and time.time() - inicio
        except OSError:
            time.sleep(0.1)
    anotar(f"la ventana del aviso responde a los {visible or 0:.1f} s del evento")
    time.sleep(1.0)
    captura("02-aviso-listo")
    try:
        estado = consultar()
        (RES / "02-estado.json").write_text(json.dumps(estado, indent=2), encoding="utf-8")
        paso("la mascota está en pantalla (consultar)", estado.get("cartel") is True, json.dumps(estado))
    except OSError as e:
        paso("la mascota está en pantalla (consultar)", False, repr(e))
    anotar("log: " + log_nuevo(desde).strip().replace("\n", " || ")[:900])
    time.sleep(6)
    paso("el aviso se va solo", not procesos("WaveMascot mascota"), str(procesos("WaveMascot mascota")))

    disparar("Notification", message="Claude needs your permission to use Bash", notification_type="permission_prompt")
    time.sleep(1.4)
    captura("03-aviso-permiso")
    time.sleep(1)

    # Varias sesiones: el aviso de otra sesión espera su turno
    disparar("SubagentStop", agent_type="Explore", session_id="sesion-2")
    time.sleep(1.4)
    captura("03b-cola-otra-sesion")
    time.sleep(8)

    # Permitir / Denegar desde la mascota
    desde = largo_log()
    proceso, inicio = disparar("PermissionRequest", esperar=False, tool_name="Bash",
                               tool_input={"command": "npm install --save-dev vitest"})
    try:
        estado, fin = {}, time.time() + 12
        while time.time() < fin and not (estado.get("estado") == "permiso" and estado.get("botones")):
            time.sleep(0.2)
            try:
                estado = consultar()
            except OSError:
                pass
        anotar(f"el cartel con botones se ve a los {time.time() - inicio:.1f} s del evento")
        time.sleep(0.6)
        captura("04-permiso-botones")
        (RES / "04-estado.json").write_text(json.dumps(estado, indent=2), encoding="utf-8")
        botones = estado.get("botones") or {}
        paso("botones Permitir/Denegar", "permitir" in botones and "denegar" in botones, json.dumps(botones))
        if "permitir" in botones:
            x, y = botones["permitir"]
            mover(x, y)
            time.sleep(0.6)
            captura("04b-permiso-mouse-encima")
            click(x, y)
    except OSError as e:
        paso("botones Permitir/Denegar", False, repr(e))
    try:
        salida, error = proceso.communicate(timeout=40)
    except subprocess.TimeoutExpired:
        proceso.kill()
        salida, error = proceso.communicate()
    permitido = '"behavior": "allow"' in salida
    paso("click en Permitir llega a Claude Code" if AS.AXIsProcessTrusted() else
         "Permitir (sin permiso de accesibilidad el click simulado puede no llegar)",
         permitido or not AS.AXIsProcessTrusted(),
         f"salida={salida!r} {time.time() - inicio:.1f} s")
    anotar("log: " + log_nuevo(desde).strip().replace("\n", " || ")[:900])
    time.sleep(2)
    captura("04c-despues-de-permitir")
    time.sleep(2)

    # Límite de uso
    disparar("StopFailure", error="rate_limit", error_details="Claude usage limit reached. Your limit will reset at 3pm.")
    time.sleep(1.4)
    captura("05-limite")
    time.sleep(6)


def compania() -> None:
    anotar("== Compañera ==")
    config(modo="compania")
    desde = largo_log()
    correr([str(EXE), "--compania"])
    time.sleep(3)
    captura("06-compania-chiquita")
    try:
        estado = consultar()
        paso("compañera abierta", estado.get("modo") == "compania", json.dumps(estado))
        x, y = estado["posicion"]
        w, h = estado["tamano"]
        mover(x + w - 98, y + h - 32)  # el mouse sobre la mascota chiquita: crece
        time.sleep(1.5)
        captura("06b-compania-mouse-encima")
        estado = consultar()
        paso("al pasar el mouse crece (enterEvent con la app inactiva)", estado.get("salida", 0) > 0.5,
             json.dumps(estado))
        mover(200, 300)
    except (OSError, KeyError, ValueError) as e:
        paso("compañera abierta", False, repr(e))
    disparar("UserPromptSubmit", prompt="Escribí los tests del carrito")
    time.sleep(2)
    captura("07-compania-pensando")
    disparar("Stop")
    time.sleep(1.5)
    captura("08-compania-listo")
    anotar("log: " + log_nuevo(desde).strip().replace("\n", " || ")[:900])
    time.sleep(6)
    config(modo="aviso")  # la compañera se va sola al ver el cambio
    time.sleep(3)
    paso("al volver a modo aviso la compañera se va", not procesos("WaveMascot mascota"))


def ajustes() -> None:
    anotar("== Ajustes ==")
    r = correr(["/usr/bin/open", "-n", "-a", str(APP), "--args", "ajustes", "--ventana"])
    time.sleep(6)
    paso("ajustes abiertos por LaunchServices", bool(procesos("ajustes --ventana")), r.stderr.strip())
    captura("09-ajustes")
    frente = en_python("import ventanas; print(ventanas._pid_al_frente())")
    pids = [l.split()[0] for l in procesos("ajustes --ventana")]
    paso("la ventana de ajustes queda adelante", frente in pids, f"frente={frente} ajustes={pids}")
    correr(["/usr/bin/pkill", "-f", "ajustes --ventana"])
    time.sleep(2)

    # Abrir WaveMascot.app con el ícono corriendo: el proceso que ya corre recibe el "reopen".
    r = correr(["/usr/bin/open", str(APP)])
    time.sleep(8)
    paso("abrir la app ya abierta muestra los ajustes", bool(procesos("ajustes --ventana")),
         str(procesos("WaveMascot")))
    captura("10-reabrir")
    correr(["/usr/bin/pkill", "-f", "ajustes --ventana"])
    time.sleep(1)

    # Las pestañas, dibujadas por Qt con la letra de macOS (en español y en inglés, oscuro y claro).
    r = correr([PY, str(RAIZ / "pruebas_mac" / "capturas_ajustes.py"), str(RES)], timeout=180)
    paso("capturas de cada pestaña", r.returncode == 0, (r.stdout + r.stderr).strip()[-600:])


def terminal() -> None:
    anotar("== Terminal anfitriona ==")
    evento_json = Path("/tmp/wm-evento.json")
    evento_json.write_text(json.dumps(evento("Stop")), encoding="utf-8")
    script = Path("/tmp/wm-hook.command")
    script.write_text(f"#!/bin/bash\ncd {json.dumps(str(PROYECTO))}\n/bin/sh -c {json.dumps(comando_hook('Stop'))} "
                      f"< {evento_json}\necho hook-terminado\n", encoding="utf-8")
    script.chmod(0o755)

    config(omitir_si_enfocada=True)
    desde = largo_log()
    correr(["/usr/bin/open", "-a", "Terminal", str(script)])
    time.sleep(8)
    texto = log_nuevo(desde)
    paso("con la terminal adelante no avisa (omitir_si_enfocada)", "ya tiene el foco" in texto,
         texto.strip().replace("\n", " || ")[:500])
    captura("11-terminal-con-foco")

    config(omitir_si_enfocada=False)
    desde = largo_log()
    correr(["/usr/bin/open", "-a", "Terminal", str(script)])
    time.sleep(3)
    captura("12-aviso-desde-terminal")
    try:
        estado = consultar()
        paso("botón 'Ir a la terminal'", "enfocar" in (estado.get("botones") or {}), json.dumps(estado))
    except OSError as e:
        paso("botón 'Ir a la terminal'", False, repr(e))
    anotar("log: " + log_nuevo(desde).strip().replace("\n", " || ")[:600])
    time.sleep(6)

    terminal_pid = next((l.split()[0] for l in procesos("Terminal.app/Contents/MacOS/Terminal")), "")
    correr(["/usr/bin/open", "-a", "Finder"])
    time.sleep(2)
    antes = en_python("import ventanas; print(ventanas._pid_al_frente())")
    ok = en_python(f"import ventanas; print(ventanas.enfocar({terminal_pid or 0}))")
    time.sleep(1.5)
    despues = en_python("import ventanas; print(ventanas._pid_al_frente())")
    paso("'Ir a la terminal' la trae al frente", despues == terminal_pid,
         f"terminal={terminal_pid} antes={antes} enfocar={ok} después={despues}")
    correr(["/usr/bin/osascript", "-e", 'tell application "Terminal" to quit'])
    time.sleep(2)


def pantalla_completa() -> None:
    anotar("== Pantalla completa ==")
    antes = en_python("import ventanas; print(ventanas.pantalla_completa())")
    p = subprocess.Popen([PY, str(RAIZ / "pruebas_mac" / "pantalla_completa.py"), "14"])
    time.sleep(6)
    durante = en_python("import ventanas; print(ventanas.pantalla_completa())")
    captura("13-pantalla-completa")
    desde = largo_log()
    disparar("Stop")
    time.sleep(1)
    texto = log_nuevo(desde)
    paso("detecta pantalla completa", antes == "False" and durante == "True", f"antes={antes} durante={durante}")
    paso("con pantalla completa no avisa", "pantalla completa" in texto, texto.strip()[:300])
    p.wait(30)
    time.sleep(3)


def menu_de_la_barra() -> bool:
    """Abre el menú del ícono de la barra de menús con un click, como una persona."""
    bandeja = procesos("WaveMascot bandeja")
    if not bandeja:
        return False
    pid = bandeja[0].split()[0]
    datos = json.loads(en_python(f"import ventanas, json; print(json.dumps([v for v in ventanas._ventanas_mac() "
                                 f"if v[0] == {pid}]))") or "[]")
    item = next((v for v in datos if v[1] == 25), None)  # kCGStatusWindowLevel
    anotar(f"ventanas del ícono: {datos}")
    if not item:
        return False
    click(item[2] + item[4] / 2, item[3] + item[5] / 2)
    time.sleep(1.5)
    return True


def desinstalar() -> None:
    anotar("== Desinstalar desde el menú de la barra ==")
    if paso("menú del ícono de la barra de menús", menu_de_la_barra()):
        captura("15-menu-barra")
        tecla(2)  # "D": el menú salta a "Desinstalar WaveMascot…"
        time.sleep(0.5)
        captura("15b-menu-desinstalar")
        tecla(36)
    else:
        subprocess.Popen(["/bin/sh", "-c", '"$@" &', "sh", str(EXE), "desinstalar"])
    time.sleep(5)
    captura("16-pregunta-desinstalar")
    paso("pregunta antes de desinstalar", bool(procesos("osascript")))
    tecla(36)  # Return: "Sí"
    time.sleep(10)
    captura("17-desinstalada-listo")
    tecla(36)  # cierra el "Listo."
    time.sleep(5)
    original = json.loads((RES / "settings-original.json").read_text(encoding="utf-8"))
    actual = json.loads(SETTINGS.read_text(encoding="utf-8"))
    paso("settings.json vuelve a como estaba", actual == original, json.dumps(actual)[:300])
    paso("sin LaunchAgent", not (HOME / "Library" / "LaunchAgents" / "io.github.marescaa.wavemascot.plist").exists())
    paso("sin /wavemascot", not (HOME / ".claude" / "commands" / "wavemascot.md").exists())
    paso("la app se borró", not APP.exists())
    paso("no quedan procesos", not procesos("WaveMascot"), str(procesos("WaveMascot")))
    paso("la configuración queda", CONFIG.exists())
    captura("14-desinstalada")


def fuente() -> None:
    anotar("== Desde el código: install.sh / uninstall.sh ==")
    original = json.loads((RES / "settings-original.json").read_text(encoding="utf-8"))
    destino = HOME / "Library" / "Application Support" / "WaveMascot"
    r = correr(["/bin/bash", str(RAIZ / "install.sh")], timeout=900)
    anotar(r.stdout.strip()[-800:])
    paso("install.sh", r.returncode == 0 and (destino / "venv" / "bin" / "python").exists(), r.stderr.strip()[-500:])
    comando = comando_hook("Stop")
    anotar(f"hook: {comando}")
    paso("el hook apunta al código", "mascota.py" in comando and comando.endswith("|| true"))
    time.sleep(5)
    paso("ícono de la barra de menús (desde el código) corriendo", bool(procesos("bandeja.py")))
    desde = largo_log()
    codigo, _, error, segundos = disparar("Stop")
    time.sleep(1.5)
    captura("18-aviso-desde-el-codigo")
    paso("aviso desde el código", codigo == 0 and "evento=Stop" in log_nuevo(desde), f"{segundos:.2f} s {error[:200]}")
    time.sleep(6)
    r = correr(["/bin/bash", str(destino / "uninstall.sh")], timeout=300)
    anotar(r.stdout.strip()[-800:])
    time.sleep(3)
    actual = json.loads(SETTINGS.read_text(encoding="utf-8"))
    paso("uninstall.sh deja todo como estaba", r.returncode == 0 and not destino.exists() and actual == original,
         f"{r.stderr.strip()[-400:]} {json.dumps(actual)[:200]}")
    paso("no quedan procesos (código)", not procesos("bandeja.py") and not procesos("mascota.py"))


def main() -> int:
    for etapa in (informacion, instalar, avisos, compania, ajustes, terminal, pantalla_completa, desinstalar, fuente):
        try:
            etapa()
        except Exception:
            paso(f"{etapa.__name__} terminó sin errores", False, traceback.format_exc()[-1500:])
    for archivo in (LOG, LOG.with_suffix(".log.1")):
        if archivo.exists():
            shutil.copy2(archivo, RES / archivo.name)
    anotar(f"== {fallas} fallas ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
