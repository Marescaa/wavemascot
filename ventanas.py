"""Utilidades de Windows para la mascota: de qué ventana viene un hook, si tiene el foco,
si hay algo en pantalla completa y cómo traer una ventana al frente.

La ventana "anfitriona" es la de la terminal, el editor o la app donde corre Claude Code:
se encuentra subiendo por los procesos padre del hook (bash -> Claude Code -> terminal).
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

ES_WINDOWS = os.name == "nt"
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
    if not ES_WINDOWS or not hwnd:
        return False
    activa = ventana_activa()
    if not activa:
        return False
    raiz = u32.GetAncestor(activa, GA_ROOTOWNER) or activa
    return raiz == hwnd or activa == hwnd or pid_de_ventana(raiz) == pid_de_ventana(hwnd)


def pantalla_completa() -> bool:
    """Hay un juego, video o presentación en pantalla completa (o Windows pide silencio)."""
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
