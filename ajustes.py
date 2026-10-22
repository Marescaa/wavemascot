#!/usr/bin/env python3
"""Centro de ajustes de la mascota de Claude Code.

Uso:  pythonw ajustes.py   (o click en el ícono de la mascota junto al reloj)

Se abre en un proceso aparte y vuelve enseguida. Los cambios se guardan solos en
~/.wavemascot/config.json y mascota.py los lee en cada aviso.
"""

from __future__ import annotations

import ctypes
import json
import os
import random
import threading
import re
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mascota as m  # noqa: E402
import celular  # noqa: E402
import idiomas  # noqa: E402
import sprites  # noqa: E402
import ventanas  # noqa: E402
from idiomas import t  # noqa: E402

if __name__ == "__main__" and "--ventana" not in sys.argv[1:]:
    # Lanzador: abre la ventana desacoplada y sale sin cargar Qt.
    m.lanzar_desacoplado([str(Path(__file__).resolve()), "--ventana"])
    os._exit(0)

from PyQt6.QtCore import (QEasingCurve, QElapsedTimer, QLibraryInfo, QPointF, QRectF, QSize, Qt, QTimer,  # noqa: E402
                          QTranslator, QUrl, pyqtSignal)
from PyQt6.QtGui import (QColor, QDesktopServices, QIcon, QImageReader, QKeySequence, QLinearGradient, QPainter,  # noqa: E402
                         QPainterPath, QPalette, QPen, QPixmap, QShortcut)
from PyQt6.QtNetwork import QLocalServer, QLocalSocket  # noqa: E402
from PyQt6.QtCore import QFileSystemWatcher, QTime  # noqa: E402
from PyQt6.QtWidgets import (QAbstractButton, QAbstractSpinBox, QApplication, QButtonGroup, QCheckBox, QComboBox,  # noqa: E402
                             QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QMenu, QMessageBox, QPushButton, QScrollArea, QSlider, QTabWidget,
                             QTimeEdit, QToolButton, QVBoxLayout, QWidget)

import bandeja  # noqa: E402

CANAL_AJUSTES = m.CANAL + "-ajustes"
NOMBRES_ESTADO = {"listo": "Listo", "permiso": "Permiso", "pensando": "Pensando", "subagente": "Subagente",
                  "limite": "Límite", "error": "Error"}
NOMBRES_EVENTO = {"Stop": "Cuando termina", "Notification": "Cuando necesita algo (permisos, preguntas)",
                  "UserPromptSubmit": "Mientras piensa", "SubagentStop": "Cuando termina un subagente",
                  "StopFailure": "Límite de uso o error de la API"}
NOMBRES_CELULAR = {"listo": "Cuando termina", "permiso": "Cuando necesita algo (permisos, preguntas)",
                   "subagente": "Cuando termina un subagente", "limite": "Cuando llega al límite de uso",
                   "error": "Cuando hay un error de la API"}
NOMBRES_CONTENIDO = {"resumen": "Resumen del último mensaje", "duracion": "Duración de la tarea",
                     "proyecto": "Proyecto o carpeta", "chat": "Título del chat"}
NOMBRES_ESQUINA = {"arriba-derecha": "Arriba a la derecha", "arriba-izquierda": "Arriba a la izquierda",
                   "abajo-derecha": "Abajo a la derecha", "abajo-izquierda": "Abajo a la izquierda"}
NOMBRES_TAMANO = {2: "Chica", 3: "Mediana", 4: "Grande", 5: "Enorme"}
# Lo que mostraría cada aviso sin plantilla, y valores de ejemplo para la vista previa.
AUTOMATICO = {"listo": "¡Listo! Terminé", "permiso": "Necesito permiso para usar Bash", "error": "Error de la API",
              "pensando": "Pensando…", "subagente": "Terminó el subagente Explore", "limite": "Llegué al límite de uso"}
EJEMPLO = {"proyecto": "mi-proyecto", "chat": "Título del chat"}
RESUMEN_EJEMPLO = {"listo": "Agregué la validación y los tests pasan.", "permiso": "npm install --save-dev vitest",
                   "pensando": "Arreglá el bug del login", "subagente": "Encontré 3 archivos que usan el hook.",
                   "limite": "Claude usage limit reached. Your limit will reset at 3pm.",
                   "error": "API Error: 500 Internal server error"}
# Recortes (en píxeles de arte) de las miniaturas de cada parte del vestuario.
RECORTES = {"cabeza": (12, 18, 44, 42), "ropa": (10, 30, 46, 55), "accesorio": (12, 25, 44, 43),
            "entera": (4, 14, 52, 56)}

UI = (m.ASSETS / "ui").as_posix()  # flechas de las listas desplegables (una por tema)
C_OSCURO = {"fondo": "#1C1513", "panel": "#251D1A", "campo": "#2F2623", "borde": "#43362F",
            "texto": "#F4EDE8", "suave": "#B3A39A", "acento": "#D97757", "acento2": "#E8906F",
            "sobre": "#1C1513", "flecha": f"{UI}/flecha-oscuro.svg"}
C_CLARO = {"fondo": "#F3EDE6", "panel": "#FFFBF7", "campo": "#EFE6DD", "borde": "#D9CBBE",
           "texto": "#2B1A14", "suave": "#7A675C", "acento": "#C8643F", "acento2": "#D97757",
           "sobre": "#1C1513", "flecha": f"{UI}/flecha-claro.svg"}
CLAVES_PALETA = ("fondo", "panel", "campo", "borde", "texto", "suave", "acento", "acento2", "sobre")
# Cada estilo cambia solo los colores de esta ventana (oscuro, claro); el Clásico es el de siempre.
PALETAS = {
    "clasico": (C_OSCURO, C_CLARO),
    "sakura": (dict(zip(CLAVES_PALETA, ("#1E1418", "#281B21", "#33232B", "#4A3440", "#F8EAF0", "#BDA2AF", "#E8709F",
                                       "#F090B6", "#1E1418")), flecha=C_OSCURO["flecha"]),
               dict(zip(CLAVES_PALETA, ("#F7EEF2", "#FFFAFC", "#F1E4EA", "#E0CBD5", "#2E1823", "#7C5F6C", "#D4558A",
                                       "#E8709F", "#1E1418")), flecha=C_CLARO["flecha"])),
    "ninja": (dict(zip(CLAVES_PALETA, ("#141416", "#1B1B1E", "#252528", "#3A3A40", "#EFEFF1", "#A3A3AB", "#E0453F",
                                      "#EA6863", "#141416")), flecha=C_OSCURO["flecha"]),
              dict(zip(CLAVES_PALETA, ("#EFEFF1", "#FBFBFC", "#E6E6E9", "#D0D0D6", "#18181B", "#5F5F68", "#CC2F2A",
                                      "#E0453F", "#FFFFFF")), flecha=C_CLARO["flecha"])),
    "robot": (dict(zip(CLAVES_PALETA, ("#121820", "#18212A", "#212C37", "#344352", "#E7EEF4", "#9AA9B6", "#39B6D6",
                                      "#5FC8E2", "#121820")), flecha=C_OSCURO["flecha"]),
              dict(zip(CLAVES_PALETA, ("#EDF2F6", "#F9FBFD", "#E3EAF0", "#CCD7E0", "#142029", "#5B6B78", "#1F97B8",
                                      "#39B6D6", "#121820")), flecha=C_CLARO["flecha"])),
}
C = dict(C_OSCURO)  # colores en uso: el tema y el estilo los reemplazan en el lugar
ESTILO = """
QWidget { color: %(texto)s; font-family: "Segoe UI"; font-size: 10pt; }
QWidget#raiz { background: %(fondo)s; }
QLabel#titulo { font-size: 15pt; font-weight: 600; }
QLabel#subtitulo, QLabel#ayuda, QLabel#estado, QLabel#valor { color: %(suave)s; }
QLabel#ayuda { font-size: 9pt; }
QLabel#seccion { color: %(suave)s; font-size: 8pt; font-weight: 700; }
QLabel#beta { background: %(acento)s; color: %(sobre)s; font-size: 7pt; font-weight: 700; border-radius: 4px;
              padding: 0 5px; }
QLabel#codigo { color: %(acento)s; font-size: 22pt; font-weight: 700; }
QTabWidget::pane { border: 1px solid %(borde)s; border-radius: 12px; background: %(panel)s; top: -1px; }
QTabBar::tab { background: transparent; color: %(suave)s; padding: 8px 9px; border: none;
               border-bottom: 2px solid transparent; margin-right: 3px; font-weight: 600; }
QTabBar::tab:selected { color: %(texto)s; border-bottom: 2px solid %(acento)s; }
QTabBar::tab:hover { color: %(texto)s; }
QPushButton { background: %(campo)s; border: 1px solid %(borde)s; border-radius: 8px; padding: 7px 14px; }
QPushButton:hover { border-color: %(acento)s; }
QPushButton:pressed { background: %(borde)s; }
QPushButton:disabled { color: #6E605A; border-color: %(borde)s; }
QPushButton#primario { background: %(acento)s; border-color: %(acento)s; color: %(sobre)s; font-weight: 600; }
QPushButton#primario:hover { background: %(acento2)s; border-color: %(acento2)s; }
QPushButton#segmento { border-radius: 0; padding: 6px 0; min-width: 88px; }
QPushButton#segmento[pos="ini"] { border-top-left-radius: 8px; border-bottom-left-radius: 8px; }
QPushButton#segmento[pos="fin"] { border-top-right-radius: 8px; border-bottom-right-radius: 8px; }
QPushButton#segmento:checked { background: %(acento)s; border-color: %(acento)s; color: %(sobre)s; font-weight: 600; }
QLineEdit { background: %(campo)s; border: 1px solid %(borde)s; border-radius: 8px; padding: 6px 9px;
            selection-background-color: %(acento)s; }
QLineEdit:focus { border-color: %(acento)s; }
QSlider { min-height: 22px; }
QSlider::groove:horizontal { height: 4px; background: %(borde)s; border-radius: 2px; margin: 0 7px; }
QSlider::sub-page:horizontal { background: %(acento)s; border-radius: 2px; margin-left: 7px; }
QSlider::add-page:horizontal { margin-right: 7px; }
QSlider::sub-page:horizontal:disabled { background: #5A4A44; }
QSlider::handle:horizontal { background: %(texto)s; width: 14px; height: 14px; margin: -5px -7px; border-radius: 7px; }
QSlider::handle:horizontal:disabled { background: #7A6C66; }
QListWidget { background: transparent; border: none; outline: none; font-size: 9pt; }
QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 8px; }
QScrollBar::handle:vertical { background: %(borde)s; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QListWidget::item { border: 1px solid transparent; border-radius: 10px; padding: 2px; color: %(texto)s; }
QListWidget::item:hover { background: %(campo)s; }
QListWidget::item:selected { background: %(campo)s; border-color: %(acento)s; color: %(texto)s; }
QToolTip { background: %(campo)s; color: %(texto)s; border: 1px solid %(borde)s; padding: 4px; }
QMessageBox { background: %(fondo)s; }
QComboBox, QTimeEdit { background: %(campo)s; border: 1px solid %(borde)s; border-radius: 8px; padding: 5px 9px; }
QComboBox { padding-right: 30px; }
QComboBox:hover, QTimeEdit:hover, QTimeEdit:focus { border-color: %(acento)s; }
QComboBox:disabled, QTimeEdit:disabled { color: %(suave)s; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; width: 28px;
                       border: none; background: transparent; }
QComboBox::down-arrow { image: url(%(flecha)s); width: 12px; height: 8px; }
QComboBox::down-arrow:on { top: 1px; }
QComboBox QAbstractItemView { background: %(campo)s; border: 1px solid %(borde)s; padding: 4px; outline: none;
                              selection-background-color: %(acento)s; selection-color: %(sobre)s; }
QToolButton#idioma { background: %(campo)s; border: 1px solid %(borde)s; border-radius: 8px;
                     padding: 5px 26px 5px 9px; font-weight: 600; }
QToolButton#idioma:hover, QToolButton#idioma:open { border-color: %(acento)s; }
QToolButton#idioma::menu-indicator { image: url(%(flecha)s); width: 12px; height: 8px;
                                     subcontrol-origin: padding; subcontrol-position: center right; right: 9px; }
QMenu { background: %(campo)s; border: 1px solid %(borde)s; padding: 4px; }
QMenu::item { padding: 6px 18px 6px 10px; border-radius: 6px; }
QMenu::item:selected { background: %(acento)s; color: %(sobre)s; }
QMenu::icon { padding-left: 6px; }
"""  # se completa con C (ver aplicar_tema)
if m.MAC:
    # La letra del sistema y los mismos píxeles que en Windows (macOS cuenta 72 puntos por pulgada, no 96).
    ESTILO = re.sub(r"(\d+)pt\b", lambda x: f"{round(int(x.group(1)) * 96 / 72)}px",
                    ESTILO.replace('font-family: "Segoe UI"; ', ""))


