"""Marco propio para la ventana de ajustes en Windows.

Saca la barra de título del sistema (que Windows pinta negra o blanca, sin los colores de la app) y pone en su
lugar los botones de minimizar, maximizar y cerrar dibujados con los colores del tema. La ventana sigue siendo
una ventana normal para Windows: se arrastra, se acopla a los bordes (Win + flechas o llevándola al borde), se
estira desde los bordes, tiene sombra y anima al minimizar.

En macOS y Linux no hace nada: la barra del sistema queda como está.
"""

from __future__ import annotations

import ctypes
import math
import os
from ctypes import wintypes

from PyQt6.QtCore import QEvent, QMargins, QObject, QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QAbstractButton, QHBoxLayout, QWidget

from idiomas import t

ACTIVO = os.name == "nt"
ANCHO_BOTON, ALTO_BOTON = 46, 32  # como los de Windows 10 y 11
ANCHO_BOTONES = 3 * ANCHO_BOTON
BORDE = 6  # píxeles del borde que sirven para estirar la ventana
ROJO_CERRAR = "#C42B1C"  # el rojo del botón cerrar de Windows

C: dict = {}


def usar_colores(colores: dict) -> None:
    """ajustes.py pasa su diccionario de colores (el mismo objeto: los cambios de tema se ven solos)."""
    global C
    C = colores


# Windows

WM_NCCALCSIZE, WM_NCHITTEST = 0x0083, 0x0084
HT = {(True, False, False, False): 10, (False, True, False, False): 11, (False, False, True, False): 12,
      (True, False, True, False): 13, (False, True, True, False): 14, (False, False, False, True): 15,
      (True, False, False, True): 16, (False, True, False, True): 17}  # (izq, der, arriba, abajo) -> HT*
WS_CAPTION, WS_THICKFRAME, WS_SYSMENU = 0x00C00000, 0x00040000, 0x00080000
WS_MINIMIZEBOX, WS_MAXIMIZEBOX = 0x00020000, 0x00010000


class MARGINS(ctypes.Structure):
    _fields_ = [("izquierda", ctypes.c_int), ("derecha", ctypes.c_int), ("arriba", ctypes.c_int),
                ("abajo", ctypes.c_int)]


def preparar(ventana: QWidget) -> None:
    """Antes de mostrarla: sin barra del sistema, pero con los estilos que le dan acople, animaciones y sombra."""
    if not ACTIVO:
        return
    ventana.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    hwnd = wintypes.HWND(int(ventana.winId()))
    try:
        u32 = ctypes.windll.user32
        u32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
        u32.SetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_long)
        estilo = u32.GetWindowLongW(hwnd, -16)  # GWL_STYLE
        u32.SetWindowLongW(hwnd, -16, estilo | WS_CAPTION | WS_THICKFRAME | WS_SYSMENU | WS_MINIMIZEBOX
                           | WS_MAXIMIZEBOX)
        # Un píxel del marco de vidrio dentro de la ventana: con eso Windows le dibuja la sombra.
        ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(MARGINS(0, 0, 0, 1)))
        u32.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020)  # FRAMECHANGED
    except (AttributeError, OSError):
        pass


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD)]


def fuera_de_pantalla(ventana: QWidget) -> QMargins:
    """Maximizada, cuánto se sale la ventana del área de trabajo de su monitor, en píxeles de Qt.

    Windows agranda las ventanas maximizadas el ancho del marco (8 px por lado, también sobre la barra de
    tareas) y no deja achicarlas: ni WM_GETMINMAXINFO ni WM_WINDOWPOSCHANGING lo cambian. Antes se recortaba
    eso en WM_NCCALCSIZE, pero con el vidrio la ventana es "layered": Qt la pinta con UpdateLayeredWindow del
    tamaño de la ventana entera y, si el contenido es más chico, Windows descarta el dibujo y en pantalla
    queda el de antes de maximizar. Por eso la ventana entera es contenido y lo que se sale queda de margen."""
    # Minimizada sigue contando como maximizada, pero Windows la lleva a (-32000, -32000): sin margen.
    if not ACTIVO or not ventana.isMaximized() or ventana.isMinimized() or ventana.isFullScreen():
        return QMargins()
    u32 = ctypes.windll.user32
    u32.MonitorFromWindow.restype = wintypes.HMONITOR
    u32.MonitorFromWindow.argtypes = (wintypes.HWND, wintypes.DWORD)
    hwnd = wintypes.HWND(int(ventana.winId()))
    rect, monitor = wintypes.RECT(), MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
    if (not u32.GetWindowRect(hwnd, ctypes.byref(rect))
            or not u32.GetMonitorInfoW(u32.MonitorFromWindow(hwnd, 2), ctypes.byref(monitor))):
        return QMargins()  # 2: MONITOR_DEFAULTTONEAREST
    area, escala = monitor.rcWork, ventana.devicePixelRatioF() or 1.0
    lado = lambda px: math.ceil(max(0, px) / escala)
    return QMargins(lado(area.left - rect.left), lado(area.top - rect.top), lado(rect.right - area.right),
                    lado(rect.bottom - area.bottom))


