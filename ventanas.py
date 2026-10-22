"""Utilidades de Windows y macOS para la mascota: de qué ventana viene un hook, si tiene el foco,
si hay algo en pantalla completa y cómo traer una ventana al frente.

La ventana "anfitriona" es la de la terminal, el editor o la app donde corre Claude Code:
se encuentra subiendo por los procesos padre del hook (bash -> Claude Code -> terminal).
En Windows es su HWND; en macOS, el pid de la app dueña de la ventana.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from ctypes import wintypes

ES_WINDOWS = os.name == "nt"
ES_MAC = sys.platform == "darwin"
if ES_WINDOWS:
    u32 = ctypes.WinDLL("user32", use_last_error=True)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    u32.GetForegroundWindow.restype = wintypes.HWND
    u32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    u32.GetWindowThreadProcessId.restype = wintypes.DWORD
    u32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
    u32.GetAncestor.restype = wintypes.HWND
    u32.GetWindow.argtypes = (wintypes.HWND, wintypes.UINT)
    u32.GetWindow.restype = wintypes.HWND
    u32.IsWindowVisible.argtypes = u32.IsIconic.argtypes = u32.IsWindow.argtypes = (wintypes.HWND,)
    u32.SetForegroundWindow.argtypes = u32.BringWindowToTop.argtypes = (wintypes.HWND,)
    u32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
    u32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
    u32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    u32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    u32.MonitorFromWindow.argtypes = (wintypes.HWND, wintypes.DWORD)
    u32.MonitorFromWindow.restype = wintypes.HMONITOR
    k32.GetConsoleWindow.restype = wintypes.HWND
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE

TH32CS_SNAPPROCESS = 0x2
GA_ROOTOWNER = 3
GW_OWNER = 4


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD)]


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD), ("szDevice", ctypes.c_wchar * 32)]


def procesos() -> dict[int, tuple[int, str]]:
    """pid -> (pid del padre, ejecutable) de todos los procesos."""
    tabla: dict[int, tuple[int, str]] = {}
    if ES_MAC:
        return _procesos_mac()
    if not ES_WINDOWS:
        return tabla
    foto = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not foto or foto == wintypes.HANDLE(-1).value:
        return tabla
    entrada = PROCESSENTRY32W()
    entrada.dwSize = ctypes.sizeof(entrada)
    ok = k32.Process32FirstW(foto, ctypes.byref(entrada))
    while ok:
        tabla[entrada.th32ProcessID] = (entrada.th32ParentProcessID, entrada.szExeFile.lower())
        ok = k32.Process32NextW(foto, ctypes.byref(entrada))
    k32.CloseHandle(foto)
    return tabla


def ancestros(pid: int | None = None) -> list[int]:
    """Los procesos padre, del más cercano al más lejano (sin el propio)."""
    tabla = procesos()
    actual, cadena = pid or os.getpid(), []
    while actual in tabla and len(cadena) < 40:
        padre = tabla[actual][0]
        if not padre or padre in cadena or padre == actual or padre not in tabla:
            break
        cadena.append(padre)
        actual = padre
    return cadena


def pid_de_ventana(hwnd) -> int:
    pid = wintypes.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def ventanas_principales() -> list[tuple[int, int]]:
    """(hwnd, pid) de las ventanas visibles de primer nivel, sin dueño y con título."""
    encontradas: list[tuple[int, int]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cada(hwnd, _):
        if u32.IsWindowVisible(hwnd) and not u32.GetWindow(hwnd, GW_OWNER) and u32.GetWindowTextLengthW(hwnd):
            encontradas.append((hwnd, pid_de_ventana(hwnd)))
        return True

    u32.EnumWindows(cada, 0)
    return encontradas


def ventana_anfitriona() -> int:
    """La ventana de la terminal, editor o app desde la que corre este proceso (0 si no se sabe)."""
    if ES_MAC:
        return _seguro(_anfitriona_mac, 0)
    if not ES_WINDOWS:
        return 0
    cadena = ancestros()
    por_pid: dict[int, int] = {}
    for hwnd, pid in ventanas_principales():
        por_pid.setdefault(pid, hwnd)
    for pid in cadena:  # el ancestro más cercano con ventana propia
        if pid in por_pid:
            return por_pid[pid]
    for pid in cadena:  # consola clásica: la ventana es de conhost, que no es ancestro
        if k32.AttachConsole(pid):
            hwnd = k32.GetConsoleWindow()
            k32.FreeConsole()
            if hwnd and u32.IsWindowVisible(hwnd):
                return hwnd
    return 0


def ventana_activa() -> int:
    return u32.GetForegroundWindow() if ES_WINDOWS else 0


def tiene_el_foco(hwnd: int) -> bool:
    """¿La ventana (o algo de su mismo proceso) es la que está en primer plano?"""
    if ES_MAC:
        return bool(hwnd) and _seguro(_pid_al_frente, 0) == hwnd
    if not ES_WINDOWS or not hwnd:
        return False
    activa = ventana_activa()
    if not activa:
        return False
    raiz = u32.GetAncestor(activa, GA_ROOTOWNER) or activa
    return raiz == hwnd or activa == hwnd or pid_de_ventana(raiz) == pid_de_ventana(hwnd)


def pantalla_completa() -> bool:
    """Hay un juego, video o presentación en pantalla completa (o Windows pide silencio)."""
    if ES_MAC:
        return _seguro(_pantalla_completa_mac, False)
    if not ES_WINDOWS:
        return False
    estado = ctypes.c_int(0)
    # QUNS_BUSY, QUNS_RUNNING_D3D_FULL_SCREEN, QUNS_PRESENTATION_MODE, QUNS_APP
    if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(estado)) == 0 and estado.value in (2, 3, 4, 7):
        return True
    activa = ventana_activa()
    if not activa:
        return False
    clase = ctypes.create_unicode_buffer(64)
    u32.GetClassNameW(activa, clase, 64)
    if clase.value in ("Progman", "WorkerW", "Shell_TrayWnd"):  # el escritorio no cuenta
        return False
    ventana, info = wintypes.RECT(), MONITORINFO()
    info.cbSize = ctypes.sizeof(info)
    u32.GetWindowRect(activa, ctypes.byref(ventana))
    u32.GetMonitorInfoW(u32.MonitorFromWindow(activa, 2), ctypes.byref(info))
    m = info.rcMonitor
    return (ventana.left <= m.left and ventana.top <= m.top and ventana.right >= m.right
            and ventana.bottom >= m.bottom)


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def segundos_inactivo() -> float | None:
    """Cuántos segundos pasaron desde que tocaste el mouse o el teclado, o None si no se sabe."""
    if ES_MAC:
        def mac():
            cg = _bibliotecas()["cg"]
            cg.CGEventSourceSecondsSinceLastEventType.restype = ctypes.c_double
            cg.CGEventSourceSecondsSinceLastEventType.argtypes = (ctypes.c_int32, ctypes.c_uint32)
            return float(cg.CGEventSourceSecondsSinceLastEventType(0, 0xFFFFFFFF))  # sesión, cualquier evento
        return _seguro(mac, None)
    if not ES_WINDOWS:
        return None
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not u32.GetLastInputInfo(ctypes.byref(info)):
        return None
    k32.GetTickCount.restype = wintypes.DWORD
    return ((k32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000  # el contador da la vuelta cada 49 días


def monitor_de_ventana(hwnd: int) -> str:
    """Nombre del monitor (p. ej. \\\\.\\DISPLAY2) donde está la ventana, o "" si no se sabe."""
    if not ES_WINDOWS or not hwnd or not u32.IsWindow(hwnd):
        return ""
    info = MONITORINFOEXW()
    info.cbSize = ctypes.sizeof(info)
    if u32.GetMonitorInfoW(u32.MonitorFromWindow(hwnd, 2), ctypes.byref(info)):  # 2 = el más cercano
        return info.szDevice
    return ""


def enfocar(hwnd: int) -> bool:
    """Trae la ventana al frente (la restaura si estaba minimizada)."""
    if ES_MAC:
        return bool(hwnd) and _seguro(lambda: _enfocar_mac(hwnd), False)
    if not ES_WINDOWS or not hwnd or not u32.IsWindow(hwnd):
        return False
    if u32.IsIconic(hwnd):
        u32.ShowWindow(hwnd, 9)  # SW_RESTORE
    hilo_frente = u32.GetWindowThreadProcessId(u32.GetForegroundWindow(), None)
    hilo = k32.GetCurrentThreadId()
    # Windows solo deja tomar el foco a quien ya lo tiene: nos "pegamos" un instante a ese hilo.
    pegado = hilo_frente and hilo_frente != hilo and u32.AttachThreadInput(hilo, hilo_frente, True)
    u32.SetForegroundWindow(hwnd)
    u32.BringWindowToTop(hwnd)
    if pegado:
        u32.AttachThreadInput(hilo, hilo_frente, False)
    return u32.GetForegroundWindow() == hwnd


def centro_de_ventana(ventana: int) -> tuple[int, int] | None:
    """macOS: centro (en coordenadas de pantalla) de la ventana de adelante de esa app, o None.
    En Windows el monitor se busca por nombre (monitor_de_ventana)."""
    if not ES_MAC or not ventana:
        return None
    return _seguro(lambda: _centro_mac(ventana), None)


def _seguro(funcion, si_falla):
    """Lo de macOS va por ctypes: si algo no está (otra versión del sistema), se sigue sin eso."""
    try:
        return funcion()
    except (OSError, AttributeError, ValueError, TypeError, subprocess.SubprocessError):
        return si_falla


# --- macOS -------------------------------------------------------------------------
# Sin dependencias extra: CoreGraphics, CoreFoundation y el runtime de Objective-C, por ctypes.
# Ninguna de estas llamadas pide permisos (no se leen títulos ni contenido de ventanas ajenas).

BUNDLE_ID = "io.github.marescaa.wavemascot"
_mac: dict = {}


class _CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


class _CGSize(ctypes.Structure):
    _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]


class _CGRect(ctypes.Structure):
    _fields_ = [("origin", _CGPoint), ("size", _CGSize)]


def _bibliotecas() -> dict:
    """Carga una sola vez lo que se usa de macOS."""
    if _mac:
        return _mac
    vacio, entero = ctypes.c_void_p, ctypes.c_long
    cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    cg = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
    objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
    ctypes.CDLL("/System/Library/Frameworks/AppKit.framework/AppKit")  # NSWorkspace, NSApplication...
    cf.CFArrayGetCount.restype, cf.CFArrayGetCount.argtypes = entero, (vacio,)
    cf.CFArrayGetValueAtIndex.restype, cf.CFArrayGetValueAtIndex.argtypes = vacio, (vacio, entero)
    cf.CFDictionaryGetValue.restype, cf.CFDictionaryGetValue.argtypes = vacio, (vacio, vacio)
    cf.CFNumberGetValue.restype, cf.CFNumberGetValue.argtypes = ctypes.c_bool, (vacio, entero, vacio)
    cf.CFRelease.argtypes = (vacio,)
    cg.CGWindowListCopyWindowInfo.restype = vacio
    cg.CGWindowListCopyWindowInfo.argtypes = (ctypes.c_uint32, ctypes.c_uint32)
    cg.CGRectMakeWithDictionaryRepresentation.restype = ctypes.c_bool
    cg.CGRectMakeWithDictionaryRepresentation.argtypes = (vacio, ctypes.POINTER(_CGRect))
    cg.CGGetActiveDisplayList.argtypes = (ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32),
                                          ctypes.POINTER(ctypes.c_uint32))
    cg.CGDisplayBounds.restype, cg.CGDisplayBounds.argtypes = _CGRect, (ctypes.c_uint32,)
    objc.objc_getClass.restype, objc.objc_getClass.argtypes = vacio, (ctypes.c_char_p,)
    objc.sel_registerName.restype, objc.sel_registerName.argtypes = vacio, (ctypes.c_char_p,)
    objc.objc_autoreleasePoolPush.restype = vacio
    objc.objc_autoreleasePoolPop.argtypes = (vacio,)
    objc.objc_allocateClassPair.restype = vacio
    objc.objc_allocateClassPair.argtypes = (vacio, ctypes.c_char_p, ctypes.c_size_t)
    objc.class_addMethod.restype = ctypes.c_bool
    objc.class_addMethod.argtypes = (vacio, vacio, vacio, ctypes.c_char_p)
    objc.objc_registerClassPair.argtypes = (vacio,)
    claves = {nombre: vacio.in_dll(cg, nombre).value
              for nombre in ("kCGWindowOwnerPID", "kCGWindowLayer", "kCGWindowBounds", "kCGWindowAlpha")}
    _mac.update(cf=cf, cg=cg, objc=objc, claves=claves, firmas={}, vivos=[])
    return _mac


def _clase(nombre: str):
    return _bibliotecas()["objc"].objc_getClass(nombre.encode())


def _selector(nombre: str):
    return _bibliotecas()["objc"].sel_registerName(nombre.encode())


def _enviar(objeto, selector: str, *args, tipo=ctypes.c_void_p, tipos=()):
    """objc_msgSend con los tipos de cada llamada (hace falta declararlos para que ande en Apple Silicon)."""
    b = _bibliotecas()
    clave = (tipo, tipos)
    if clave not in b["firmas"]:
        prototipo = ctypes.CFUNCTYPE(tipo, ctypes.c_void_p, ctypes.c_void_p, *tipos)
        b["firmas"][clave] = prototipo(("objc_msgSend", b["objc"]))
    return b["firmas"][clave](objeto, _selector(selector), *args)


class _Pileta:
    """Autorelease pool: los objetos que devuelve AppKit se liberan al salir del bloque."""

    def __enter__(self):
        self.pileta = _bibliotecas()["objc"].objc_autoreleasePoolPush()

    def __exit__(self, *_):
        _bibliotecas()["objc"].objc_autoreleasePoolPop(self.pileta)


def _nsapp():
    return _enviar(_clase("NSApplication"), "sharedApplication")


def _procesos_mac() -> dict[int, tuple[int, str]]:
    salida = subprocess.run(["/bin/ps", "-axo", "pid=,ppid=,comm="], capture_output=True, text=True,
                            timeout=10).stdout
    tabla: dict[int, tuple[int, str]] = {}
    for linea in salida.splitlines():
        partes = linea.split(None, 2)
        if len(partes) >= 2 and partes[0].isdigit() and partes[1].isdigit():
            tabla[int(partes[0])] = (int(partes[1]), (partes[2] if len(partes) > 2 else "").lower())
    return tabla


def _ventanas_mac(todas: bool = False) -> list[tuple[int, int, float, float, float, float]]:
    """(pid, capa, x, y, ancho, alto) de cada ventana, de la de adelante a la de atrás.
    todas=False: solo las que están en pantalla (no las minimizadas ni las de otros escritorios)."""
    b = _bibliotecas()
    cf, cg, k = b["cf"], b["cg"], b["claves"]
    # kCGWindowListOptionAll, o OnScreenOnly | ExcludeDesktopElements
    lista = cg.CGWindowListCopyWindowInfo(0 if todas else 1 | 16, 0)
    if not lista:
        return []
    encontradas = []
    try:
        for i in range(cf.CFArrayGetCount(lista)):
            d = cf.CFArrayGetValueAtIndex(lista, i)
            pid, capa, alfa, caja = ctypes.c_int64(), ctypes.c_int64(), ctypes.c_double(1.0), _CGRect()
            numeros = [cf.CFDictionaryGetValue(d, k[c])
                       for c in ("kCGWindowOwnerPID", "kCGWindowLayer", "kCGWindowAlpha")]
            limites = cf.CFDictionaryGetValue(d, k["kCGWindowBounds"])
            if not (numeros[0] and numeros[1] and limites):
                continue
            cf.CFNumberGetValue(numeros[0], 4, ctypes.byref(pid))  # kCFNumberSInt64Type
            cf.CFNumberGetValue(numeros[1], 4, ctypes.byref(capa))
            if numeros[2]:
                cf.CFNumberGetValue(numeros[2], 13, ctypes.byref(alfa))  # kCFNumberDoubleType
            if alfa.value > 0 and cg.CGRectMakeWithDictionaryRepresentation(limites, ctypes.byref(caja)):
                encontradas.append((pid.value, capa.value, caja.origin.x, caja.origin.y,
                                    caja.size.width, caja.size.height))
    finally:
        cf.CFRelease(lista)
    return encontradas


def _ventana_normal(capa: int, ancho: float, alto: float) -> bool:
    """Una ventana de documento o terminal (no un menú, un ícono de la barra ni un panelcito)."""
    return capa == 0 and ancho >= 100 and alto >= 60


def _pantallas_mac() -> list[tuple[float, float, float, float]]:
    cg = _bibliotecas()["cg"]
    ids, cuantas = (ctypes.c_uint32 * 16)(), ctypes.c_uint32()
    if cg.CGGetActiveDisplayList(16, ids, ctypes.byref(cuantas)) != 0:
        return []
    cajas = [cg.CGDisplayBounds(ids[i]) for i in range(cuantas.value)]
    return [(c.origin.x, c.origin.y, c.size.width, c.size.height) for c in cajas]


def _pid_al_frente() -> int:
    with _Pileta():
        app = _enviar(_enviar(_clase("NSWorkspace"), "sharedWorkspace"), "frontmostApplication")
        return _enviar(app, "processIdentifier", tipo=ctypes.c_int) if app else 0


def _pids_de_bundle(bundle: str) -> list[int]:
    with _Pileta():
        texto = _enviar(_clase("NSString"), "stringWithUTF8String:", bundle.encode(), tipos=(ctypes.c_char_p,))
        apps = _enviar(_clase("NSRunningApplication"), "runningApplicationsWithBundleIdentifier:", texto,
                       tipos=(ctypes.c_void_p,))
        cuantas = _enviar(apps, "count", tipo=ctypes.c_ulong) if apps else 0
        return [_enviar(_enviar(apps, "objectAtIndex:", i, tipos=(ctypes.c_ulong,)), "processIdentifier",
                        tipo=ctypes.c_int) for i in range(cuantas)]


def _anfitriona_mac() -> int:
    """El pid de la app (Terminal, iTerm2, VS Code, Claude...) de la que viene este proceso, o 0."""
    con_ventanas = {pid for pid, capa, _, _, w, h in _ventanas_mac(todas=True) if _ventana_normal(capa, w, h)}
    con_ventanas.discard(os.getpid())
    for pid in ancestros():
        if pid in con_ventanas:
            return pid
    # iTerm2 y otras terminales corren las sesiones en un proceso aparte que no es hijo de la app;
    # macOS deja en el entorno el bundle de la app desde la que se abrió la terminal.
    bundle = os.environ.get("__CFBundleIdentifier") or ""
    if bundle and bundle != BUNDLE_ID:
        for pid in _pids_de_bundle(bundle):
            if pid in con_ventanas:
                return pid
    return 0


def _pantalla_completa_mac() -> bool:
    """La app de adelante tiene una ventana que tapa un monitor entero (video, juego, presentación
    o una app en pantalla completa). Las ventanas maximizadas no cuentan: dejan ver la barra de menús."""
    frente = _pid_al_frente()
    if not frente or frente == os.getpid():
        return False
    pantallas = _pantallas_mac()
    for pid, capa, x, y, w, h in _ventanas_mac():
        if pid != frente or capa < 0:
            continue
        for px, py, pw, ph in pantallas:
            if x <= px + 1 and y <= py + 1 and x + w >= px + pw - 1 and y + h >= py + ph - 1:
                return True
    return False


def _centro_mac(pid: int) -> tuple[int, int] | None:
    for duena, capa, x, y, w, h in _ventanas_mac():
        if duena == pid and _ventana_normal(capa, w, h):
            return int(x + w / 2), int(y + h / 2)
    return None


def _app_de_pid(pid: int):
    return _enviar(_clase("NSRunningApplication"), "runningApplicationWithProcessIdentifier:", pid,
                   tipos=(ctypes.c_int,))


def _enfocar_mac(pid: int) -> bool:
    with _Pileta():
        app = _app_de_pid(pid)
        if not app:
            return False
        url = _enviar(app, "bundleURL")
        ruta = _enviar(_enviar(url, "path"), "UTF8String", tipo=ctypes.c_char_p) if url else None
    if ruta:  # por LaunchServices: macOS lo respeta aunque la mascota no sea la app activa
        if subprocess.run(["/usr/bin/open", "-a", ruta.decode()], capture_output=True, timeout=10).returncode == 0:
            return True
    with _Pileta():
        app = _app_de_pid(pid)
        # NSApplicationActivateAllWindows | NSApplicationActivateIgnoringOtherApps
        return bool(app) and bool(_enviar(app, "activateWithOptions:", 3, tipo=ctypes.c_bool,
                                          tipos=(ctypes.c_ulong,)))


# --- macOS: cómo se comporta cada proceso de la app ------------------------------------------

def app_de_fondo() -> None:
    """Mascota e ícono: sin ícono en el Dock ni menú propio (como una app de la barra de menús)."""
    if ES_MAC:
        _seguro(lambda: _enviar(_nsapp(), "setActivationPolicy:", 1, tipo=ctypes.c_bool,
                                tipos=(ctypes.c_long,)), None)


def app_con_ventana() -> None:
    """Ajustes: con ícono en el Dock y su menú, como cualquier ventana (en Windows, la barra de tareas)."""
    if ES_MAC:
        _seguro(lambda: _enviar(_nsapp(), "setActivationPolicy:", 0, tipo=ctypes.c_bool,
                                tipos=(ctypes.c_long,)), None)


def activar_esta_app() -> None:
    if ES_MAC:
        _seguro(lambda: _enviar(_nsapp(), "activateIgnoringOtherApps:", True, tipo=None,
                                tipos=(ctypes.c_bool,)), None)


def ventana_flotante(winid: int) -> None:
    """La mascota en macOS: visible en todos los escritorios aunque la app no esté activa, y sin
    robarle el foco a la terminal al hacerle click (lo mismo que hace Windows con estas ventanas)."""
    if not ES_MAC or not winid:
        return

    def ajustar():
        with _Pileta():
            ventana = _enviar(ctypes.c_void_p(int(winid)), "window")
            if not ventana:
                return
            entero = ctypes.c_ulong
            actual = _enviar(ventana, "collectionBehavior", tipo=entero)
            # Fuera MoveToActiveSpace, Managed, Transient, ParticipatesInCycle, FullScreenPrimary y
            # FullScreenNone (algunas combinaciones tiran una excepción); se suman CanJoinAllSpaces,
            # Stationary, IgnoresCycle y FullScreenAuxiliary.
            nuevo = (actual & ~(2 | 4 | 8 | 32 | 128 | 512)) | 1 | 16 | 64 | 256
            _enviar(ventana, "setCollectionBehavior:", nuevo, tipo=None, tipos=(entero,))
            _enviar(ventana, "setHidesOnDeactivate:", False, tipo=None, tipos=(ctypes.c_bool,))
            mascara = _enviar(ventana, "styleMask", tipo=entero)
            _enviar(ventana, "setStyleMask:", mascara | 128, tipo=None, tipos=(entero,))  # NonactivatingPanel
            if _enviar(ventana, "respondsToSelector:", _selector("_setPreventsActivation:"), tipo=ctypes.c_bool,
                       tipos=(ctypes.c_void_p,)):
                _enviar(ventana, "_setPreventsActivation:", True, tipo=None, tipos=(ctypes.c_bool,))

    _seguro(ajustar, None)


def al_reabrir(funcion) -> None:
    """Llama a funcion cuando abren la app de nuevo estando ya abierta (Finder, Launchpad, Spotlight).

    macOS no lanza otro proceso: le avisa al que ya corre (la mascota o el ícono) con el evento
    "reopen". Se instala después de que arranque el loop de Qt, así reemplaza al de AppKit."""
    if not ES_MAC:
        return

    def instalar():
        b = _bibliotecas()
        objc = b["objc"]

        def recibir(_yo, _sel, _evento, _respuesta):
            try:
                funcion()
            except Exception:  # un error acá no puede tirar abajo la app
                pass

        imp = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(recibir)
        nombre = f"WaveMascotReabrir{os.getpid()}_{len(b['vivos'])}".encode()
        clase = objc.objc_allocateClassPair(_clase("NSObject"), nombre, 0)
        if not clase:
            return
        objc.class_addMethod(clase, _selector("reabrir:respuesta:"), ctypes.cast(imp, ctypes.c_void_p), b"v@:@@")
        objc.objc_registerClassPair(clase)
        oyente = _enviar(_enviar(clase, "alloc"), "init")
        gestor = _enviar(_clase("NSAppleEventManager"), "sharedAppleEventManager")
        _enviar(gestor, "setEventHandler:andSelector:forEventClass:andEventID:", oyente,
                _selector("reabrir:respuesta:"), int.from_bytes(b"aevt", "big"), int.from_bytes(b"rapp", "big"),
                tipo=None, tipos=(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32))
        b["vivos"].append((imp, oyente))  # que el callback no se libere mientras viva la app

    from PyQt6.QtCore import QTimer
    QTimer.singleShot(400, lambda: _seguro(instalar, None))