def aplicar_tema(tema: str, estilo: str = "clasico") -> None:
    """Tema de la ventana: el claro usa colores claros; oscuro y acento, los oscuros. Cada estilo de
    mascota tiene su propia versión de esos colores."""
    oscuro, claro = PALETAS.get(estilo, PALETAS["clasico"])
    C.clear()
    C.update(claro if tema == "claro" else oscuro)
    app = QApplication.instance()
    paleta = QPalette()
    for rol, color in ((QPalette.ColorRole.Window, C["fondo"]), (QPalette.ColorRole.WindowText, C["texto"]),
                       (QPalette.ColorRole.Base, C["campo"]), (QPalette.ColorRole.Text, C["texto"]),
                       (QPalette.ColorRole.Button, C["campo"]), (QPalette.ColorRole.ButtonText, C["texto"]),
                       (QPalette.ColorRole.Highlight, C["acento"])):
        paleta.setColor(rol, QColor(color))
    app.setPalette(paleta)
    app.setStyleSheet(ESTILO % C)
    for ventana in app.topLevelWidgets():  # los controles dibujados a mano leen C al pintarse
        ventana.update()


def seccion(texto: str) -> QLabel:
    etiqueta = QLabel(t(texto).upper())
    etiqueta.setObjectName("seccion")
    return etiqueta


def ayuda(texto: str) -> QLabel:
    etiqueta = QLabel(t(texto))
    etiqueta.setObjectName("ayuda")
    etiqueta.setWordWrap(True)
    return etiqueta


def valor() -> QLabel:
    """Etiqueta para el valor de un control deslizante: ancho fijo, alineada a la derecha."""
    etiqueta = QLabel(objectName="valor")
    etiqueta.setFixedWidth(64)
    etiqueta.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return etiqueta


def fila(*widgets, espacio: int = 14) -> QHBoxLayout:
    caja = QHBoxLayout()
    caja.setSpacing(espacio)
    for w in widgets:
        caja.addWidget(w, 1 if isinstance(w, QSlider) else 0)
    return caja


def opcion(texto: str, al_cambiar) -> tuple[QCheckBox, QHBoxLayout]:
    """Interruptor con su texto al lado."""
    interruptor = Interruptor()
    interruptor.toggled.connect(al_cambiar)
    caja = fila(interruptor, QLabel(t(texto)), espacio=10)
    caja.addStretch(1)
    return interruptor, caja


def segmentado(opciones: dict[str, str], al_elegir, padre) -> tuple[dict[str, QPushButton], QHBoxLayout]:
    """Botones pegados de los que se elige uno (como un selector de pestañas)."""
    caja, botones, grupo = QHBoxLayout(), {}, QButtonGroup(padre)
    caja.setSpacing(0)
    for i, (clave, texto) in enumerate(opciones.items()):
        boton = QPushButton(t(texto), objectName="segmento", checkable=True)
        boton.setProperty("pos", "ini" if i == 0 else "fin" if i == len(opciones) - 1 else "medio")
        boton.clicked.connect(lambda _, c=clave: al_elegir(c))
        grupo.addButton(boton)
        botones[clave] = boton
        caja.addWidget(boton)
    caja.addStretch(1)
    return botones, caja


def pixmap_png(datos: bytes, dpr: float) -> QPixmap:
    pixmap = QPixmap()
    pixmap.loadFromData(datos)
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


def miniatura(aspecto: dict, recorte: str, dpr: float, escala: int = 2) -> QPixmap:
    """La mascota quieta, recortada, a `escala` px lógicos por pixel de arte y nítida en cualquier DPI."""
    fisica = max(1, round(escala * dpr))
    return pixmap_png(sprites.miniatura(aspecto, RECORTES[recorte], fisica), fisica / escala)