def evento_nativo(ventana: QWidget, tipo, mensaje) -> tuple[bool, int] | None:
    """Lo que la ventana responde a Windows en lugar de su comportamiento normal (None: el de siempre)."""
    if not ACTIVO or bytes(tipo) != b"windows_generic_MSG":
        return None
    msg = wintypes.MSG.from_address(int(mensaje))
    if msg.message == WM_NCCALCSIZE:
        # Toda la ventana es "contenido": así desaparecen la barra y el marco del sistema (también maximizada:
        # ver fuera_de_pantalla).
        return True, 0
    if msg.message == WM_NCHITTEST and not (ventana.isMaximized() or ventana.isFullScreen()):
        # El punto viene en píxeles de pantalla: a píxeles de la ventana y de ahí a los de Qt (escala de Windows).
        x16, y16 = msg.lParam & 0xFFFF, msg.lParam >> 16 & 0xFFFF
        punto = wintypes.POINT(ctypes.c_short(x16).value, ctypes.c_short(y16).value)
        ctypes.windll.user32.ScreenToClient(msg.hWnd, ctypes.byref(punto))
        escala = ventana.devicePixelRatioF() or 1.0
        x, y = punto.x / escala, punto.y / escala
        lados = (x < BORDE, x >= ventana.width() - BORDE, y < BORDE, y >= ventana.height() - BORDE)
        if any(lados):
            return True, HT[lados]
    return None


def alternar_maximizada(ventana: QWidget) -> None:
    ventana.showNormal() if ventana.isMaximized() else ventana.showMaximized()


def arrastrar(ventana: QWidget) -> None:
    """Mueve la ventana con el mouse como si se la agarrara de la barra (con acople a los bordes)."""
    if ventana.windowHandle():
        ventana.windowHandle().startSystemMove()


# los botones

class BotonVentana(QAbstractButton):
    """Minimizar, maximizar / restaurar o cerrar, dibujados como los de Windows con los colores del tema."""

    def __init__(self, tipo: str, padre: QWidget):
        super().__init__(padre)
        self.tipo = tipo
        self.setFixedSize(ANCHO_BOTON, ALTO_BOTON)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

    def paintEvent(self, _evento) -> None:
        p = QPainter(self)
        encima, apretado = self.underMouse(), self.isDown()
        texto = QColor(C.get("texto", "#FFFFFF"))
        if self.tipo == "cerrar" and (encima or apretado):
            fondo = QColor(ROJO_CERRAR)
            if apretado:
                fondo.setAlpha(200)
            p.fillRect(self.rect(), fondo)
            texto = QColor("#FFFFFF")
        elif encima or apretado:
            fondo = QColor(C.get("texto", "#FFFFFF"))
            fondo.setAlpha(14 if apretado else 24)
            p.fillRect(self.rect(), fondo)
        if not self.window().isActiveWindow() and not encima:
            texto = QColor(C.get("suave", "#999999"))
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(texto, 1.0))
        x, y = self.width() / 2 - 5, self.height() / 2 - 5
        if self.tipo == "minimizar":
            p.drawLine(QPointF(x, y + 5.5), QPointF(x + 10, y + 5.5))
        elif self.tipo == "cerrar":
            p.drawLine(QPointF(x, y), QPointF(x + 10, y + 10))
            p.drawLine(QPointF(x + 10, y), QPointF(x, y + 10))
        elif self.window().isMaximized():  # restaurar: dos ventanitas encimadas
            p.drawRect(QRectF(x + 0.5, y + 2.5, 7, 7))
            p.drawPolyline([QPointF(x + 2.5, y + 2.5), QPointF(x + 2.5, y + 0.5), QPointF(x + 9.5, y + 0.5),
                            QPointF(x + 9.5, y + 7.5), QPointF(x + 7.5, y + 7.5)])
        else:
            p.drawRect(QRectF(x + 0.5, y + 0.5, 9, 9))


class BotonesVentana(QWidget):
    """Los tres botones, pegados a la esquina de arriba a la derecha de la ventana."""

    def __init__(self, ventana: QWidget):
        super().__init__(ventana)
        self.ventana = ventana
        caja = QHBoxLayout(self)
        caja.setContentsMargins(0, 0, 0, 0)
        caja.setSpacing(0)
        self.botones = {}
        for tipo in ("minimizar", "maximizar", "cerrar"):
            boton = BotonVentana(tipo, self)
            self.botones[tipo] = boton
            caja.addWidget(boton)
        self.botones["minimizar"].clicked.connect(ventana.showMinimized)
        self.botones["maximizar"].clicked.connect(lambda: alternar_maximizada(ventana))
        self.botones["cerrar"].clicked.connect(ventana.close)
        self.setFixedSize(ANCHO_BOTONES, ALTO_BOTON)
        self.poner_textos()
        ventana.installEventFilter(self)

    def poner_textos(self) -> None:
        self.botones["minimizar"].setToolTip(t("Minimizar"))
        self.botones["maximizar"].setToolTip(t("Restaurar") if self.ventana.isMaximized() else t("Maximizar"))
        self.botones["cerrar"].setToolTip(t("Cerrar"))

    def eventFilter(self, objeto: QObject, evento: QEvent) -> bool:
        if objeto is self.ventana:
            if evento.type() in (QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.WindowStateChange):
                margen = fuera_de_pantalla(self.ventana)  # maximizada: el contenido, dentro de la pantalla
                if self.ventana.contentsMargins() != margen:
                    self.ventana.setContentsMargins(margen)
                self.move(self.ventana.width() - self.width() - margen.right(), margen.top())
                self.raise_()
            if evento.type() in (QEvent.Type.WindowStateChange, QEvent.Type.ActivationChange):
                self.poner_textos()
                for boton in self.botones.values():
                    boton.update()
        return False