def miniatura_imagen(ruta: Path, lado: QSize, dpr: float) -> QPixmap:
    img = QImageReader(str(ruta)).read()
    lienzo = QPixmap(round(lado.width() * dpr), round(lado.height() * dpr))
    lienzo.fill(Qt.GlobalColor.transparent)
    if not img.isNull():
        caja = lienzo.size()
        if max(img.width(), img.height()) * 2 <= min(caja.width(), caja.height()):  # pixel art chico
            k = min(caja.width() // img.width(), caja.height() // img.height())
            img = img.scaled(img.width() * k, img.height() * k)
        else:
            img = img.scaled(caja, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        p = QPainter(lienzo)
        p.drawImage(QPointF((caja.width() - img.width()) / 2, (caja.height() - img.height()) / 2), img)
        p.end()
    lienzo.setDevicePixelRatio(dpr)
    return lienzo


def traducir_qt(app: QApplication, idioma: str) -> None:
    """Los textos propios de Qt (Sí/No, Copiar/Pegar...) en el mismo idioma que el resto."""
    for viejo in getattr(app, "traductores", []):
        app.removeTranslator(viejo)
    app.traductores = []
    archivo = {"es": "qtbase_es", "pt": "qtbase_pt_BR"}.get(idioma)
    traductor = QTranslator(app)
    if archivo and traductor.load(archivo, QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(traductor)
        app.traductores.append(traductor)


def bandera(idioma: str, dpr: float) -> QPixmap:
    """Banderita de 22x15 dibujada a mano: Estados Unidos (en), Argentina (es) y Brasil (pt)."""
    ancho, alto = 22, 15
    lienzo = QPixmap(round(ancho * dpr), round(alto * dpr))
    lienzo.fill(Qt.GlobalColor.transparent)
    lienzo.setDevicePixelRatio(dpr)
    p = QPainter(lienzo)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    forma = QPainterPath()
    forma.addRoundedRect(QRectF(0, 0, ancho, alto), 2.5, 2.5)
    p.setClipPath(forma)
    p.setPen(Qt.PenStyle.NoPen)
    if idioma == "en":
        for franja in range(7):  # 7 franjas en vez de 13: a este tamaño se leen mejor
            p.setBrush(QColor("#B22234" if franja % 2 == 0 else "#FFFFFF"))
            p.drawRect(QRectF(0, franja * alto / 7, ancho, alto / 7 + 0.5))
        p.setBrush(QColor("#3C3B6E"))
        p.drawRect(QRectF(0, 0, ancho * 0.45, alto * 4 / 7))
        p.setBrush(QColor("#FFFFFF"))
        for fila_e in range(3):
            for col in range(4 - fila_e % 2):
                p.drawEllipse(QPointF(1.6 + col * 2.4 + (fila_e % 2) * 1.2, 1.5 + fila_e * 2.3), 0.55, 0.55)
    elif idioma == "es":
        for franja, color in enumerate(("#74ACDF", "#FFFFFF", "#74ACDF")):
            p.setBrush(QColor(color))
            p.drawRect(QRectF(0, franja * alto / 3, ancho, alto / 3 + 0.5))
        p.setBrush(QColor("#F6B40E"))
        p.drawEllipse(QPointF(ancho / 2, alto / 2), 1.9, 1.9)
    else:
        p.setBrush(QColor("#009C3B"))
        p.drawRect(QRectF(0, 0, ancho, alto))
        p.setBrush(QColor("#FFDF00"))
        p.drawPolygon([QPointF(ancho / 2, 1.6), QPointF(ancho - 2, alto / 2), QPointF(ancho / 2, alto - 1.6),
                       QPointF(2, alto / 2)])
        p.setBrush(QColor("#002776"))
        p.drawEllipse(QPointF(ancho / 2, alto / 2), 3.6, 3.6)
        p.setPen(QPen(QColor("#FFFFFF"), 0.8))
        p.drawArc(QRectF(ancho / 2 - 5, alto / 2 - 1.4, 10, 8), 40 * 16, 100 * 16)
    p.setClipping(False)
    p.setPen(QPen(QColor(0, 0, 0, 60), 1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(0.5, 0.5, ancho - 1, alto - 1), 2.5, 2.5)
    p.end()
    return lienzo


def traer_al_frente(ventana: QWidget) -> None:
    """La ventana la pidió el usuario: que aparezca adelante y con foco."""
    ventana.setWindowState(ventana.windowState() & ~Qt.WindowState.WindowMinimized)
    ventana.show()
    ventana.raise_()
    ventana.activateWindow()
    if m.MAC:
        ventanas.activar_esta_app()
    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    u32.GetForegroundWindow.restype = wintypes.HWND
    u32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.c_void_p)
    u32.SetForegroundWindow.argtypes = u32.BringWindowToTop.argtypes = (wintypes.HWND,)
    hwnd = wintypes.HWND(int(ventana.winId()))
    hilo_frente = u32.GetWindowThreadProcessId(u32.GetForegroundWindow(), None)
    hilo = k32.GetCurrentThreadId()
    # Windows solo deja tomar el foco a quien ya lo tiene: nos "pegamos" un instante a ese hilo.
    if hilo_frente and hilo_frente != hilo and u32.AttachThreadInput(hilo, hilo_frente, True):
        u32.SetForegroundWindow(hwnd)
        u32.BringWindowToTop(hwnd)
        u32.AttachThreadInput(hilo, hilo_frente, False)


# --- controles propios -------------------------------------------------------------

class BotonEscuchar(QAbstractButton):
    """Botón cuadrado con un triángulo de "reproducir", del alto de las listas de sonidos."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(32, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(t("Escuchar"))

    def paintEvent(self, evento) -> None:
        from PyQt6.QtGui import QPolygonF

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        borde = C["acento"] if self.underMouse() or self.isDown() else C["borde"]
        p.setPen(QPen(QColor(borde), 1))
        p.setBrush(QColor(C["borde"] if self.isDown() else C["campo"]))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(C["acento"] if self.isEnabled() else C["suave"]))
        cx, cy = self.width() / 2 + 1, self.height() / 2
        p.drawPolygon(QPolygonF([QPointF(cx - 4, cy - 5.5), QPointF(cx + 5.5, cy), QPointF(cx - 4, cy + 5.5)]))

    def enterEvent(self, evento) -> None:
        self.update()

    def leaveEvent(self, evento) -> None:
        self.update()


class Interruptor(QCheckBox):
    """Casilla con forma de interruptor."""

    def sizeHint(self) -> QSize:
        return QSize(40, 22)

    def hitButton(self, pos) -> bool:
        return self.rect().contains(pos)

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pista = QRectF(1, (self.height() - 20) / 2, 38, 20)
        if not self.isEnabled():
            p.setOpacity(0.4)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(C["acento"] if self.isChecked() else C["borde"]))
        p.drawRoundedRect(pista, 10, 10)
        p.setBrush(QColor("#FFF9F4"))  # la perilla siempre clara, en cualquier tema
        p.drawEllipse(QPointF(pista.right() - 10 if self.isChecked() else pista.left() + 10, pista.center().y()), 7, 7)


class MuestraColor(QAbstractButton):
    """Un círculo de color para elegir el color de la mascota (o, con pieles=True, el tono de piel del ninja)."""

    def __init__(self, color_id: str, pieles: bool = False):
        super().__init__()
        if pieles:
            nombre, cuerpo = sprites.PIELES[color_id]
            sombra = tuple(round(x * 0.78) for x in cuerpo)
        else:
            nombre, cuerpo, sombra, _ = sprites.COLORES[color_id]
        self.color_id, self.cuerpo, self.sombra = color_id, QColor(*cuerpo), QColor(*sombra)
        self.setCheckable(True)
        self.setToolTip(t(nombre))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(36, 36)

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        centro = QPointF(18, 18)
        if self.isChecked() or self.underMouse():
            p.setPen(QPen(QColor(C["acento"] if self.isChecked() else C["suave"]), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(centro, 16, 16)
        p.setPen(QPen(self.sombra, 2))
        p.setBrush(self.cuerpo)
        p.drawEllipse(centro, 11, 11)

    def enterEvent(self, evento) -> None:
        self.update()

    def leaveEvent(self, evento) -> None:
        self.update()


class Galeria(QListWidget):
    """Grilla de miniaturas elegibles, con la altura justa para que no haga falta scroll."""

    elegido = pyqtSignal(str)

    def __init__(self, lado_icono: QSize, ancho: int = 0):
        super().__init__()
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setIconSize(lado_icono)
        self.setGridSize(QSize(ancho or max(lado_icono.width() + 12, 82), lado_icono.height() + 30))
        self.setMovement(QListWidget.Movement.Static)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setWordWrap(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Se avisa en el ciclo siguiente: quien escucha puede reconstruir esta misma galería.
        self.currentItemChanged.connect(lambda item, _: item and QTimer.singleShot(
            0, lambda clave=item.data(Qt.ItemDataRole.UserRole): self.elegido.emit(clave)))

    def cargar(self, opciones: list[tuple[str, str, QPixmap]], elegido: str | None) -> None:
        """opciones: (id, nombre, miniatura). Si elegido no está, no queda nada seleccionado."""
        self.blockSignals(True)
        self.clear()
        # Una segunda línea de texto solo si algún nombre no entra (pasa en algunos idiomas).
        self.ensurePolished()  # con la fuente de la hoja de estilo, no la de por defecto
        fm = self.fontMetrics()
        largo = any(fm.horizontalAdvance(nombre) > self.gridSize().width() - 13 for _, nombre, _ in opciones)
        self.setGridSize(QSize(self.gridSize().width(), self.iconSize().height() + 30 + (fm.height() if largo else 0)))
        for clave, nombre, pixmap in opciones:
            icono = QIcon(pixmap)
            icono.addPixmap(pixmap, QIcon.Mode.Selected)  # sin el tinte que Qt le pone al elegido
            item = QListWidgetItem(icono, nombre)
            item.setData(Qt.ItemDataRole.UserRole, clave)
            item.setToolTip(nombre)
            item.setSizeHint(self.gridSize())  # así el nombre puede usar la segunda línea
            self.addItem(item)
            if clave == elegido:
                self.setCurrentItem(item)
        if elegido is None or self.currentItem() is None:
            self.clearSelection()
            self.setCurrentItem(None)
        self.blockSignals(False)
        self.ajustar_alto()

    def ajustar_alto(self) -> None:
        por_fila = max(1, self.viewport().width() // self.gridSize().width())
        filas = max(1, -(-self.count() // por_fila))
        self.setFixedHeight(filas * self.gridSize().height() + 4)

    def resizeEvent(self, evento) -> None:
        super().resizeEvent(evento)
        self.ajustar_alto()


class SelectorEsquina(QWidget):
    """Un monitor en miniatura: se hace click en la esquina donde aparece la mascota."""

    cambio = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setFixedSize(204, 128)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.esquina, self.encima = m.ESQUINAS[0], None
        self.pantalla = QRectF(16, 10, 172, 94)

    def zona(self, esquina: str) -> QRectF:
        w, h, s = 56, 34, self.pantalla
        x = s.right() - 6 - w if esquina.endswith("derecha") else s.left() + 6
        y = s.top() + 6 if esquina.startswith("arriba") else s.bottom() - 6 - h
        return QRectF(x, y, w, h)

    def esquina_en(self, pos) -> str:
        arriba = pos.y() < self.pantalla.center().y()
        derecha = pos.x() > self.pantalla.center().x()
        return f"{'arriba' if arriba else 'abajo'}-{'derecha' if derecha else 'izquierda'}"

    def elegir(self, esquina: str) -> None:
        if esquina != self.esquina:
            self.esquina = esquina
            self.update()
            self.cambio.emit(esquina)

    def mousePressEvent(self, evento) -> None:
        self.elegir(self.esquina_en(evento.position()))

    def mouseMoveEvent(self, evento) -> None:
        self.encima = self.esquina_en(evento.position())
        self.update()

    def leaveEvent(self, evento) -> None:
        self.encima = None
        self.update()

    def keyPressEvent(self, evento) -> None:
        vertical, horizontal = self.esquina.split("-")
        tecla = evento.key()
        if tecla in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            vertical = "arriba" if tecla == Qt.Key.Key_Up else "abajo"
        elif tecla in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            horizontal = "izquierda" if tecla == Qt.Key.Key_Left else "derecha"
        else:
            return super().keyPressEvent(evento)
        self.elegir(f"{vertical}-{horizontal}")

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(C["borde"]), 1.5))
        p.setBrush(QColor(C["campo"]))
        p.drawRoundedRect(QRectF(9, 3, 186, 108), 9, 9)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(C["borde"]))
        p.drawRect(QRectF(94, 111, 16, 6))
        p.drawRoundedRect(QRectF(72, 117, 60, 6), 3, 3)
        p.setBrush(QColor("#2A3039"))
        p.drawRoundedRect(self.pantalla, 4, 4)
        for esquina in m.ESQUINAS:
            z = self.zona(esquina)
            if esquina == self.esquina:
                relleno = QColor(C["acento"])
                relleno.setAlpha(60)
                p.setPen(QPen(QColor(C["acento"]), 1.5))
                p.setBrush(relleno)
                p.drawRoundedRect(z, 6, 6)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(C["acento"]))
                p.drawEllipse(QPointF(z.center().x(), z.top() + 11), 6, 5.5)
                p.setBrush(QColor(C["fondo"]))
                p.drawRoundedRect(QRectF(z.center().x() - 15, z.top() + 20, 30, 7), 3.5, 3.5)
            else:
                color = QColor(C["suave"] if esquina == self.encima else C["borde"])
                p.setPen(QPen(color, 1.2, Qt.PenStyle.DashLine))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(z, 6, 6)
        if self.hasFocus():
            p.setPen(QPen(QColor(C["acento"]), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(7, 1, 190, 112), 10, 10)


def cuadro_en(cuadros: list, ms: float, repetir: bool = True):
    """El cuadro que se ve a los ms de empezar una animación (la última imagen si no se repite)."""
    total = sum(d for _, d in cuadros)
    ms = ms % total if repetir else min(ms, total - 1)
    for pm, d in cuadros:
        if ms < d:
            return pm
        ms -= d
    return cuadros[-1][0]


class VistaPrevia(QWidget):
    """Dibuja el aviso completo tal como se ve en la pantalla: la mascota entra desde el costado (con la
    animación de su estilo, si tiene), avisa con el cartel durante la duración elegida, se va y vuelve."""

    RETRASO = 0.18   # como en mascota.py: el cartel llega un poco después que la mascota
    ENTRADA, SALIDA, PAUSA = 650, 480, 900  # ms del Clásico (solo se desliza) y de la pausa entre avisos

    def __init__(self):
        super().__init__()
        self.setMinimumSize(330, 410)
        self.cartel = m.Cartel()
        self.cuadros: list = []
        self.entrada = self.salida = None
        self.clave, self.estado, self.duracion, self.fase = None, "listo", 5.0, "entrada"
        self.curva = QEasingCurve(QEasingCurve.Type.OutBack)
        self.curva.setOvershoot(1.2)
        self.reloj = QElapsedTimer()
        self.reloj.start()
        self.tic = QTimer(self, interval=30, timeout=self.update)
        self.tic.start()

    def mostrar(self, config: dict, estado: str, mensaje: str, resumen: str, meta: str, botones=()) -> None:
        dpr = self.devicePixelRatioF()
        clave = (json.dumps(config["aspecto"], sort_keys=True), config["imagen"], estado, config["tamano"], dpr)
        if clave != self.clave:  # otra mascota u otro estado: el aviso vuelve a empezar
            self.clave = clave
            aspecto, imagen, tamano = config["aspecto"], config["imagen"], config["tamano"]
            self.cuadros = m.cargar_cuadros(aspecto, imagen, estado, tamano, dpr)
            propia = not imagen and sprites.tiene_entrada(aspecto)
            self.entrada = m.cargar_cuadros(aspecto, imagen, "entrada", tamano, dpr) if propia else None
            self.salida = m.cargar_cuadros(aspecto, imagen, "salida", tamano, dpr) if propia else None
            self.fase = "entrada"
            self.reloj.restart()
        self.duracion = config["duracion"]
        self.estado = estado
        self.cartel.tema = config["tema"]
        self.cartel.estilo = config["aspecto"]["estilo"]
        self.cartel.medir(mensaje, resumen, meta, botones)
        self.update()

    def avance(self, t: float, retraso: float) -> float:
        return self.curva.valueForProgress(min(1.0, max(0.0, (t - retraso) / (1 - self.RETRASO))))

    def momento(self):
        """(cuadro, línea de tiempo 0..1, cuánto queda del cartel 0..1, barra del cartel) según la fase."""
        n = sprites.CUADROS_DESLIZ
        dt = self.reloj.elapsed()
        siguiente = None
        pm, t, k, barra = None, 1.0, 1.0, 1.0
        if self.fase == "entrada":
            if self.entrada:
                largo = sum(d for _, d in self.entrada[:n]) / (1 - self.RETRASO)
                pm, t = cuadro_en(self.entrada, dt, repetir=False), min(1.0, dt / largo)
                fin = max(largo, sum(d for _, d in self.entrada))
            else:
                pm, t, fin = cuadro_en(self.cuadros, dt), min(1.0, dt / self.ENTRADA), self.ENTRADA
            siguiente = "estado" if dt >= fin else None
        elif self.fase == "estado":
            ms = max(1000, self.duracion * 1000)
            pm, barra = cuadro_en(self.cuadros, dt), 1 - min(1.0, dt / ms)
            siguiente = "salida" if dt >= ms else None
        elif self.fase == "salida":
            barra = 0.0
            if self.salida:
                quieta = sum(d for _, d in self.salida[:-n]) or 1
                largo = sum(d for _, d in self.salida[-n:]) / (1 - self.RETRASO)
                pm = cuadro_en(self.salida, dt, repetir=False)
                k = 1 - min(1.0, dt / quieta) ** 3  # el cartel se va primero
                t = 1 - min(1.0, max(0.0, (dt - quieta) / largo))
                siguiente = "pausa" if dt >= quieta + largo else None
            else:
                pm, t = cuadro_en(self.cuadros, dt), 1 - min(1.0, dt / self.SALIDA)
                siguiente = "pausa" if dt >= self.SALIDA else None
        else:
            t = 0.0
            siguiente = "entrada" if dt >= self.PAUSA else None
        if siguiente:
            self.fase = siguiente
            self.reloj.restart()
        return pm, t, k, barra

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        fondo = QLinearGradient(r.topLeft(), r.bottomRight())
        fondo.setColorAt(0, QColor("#3A4250"))
        fondo.setColorAt(1, QColor("#20242C"))
        forma = QPainterPath()
        forma.addRoundedRect(r, 14, 14)
        p.fillPath(forma, fondo)
        p.setPen(QPen(QColor(C["borde"]), 1))
        p.drawPath(forma)
        if not self.cuadros:
            return
        pm, t, k, barra = self.momento()
        if t <= 0 or pm is None:
            return
        sw, sh = pm.width() / pm.devicePixelRatio(), pm.height() / pm.devicePixelRatio()
        arriba = r.top() + (r.height() - sh - 2 - self.cartel.alto) / 2
        cx = r.center().x()
        recorrido = r.width()  # entra y sale por el costado derecho, como en la esquina por defecto
        p.setClipPath(forma)
        p.save()
        p.translate((1 - self.avance(t, 0.0)) * recorrido, 0)
        m.pintar_sombra(p, cx, arriba + sh, sw)
        p.drawPixmap(QPointF(cx - sw / 2, arriba), pm)
        p.restore()
        p.translate((1 - self.avance(t, self.RETRASO) * k) * recorrido, 0)
        self.cartel.pintar(p, cx, arriba + sh + 2, QColor(m.ESTADOS[self.estado]["acento"]), barra)


# --- ventana principal -------------------------------------------------------------

class Ajustes(QWidget):
    idioma_cambiado = pyqtSignal(str)
    respuesta_telegram = pyqtSignal(str, object)  # (qué se pidió, resultado o texto del error)

    def __init__(self):
        super().__init__()
        self.setObjectName("raiz")
        self.config = m.cargar_config()
        idiomas.usar(self.config["idioma"])  # antes de cualquier texto
        self.setWindowTitle(t("Ajustes de WaveMascot"))
        self.setWindowIcon(bandeja.icono_mascota("terracota", grande=m.MAC))
        self.estado_vista = "listo"
        self.sonidos = m.Sonidos(self)
        self.timer_guardar = QTimer(self, singleShot=True, interval=300, timeout=self.guardar)
        # Conectar Telegram: el código que se le muestra a la persona y la consulta al servidor hasta que
        # se lo manda al bot.
        self.codigo, self.consultando, self.fin_codigo = "", False, 0.0
        self.timer_estado = QTimer(self, interval=2500, timeout=self.consultar_estado)
        self.respuesta_telegram.connect(self.al_responder_telegram)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(22, 18, 22, 16)
        raiz.setSpacing(14)
        raiz.addLayout(self.cabecera())
        cuerpo = QHBoxLayout()
        cuerpo.setSpacing(18)
        self.pestanas = QTabWidget()
        for pagina, titulo in ((self.pestana_notificacion(), "Notificación"),
                               (self.pestana_comportamiento(), "Comportamiento"), (self.pestana_mascota(), "Mascota"),
                               (self.pestana_vestuario(), "Vestuario"), (self.pestana_estilo(), "Sonido y estilo"),
                               (self.pestana_celular(), "Celular")):
            area = QScrollArea(widgetResizable=True, frameShape=QFrame.Shape.NoFrame)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            area.setWidget(pagina)  # si la pantalla es chica, la pestaña se desplaza en vez de cortarse
            self.pestanas.addTab(area, t(titulo))
        cuerpo.addWidget(self.pestanas, 1)
        cuerpo.addLayout(self.panel_vista())
        raiz.addLayout(cuerpo, 1)
        raiz.addLayout(self.pie())
        QShortcut(QKeySequence("Esc"), self, activated=self.close)
        if m.MAC:
            QShortcut(QKeySequence("Ctrl+W"), self, activated=self.close)  # Qt lo muestra como ⌘W

        self.cargar_en_controles()
        self.estado_guardado.setText(t("Los cambios se guardan solos"))
        if self.config["celular"]["llave"] and self.config["celular"]["conectado"]:
            llave = self.config["celular"]["llave"]  # ¿sigue conectado? (pudo mandar /stop desde Telegram)
            self.en_segundo_plano("inicial", lambda: celular.estado(llave))
        m.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.vigia = QFileSystemWatcher([str(m.CONFIG_DIR)], self)
        self.vigia.directoryChanged.connect(lambda _: QTimer.singleShot(300, self.sincronizar))

    # armado

    def cabecera(self) -> QHBoxLayout:
        caja = QHBoxLayout()
        caja.setSpacing(12)
        self.icono_cabecera = QLabel()
        self.icono_cabecera.setFixedSize(48, 42)
        textos = QVBoxLayout()
        textos.setSpacing(0)
        textos.addWidget(QLabel("WaveMascot", objectName="titulo"))
        textos.addWidget(QLabel(t("Cómo y dónde te avisa cuando Claude Code termina o necesita algo"),
                                objectName="subtitulo"))
        caja.addWidget(self.icono_cabecera)
        caja.addLayout(textos, 1)
        caja.addWidget(self.selector_idioma(), 0, Qt.AlignmentFlag.AlignTop)
        return caja

    def selector_idioma(self) -> QToolButton:
        """La banderita de arriba a la derecha: cambia el idioma de todo."""
        boton = QToolButton(objectName="idioma")
        boton.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        boton.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        boton.setCursor(Qt.CursorShape.PointingHandCursor)
        boton.setToolTip("Idioma · Language · Idioma")
        dpr = self.devicePixelRatioF()
        boton.setIcon(QIcon(bandera(idiomas.actual(), dpr)))
        boton.setIconSize(QSize(22, 15))
        boton.setText(idiomas.actual().upper())
        menu = QMenu(boton)
        for codigo, nombre in idiomas.IDIOMAS.items():
            accion = menu.addAction(QIcon(bandera(codigo, dpr)), nombre)
            accion.setCheckable(True)
            accion.setChecked(codigo == idiomas.actual())
            accion.triggered.connect(lambda _=False, c=codigo: self.cambiar_idioma(c))
        boton.setMenu(menu)
        return boton

    def pestana_notificacion(self) -> QWidget:
        pagina = QWidget()
        grilla = QGridLayout(pagina)
        grilla.setContentsMargins(22, 18, 22, 18)
        grilla.setHorizontalSpacing(28)
        grilla.setVerticalSpacing(6)

        grilla.addWidget(seccion("Esquina de la pantalla"), 0, 0)
        self.selector = SelectorEsquina()
        self.selector.cambio.connect(lambda e: self.cambiar("esquina", e))
        grilla.addWidget(self.selector, 1, 0, 6, 1, Qt.AlignmentFlag.AlignTop)
        self.nombre_esquina = ayuda("")
        grilla.addWidget(self.nombre_esquina, 7, 0)

        grilla.addWidget(seccion("Duración en pantalla"), 0, 1)
        self.duracion = QSlider(Qt.Orientation.Horizontal, minimum=2, maximum=30)
        self.valor_duracion = valor()
        self.duracion.valueChanged.connect(lambda v: self.cambiar("duracion", v))
        grilla.addLayout(fila(self.duracion, self.valor_duracion), 1, 1)
        grilla.setRowMinimumHeight(2, 10)

        grilla.addWidget(seccion("Mostrar en el cartel"), 3, 1)
        self.contenido = {}
        for numero, (clave, texto) in enumerate(NOMBRES_CONTENIDO.items(), 4):
            interruptor, caja = opcion(texto, lambda v, c=clave: self.cambiar_grupo("contenido", c, v))
            self.contenido[clave] = interruptor
            grilla.addLayout(caja, numero, 1)

        grilla.setRowMinimumHeight(8, 14)
        grilla.addWidget(seccion("Mensajes"), 9, 0, 1, 2)
        self.textos = {}
        for numero, (evento, titulo) in enumerate((("Stop", "Cuando termina (Stop)"),
                                                    ("Notification", "Cuando necesita algo (Notification)")), 10):
            campo = QLineEdit(placeholderText=t("Vacío = texto automático"), clearButtonEnabled=True)
            campo.textChanged.connect(lambda texto, ev=evento: self.cambiar_mensaje(ev, texto))
            self.textos[evento] = campo
            bloque = QVBoxLayout()
            bloque.setSpacing(4)
            bloque.addWidget(QLabel(t(titulo)))
            bloque.addWidget(campo)
            grilla.addLayout(bloque, numero, 0, 1, 2)
        grilla.addWidget(ayuda("Podés usar {mensaje} (el texto original del aviso, por ejemplo "
                               "«Necesito permiso para usar Bash»), {proyecto} y {chat}."), 12, 0, 1, 2)

        grilla.setRowStretch(15, 1)
        self.probar = QPushButton(objectName="primario", clicked=self.probar_aviso)
        self.probar.setCursor(Qt.CursorShape.PointingHandCursor)
        caja = fila(self.probar, ayuda("Muestra el aviso real en tu pantalla, con lo guardado."))
        caja.setStretch(1, 1)
        grilla.addLayout(caja, 16, 0, 1, 2)
        grilla.setColumnStretch(1, 1)
        return pagina

    def pestana_comportamiento(self) -> QWidget:
        pagina = QWidget()
        caja = QVBoxLayout(pagina)
        caja.setContentsMargins(22, 18, 22, 18)
        caja.setSpacing(6)

        caja.addWidget(seccion("Modo"))
        self.botones_modo, segmentos = segmentado({"aviso": "Aviso", "compania": "Compañera"}, self.cambiar_modo, self)
        caja.addLayout(segmentos)
        caja.addWidget(ayuda("Aviso: aparece desde el borde y se va sola. Compañera: vive sobre el Dock "
                             "(arrastrala a donde quieras), crece para avisarte y se duerme si se termina el "
                             "límite de uso." if m.MAC else
                             "Aviso: aparece desde el borde y se va sola. Compañera: vive sobre la barra de "
                             "tareas (arrastrala a donde quieras), crece para avisarte y se duerme si se "
                             "termina el límite de uso."))
        self.vida = {}
        for clave, texto in (("chiquita", "Esperar chiquita, parada sobre el Dock" if m.MAC else
                              "Esperar chiquita, parada sobre la barra de tareas"),
                             ("pasear", "Dar una caminatita de vez en cuando"),
                             ("idle", "Animaciones de reposo al azar"), ("mirada", "Los ojos siguen al cursor")):
            interruptor, fila_vida = opcion(texto, lambda v, c=clave: self.cambiar_grupo("vida", c, v))
            self.vida[clave] = interruptor
            caja.addLayout(fila_vida)

        caja.addSpacing(10)
        caja.addWidget(seccion("Avisar"))
        self.eventos = {}
        for evento, texto in NOMBRES_EVENTO.items():
            interruptor, fila_evento = opcion(texto, lambda v, e=evento: self.cambiar_grupo("eventos", e, v))
            self.eventos[evento] = interruptor
            caja.addLayout(fila_evento)

        caja.addSpacing(10)
        caja.addWidget(seccion("No molestar"))
        self.no_molestar, fila_nm = opcion("Silenciar entre", lambda v: self.cambiar_grupo("no_molestar", "activo", v))
        self.desde, self.hasta = QTimeEdit(displayFormat="HH:mm"), QTimeEdit(displayFormat="HH:mm")
        for hora in (self.desde, self.hasta):  # sin los botoncitos: se escribe o se usa la ruedita
            hora.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            hora.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hora.setFixedWidth(66)
            hora.setToolTip(t("Escribí la hora o cambiala con la ruedita del mouse o las flechas"))
        self.desde.timeChanged.connect(lambda t: self.cambiar_grupo("no_molestar", "desde", t.toString("HH:mm")))
        self.hasta.timeChanged.connect(lambda t: self.cambiar_grupo("no_molestar", "hasta", t.toString("HH:mm")))
        fila_nm.insertWidget(2, self.desde)
        fila_nm.insertWidget(3, QLabel(t("y")))
        fila_nm.insertWidget(4, self.hasta)
        caja.addLayout(fila_nm)
        self.pantalla_completa, fila_pc = opcion("Silenciar si hay algo en pantalla completa (juegos, videos, "
                                                 "presentaciones)",
                                                 lambda v: self.cambiar_grupo("no_molestar", "pantalla_completa", v))
        caja.addLayout(fila_pc)
        self.enfocada, fila_foco = opcion("No avisar si la terminal o el editor de Claude ya tiene el foco",
                                          lambda v: self.cambiar("omitir_si_enfocada", v))
        caja.addLayout(fila_foco)
        caja.addWidget(QLabel(t("Avisar «terminó» solo si la tarea duró más de")))
        self.umbral = QSlider(Qt.Orientation.Horizontal, minimum=0, maximum=300, singleStep=5, pageStep=30)
        self.valor_umbral = valor()
        self.umbral.valueChanged.connect(lambda v: self.cambiar("umbral_segundos", v))
        caja.addLayout(fila(self.umbral, self.valor_umbral))

        caja.addSpacing(10)
        caja.addWidget(seccion("Acciones"))
        self.permisos, fila_permisos = opcion("Aprobar o denegar permisos desde la mascota",
                                              lambda v: self.cambiar("permisos_desde_mascota", v))
        caja.addLayout(fila_permisos)
        self.etiqueta_espera = QLabel(t("Esperar mi respuesta"))
        self.espera = QSlider(Qt.Orientation.Horizontal, minimum=5, maximum=120, singleStep=5, pageStep=15)
        self.valor_espera = valor()
        self.espera.valueChanged.connect(lambda v: self.cambiar("espera_permiso", v))
        caja.addLayout(fila(self.etiqueta_espera, self.espera, self.valor_espera))
        caja.addWidget(ayuda("Si no elegís a tiempo, decide el diálogo de permisos de siempre. Las preguntas "
                             "(AskUserQuestion) se contestan en la terminal."))
        self.enfocar, fila_enfocar = opcion("Botón «Ir a la terminal» en el cartel",
                                            lambda v: self.cambiar("boton_enfocar", v))
        caja.addLayout(fila_enfocar)
        caja.addStretch(1)
        return pagina

    def pestana_estilo(self) -> QWidget:
        pagina = QWidget()
        caja = QVBoxLayout(pagina)
        caja.setContentsMargins(22, 18, 22, 18)
        caja.setSpacing(6)

        caja.addWidget(seccion("Sonido"))
        self.sonido = Interruptor()
        self.sonido.toggled.connect(self.al_cambiar_sonido)
        self.texto_sonido = QLabel()
        fila_sonido = fila(self.sonido, self.texto_sonido, espacio=10)
        fila_sonido.addStretch(1)
        caja.addLayout(fila_sonido)
        self.volumen = QSlider(Qt.Orientation.Horizontal, minimum=0, maximum=100, singleStep=5, pageStep=10)
        self.valor_volumen = valor()
        self.volumen.valueChanged.connect(lambda v: self.cambiar("volumen", v))
        self.volumen.sliderReleased.connect(self.escuchar)
        self.etiqueta_volumen = QLabel(t("Volumen"))
        caja.addLayout(fila(self.etiqueta_volumen, self.volumen, self.valor_volumen))

        caja.addSpacing(10)
        caja.addWidget(seccion("Sonido de cada evento"))
        grilla = QGridLayout()
        grilla.setHorizontalSpacing(10)
        grilla.setVerticalSpacing(6)
        self.sonidos_evento = {}
        nombres = {"ninguno": t("Sin sonido"), **{c: t(n) for c, (n, _) in sprites.SONIDOS.items()}}
        for numero, estado in enumerate(("listo", "permiso", "pensando", "subagente", "limite", "error")):
            combo = QComboBox()
            for clave, nombre in nombres.items():
                combo.addItem(nombre, clave)
            combo.currentIndexChanged.connect(lambda _, e=estado, cb=combo: self.cambiar_sonido(e, cb.currentData()))
            escuchar = BotonEscuchar()
            escuchar.clicked.connect(lambda _=False, e=estado: self.escuchar(e))
            self.sonidos_evento[estado] = combo
            grilla.addWidget(QLabel(t(NOMBRES_ESTADO[estado])), numero, 0)
            grilla.addWidget(combo, numero, 1)
            grilla.addWidget(escuchar, numero, 2)
        grilla.setColumnStretch(1, 1)
        caja.addLayout(grilla)

        caja.addSpacing(10)
        caja.addWidget(seccion("Tema"))
        self.botones_tema, segmentos = segmentado({"oscuro": "Oscuro", "claro": "Claro", "acento": "Acento"},
                                                  self.cambiar_tema, self)
        caja.addLayout(segmentos)
        caja.addWidget(ayuda("El cartel del aviso y esta ventana. Acento pinta el cartel con el color de cada estado."))

        caja.addSpacing(10)
        caja.addWidget(seccion("Ícono en la barra de menús" if m.MAC else "Ícono junto al reloj"))
        self.inicio, fila_inicio = opcion("Abrir al iniciar sesión" if m.MAC else "Abrir al iniciar Windows",
                                          self.cambiar_inicio)
        caja.addLayout(fila_inicio)
        caja.addWidget(ayuda("Click en el ícono de la mascota (en la barra de menús) para volver a estos "
                             "ajustes, silenciar los avisos o cambiar de modo." if m.MAC else
                             "Click en el ícono de la mascota (junto al reloj) para volver a estos ajustes; "
                             "click derecho para silenciar o cambiar de modo."))
        caja.addStretch(1)
        return pagina

    def pestana_mascota(self) -> QWidget:
        pagina = QWidget()
        caja = QVBoxLayout(pagina)
        caja.setContentsMargins(22, 18, 22, 18)
        caja.setSpacing(8)

        titulo_estilo = QHBoxLayout()
        titulo_estilo.setSpacing(6)
        titulo_estilo.addWidget(seccion("Estilo"))
        titulo_estilo.addWidget(QLabel(t("BETA"), objectName="beta"))
        titulo_estilo.addStretch(1)
        caja.addLayout(titulo_estilo)
        self.galeria_estilos = Galeria(QSize(96, 84), ancho=118)
        self.galeria_estilos.elegido.connect(self.cambiar_estilo)
        caja.addWidget(self.galeria_estilos)
        caja.addWidget(ayuda("Cambia la cara de la mascota y cómo aparece, festeja y se va. El vestuario se mantiene."))

        caja.addSpacing(10)
        titulo_color = QHBoxLayout()
        titulo_color.setSpacing(6)
        titulo_color.addWidget(seccion("Color"))
        self.color_de = QLabel(objectName="ayuda")
        titulo_color.addWidget(self.color_de)
        titulo_color.addStretch(1)
        caja.addLayout(titulo_color)
        self.grupo_color = QButtonGroup(self)
        self.muestras = {}
        filas_color = [[]]  # por tono, y los neutros en otra fila
        for color_id in sprites.ORDEN_COLORES:
            if color_id is None:
                filas_color.append([])
            else:
                filas_color[-1].append(color_id)
        for numero, colores in enumerate(filas_color):
            muestras = QHBoxLayout()
            muestras.setSpacing(4)
            for color_id in colores:
                muestra = MuestraColor(color_id)
                muestra.clicked.connect(lambda _, c=color_id: self.cambiar_aspecto("color", c))
                self.grupo_color.addButton(muestra)
                self.muestras[color_id] = muestra
                muestras.addWidget(muestra)
            if numero == len(filas_color) - 1:
                self.nombre_color = QLabel(objectName="valor")
                muestras.addSpacing(10)
                muestras.addWidget(self.nombre_color)
            muestras.addStretch(1)
            caja.addLayout(muestras)
        caja.addWidget(ayuda("Cada estilo guarda su propio color: cambiar este no cambia el de los otros."))

        self.bloque_piel = QWidget()  # solo el Ninja: la cara se le ve por la franja de la máscara
        piel = QVBoxLayout(self.bloque_piel)
        piel.setContentsMargins(0, 10, 0, 0)
        piel.setSpacing(8)
        piel.addWidget(seccion("Piel"))
        fila_piel = QHBoxLayout()
        fila_piel.setSpacing(4)
        self.grupo_piel = QButtonGroup(self)
        self.muestras_piel = {}
        for piel_id in sprites.PIELES:
            muestra = MuestraColor(piel_id, pieles=True)
            muestra.clicked.connect(lambda _, c=piel_id: self.cambiar_aspecto("piel", c))
            self.grupo_piel.addButton(muestra)
            self.muestras_piel[piel_id] = muestra
            fila_piel.addWidget(muestra)
        self.nombre_piel = QLabel(objectName="valor")
        fila_piel.addSpacing(10)
        fila_piel.addWidget(self.nombre_piel)
        fila_piel.addStretch(1)
        piel.addLayout(fila_piel)
        caja.addWidget(self.bloque_piel)

        caja.addSpacing(10)
        caja.addWidget(seccion("Tamaño"))
        self.tamano = QSlider(Qt.Orientation.Horizontal, minimum=m.TAMANOS[0], maximum=m.TAMANOS[1], pageStep=1)
        self.valor_tamano = valor()
        self.valor_tamano.setFixedWidth(120)
        self.tamano.valueChanged.connect(lambda v: self.cambiar("tamano", v))
        caja.addLayout(fila(self.tamano, self.valor_tamano))

        caja.addSpacing(10)
        caja.addWidget(seccion("Imagen propia"))
        self.galeria_imagenes = Galeria(QSize(72, 63), ancho=118)
        self.galeria_imagenes.elegido.connect(self.elegir_imagen)
        caja.addWidget(self.galeria_imagenes)
        botones = QHBoxLayout()
        botones.addWidget(QPushButton(t("Agregar PNG/GIF…"), clicked=self.agregar_imagen))
        self.quitar = QPushButton(t("Quitar"), clicked=self.quitar_imagen)
        botones.addWidget(self.quitar)
        botones.addStretch(1)
        caja.addLayout(botones)
        caja.addWidget(ayuda("Una imagen propia reemplaza a la mascota dibujada en los tres estados (los "
                             "GIF animados también andan). Se guarda una copia en ~/.wavemascot/imagenes."))
        caja.addStretch(1)
        return pagina

    def pestana_vestuario(self) -> QWidget:
        pagina = QWidget()
        caja = QVBoxLayout(pagina)
        caja.setContentsMargins(22, 18, 22, 18)
        caja.setSpacing(6)
        self.galerias = {}
        lados = {"cabeza": QSize(64, 48), "ropa": QSize(72, 50), "accesorio": QSize(64, 36)}
        for parte, titulo in (("cabeza", "Cabeza"), ("ropa", "Ropa"), ("accesorio", "Accesorio")):
            caja.addWidget(seccion(titulo))
            galeria = Galeria(lados[parte])
            galeria.elegido.connect(lambda clave, p=parte: self.cambiar_aspecto(p, clave))
            self.galerias[parte] = galeria
            caja.addWidget(galeria)
        self.aviso_imagen = ayuda("Estás usando una imagen propia: elegí cualquier prenda o color para "
                                  "volver a la mascota dibujada.")
        caja.addWidget(self.aviso_imagen)
        caja.addStretch(1)
        botones = QHBoxLayout()
        botones.addWidget(QPushButton(t("Al azar"), clicked=self.al_azar))
        botones.addWidget(QPushButton(t("Sacar todo"), clicked=self.sacar_todo))
        botones.addStretch(1)
        caja.addLayout(botones)
        return pagina

    def pestana_celular(self) -> QWidget:
        pagina = QWidget()
        caja = QVBoxLayout(pagina)
        caja.setContentsMargins(22, 18, 22, 18)
        caja.setSpacing(6)

        caja.addWidget(seccion("Telegram"))
        caja.addWidget(ayuda("Te manda los avisos a Telegram, con Wave animada: te enterás aunque no estés en la "
                             "compu. Te escribe el bot oficial, @WaveNotificationBot."))
        self.cel_activo, fila_activo = opcion("Mandarme los avisos a Telegram",
                                              lambda v: self.cambiar_grupo("celular", "activo", v))
        caja.addLayout(fila_activo)
        self.cel_estado = QLabel(objectName="valor", wordWrap=True)
        caja.addWidget(self.cel_estado)

        self.cel_desconectado = QWidget()
        boton = fila(QPushButton(t("Conectar con Telegram"), objectName="primario", clicked=self.conectar_telegram))
        boton.setContentsMargins(0, 4, 0, 0)
        boton.addStretch(1)
        self.cel_conectar = boton.itemAt(0).widget()
        self.cel_desconectado.setLayout(boton)
        caja.addWidget(self.cel_desconectado)

        # Mientras espera: el código, el botón que abre el bot y cómo seguir.
        self.cel_esperando = QWidget()
        espera = QVBoxLayout(self.cel_esperando)
        espera.setContentsMargins(0, 4, 0, 0)
        espera.setSpacing(6)
        espera.addWidget(QLabel(t("Tu código:")))
        self.cel_codigo = QLabel(objectName="codigo")
        self.cel_codigo.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        espera.addWidget(self.cel_codigo)
        botones = fila(QPushButton(t("Abrir @WaveNotificationBot"), objectName="primario",
                                   clicked=lambda: self.abrir_enlace(celular.enlace_bot(self.codigo))),
                       QPushButton(t("Copiar código"), clicked=lambda: QApplication.clipboard().setText(self.codigo)),
                       QPushButton(t("Cancelar"), clicked=self.cancelar_codigo), espacio=8)
        botones.addStretch(1)
        espera.addLayout(botones)
        espera.addWidget(ayuda("Se abre Telegram con el código listo: tocá «Iniciar» y listo. También podés "
                               "escribirle el código al bot. Vence en 15 minutos."))
        caja.addWidget(self.cel_esperando)

        self.cel_conectado = QWidget()
        conectado = fila(QPushButton(t("Mandar un aviso de prueba"), clicked=self.probar_telegram),
                         QPushButton(t("Desconectar"), clicked=self.desconectar_telegram), espacio=8)
        conectado.setContentsMargins(0, 4, 0, 0)
        conectado.addStretch(1)
        self.cel_conectado.setLayout(conectado)
        caja.addWidget(self.cel_conectado)

        caja.addSpacing(10)
        caja.addWidget(seccion("Cuándo"))
        self.cel_ausente, fila_ausente = opcion("Solo si no estoy usando la compu",
                                                lambda v: self.cambiar_grupo("celular", "solo_ausente", v))
        caja.addLayout(fila_ausente)
        self.cel_etiqueta_minutos = QLabel(t("Sin tocar el mouse ni el teclado por"))
        self.cel_minutos = QSlider(Qt.Orientation.Horizontal, minimum=1, maximum=30, pageStep=5)
        self.cel_valor_minutos = valor()
        self.cel_minutos.valueChanged.connect(lambda v: self.cambiar_grupo("celular", "minutos", v))
        caja.addLayout(fila(self.cel_etiqueta_minutos, self.cel_minutos, self.cel_valor_minutos))
        caja.addWidget(ayuda("Si estás en la compu te avisa solo la mascota, así no te llega todo dos veces. "
                             "El silencio y el «no molestar» también valen para Telegram."))

        caja.addSpacing(10)
        caja.addWidget(seccion("Qué avisos"))
        self.cel_estados = {}
        for estado, texto in NOMBRES_CELULAR.items():
            interruptor, fila_estado = opcion(texto, lambda v, e=estado: self.cambiar_estado_celular(e, v))
            self.cel_estados[estado] = interruptor
            caja.addLayout(fila_estado)
        self.cel_gif, fila_gif = opcion("Con Wave animada (GIF)", lambda v: self.cambiar_grupo("celular", "gif", v))
        caja.addLayout(fila_gif)
        caja.addSpacing(6)
        caja.addWidget(ayuda("Los avisos pasan por el servidor de WaveMascot para llegar a Telegram; no se guardan. "
                             "Para dejar de recibirlos: Desconectar, o mandale /stop al bot."))
        caja.addStretch(1)
        return pagina

    def panel_vista(self) -> QVBoxLayout:
        columna = QVBoxLayout()
        columna.setSpacing(10)
        columna.addWidget(seccion("Vista previa"))
        self.vista = VistaPrevia()
        columna.addWidget(self.vista, 1)
        self.grupo_estado = QButtonGroup(self)
        for fila_estados in (("listo", "permiso", "pensando"), ("subagente", "limite", "error")):
            segmentos = QHBoxLayout()
            segmentos.setSpacing(0)
            for i, estado in enumerate(fila_estados):
                boton = QPushButton(t(NOMBRES_ESTADO[estado]), objectName="segmento", checkable=True)
                boton.setProperty("pos", "ini" if i == 0 else "fin" if i == len(fila_estados) - 1 else "medio")
                boton.setChecked(estado == self.estado_vista)
                boton.clicked.connect(lambda _, e=estado: self.ver_estado(e))
                self.grupo_estado.addButton(boton)
                segmentos.addWidget(boton)
            columna.addLayout(segmentos)
        columna.setSpacing(6)
        return columna

    def pie(self) -> QHBoxLayout:
        caja = QHBoxLayout()
        self.estado_guardado = QLabel(objectName="estado")
        caja.addWidget(self.estado_guardado, 1)
        caja.addWidget(QPushButton(t("Restablecer valores"), clicked=self.restablecer))
        caja.addWidget(QPushButton(t("Cerrar"), clicked=self.close))
        return caja

    # datos <-> controles

    def cargar_en_controles(self) -> None:
        c = self.config
        grupos = {"contenido": self.contenido, "eventos": self.eventos, "vida": self.vida}
        controles = [self.duracion, self.sonido, self.volumen, self.tamano, self.inicio, self.no_molestar,
                     self.desde, self.hasta, self.pantalla_completa, self.enfocada, self.umbral, self.permisos,
                     self.espera, self.enfocar, *self.textos.values(), *self.sonidos_evento.values(),
                     self.cel_activo, self.cel_ausente, self.cel_minutos, self.cel_gif,
                     *self.cel_estados.values(),
                     *(w for g in grupos.values() for w in g.values())]
        for control in controles:
            control.blockSignals(True)
        self.selector.esquina = c["esquina"]
        self.selector.update()
        self.duracion.setValue(round(c["duracion"]))
        self.sonido.setChecked(c["sonido"])
        self.volumen.setValue(c["volumen"])
        self.tamano.setValue(c["tamano"])
        self.inicio.setChecked(bandeja.inicio_automatico())
        for evento, campo in self.textos.items():
            campo.setText(c["mensajes"][evento])
        for grupo, controles_grupo in grupos.items():
            for clave, interruptor in controles_grupo.items():
                interruptor.setChecked(c[grupo][clave])
        nm = c["no_molestar"]
        self.no_molestar.setChecked(nm["activo"])
        self.desde.setTime(QTime.fromString(nm["desde"], "HH:mm"))
        self.hasta.setTime(QTime.fromString(nm["hasta"], "HH:mm"))
        self.pantalla_completa.setChecked(nm["pantalla_completa"])
        self.enfocada.setChecked(c["omitir_si_enfocada"])
        self.umbral.setValue(c["umbral_segundos"])
        self.permisos.setChecked(c["permisos_desde_mascota"])
        self.espera.setValue(c["espera_permiso"])
        self.enfocar.setChecked(c["boton_enfocar"])
        for estado, combo in self.sonidos_evento.items():
            combo.setCurrentIndex(max(0, combo.findData(c["sonidos"][estado])))
        self.botones_modo[c["modo"]].setChecked(True)
        self.botones_tema[c["tema"]].setChecked(True)
        cel = c["celular"]
        self.cel_activo.setChecked(cel["activo"])
        self.cel_ausente.setChecked(cel["solo_ausente"])
        self.cel_minutos.setValue(cel["minutos"])
        self.cel_gif.setChecked(cel["gif"])
        for estado, interruptor in self.cel_estados.items():
            interruptor.setChecked(cel["estados"][estado])
        for control in controles:
            control.blockSignals(False)
        self.cargar_galerias()
        self.actualizar_etiquetas()
        self.refrescar_vista()

    def cargar_galerias(self) -> None:
        """Miniaturas del vestuario con el aspecto actual (cada una prueba una opción)."""
        dpr = self.devicePixelRatioF()
        aspecto = self.config["aspecto"]
        usando_imagen = bool(self.config["imagen"])
        for parte, galeria in self.galerias.items():
            opciones = [(clave, t(nombre), miniatura({**aspecto, parte: clave}, parte, dpr))
                        for clave, nombre in sprites.OPCIONES[parte].items()]
            galeria.cargar(opciones, None if usando_imagen else aspecto[parte])
        imagenes = [("", t("Mascota dibujada"), miniatura(aspecto, "entera", dpr, escala=1.5))]
        imagenes += [(ruta.name, ruta.stem, miniatura_imagen(ruta, QSize(72, 63), dpr)) for ruta in m.listar_imagenes()]
        self.galeria_imagenes.cargar(imagenes, self.config["imagen"])
        self.quitar.setEnabled(usando_imagen)
        self.aviso_imagen.setVisible(usando_imagen)
        estilos = [(e, t(nombre), miniatura(sprites.con_estilo(aspecto, e), "entera", dpr))
                   for e, nombre in sprites.ESTILOS.items()]
        self.galeria_estilos.cargar(estilos, None if usando_imagen else aspecto["estilo"])
        for grupo, muestras, elegido in ((self.grupo_color, self.muestras, aspecto["color"]),
                                         (self.grupo_piel, self.muestras_piel, aspecto["piel"])):
            grupo.setExclusive(False)  # un grupo exclusivo no deja des-elegir a todos
            for clave, muestra in muestras.items():
                muestra.setChecked(clave == elegido and not usando_imagen)
            grupo.setExclusive(True)
        self.bloque_piel.setVisible(aspecto["estilo"] == "ninja")
        icono = (miniatura_imagen(m.IMAGENES / self.config["imagen"], QSize(48, 42), dpr) if usando_imagen
                 else miniatura(aspecto, "entera", dpr, escala=1))
        self.icono_cabecera.setPixmap(icono)

    def actualizar_etiquetas(self) -> None:
        c = self.config
        self.nombre_esquina.setText(t(NOMBRES_ESQUINA[c["esquina"]]))
        self.valor_duracion.setText(f"{round(c['duracion'])} s")
        self.texto_sonido.setText(t("Activado") if c["sonido"] else t("Desactivado"))
        self.valor_volumen.setText(f"{c['volumen']} %")
        for control in (self.volumen, self.valor_volumen, self.etiqueta_volumen):
            control.setEnabled(c["sonido"])
        self.valor_tamano.setText(f"{t(NOMBRES_TAMANO.get(c['tamano'], ''))} · {m.LADO_ARTE * c['tamano']} px")
        self.nombre_color.setText("" if c["imagen"] else t(sprites.COLORES[c["aspecto"]["color"]][0]))
        self.color_de.setText("· " + t("de {estilo}", estilo=t(sprites.ESTILOS[c["aspecto"]["estilo"]])))
        self.nombre_piel.setText(t(sprites.PIELES[c["aspecto"]["piel"]][0]))
        self.probar.setText(t("Probar aviso «{estado}»", estado=t(NOMBRES_ESTADO[self.estado_vista])))
        self.valor_umbral.setText(t("Siempre") if not c["umbral_segundos"] else m.formato_duracion(c["umbral_segundos"]))
        self.valor_espera.setText(f"{c['espera_permiso']} s")
        for control in (self.espera, self.valor_espera, self.etiqueta_espera):
            control.setEnabled(c["permisos_desde_mascota"])
        for control in (self.desde, self.hasta):
            control.setEnabled(c["no_molestar"]["activo"])
        for interruptor in self.vida.values():
            interruptor.setEnabled(c["modo"] == "compania")
        for combo in self.sonidos_evento.values():
            combo.setEnabled(c["sonido"])
        self.actualizar_celular()

    def actualizar_celular(self) -> None:
        cel = self.config["celular"]
        conectado = bool(cel["llave"] and cel["conectado"])
        self.cel_desconectado.setVisible(not conectado and not self.codigo)
        self.cel_esperando.setVisible(not conectado and bool(self.codigo))
        self.cel_conectado.setVisible(conectado)
        self.cel_activo.setEnabled(conectado)
        self.cel_codigo.setText(celular.codigo_visible(self.codigo))
        if conectado:
            self.cel_estado.setText(t("✓ Conectado al Telegram de {nombre}", nombre=cel["nombre"]) if cel["nombre"]
                                    else t("✓ Conectado a Telegram"))
        elif not self.codigo and self.cel_conectar.isEnabled():
            self.cel_estado.setText(t("Sin conectar: tocá el botón, se abre Telegram y tocás «Iniciar»."))
        self.cel_valor_minutos.setText(f"{cel['minutos']} min")
        for control in (self.cel_minutos, self.cel_valor_minutos, self.cel_etiqueta_minutos):
            control.setEnabled(cel["solo_ausente"])

    def mensaje_de_ejemplo(self) -> str:
        automatico = t(AUTOMATICO[self.estado_vista])
        plantilla = self.config["mensajes"].get(m.EVENTO_POR_ESTADO.get(self.estado_vista), "")
        if not plantilla.strip():
            return automatico
        ejemplo = {clave: t(texto) for clave, texto in EJEMPLO.items()}
        return m.aplicar_plantilla(plantilla, {"mensaje": automatico, **ejemplo}) or automatico

    def refrescar_vista(self) -> None:
        c, estado = self.config, self.estado_vista
        datos = ["2 min 05 s" if c["contenido"]["duracion"] and estado == "listo" else "",
                 t(EJEMPLO["proyecto"]) if c["contenido"]["proyecto"] else "",
                 t(EJEMPLO["chat"]) if c["contenido"]["chat"] else ""]
        botones = ["permitir", "denegar"] if estado == "permiso" and c["permisos_desde_mascota"] else []
        if c["boton_enfocar"]:
            botones.append("enfocar")
        self.vista.mostrar(c, estado, self.mensaje_de_ejemplo()[:120],
                           t(RESUMEN_EJEMPLO[estado]) if c["contenido"]["resumen"] else "",
                           " · ".join(d for d in datos if d), botones)

    # cambios

    def cambiar(self, clave: str, nuevo) -> None:
        self.config[clave] = nuevo
        self.cambio()

    def cambiar_mensaje(self, evento: str, texto: str) -> None:
        self.config["mensajes"][evento] = texto
        self.cambio()

    def cambiar_grupo(self, grupo: str, clave: str, nuevo) -> None:
        self.config[grupo][clave] = nuevo
        self.cambio()

    def cambiar_estado_celular(self, estado: str, activo: bool) -> None:
        self.config["celular"]["estados"][estado] = activo
        self.cambio()

    def cambiar_sonido(self, estado: str, sonido: str) -> None:
        self.config["sonidos"][estado] = sonido
        self.cambio()
        self.escuchar(estado)

    def cambiar_tema(self, tema: str) -> None:
        aplicar_tema(tema, self.config["aspecto"]["estilo"])
        self.cambiar("tema", tema)

    def cambiar_modo(self, modo: str) -> None:
        self.cambiar("modo", modo)
        self.guardar()  # la compañera y el ícono leen config.json
        if modo == "compania":  # si ya está abierta, la nueva se cierra sola
            m.lanzar_desacoplado([str(m.DIR / "mascota.py"), "--compania"])

    def cambiar_aspecto(self, parte: str, opcion: str) -> None:
        """Elegir un color o una prenda vuelve a la mascota dibujada si había una imagen propia.
        El color queda guardado para el estilo elegido (normalizar lo copia a "colores")."""
        self.config["aspecto"][parte] = opcion
        self.config["aspecto"] = sprites.normalizar(self.config["aspecto"])
        self.config["imagen"] = ""
        self.cargar_galerias()
        self.cambio()

    def cambiar_estilo(self, estilo: str) -> None:
        """Otro estilo: su cara, sus animaciones y su color guardado; la ventana toma sus colores."""
        self.config["aspecto"] = sprites.con_estilo(self.config["aspecto"], estilo)
        self.config["imagen"] = ""
        aplicar_tema(self.config["tema"], estilo)
        self.cargar_galerias()
        self.cambio()

    def cambio(self) -> None:
        self.actualizar_etiquetas()
        self.refrescar_vista()
        self.estado_guardado.setText(t("Guardando…"))
        self.timer_guardar.start()

    def al_cambiar_sonido(self, activo: bool) -> None:
        self.cambiar("sonido", activo)
        if activo:
            self.escuchar()

    def escuchar(self, estado: str | None = None) -> None:
        if self.config["sonido"]:
            self.sonidos.tocar(self.config["sonidos"][estado or self.estado_vista], self.config["volumen"])

    def ver_estado(self, estado: str) -> None:
        self.estado_vista = estado
        self.actualizar_etiquetas()
        self.refrescar_vista()

    def al_azar(self) -> None:
        for parte, opciones in sprites.OPCIONES.items():
            self.config["aspecto"][parte] = random.choice(list(opciones))
        self.config["aspecto"] = sprites.normalizar(self.config["aspecto"])  # el color, solo para este estilo
        self.config["imagen"] = ""
        self.cargar_galerias()
        self.cambio()

    def sacar_todo(self) -> None:
        a = self.config["aspecto"]
        self.config["aspecto"] = sprites.normalizar({**sprites.ASPECTO_DEFECTO, **{
            clave: a[clave] for clave in ("color", "colores", "estilo", "piel")}})
        self.config["imagen"] = ""
        self.cargar_galerias()
        self.cambio()

    def elegir_imagen(self, nombre: str) -> None:
        self.config["imagen"] = nombre
        self.cargar_galerias()
        self.cambio()

    def agregar_imagen(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(self, t("Elegí una imagen para la mascota"), str(Path.home()),
                                              t("Imágenes") + " (*.png *.gif)")
        if not ruta:
            return
        origen = Path(ruta)
        if origen.stat().st_size > 20_000_000 or not QImageReader(str(origen)).canRead():
            QMessageBox.warning(self, t("Imagen no válida"),
                                t("No pude leer esa imagen. Probá con un PNG o GIF de menos de 20 MB."))
            return
        m.IMAGENES.mkdir(parents=True, exist_ok=True)
        base = re.sub(r"[^\w\- ]", "", origen.stem).strip()[:40] or "propia"
        destino, n = m.IMAGENES / f"{base}{origen.suffix.lower()}", 2
        while destino.exists():
            destino, n = m.IMAGENES / f"{base}-{n}{origen.suffix.lower()}", n + 1
        shutil.copyfile(origen, destino)
        self.elegir_imagen(destino.name)

    def quitar_imagen(self) -> None:
        nombre = self.config["imagen"]
        if not nombre:
            return
        respuesta = QMessageBox.question(self, t("Quitar imagen"),
                                         t("¿Quitar «{nombre}»? Tu archivo original no se toca.",
                                           nombre=Path(nombre).stem))
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        (m.IMAGENES / nombre).unlink(missing_ok=True)  # es la copia guardada en ~/.wavemascot/imagenes
        self.elegir_imagen("")

    def cambiar_inicio(self, activar: bool) -> None:
        self.setCursor(Qt.CursorShape.WaitCursor)
        try:
            bandeja.activar_inicio_automatico(activar)
            if activar:
                bandeja.lanzar()
        except (OSError, subprocess.SubprocessError) as e:
            m.log(f"[ajustes] no se pudo cambiar el inicio automático: {e}")
            self.estado_guardado.setText(t("No se pudo crear el acceso directo de inicio"))
        finally:
            self.unsetCursor()
            self.inicio.blockSignals(True)
            self.inicio.setChecked(bandeja.inicio_automatico())
            self.inicio.blockSignals(False)

    def restablecer(self) -> None:
        if QMessageBox.question(self, t("Restablecer"), t("¿Volver a los valores por defecto? "
                                "Las imágenes propias quedan guardadas.")) != QMessageBox.StandardButton.Yes:
            return
        idioma, cel = self.config["idioma"], self.config["celular"]
        self.config = json.loads(json.dumps(m.CONFIG_DEFECTO))  # copia profunda
        self.config["idioma"] = idioma  # el idioma elegido se queda
        self.config["aspecto"] = sprites.normalizar(self.config["aspecto"])
        for clave in ("llave", "conectado", "nombre"):  # y Telegram sigue conectado
            self.config["celular"][clave] = cel[clave]
        aplicar_tema(self.config["tema"], self.config["aspecto"]["estilo"])
        self.cargar_en_controles()
        self.cambio()

    def sincronizar(self) -> None:
        """El modo también se cambia desde el ícono o el menú de la compañera: se refleja acá."""
        disco = m.cargar_config()
        if disco["modo"] != self.config["modo"] and not self.timer_guardar.isActive():
            self.config["modo"] = disco["modo"]
            self.botones_modo[disco["modo"]].setChecked(True)
            self.actualizar_etiquetas()

    def guardar(self) -> None:
        self.timer_guardar.stop()
        try:
            # El silencio (ícono del reloj) y la posición (arrastrar la compañera) se manejan
            # en otro lado: se respeta lo que esté guardado.
            disco = m.cargar_config()
            self.config["silenciado_hasta"], self.config["posicion"] = disco["silenciado_hasta"], disco["posicion"]
            m.guardar_config(self.config)
        except OSError as e:
            self.estado_guardado.setText(t("No se pudo guardar: {error}", error=e))
            m.log(f"[ajustes] no se pudo guardar: {e}")
            return
        self.estado_guardado.setText(t("✓ Guardado en {archivo}", archivo=f"{m.CONFIG.parent.name}/{m.CONFIG.name}"))

    def probar_aviso(self) -> None:
        self.guardar()  # el aviso de prueba lee config.json, igual que uno real
        m.lanzar_desacoplado([str(m.DIR / "mascota.py"), f"--estado={self.estado_vista}", "--forzar",
                              "--detalle=" + t("Prueba desde ajustes")])

    # Telegram

    def abrir_enlace(self, url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))

    def en_segundo_plano(self, pedido: str, funcion) -> None:
        """Las llamadas al servidor van en otro hilo, así la ventana no se congela esperando la red.
        Al terminar llega respuesta_telegram(pedido, resultado) o (pedido + "_error", ErrorCelular)."""
        def correr():
            try:
                resultado, tipo = funcion(), pedido
            except celular.ErrorCelular as e:
                resultado, tipo = e, pedido + "_error"
            except Exception as e:  # nunca un error suelto en un hilo
                m.log(f"[ajustes] Telegram: {e!r}")
                resultado, tipo = celular.ErrorCelular(str(e)), pedido + "_error"
            try:
                self.respuesta_telegram.emit(tipo, resultado)
            except RuntimeError:
                pass  # la ventana ya se cerró
        threading.Thread(target=correr, daemon=True).start()

    def conectar_telegram(self) -> None:
        """Pide un código (y, la primera vez, registra esta instalación en el servidor)."""
        self.cel_conectar.setEnabled(False)
        self.cel_estado.setText(t("Preparando tu código…"))
        llave = self.config["celular"]["llave"]
        if llave:
            self.en_segundo_plano("codigo", lambda: celular.nuevo_codigo(llave))
        else:
            self.en_segundo_plano("registro", celular.registrar)

    def cancelar_codigo(self) -> None:
        self.timer_estado.stop()
        self.codigo = ""
        self.actualizar_celular()

    def consultar_estado(self) -> None:
        if time.time() > self.fin_codigo:
            self.cancelar_codigo()
            self.cel_estado.setText(t("El código venció. Tocá «Conectar con Telegram» para sacar otro."))
            return
        if not self.consultando:
            self.consultando = True
            llave = self.config["celular"]["llave"]
            self.en_segundo_plano("estado", lambda: celular.estado(llave))

    def marcar_conexion(self, conectado: bool, nombre: str = "") -> None:
        cel = self.config["celular"]
        cel.update(conectado=conectado, nombre=nombre if conectado else "")
        if conectado:
            cel["activo"] = True
        self.cargar_en_controles()
        self.guardar()

    def al_responder_telegram(self, tipo: str, resultado) -> None:
        if tipo in ("registro", "codigo"):
            if tipo == "registro":  # la llave se guarda enseguida: identifica a esta compu en el servidor
                self.config["celular"].update(llave=resultado["llave"], conectado=False, nombre="")
                self.guardar()
            self.codigo = resultado["codigo"]
            self.fin_codigo = time.time() + 15 * 60
            self.cel_conectar.setEnabled(True)
            self.actualizar_celular()
            self.cel_estado.setText(t("Esperando que le mandes el código al bot…"))
            self.timer_estado.start()
            self.abrir_enlace(celular.enlace_bot(self.codigo))
        elif tipo == "codigo_error" and resultado.estado == 401:
            self.config["celular"]["llave"] = ""  # el servidor ya no conoce esta compu: se registra de nuevo
            self.en_segundo_plano("registro", celular.registrar)
        elif tipo in ("registro_error", "codigo_error"):
            self.cel_conectar.setEnabled(True)
            self.cel_estado.setText(t("No pude conectarme con el servidor de WaveMascot ({error}). Probá de nuevo "
                                      "en un rato.", error=resultado))
        elif tipo == "estado":
            self.consultando = False
            if resultado.get("conectado") and self.timer_estado.isActive():
                self.timer_estado.stop()
                self.codigo = ""
                self.marcar_conexion(True, resultado.get("nombre") or "")
        elif tipo == "estado_error":
            self.consultando = False  # se reintenta en la próxima vuelta del timer
        elif tipo == "inicial" and not resultado.get("conectado"):
            self.marcar_conexion(False)
            self.cel_estado.setText(t("Telegram se desconectó (¿le mandaste /stop al bot?). Conectalo de nuevo "
                                      "cuando quieras."))
        elif tipo == "inicial_error" and resultado.estado == 401:
            self.config["celular"]["llave"] = ""
            self.marcar_conexion(False)
        elif tipo == "prueba":
            self.cel_estado.setText(t("✓ Mensaje enviado: mirá tu Telegram."))
        elif tipo == "prueba_error":
            if resultado.datos.get("conectado") is False:
                self.marcar_conexion(False)
            self.cel_estado.setText(t("No se pudo mandar ({error}).", error=resultado))

    def probar_telegram(self) -> None:
        self.guardar()
        c, estado = self.config, self.estado_vista
        aviso = {"estado": estado, "mensaje": self.mensaje_de_ejemplo(), "resumen": t(RESUMEN_EJEMPLO[estado]),
                 "meta": t("Prueba desde ajustes"), "aspecto": c["aspecto"], "imagen": c["imagen"],
                 "gif": c["celular"]["gif"]}
        llave = c["celular"]["llave"]
        self.cel_estado.setText(t("Mandando…"))
        self.en_segundo_plano("prueba", lambda: celular.enviar(llave, aviso))

    def desconectar_telegram(self) -> None:
        if QMessageBox.question(self, t("Desconectar"), t("¿Dejar de mandar avisos a Telegram? Podés volver a "
                                "conectarlo cuando quieras.")) != QMessageBox.StandardButton.Yes:
            return
        llave = self.config["celular"]["llave"]
        self.en_segundo_plano("desconectar", lambda: celular.desconectar(llave))
        self.config["celular"].update(llave="", conectado=False, nombre="", activo=False)
        self.cargar_en_controles()
        self.cambio()

    def cambiar_idioma(self, idioma: str) -> None:
        """Guarda el idioma y pide rearmar la ventana con los textos nuevos."""
        if idioma == self.config["idioma"]:
            return
        self.config["idioma"] = idioma
        self.guardar()  # el ícono, la mascota y el próximo aviso lo leen de config.json
        self.idioma_cambiado.emit(idioma)

    def closeEvent(self, evento) -> None:
        if self.timer_guardar.isActive():
            self.guardar()
        super().closeEvent(evento)


def identidad_en_barra() -> None:
    """Sin esto Windows agrupa la ventana con pythonw.exe y la barra de tareas muestra el ícono de Python.
    (En macOS la ventana aparece en el Dock con el ícono de la mascota: ver ejecutar_ventana.)"""
    if os.name == "nt":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("WaveMascot.Ajustes")
        except (AttributeError, OSError):
            pass


def ejecutar_ventana() -> int:
    # Un error se registra en el log; no cierra la ventana (PyQt6 aborta ante errores no atrapados).
    sys.excepthook = lambda tipo, valor, tb: m.log("[ajustes] error:\n" + "".join(
        traceback.format_exception(tipo, valor, tb)))
    identidad_en_barra()  # antes de crear cualquier ventana
    app = QApplication(sys.argv[:1])
    app.setWindowIcon(bandeja.icono_mascota("terracota", grande=m.MAC))  # también para los diálogos (y el Dock)
    ventanas.app_con_ventana()  # macOS: la app empaquetada arranca sin Dock (LSUIElement); los ajustes lo usan
    app.setStyle("Fusion")
    config = m.cargar_config()
    aplicar_tema(config["tema"], config["aspecto"]["estilo"])
    traducir_qt(app, config["idioma"])

    # Una sola ventana de ajustes: si ya hay una abierta, se la trae al frente.
    s = QLocalSocket()
    s.connectToServer(CANAL_AJUSTES)
    if s.waitForConnected(300):
        s.write(b"mostrar\n")
        s.flush()
        s.waitForBytesWritten(300)
        return 0
    servidor = QLocalServer()
    m.escuchar(servidor, CANAL_AJUSTES)

    actual = {}

    def abrir(anterior: Ajustes | None = None) -> None:
        """Arma la ventana; al cambiar de idioma se rearma en el mismo lugar y en la misma pestaña."""
        ventana = Ajustes()
        ventana.idioma_cambiado.connect(lambda idioma: (traducir_qt(app, idioma), abrir(ventana)))
        if anterior is None:
            ventana.resize(940, 760)
        else:
            ventana.setGeometry(anterior.geometry())
            ventana.pestanas.setCurrentIndex(anterior.pestanas.currentIndex())
        actual["ventana"] = ventana
        traer_al_frente(ventana)
        if anterior is not None:  # recién ahora: si se cerrara antes, la app terminaría
            anterior.close()
            anterior.deleteLater()

    servidor.newConnection.connect(lambda: (servidor.nextPendingConnection(), traer_al_frente(actual["ventana"])))
    ventanas.al_reabrir(lambda: traer_al_frente(actual["ventana"]))  # macOS: click en el Dock o abrir la app
    abrir()
    m.log("[ajustes] ventana abierta")
    return app.exec()


if __name__ == "__main__":
    try:
        codigo = ejecutar_ventana()
    except Exception:
        m.log("[ajustes] error:\n" + traceback.format_exc())
        codigo = 1
    os._exit(codigo)
