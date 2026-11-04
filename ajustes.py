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
import actualizacion  # noqa: E402
import celular  # noqa: E402
import idiomas  # noqa: E402
import sprites  # noqa: E402
import ventanas  # noqa: E402
from idiomas import t  # noqa: E402

if __name__ == "__main__" and "--ventana" not in sys.argv[1:]:
    # Lanzador: abre la ventana desacoplada y sale sin cargar Qt.
    m.lanzar_desacoplado([str(Path(__file__).resolve()), "--ventana", *sys.argv[1:]])
    os._exit(0)

import html  # noqa: E402

from PyQt6.QtCore import (QEasingCurve, QElapsedTimer, QEvent, QLibraryInfo, QObject, QPoint, QPointF, QRectF, QSize,  # noqa: E402
                          Qt, QTimer, QTranslator, QUrl, pyqtSignal)
from PyQt6.QtGui import (QColor, QDesktopServices, QFont, QFontMetrics, QIcon, QImageReader,  # noqa: E402
                         QKeySequence, QLinearGradient, QPainter, QPainterPath, QPalette, QPen, QPixmap,
                         QRadialGradient, QShortcut)
from PyQt6.QtNetwork import QLocalServer, QLocalSocket  # noqa: E402
from PyQt6.QtCore import QFileSystemWatcher, QTime  # noqa: E402
from PyQt6.QtWidgets import (QAbstractButton, QAbstractSpinBox, QApplication, QButtonGroup, QCheckBox, QComboBox,  # noqa: E402
                             QFileDialog, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QLineEdit,
                             QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea, QSizePolicy,
                             QSlider, QTimeEdit, QToolTip, QVBoxLayout, QWidget)

import bandeja  # noqa: E402
import marco  # noqa: E402
from animacion import Resorte, Velo, mezcla, reducir_movimiento  # noqa: E402

CANAL_AJUSTES = m.CANAL + "-ajustes"
NOMBRES_ESTADO = {"listo": "Listo", "permiso": "Permiso", "pensando": "Pensando", "subagente": "Subagente",
                  "limite": "Límite", "error": "Error"}
ESTADOS_ORDEN = ("listo", "permiso", "pensando", "subagente", "limite", "error")
ESTADOS_CELULAR = ("listo", "permiso", "subagente", "limite", "error")  # "pensando" no llega al celular
# Las secciones de la barra lateral: (clave, nombre, ícono). La última va abajo de todo.
PAGINAS = {"avisos": ("Avisos", "campana"), "mascota": ("Mascota", "cara"), "celular": ("Celular", "celular"),
           "general": ("General", "engranaje")}
PARTES = {"estilo": "Estilo", "color": "Color", "cabeza": "Cabeza", "ropa": "Ropa", "accesorio": "Accesorio",
          "imagen": "Imagen"}
ANCHO_VISTA = 310  # la columna de la vista previa, con su margen
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
marco.usar_colores(C)  # los botones de la ventana (Windows)
ESTILO = """
QWidget { color: %(texto)s; font-family: "Segoe UI"; font-size: 10pt; }
QWidget#raiz { background: %(fondo)s; }
QLabel#marca { font-size: 11pt; font-weight: 700; }
QLabel#ayuda, QLabel#estado, QLabel#valor, QLabel#detalle, QLabel#columna { color: %(suave)s; }
QLabel#ayuda { font-size: 9pt; }
QLabel#detalle { font-size: 8.5pt; }
QLabel:disabled { color: %(apagado)s; }
QLabel#columna { font-size: 8pt; font-weight: 600; }
QLabel#columna:disabled { color: %(apagado)s; }
QLabel#seccion { color: %(suave)s; font-size: 9pt; font-weight: 600; padding: 0 0 2px 4px; }
QPushButton#enlace { background: transparent; border: none; color: %(acento)s; padding: 2px 0; font-weight: 600; }
QPushButton#enlace:hover { color: %(acento2)s; }
QLabel#beta { background: %(acento)s; color: %(sobre)s; font-size: 7pt; font-weight: 700; border-radius: 4px;
              padding: 0 5px; }
QLabel#pronto { background: %(campo)s; color: %(suave)s; border: 1px solid %(borde)s; font-size: 8pt;
                font-weight: 600; border-radius: 6px; padding: 3px 8px; }
QLabel#codigo { color: %(acento)s; font-size: 22pt; font-weight: 700; }
QFrame#franja { background: %(panel)s; border: 1px solid %(acento)s; border-radius: 12px; }
QLabel#franja_titulo { font-size: 11pt; font-weight: 600; }
QPushButton { background: %(campo)s; border: 1px solid %(borde)s; border-radius: 8px; padding: 7px 14px; }
QPushButton:hover { border-color: %(acento)s; }
QPushButton:pressed { background: %(borde)s; }
QPushButton:disabled { color: #6E605A; border-color: %(borde)s; }
QPushButton#primario { background: %(acento)s; border-color: %(acento)s; color: %(sobre)s; font-weight: 600; }
QPushButton#primario:hover { background: %(acento2)s; border-color: %(acento2)s; }
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
QMenu { background: %(campo)s; border: 1px solid %(borde)s; padding: 4px; }
QMenu::item { padding: 6px 18px 6px 10px; border-radius: 6px; }
QMenu::item:selected { background: %(acento)s; color: %(sobre)s; }
QMenu::icon { padding-left: 6px; }
"""  # se completa con C (ver aplicar_tema)
if m.MAC:
    # La letra del sistema y los mismos píxeles que en Windows (macOS cuenta 72 puntos por pulgada, no 96).
    ESTILO = re.sub(r"(\d+(?:\.\d+)?)pt\b", lambda x: f"{round(float(x.group(1)) * 96 / 72)}px",
                    ESTILO.replace('font-family: "Segoe UI"; ', ""))


def aplicar_tema(tema: str, estilo: str = "clasico") -> None:
    """Tema de la ventana: el claro usa colores claros; oscuro y acento, los oscuros. Cada estilo de
    mascota tiene su propia versión de esos colores."""
    oscuro, claro = PALETAS.get(estilo, PALETAS["clasico"])
    C.clear()
    C.update(claro if tema == "claro" else oscuro)
    C["apagado"] = mezcla(C["suave"], C["fondo"], 0.45).name()  # textos de opciones desactivadas
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
    """El título chiquito de un grupo de ajustes, como en macOS: en minúsculas y apagado."""
    etiqueta = QLabel(t(texto))
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


def opcion(texto: str, al_cambiar, info: str = "") -> tuple["Interruptor", "Fila"]:
    """Una fila con su texto a la izquierda y el interruptor a la derecha."""
    interruptor = Interruptor()
    interruptor.toggled.connect(al_cambiar)
    return interruptor, Fila(texto, interruptor, info=info)


def segmentado(opciones: dict[str, str], al_elegir, suave: bool = False) -> "Segmentos":
    """Opciones pegadas de las que se elige una; la marca se desliza hasta la elegida."""
    control = Segmentos({clave: t(texto) for clave, texto in opciones.items()}, suave=suave)
    control.elegido.connect(al_elegir)
    return control


def fuente(px: float, peso: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """La letra de la ventana a un tamaño en píxeles (igual en Windows y en macOS)."""
    letra = QFont(QApplication.font())
    if not m.MAC:
        letra.setFamily("Segoe UI")
    letra.setPixelSize(round(px))
    letra.setWeight(peso)
    return letra


def lapiz(color, ancho: float = 1.6) -> QPen:
    pluma = QPen(QColor(color), ancho)
    pluma.setCapStyle(Qt.PenCapStyle.RoundCap)
    pluma.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pluma


def con_alfa(color, alfa: float) -> QColor:
    c = QColor(color)
    c.setAlphaF(max(0.0, min(1.0, alfa)))
    return c


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
    """Interruptor como los de iOS: la perilla se desliza con un resorte, el color de la pista se funde y,
    mientras se aprieta, la perilla se estira hacia el lado al que va a ir."""

    def __init__(self):
        super().__init__()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.posicion = Resorte(self, 0.0, 0.3, 0.86, al_paso=lambda _: self.update())
        self.apriete = Resorte(self, 0.0, 0.2, 1.0, al_paso=lambda _: self.update())
        self.pintado = False

    def sizeHint(self) -> QSize:
        return QSize(42, 24)

    def hitButton(self, pos) -> bool:
        return self.rect().contains(pos)

    def mousePressEvent(self, evento) -> None:
        self.apriete.ir_a(1.0)
        super().mousePressEvent(evento)

    def mouseReleaseEvent(self, evento) -> None:
        self.apriete.ir_a(0.0)
        super().mouseReleaseEvent(evento)

    def paintEvent(self, evento) -> None:
        destino = 1.0 if self.isChecked() else 0.0
        if self.posicion.objetivo != destino:  # también cuando se cambia por código (con las señales bloqueadas)
            if self.pintado:
                self.posicion.ir_a(destino)
            else:
                self.posicion.x = self.posicion.objetivo = destino
        self.pintado = True
        k = min(1.0, max(0.0, self.posicion.x))
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pista = QRectF(1, (self.height() - 22) / 2, 40, 22)
        if not self.isEnabled():
            p.setOpacity(0.4)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(mezcla(C["borde"], C["acento"], k))
        p.drawRoundedRect(pista, 11, 11)
        ancho = 18 + 5 * self.apriete.x  # se estira al apretar
        izquierda, derecha = pista.left() + 2, pista.right() - 2 - ancho
        perilla = QRectF(izquierda + (derecha - izquierda) * k, pista.top() + 2, ancho, 18)
        p.setBrush(QColor(0, 0, 0, 45))
        p.drawRoundedRect(perilla.translated(0, 1), 9, 9)
        p.setBrush(QColor("#FFF9F4"))  # la perilla siempre clara, en cualquier tema
        p.drawRoundedRect(perilla, 9, 9)


class BotonNovedad(QAbstractButton):
    """Hay una versión nueva: una píldora del tamaño de la banderita con una flecha de descarga y el número
    de versión, y un puntito que late en la esquina. Al tocarla se abre el cartelito con la actualización."""

    ALTO = 32

    def __init__(self):
        super().__init__()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.version = ""
        self.reloj = QElapsedTimer()
        self.reloj.start()
        self.timer = QTimer(self, interval=40, timeout=self.update)  # el latido del puntito
        self.poner_version("")

    def fuente(self):
        fuente = self.font()
        fuente.setBold(True)
        return fuente

    def poner_version(self, version: str) -> None:
        self.version = version
        ancho = QFontMetrics(self.fuente()).horizontalAdvance(version) if version else 0
        self.setFixedSize(12 + 14 + (6 + ancho if version else 0) + 12 + 4, self.ALTO + 4)  # + lugar del puntito
        self.update()

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        acento = QColor(C["acento"])
        caja = QRectF(0.5, 4.5, self.width() - 5, self.ALTO - 1)  # el puntito sobresale arriba a la derecha
        fondo = QColor(acento)
        fondo.setAlpha(70 if self.underMouse() or self.isDown() else 34)
        p.setPen(QPen(acento, 1))
        p.setBrush(fondo)
        p.drawRoundedRect(caja, 8, 8)
        # Flecha de descarga: palito, punta y la bandejita de abajo.
        x, y = caja.left() + 12, caja.center().y()
        lapiz = QPen(QColor(C["texto"]), 1.8)
        lapiz.setCapStyle(Qt.PenCapStyle.RoundCap)
        lapiz.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(lapiz)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(x + 7, y - 6), QPointF(x + 7, y + 2))
        p.drawPolyline([QPointF(x + 3.5, y - 1.5), QPointF(x + 7, y + 2), QPointF(x + 10.5, y - 1.5)])
        p.drawPolyline([QPointF(x + 1, y + 3), QPointF(x + 1, y + 6), QPointF(x + 13, y + 6), QPointF(x + 13, y + 3)])
        if self.version:
            p.setFont(self.fuente())
            p.setPen(QColor(C["texto"]))
            p.drawText(QRectF(x + 20, caja.top(), caja.width(), caja.height()),
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self.version)
        # Puntito que late: un aro que se agranda y se desvanece cada 1,6 s.
        centro = QPointF(caja.right() - 1, caja.top() + 1)
        fase = (self.reloj.elapsed() % 1600) / 1600
        aro = QColor(acento)
        aro.setAlphaF(0.55 * (1 - fase))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(aro)
        p.drawEllipse(centro, 4 + 5 * fase, 4 + 5 * fase)
        p.setPen(QPen(QColor(C["fondo"]), 1.5))
        p.setBrush(acento)
        p.drawEllipse(centro, 4, 4)

    def showEvent(self, evento) -> None:
        self.timer.start()
        super().showEvent(evento)

    def hideEvent(self, evento) -> None:
        self.timer.stop()
        super().hideEvent(evento)

    def enterEvent(self, evento) -> None:
        self.update()

    def leaveEvent(self, evento) -> None:
        self.update()


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


# --- controles con movimiento (ver animacion.py) ----------------------------------

class Segmentos(QWidget):
    """Opciones pegadas, como el UISegmentedControl de iOS: la marca se desliza (y se estira si la opción
    es más ancha) y el texto cambia de color justo donde la marca lo tapa."""

    elegido = pyqtSignal(str)
    ALTO = 32

    def __init__(self, opciones: dict[str, str], iconos: dict[str, QPixmap] | None = None, suave: bool = False):
        super().__init__()
        self.claves, self.textos = list(opciones), list(opciones.values())
        self.iconos = iconos or {}
        self.suave = suave  # suave: la marca es gris (para pestañas); si no, del color de acento
        self.actual, self.encima, self.pintado = self.claves[0], -1, False
        self.letra = fuente(13, QFont.Weight.DemiBold)  # (la hoja de estilo le ganaría a setFont)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.izq = Resorte(self, 0.0, 0.34, 0.86, al_paso=lambda _: self.update())
        self.der = Resorte(self, 0.0, 0.34, 0.86, al_paso=lambda _: self.update())
        self.desactivadas: dict[str, str] = {}  # clave -> por qué no se puede elegir

    def desactivar(self, clave: str, motivo: str) -> None:
        """La opción se ve en gris y no se puede elegir; al pasar el mouse se explica por qué."""
        self.desactivadas[clave] = motivo
        self.update()

    def anchos(self) -> list[float]:
        fm = QFontMetrics(self.letra)
        anchos = [fm.horizontalAdvance(texto) + 30 + (28 if clave in self.iconos else 0)
                  for clave, texto in zip(self.claves, self.textos)]
        return anchos if self.suave else [max(anchos)] * len(anchos)  # las de acento, todas iguales

    def sizeHint(self) -> QSize:
        return QSize(round(sum(self.anchos())) + 4, self.ALTO)

    def rects(self) -> list[QRectF]:
        x, salida = 2.0, []
        for ancho in self.anchos():
            salida.append(QRectF(x, 2, ancho, self.height() - 4))
            x += ancho
        return salida

    def elegir(self, clave: str, animar: bool = True) -> None:
        self.actual = clave
        r = self.rects()[self.claves.index(clave)]
        if animar and self.pintado and self.isVisible():
            self.izq.ir_a(r.left())
            self.der.ir_a(r.right())
        else:
            self.izq.fijar(r.left())
            self.der.fijar(r.right())
        self.update()

    def indice_en(self, pos) -> int:
        return next((i for i, r in enumerate(self.rects()) if r.contains(QPointF(pos))), -1)

    def tocar(self, i: int) -> None:
        if 0 <= i < len(self.claves) and self.claves[i] in self.desactivadas:
            QToolTip.showText(self.mapToGlobal(self.rects()[i].bottomLeft().toPoint()),
                              self.desactivadas[self.claves[i]], self)
        elif 0 <= i < len(self.claves) and self.claves[i] != self.actual:
            self.elegir(self.claves[i])
            self.elegido.emit(self.actual)

    def mousePressEvent(self, evento) -> None:
        self.tocar(self.indice_en(evento.position()))

    def mouseMoveEvent(self, evento) -> None:
        self.encima = self.indice_en(evento.position())
        apagada = 0 <= self.encima < len(self.claves) and self.claves[self.encima] in self.desactivadas
        self.setCursor(Qt.CursorShape.ForbiddenCursor if apagada else Qt.CursorShape.PointingHandCursor)
        self.setToolTip(self.desactivadas[self.claves[self.encima]] if apagada else "")
        self.update()

    def leaveEvent(self, evento) -> None:
        self.encima = -1
        self.update()

    def keyPressEvent(self, evento) -> None:
        paso = {Qt.Key.Key_Left: -1, Qt.Key.Key_Right: 1}.get(evento.key())
        if paso is None:
            return super().keyPressEvent(evento)
        i = self.claves.index(self.actual) + paso
        while 0 <= i < len(self.claves) and self.claves[i] in self.desactivadas:  # se saltea las apagadas
            i += paso
        self.tocar(i)

    def resizeEvent(self, evento) -> None:
        if not self.izq.moviendose:
            self.elegir(self.actual, animar=False)

    def paintEvent(self, evento) -> None:
        if not self.pintado:
            self.pintado = True
            self.elegir(self.actual, animar=False)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setFont(self.letra)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(Qt.PenStyle.NoPen if self.suave else QPen(QColor(C["borde"]), 1))
        p.setBrush(QColor(C["campo"]))
        p.drawRoundedRect(r, 9, 9)
        rects = self.rects()
        p.setPen(Qt.PenStyle.NoPen)
        if (0 <= self.encima < len(rects) and self.claves[self.encima] != self.actual
                and self.claves[self.encima] not in self.desactivadas):
            p.setBrush(con_alfa(C["texto"], 0.06))
            p.drawRoundedRect(rects[self.encima], 7, 7)
        marca = QRectF(self.izq.x, 2, max(0.0, self.der.x - self.izq.x), self.height() - 4)
        p.setBrush(mezcla(C["campo"], C["texto"], 0.16) if self.suave else QColor(C["acento"]))
        p.drawRoundedRect(marca, 7, 7)
        normal = QColor(C["suave"] if self.suave else C["texto"])
        elegido = QColor(C["texto"] if self.suave else C["sobre"])
        for color, recorte in ((normal, None), (elegido, marca)):
            p.save()
            if recorte is not None:  # lo tapado por la marca, con el color de la elegida
                p.setClipRect(recorte)
            p.setPen(color)
            for clave, texto, rect in zip(self.claves, self.textos, rects):
                p.setPen(QColor(C["apagado"]) if clave in self.desactivadas and recorte is None else color)
                icono = self.iconos.get(clave)
                ancho_texto = QFontMetrics(self.letra).horizontalAdvance(texto)
                x = rect.center().x() - (ancho_texto + (28 if icono else 0)) / 2
                if icono:
                    lado = icono.size() / icono.devicePixelRatio()
                    p.drawPixmap(QPointF(x, rect.center().y() - lado.height() / 2), icono)
                    x += 28
                p.drawText(QRectF(x, rect.top(), ancho_texto + 2, rect.height()),
                           int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), texto)
            p.restore()
        if self.hasFocus():
            p.setPen(QPen(con_alfa(C["acento"], 0.6), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r, 9, 9)


def pintar_icono(p: QPainter, nombre: str, centro: QPointF, color) -> None:
    """Íconos de línea de la barra lateral, de 16 px, dibujados a mano."""
    p.save()
    p.translate(centro)
    p.setPen(lapiz(color, 1.6))
    p.setBrush(Qt.BrushStyle.NoBrush)
    if nombre == "campana":
        forma = QPainterPath(QPointF(-6.5, 4))
        forma.cubicTo(-5, 2.5, -5, 0, -5, -1.5)
        forma.cubicTo(-5, -5.2, -2.8, -7, 0, -7)
        forma.cubicTo(2.8, -7, 5, -5.2, 5, -1.5)
        forma.cubicTo(5, 0, 5, 2.5, 6.5, 4)
        forma.closeSubpath()
        p.drawPath(forma)
        p.drawArc(QRectF(-2.2, 3.6, 4.4, 4.2), 200 * 16, 140 * 16)
    elif nombre == "cara":
        p.drawEllipse(QPointF(0, 0), 7, 7)
        p.setBrush(QColor(color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(-2.6, -1.5), 1.1, 1.3)
        p.drawEllipse(QPointF(2.6, -1.5), 1.1, 1.3)
        p.setPen(lapiz(color, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(-3.4, -1.6, 6.8, 5.6), 200 * 16, 140 * 16)
    elif nombre == "celular":
        p.drawRoundedRect(QRectF(-4.8, -7.5, 9.6, 15), 2.4, 2.4)
        p.drawLine(QPointF(-1.4, 4.6), QPointF(1.4, 4.6))
    else:  # engranaje
        import math
        for i in range(8):
            a = i * math.pi / 4
            p.drawLine(QPointF(5.2 * math.cos(a), 5.2 * math.sin(a)), QPointF(7.4 * math.cos(a), 7.4 * math.sin(a)))
        p.drawEllipse(QPointF(0, 0), 5, 5)
        p.drawEllipse(QPointF(0, 0), 1.9, 1.9)
    p.restore()


class Navegacion(QWidget):
    """Las secciones de la barra lateral. La marca de la elegida se desliza hasta la nueva (y el ícono de
    cada una se enciende a medida que la marca le pasa por encima); la última sección va abajo de todo."""

    elegido = pyqtSignal(int)
    ALTO, SEPARACION = 36, 2

    def __init__(self, items: list[tuple[str, str]], abajo: int = 1):
        super().__init__()
        self.items, self.abajo = items, abajo  # (texto, ícono)
        self.actual, self.encima = 0, -1
        self.letra = fuente(13.5, QFont.Weight.Medium)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(len(items) * (self.ALTO + self.SEPARACION) + 30)
        self.marca = Resorte(self, 0.0, 0.38, 0.84, al_paso=lambda _: self.update())
        self.brillo = [Resorte(self, 0.0, 0.16, 1.0, al_paso=lambda _: self.update()) for _ in items]

    def rect_item(self, i: int) -> QRectF:
        n, paso = len(self.items), self.ALTO + self.SEPARACION
        y = i * paso if i < n - self.abajo else self.height() - (n - i) * paso + self.SEPARACION
        return QRectF(0, y, self.width(), self.ALTO)

    def elegir(self, i: int, animar: bool = True) -> None:
        self.actual = i
        y = self.rect_item(i).top()
        self.marca.ir_a(y) if animar and self.isVisible() else self.marca.fijar(y)
        self.update()

    def indice_en(self, pos) -> int:
        return next((i for i in range(len(self.items)) if self.rect_item(i).contains(QPointF(pos))), -1)

    def tocar(self, i: int) -> None:
        if 0 <= i < len(self.items) and i != self.actual:
            self.elegir(i)
            self.elegido.emit(i)

    def mousePressEvent(self, evento) -> None:
        i = self.indice_en(evento.position())
        if i < 0:
            return evento.ignore()
        self.tocar(i)

    def mouseMoveEvent(self, evento) -> None:
        self.encima = self.indice_en(evento.position())
        self.setCursor(Qt.CursorShape.PointingHandCursor if self.encima >= 0 else Qt.CursorShape.ArrowCursor)
        for i, brillo in enumerate(self.brillo):
            brillo.ir_a(1.0 if i == self.encima else 0.0)

    def leaveEvent(self, evento) -> None:
        self.encima = -1
        for brillo in self.brillo:
            brillo.ir_a(0.0)

    def keyPressEvent(self, evento) -> None:
        paso = {Qt.Key.Key_Up: -1, Qt.Key.Key_Down: 1}.get(evento.key())
        if paso is None:
            return super().keyPressEvent(evento)
        self.tocar(self.actual + paso)

    def resizeEvent(self, evento) -> None:
        if not self.marca.moviendose:
            self.marca.fijar(self.rect_item(self.actual).top())

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(self.letra)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(con_alfa(C["acento"], 0.17))
        p.drawRoundedRect(QRectF(0, self.marca.x, self.width(), self.ALTO), 9, 9)
        for i, (texto, icono) in enumerate(self.items):
            r = self.rect_item(i)
            brillo = self.brillo[i].x
            if i != self.actual and brillo > 0.01:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(con_alfa(C["texto"], 0.06 * brillo))
                p.drawRoundedRect(r, 9, 9)
            cerca = max(0.0, 1 - abs(self.marca.x - r.top()) / self.ALTO)
            pintar_icono(p, icono, QPointF(r.left() + 20, r.center().y()), mezcla(C["suave"], C["acento"], cerca))
            p.setPen(mezcla(C["suave"], C["texto"], max(cerca, 0.7 * brillo)))
            p.drawText(r.adjusted(42, 0, -8, 0), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), texto)
        if self.hasFocus():
            p.setPen(QPen(con_alfa(C["acento"], 0.5), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(self.rect_item(self.actual).adjusted(0.5, 0.5, -0.5, -0.5), 9, 9)


class Lateral(QWidget):
    """El fondo de la barra lateral: un poco más claro que la ventana, con una línea finita a la derecha."""

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), mezcla(C["fondo"], C["panel"], 0.6))
        p.setPen(QPen(con_alfa(C["borde"], 0.7), 1))
        p.drawLine(QPointF(self.width() - 0.5, 0), QPointF(self.width() - 0.5, self.height()))


class TextoSuave(QWidget):
    """Un texto que, al cambiar, se funde con el anterior y se corre apenas hacia arriba o hacia abajo."""

    def __init__(self, px: float, peso: QFont.Weight = QFont.Weight.Normal, color: str = "texto"):
        super().__init__()
        self.texto = self.viejo = ""
        self.direccion, self.color = 0, color
        self.letra = fuente(px, peso)
        self.setFixedHeight(QFontMetrics(self.letra).height() + 6)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.cambio = Resorte(self, 1.0, 0.32, 1.0, al_paso=lambda _: self.update())

    def setText(self, texto: str, direccion: int = 0, animar: bool = True) -> None:
        if texto == self.texto:
            return
        self.viejo, self.texto, self.direccion = self.texto, texto, direccion
        self.setToolTip(texto if QFontMetrics(self.letra).horizontalAdvance(texto) > self.width() else "")
        if animar and self.isVisible() and self.viejo:
            self.cambio.ir_a(1.0, desde=0.0)
        else:
            self.cambio.fijar(1.0)

    def text(self) -> str:
        return self.texto

    def sizeHint(self) -> QSize:
        return QSize(QFontMetrics(self.letra).horizontalAdvance(self.texto) + 4, self.height())

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        k = min(1.0, max(0.0, self.cambio.x))
        p.setFont(self.letra)
        fm = QFontMetrics(self.letra)
        p.setPen(QColor(C[self.color]))
        alineado = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for texto, alfa, dy in ((self.viejo, max(0.0, 1 - k * 1.8), -self.direccion * 7 * k),
                                (self.texto, k, self.direccion * 9 * (1 - k))):
            if texto and alfa > 0:
                p.setOpacity(alfa)
                p.drawText(QRectF(0, dy, self.width(), self.height()), alineado,
                           fm.elidedText(texto, Qt.TextElideMode.ElideRight, self.width()))


class BotonInfo(QAbstractButton):
    """La "i" en un circulito: la explicación larga queda escondida y aparece al pasar el mouse o al tocarla."""

    def __init__(self, texto: str):
        super().__init__()
        self.setFixedSize(16, 16)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip(f"<p style='margin:2px'>{html.escape(texto)}</p>")  # con etiquetas, el globo corta líneas
        self.clicked.connect(lambda: QToolTip.showText(self.mapToGlobal(QPoint(0, self.height() + 4)),
                                                       self.toolTip(), self))

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(C["acento"] if self.underMouse() else C["suave"])
        p.setPen(QPen(color, 1.2))
        p.drawEllipse(QPointF(8, 8), 6.6, 6.6)
        p.setPen(lapiz(color, 1.5))
        p.drawLine(QPointF(8, 7.2), QPointF(8, 11))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawEllipse(QPointF(8, 4.9), 0.95, 0.95)

    def enterEvent(self, evento) -> None:
        self.update()

    def leaveEvent(self, evento) -> None:
        self.update()


class Etiqueta(QLabel):
    """Texto que corta línea solo si no entra: pide el ancho de su texto en una línea (un QLabel con
    wordWrap pide mucho menos y termina partiéndose aunque sobre lugar)."""

    def sizeHint(self) -> QSize:
        alto = super().sizeHint().height()
        return QSize(QFontMetrics(self.font()).horizontalAdvance(self.text()) + 4, alto)

    def minimumSizeHint(self) -> QSize:
        return QSize(min(90, self.sizeHint().width()), super().minimumSizeHint().height())


class Fila(QWidget):
    """Una fila de ajustes: el texto (y su "i") a la izquierda y los controles a la derecha; con debajo=True,
    los controles van en una segunda línea. Desactivar la fila apaga también su texto."""

    def __init__(self, texto: str = "", *controles, detalle: str = "", info: str = "", debajo: bool = False,
                 alto: int = 46):
        super().__init__()
        self.setMinimumHeight(alto)
        self.etiqueta = Etiqueta(t(texto), wordWrap=True)
        self.etiqueta.setVisible(bool(texto))
        cabeza = QHBoxLayout()
        cabeza.setSpacing(6)
        cabeza.addWidget(self.etiqueta, 0 if info else 1)
        if info:
            cabeza.addWidget(BotonInfo(t(info)), 0, Qt.AlignmentFlag.AlignVCenter)
            cabeza.addStretch(1)
        self.textos = QVBoxLayout()
        self.textos.setSpacing(1)
        self.textos.addStretch(1)
        self.textos.addLayout(cabeza)
        if texto or not detalle:
            self.detalle = Etiqueta(detalle, objectName="detalle", wordWrap=True)
            self.detalle.setVisible(bool(detalle))
            self.textos.addWidget(self.detalle)
        else:  # solo un texto chico: va en el lugar del título
            self.detalle = self.etiqueta
            self.etiqueta.setObjectName("detalle")
            self.etiqueta.setText(detalle.strip())
            self.etiqueta.show()
        self.textos.addStretch(1)
        self.controles = QHBoxLayout()
        self.controles.setSpacing(8)
        con_barra = any(isinstance(c, QSlider) for c in controles)
        for control in controles:
            if isinstance(control, QPushButton):  # un botón no se estira a costa del texto
                control.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            self.controles.addWidget(control, 1 if isinstance(control, QSlider) else 0)
        if debajo:
            caja = QVBoxLayout(self)
            caja.setContentsMargins(16, 10, 14, 10)
            caja.setSpacing(6)
            caja.addLayout(self.textos)
            caja.addLayout(self.controles)
        else:
            caja = QHBoxLayout(self)
            caja.setContentsMargins(16, 6, 14, 6)
            caja.setSpacing(12)
            caja.addLayout(self.textos, 2 if con_barra else 1)
            caja.addLayout(self.controles, 3 if con_barra else 0)


class Filas(QWidget):
    """Filas una debajo de otra, separadas por una línea finita que no llega a los bordes (como en iOS)."""

    def __init__(self, linea_arriba: bool = False):
        super().__init__()
        self.linea_arriba = linea_arriba
        self.caja = QVBoxLayout(self)
        self.caja.setContentsMargins(0, 0, 0, 0)
        self.caja.setSpacing(0)

    def agregar(self, widget: QWidget) -> QWidget:
        self.caja.addWidget(widget)
        return widget

    def pintar_fondo(self, p: QPainter) -> None:
        pass

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.pintar_fondo(p)
        visibles = [w for w in (self.caja.itemAt(i).widget() for i in range(self.caja.count()))
                    if w is not None and not w.isHidden() and w.height() > 0]
        alturas = [w.geometry().bottom() + 1 for w in visibles[:-1]]
        if self.linea_arriba and visibles:
            alturas.insert(0, 0)
        p.setPen(QPen(con_alfa(C["borde"], 0.75), 1))
        for y in alturas:
            p.drawLine(QPointF(16, y + 0.5), QPointF(self.width() - 16, y + 0.5))


class Grupo(Filas):
    """Una tarjeta redondeada con filas adentro."""

    def pintar_fondo(self, p: QPainter) -> None:
        p.setPen(QPen(QColor(C["borde"]), 1))
        p.setBrush(QColor(C["panel"]))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)


class Plegable(QWidget):
    """Filas que se abren y se cierran deslizándose: la altura sigue a un resorte y las filas aparecen y se
    van con un fundido (moviéndose apenas 8 px), como al abrir una sección en los ajustes de macOS."""

    def __init__(self, abierto: bool = False, al_mover=None):
        super().__init__()
        self.filas = Filas(linea_arriba=True)
        self.filas.setParent(self)
        self.abierto, self.al_mover, self.n = abierto, al_mover, 0
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        # Dos resortes: la altura, y la opacidad de las filas, que sigue a la altura con su propia inercia
        # (si dependiera directo de la altura, al darse vuelta a mitad de camino cambiaría de golpe).
        self.opacidad = Resorte(self, 1.0 if abierto else 0.0, 0.16, 1.0, al_paso=self.pintar_filas)
        self.apertura = Resorte(self, 1.0 if abierto else 0.0, 0.32 if abierto else 0.4, 1.0, al_paso=self.ubicar)
        self.ubicar()

    @property
    def alfa(self) -> float:
        return min(1.0, max(0.0, self.opacidad.x))

    def agregar(self, widget: QWidget) -> QWidget:
        self.filas.agregar(widget)
        self.ubicar()
        return widget

    def natural(self) -> int:
        caja = self.filas.caja
        ancho = max(self.width(), 200)
        return caja.totalHeightForWidth(ancho) if caja.hasHeightForWidth() else self.filas.sizeHint().height()

    def ubicar(self, _=None) -> None:
        self.n = self.natural()
        k = min(1.0, max(0.0, self.apertura.x))  # si el resorte se pasa un poquito, no queda un hueco
        alto = round(self.n * k)
        self.setFixedHeight(alto)
        # La coreografía de Apple: al abrir, primero se hace lugar y las filas aparecen en la segunda mitad,
        # bajando apenas; al cerrar, las filas se desvanecen enseguida (subiendo apenas) y después se cierra
        # el hueco. Así nunca se ven filas cortadas a medio camino.
        def suave(x: float) -> float:  # una S: arranca y termina sin pendiente
            x = min(1.0, max(0.0, x))
            return x * x * (3 - 2 * x)
        destino = suave((k - 0.25) / 0.75) if self.abierto else suave((k - 0.4) / 0.6)
        if self.isVisible() and (self.apertura.moviendose or self.opacidad.moviendose):
            self.opacidad.ir_a(destino)  # la sigue con inercia: nunca salta
        else:
            self.opacidad.fijar(destino)
        self.pintar_filas()
        if self.al_mover:
            self.al_mover(k)
        if self.parentWidget():
            self.parentWidget().update()  # sus líneas separadoras

    def pintar_filas(self, _=None) -> None:
        alfa = self.alfa
        self.filas.setGeometry(0, -round((1 - alfa) * 8), self.width(), self.n)
        # Invisibles (o sin lugar): ocultas, así no se ven sin fundido ni reciben el foco con Tab.
        self.filas.setVisible(self.height() > 0 and alfa > 0.001)
        if 0.001 < alfa < 0.999:
            efecto = self.filas.graphicsEffect()
            if efecto is None:
                efecto = QGraphicsOpacityEffect(self.filas)
                self.filas.setGraphicsEffect(efecto)
            efecto.setOpacity(alfa)
        elif self.filas.graphicsEffect() is not None:  # quieta: sin efecto (es más liviano y más nítido)
            self.filas.setGraphicsEffect(None)

    def abrir(self, si: bool, animar: bool = True) -> None:
        if si != self.abierto:  # cerrar es un poco más rápido que abrir, como en iOS
            self.apertura.configurar(0.4 if si else 0.32, 1.0)
        self.abierto = si
        destino = 1.0 if si else 0.0
        self.apertura.ir_a(destino) if animar and self.isVisible() else self.apertura.fijar(destino)

    def resizeEvent(self, evento) -> None:
        if not self.apertura.moviendose:
            self.ubicar()


class CabeceraDesplegable(QAbstractButton):
    """El título de una sección que se despliega: la flechita gira mientras se abre."""

    def __init__(self, texto: str):
        super().__init__()
        self.texto, self.resumen, self.giro = texto, "", 0.0
        self.setMinimumHeight(48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.letra = fuente(13, QFont.Weight.DemiBold)

    def girar(self, k: float) -> None:
        self.giro = k
        self.update()

    def poner_resumen(self, texto: str) -> None:
        if texto != self.resumen:
            self.resumen = texto
            self.update()

    def sizeHint(self) -> QSize:
        return QSize(200, 48)

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        if self.underMouse():
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(con_alfa(C["texto"], 0.035))
            p.drawRoundedRect(r.adjusted(4, 4, -4, -4), 9, 9)
        p.setFont(self.letra)
        p.setPen(QColor(C["texto"]))
        centrado = Qt.AlignmentFlag.AlignVCenter
        p.drawText(r.adjusted(16, 0, -40, 0), int(Qt.AlignmentFlag.AlignLeft | centrado), self.texto)
        if self.resumen:
            p.setFont(fuente(12))
            p.setPen(QColor(C["suave"]))
            p.drawText(r.adjusted(16, 0, -40, 0), int(Qt.AlignmentFlag.AlignRight | centrado), self.resumen)
        p.translate(r.right() - 22, r.center().y())
        p.rotate(90 * self.giro)
        p.setPen(lapiz(C["suave"], 1.7))
        p.drawPolyline([QPointF(-2.5, -4.5), QPointF(2.5, 0), QPointF(-2.5, 4.5)])

    def enterEvent(self, evento) -> None:
        self.update()

    def leaveEvent(self, evento) -> None:
        self.update()


class Desplegable(Grupo):
    """Una tarjeta que muestra solo su título hasta que se la toca."""

    def __init__(self, titulo: str):
        super().__init__()
        self.cabecera = CabeceraDesplegable(t(titulo))
        self.plegable = Plegable(False, al_mover=self.cabecera.girar)
        self.cabecera.clicked.connect(lambda: self.plegable.abrir(not self.plegable.abierto))
        self.agregar(self.cabecera)
        self.agregar(self.plegable)

    def agregar_fila(self, widget: QWidget) -> QWidget:
        return self.plegable.agregar(widget)


class TablaEventos(QWidget):
    """Una fila por cada aviso con lo que hace en la pantalla, qué sonido usa y si llega al celular.
    La fila elegida (la que se ve en la vista previa) tiene una marca que se desliza de una a otra."""

    elegido = pyqtSignal(str)
    COLUMNA, SONIDO = 66, 182

    def __init__(self, nombres_sonido: dict[str, str]):
        super().__init__()
        caja = QVBoxLayout(self)
        caja.setContentsMargins(6, 2, 6, 6)
        caja.setSpacing(0)
        cabecera = QHBoxLayout()
        cabecera.setContentsMargins(34, 8, 8, 2)
        cabecera.setSpacing(0)
        cabecera.addStretch(1)
        self.cabeceras = {}
        for clave, texto, ancho in (("pantalla", "Pantalla", self.COLUMNA), ("sonido", "Sonido", self.SONIDO),
                                    ("celular", "Celular", self.COLUMNA)):
            etiqueta = QLabel(t(texto), objectName="columna", alignment=Qt.AlignmentFlag.AlignCenter)
            etiqueta.setFixedWidth(ancho)
            self.cabeceras[clave] = etiqueta
            cabecera.addWidget(etiqueta)
        caja.addLayout(cabecera)
        self.filas, self.pantalla, self.sonido, self.escuchar, self.celular = {}, {}, {}, {}, {}
        for estado in ESTADOS_ORDEN:
            fila_evento = QWidget()
            fila_evento.setMinimumHeight(44)
            fila_evento.setCursor(Qt.CursorShape.PointingHandCursor)
            linea = QHBoxLayout(fila_evento)
            linea.setContentsMargins(34, 3, 8, 3)
            linea.setSpacing(0)
            linea.addWidget(QLabel(t(NOMBRES_ESTADO[estado])), 1)
            self.pantalla[estado] = Interruptor()
            linea.addWidget(self.celda(self.pantalla[estado], self.COLUMNA))
            combo = QComboBox()
            for clave, nombre in nombres_sonido.items():
                combo.addItem(nombre, clave)
            self.sonido[estado], self.escuchar[estado] = combo, BotonEscuchar()
            sonido = QWidget()
            sonido.setFixedWidth(self.SONIDO)
            fila_sonido = QHBoxLayout(sonido)
            fila_sonido.setContentsMargins(6, 0, 0, 0)
            fila_sonido.setSpacing(6)
            fila_sonido.addWidget(combo, 1)
            fila_sonido.addWidget(self.escuchar[estado])
            linea.addWidget(sonido)
            if estado in ESTADOS_CELULAR:
                self.celular[estado] = Interruptor()
                linea.addWidget(self.celda(self.celular[estado], self.COLUMNA))
            else:
                linea.addWidget(self.celda(QLabel("—", objectName="columna"), self.COLUMNA))
            self.filas[estado] = fila_evento
            for widget in (fila_evento, *fila_evento.findChildren(QWidget)):
                widget.installEventFilter(self)
            caja.addWidget(fila_evento)
        self.actual, self.encima = "listo", None
        self.marca = Resorte(self, 0.0, 0.34, 0.86, al_paso=lambda _: self.update())
        self.brillo = Resorte(self, 0.0, 0.14, 1.0, al_paso=lambda _: self.update())

    @staticmethod
    def celda(widget: QWidget, ancho: int) -> QWidget:
        celda = QWidget()
        celda.setFixedWidth(ancho)
        caja = QHBoxLayout(celda)
        caja.setContentsMargins(0, 0, 0, 0)
        caja.addWidget(widget, 0, Qt.AlignmentFlag.AlignCenter)
        return celda

    def estado_de(self, widget) -> str | None:
        while widget is not None and widget is not self:
            for estado, fila_evento in self.filas.items():
                if widget is fila_evento:
                    return estado
            widget = widget.parentWidget()
        return None

    def eventFilter(self, objeto, evento) -> bool:
        tipo = evento.type()
        if tipo == QEvent.Type.MouseButtonPress:  # tocar cualquier cosa de la fila (también su sonido) la elige
            estado = self.estado_de(objeto)
            if estado and estado != self.actual:
                self.elegir(estado)
                self.elegido.emit(estado)
        elif tipo == QEvent.Type.Enter and objeto in self.filas.values():
            self.encima = self.estado_de(objeto)
            self.brillo.ir_a(1.0, desde=0.0)
        elif tipo == QEvent.Type.Leave and objeto in self.filas.values():
            self.brillo.ir_a(0.0)
        return False

    def elegir(self, estado: str, animar: bool = True) -> None:
        self.actual = estado
        y = self.filas[estado].geometry().top()
        self.marca.ir_a(y) if animar and self.isVisible() else self.marca.fijar(y)
        self.update()

    def resizeEvent(self, evento) -> None:
        if not self.marca.moviendose:
            self.marca.fijar(self.filas[self.actual].geometry().top())

    def showEvent(self, evento) -> None:
        self.resizeEvent(evento)

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        alto = self.filas[self.actual].height()
        if self.encima and self.encima != self.actual and self.brillo.x > 0.01:
            p.setBrush(con_alfa(C["texto"], 0.04 * self.brillo.x))
            p.drawRoundedRect(QRectF(self.filas[self.encima].geometry()).adjusted(0, 1, 0, -1), 9, 9)
        p.setBrush(mezcla(C["panel"], C["acento"], 0.13))
        p.drawRoundedRect(QRectF(0, self.marca.x + 1, self.width(), alto - 2).adjusted(6, 0, -6, 0), 9, 9)
        for estado, fila_evento in self.filas.items():
            g = fila_evento.geometry()
            p.setBrush(QColor(m.ESTADOS[estado]["acento"]))
            p.drawEllipse(QPointF(g.left() + 19, g.center().y() + 0.5), 4.5, 4.5)


class BotonRedondo(QAbstractButton):
    """Botón redondo con una flechita (‹ o ›), para las flechas del probador."""

    def __init__(self, direccion: int, padre: QWidget):
        super().__init__(padre)
        self.direccion = direccion
        self.setFixedSize(36, 36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.brillo = Resorte(self, 0.0, 0.16, 1.0, al_paso=lambda _: self.update())
        self.apriete = Resorte(self, 0.0, 0.18, 1.0, al_paso=lambda _: self.update())
        self.pressed.connect(lambda: self.apriete.ir_a(1.0))
        self.released.connect(lambda: self.apriete.ir_a(0.0))

    def enterEvent(self, evento) -> None:
        self.brillo.ir_a(1.0)

    def leaveEvent(self, evento) -> None:
        self.brillo.ir_a(0.0)

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(18, 18)
        p.scale(1 - 0.08 * self.apriete.x, 1 - 0.08 * self.apriete.x)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, round(22 + 26 * self.brillo.x)))
        p.drawEllipse(QPointF(0, 0), 17, 17)
        p.setPen(lapiz(QColor(255, 255, 255, 230), 2))
        d = self.direccion
        p.drawPolyline([QPointF(-2.5 * d, -6), QPointF(3 * d, 0), QPointF(-2.5 * d, 6)])


class Escenario(QWidget):
    """El probador: la mascota grande, en su animación de reposo. Al cambiarle algo da un saltito (un resorte
    que rebota apenas) y, si se la toca, festeja. Las flechas pasan al estilo o al diseño de al lado."""

    anterior, siguiente = pyqtSignal(), pyqtSignal()
    TAMANO = 4

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(270)
        self.setMouseTracking(True)
        self.cuadros, self.festejo, self.clave, self.nombre, self.datos = [], None, None, "", None
        self.reloj = QElapsedTimer()
        self.reloj.start()
        self.inicio_festejo = 0
        self.tic = QTimer(self, interval=30, timeout=self.update)
        self.salto = Resorte(self, 1.0, 0.5, 0.52, al_paso=lambda _: self.update())
        self.flecha_izq, self.flecha_der = BotonRedondo(-1, self), BotonRedondo(1, self)
        self.flecha_izq.setToolTip(t("Anterior"))
        self.flecha_der.setToolTip(t("Siguiente"))
        self.flecha_izq.clicked.connect(self.anterior)
        self.flecha_der.clicked.connect(self.siguiente)

    def mostrar(self, aspecto: dict, imagen: str, nombre: str) -> None:
        self.nombre = nombre
        dpr = self.devicePixelRatioF()
        clave = (json.dumps(aspecto, sort_keys=True), imagen, dpr)
        if clave != self.clave:
            primera = self.clave is None
            self.clave, self.datos = clave, (aspecto, imagen)
            self.cuadros = m.cargar_cuadros(aspecto, imagen, "idle", self.TAMANO, dpr)
            self.festejo = None
            if not primera:
                self.salto.ir_a(1.0, desde=0.84)
        self.update()

    def festejar(self) -> None:
        if self.datos:
            self.festejo = m.cargar_cuadros(*self.datos, "listo", self.TAMANO, self.devicePixelRatioF())
            self.inicio_festejo = self.reloj.elapsed()
            self.salto.ir_a(1.0, desde=0.9)

    def zona_mascota(self) -> QRectF:
        r = QRectF(self.rect())
        return QRectF(r.center().x() - 110, r.top() + 20, 220, r.height() - 70)

    def mousePressEvent(self, evento) -> None:
        if self.zona_mascota().contains(evento.position()):
            self.festejar()
        else:
            evento.ignore()

    def mouseMoveEvent(self, evento) -> None:
        sobre = self.zona_mascota().contains(evento.position())
        self.setCursor(Qt.CursorShape.PointingHandCursor if sobre else Qt.CursorShape.ArrowCursor)

    def showEvent(self, evento) -> None:
        self.tic.start()

    def hideEvent(self, evento) -> None:
        self.tic.stop()

    def resizeEvent(self, evento) -> None:
        y = round(self.height() / 2 - 30)
        self.flecha_izq.move(16, y)
        self.flecha_der.move(self.width() - 52, y)

    def cuadro(self):
        if self.festejo:
            dt = self.reloj.elapsed() - self.inicio_festejo
            if dt < max(1500, sum(d for _, d in self.festejo)):
                return cuadro_en(self.festejo, dt)
            self.festejo = None
        return cuadro_en(self.cuadros, self.reloj.elapsed()) if self.cuadros else None

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        forma = QPainterPath()
        forma.addRoundedRect(r, 16, 16)
        luz = QRadialGradient(QPointF(r.center().x(), r.top() + r.height() * 0.42), r.width() * 0.62)
        luz.setColorAt(0, QColor("#46505F"))
        luz.setColorAt(1, QColor("#1D2129"))
        p.fillPath(forma, luz)
        p.setPen(QPen(QColor(C["borde"]), 1))
        p.drawPath(forma)
        pm = self.cuadro()
        if pm is not None:
            sw, sh = pm.width() / pm.devicePixelRatio(), pm.height() / pm.devicePixelRatio()
            encaje = min(1.0, (r.height() - 78) / sh)
            base = r.top() + (r.height() - 30 + sh * encaje) / 2
            cx = r.center().x()
            p.setClipPath(forma)
            m.pintar_sombra(p, cx, base, sw * encaje * min(1.0, self.salto.x))
            p.save()
            p.translate(cx, base)  # crece desde los pies, como si saltara
            s = encaje * self.salto.x
            p.scale(s, s)
            if abs(s - round(s)) > 0.001:
                p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            p.drawPixmap(QPointF(-sw / 2, -sh), pm)
            p.restore()
        p.setFont(fuente(13, QFont.Weight.DemiBold))
        p.setPen(QColor(236, 240, 246, 215))
        p.drawText(QRectF(r.left(), r.bottom() - 42, r.width(), 24), int(Qt.AlignmentFlag.AlignCenter), self.nombre)


class Paginas(QWidget):
    """Muestra una página por vez. Al cambiar, la foto de la anterior se desvanece encima mientras la nueva
    (la de verdad, que ya se puede usar) se desliza los últimos píxeles hasta su lugar."""

    def __init__(self, horizontal: bool = False, distancia: int = 18):
        super().__init__()
        self.lista: list[QWidget] = []
        self.actual, self.horizontal, self.distancia = 0, horizontal, distancia
        self.desliz = Resorte(self, 0.0, 0.46, 1.0, al_paso=lambda _: self.ubicar())
        self.velo = Velo(self)

    def agregar(self, widget: QWidget) -> QWidget:
        widget.setParent(self)
        widget.setVisible(not self.lista)
        self.lista.append(widget)
        self.ubicar()
        return widget

    def mostrar(self, i: int, direccion: int = 1, animar: bool = True, fondo=None) -> None:
        if i == self.actual:
            return
        if animar and self.isVisible() and not reducir_movimiento():
            self.velo.tapar(self.grab(), fondo)
        self.lista[self.actual].hide()
        self.actual = i
        self.lista[i].show()
        self.velo.raise_()
        if animar and self.isVisible():
            self.desliz.ir_a(0.0, desde=direccion * self.distancia)
        else:
            self.desliz.fijar(0.0)
        self.updateGeometry()
        self.ubicar()

    def ubicar(self) -> None:
        if self.lista:
            d = round(self.desliz.x)
            self.lista[self.actual].setGeometry(self.rect().translated(d, 0) if self.horizontal
                                                else self.rect().translated(0, d))

    def sizeHint(self) -> QSize:
        return self.lista[self.actual].sizeHint() if self.lista else super().sizeHint()

    def minimumSizeHint(self) -> QSize:
        return self.lista[self.actual].minimumSizeHint() if self.lista else super().minimumSizeHint()

    def event(self, evento) -> bool:
        if evento.type() == QEvent.Type.LayoutRequest:  # la página cambió de alto (por ejemplo, una galería)
            self.updateGeometry()
            self.ubicar()
        return super().event(evento)

    def resizeEvent(self, evento) -> None:
        self.ubicar()
        self.velo.setGeometry(self.rect())


class ScrollSuave(QScrollArea):
    """Un área con desplazamiento suave: cada vuelta de la ruedita lleva a un resorte en vez de saltar
    (con el touchpad, que ya manda movimientos finos, se usa tal cual)."""

    def __init__(self, pagina: QWidget):
        super().__init__(widgetResizable=True, frameShape=QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(pagina)
        barra = self.verticalScrollBar()
        self.rueda = Resorte(self, 0.0, 0.26, 1.0, al_paso=lambda v: barra.setValue(round(v)))
        barra.sliderPressed.connect(lambda: self.rueda.fijar(barra.value()))

    def wheelEvent(self, evento) -> None:
        barra, delta = self.verticalScrollBar(), evento.angleDelta().y()
        if not evento.pixelDelta().isNull() or not delta or reducir_movimiento():
            return super().wheelEvent(evento)
        desde = self.rueda.objetivo if self.rueda.moviendose else barra.value()
        destino = max(barra.minimum(), min(barra.maximum(), desde - delta / 120 * 96))
        if not self.rueda.moviendose:
            self.rueda.x = barra.value()
        self.rueda.ir_a(destino)
        evento.accept()


class FiltroRueda(QObject):
    """Que la ruedita sobre una lista o una barra no cambie su valor sin querer mientras se recorre la
    página: si el control no tiene el foco (no se lo tocó), la ruedita desplaza la página."""

    def eventFilter(self, objeto, evento) -> bool:
        if evento.type() == QEvent.Type.Wheel and not objeto.hasFocus():
            area = objeto.parentWidget()
            while area is not None and not isinstance(area, ScrollSuave):
                area = area.parentWidget()
            if area is not None:
                area.wheelEvent(evento)
                return True
        return False


class ColumnaVista(QWidget):
    """La columna de la vista previa: en la sección Mascota se va hacia la derecha (el probador ocupa su lugar)
    y vuelve al salir. El ancho sigue a un resorte; el contenido no se aprieta, se corre."""

    def __init__(self, ancho: int):
        super().__init__()
        self.ancho = ancho
        self.interior = QWidget(self)
        self.setFixedWidth(ancho)
        self.abierta = Resorte(self, 1.0, 0.44, 1.0, al_paso=self.ubicar)

    def plegar(self, si: bool, animar: bool = True) -> None:
        if not si:
            self.interior.show()
        destino = 0.0 if si else 1.0
        self.abierta.ir_a(destino) if animar and self.isVisible() else self.abierta.fijar(destino)

    def ubicar(self, k: float) -> None:
        k = max(0.0, min(1.0, k))
        self.setFixedWidth(round(self.ancho * k))
        if 0.0 < k < 1.0:
            efecto = self.interior.graphicsEffect()
            if efecto is None:
                efecto = QGraphicsOpacityEffect(self.interior)
                self.interior.setGraphicsEffect(efecto)
            efecto.setOpacity(k * k)
        else:
            self.interior.setGraphicsEffect(None)
            self.interior.setVisible(k > 0)

    def resizeEvent(self, evento) -> None:
        self.interior.setGeometry(0, 0, self.ancho, self.height())


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
        self.setMinimumSize(280, 380)
        self.cartel = m.Cartel()
        self.cuadros: list = []
        self.entrada = self.salida = self.bucle = None
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
            self.bucle = None
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

    def cuadro_estado(self, dt: float):
        """La animación del aviso: con un paquete, la acción una vez y después la espera en loop."""
        if not self.bucle:
            return cuadro_en(self.cuadros, dt)
        accion = sum(d for _, d in self.cuadros)
        return cuadro_en(self.cuadros, dt, repetir=False) if dt < accion else cuadro_en(self.bucle, dt - accion)

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
            pm, barra = self.cuadro_estado(dt), 1 - min(1.0, dt / ms)
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
                pm, t = self.cuadro_estado(dt), 1 - min(1.0, dt / self.SALIDA)
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
    respuesta_version = pyqtSignal(str, object)   # búsqueda y descarga de la versión nueva

    def __init__(self):
        super().__init__()
        self.setObjectName("raiz")
        marco.preparar(self)  # Windows: sin la barra de título del sistema, con los colores de la app
        self.config = m.cargar_config()
        idiomas.usar(self.config["idioma"])  # antes de cualquier texto
        self.setWindowTitle(t("Ajustes de WaveMascot"))
        self.setWindowIcon(bandeja.icono_mascota("terracota", grande=m.MAC))
        self.estado_vista, self.pagina, self.parte, self.aparecio = "listo", 0, "estilo", False
        self.sonidos = m.Sonidos(self)
        self.timer_guardar = QTimer(self, singleShot=True, interval=300, timeout=self.guardar)
        # El modo nuevo se aplica (guardar y abrir la compañera) cuando la animación ya terminó.
        self.timer_modo = QTimer(self, singleShot=True, interval=450, timeout=self.aplicar_modo)
        # Conectar Telegram: el código que se le muestra a la persona y la consulta al servidor hasta que
        # se lo manda al bot.
        self.codigo, self.consultando, self.fin_codigo = "", False, 0.0
        self.timer_estado = QTimer(self, interval=2500, timeout=self.consultar_estado)
        self.respuesta_telegram.connect(self.al_responder_telegram)
        self.version, self.actualizando = None, False
        self.respuesta_version.connect(self.al_responder_version)

        # Barra lateral | título y páginas | vista previa (que en Mascota se corre y deja lugar al probador).
        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(self.barra_lateral())
        principal = QVBoxLayout()
        principal.setContentsMargins(28, 14, 22, 18)
        principal.setSpacing(10)
        arriba = QHBoxLayout()
        arriba.setSpacing(10)
        self.titulo = TextoSuave(24, QFont.Weight.Bold)
        arriba.addWidget(self.titulo, 1, Qt.AlignmentFlag.AlignVCenter)
        self.boton_novedad = BotonNovedad()  # flecha de descarga + versión: solo si hay una nueva
        self.boton_novedad.setToolTip(t("Hay una versión nueva"))
        self.boton_novedad.clicked.connect(self.abrir_franja)
        self.boton_novedad.setVisible(False)
        arriba.addWidget(self.boton_novedad, 0, Qt.AlignmentFlag.AlignTop)
        if marco.ACTIVO:  # lugar para minimizar, maximizar y cerrar
            arriba.addSpacing(marco.ANCHO_BOTONES - 12)
        principal.addLayout(arriba)
        self.franja_version()  # el cartelito de la versión nueva (se abre desde la píldora de arriba)
        cuerpo = QHBoxLayout()
        cuerpo.setSpacing(0)
        self.paginas = Paginas()
        for armar in (self.pagina_avisos, self.pagina_mascota, self.pagina_celular, self.pagina_general):
            self.paginas.agregar(ScrollSuave(armar()))
        cuerpo.addWidget(self.paginas, 1)
        cuerpo.addWidget(self.panel_vista())
        principal.addLayout(cuerpo, 1)
        raiz.addLayout(principal, 1)
        if marco.ACTIVO:
            self.botones_ventana = marco.BotonesVentana(self)  # minimizar, maximizar y cerrar, arriba a la derecha
        QShortcut(QKeySequence("Esc"), self, activated=self.close)
        if m.MAC:
            QShortcut(QKeySequence("Ctrl+W"), self, activated=self.close)  # Qt lo muestra como ⌘W
        for i in range(len(PAGINAS)):  # Ctrl+1..4: cada sección
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self, activated=lambda i=i: self.ir_a(i))
        self.filtro_rueda = FiltroRueda(self)
        for tipo in (QComboBox, QSlider, QTimeEdit):
            for control in self.findChildren(tipo):
                control.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                control.installEventFilter(self.filtro_rueda)

        self.titulo.setText(t(PAGINAS["avisos"][0]), animar=False)
        self.cargar_en_controles()
        self.estado_guardado.setText(t("Los cambios se guardan solos"), animar=False)
        self.buscar_version()
        if self.config["celular"]["llave"] and self.config["celular"]["conectado"]:
            llave = self.config["celular"]["llave"]  # ¿sigue conectado? (pudo mandar /stop desde Telegram)
            self.en_segundo_plano("inicial", lambda: celular.estado(llave))
        m.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.vigia = QFileSystemWatcher([str(m.CONFIG_DIR)], self)
        self.vigia.directoryChanged.connect(lambda _: QTimer.singleShot(300, self.sincronizar))

    def showEvent(self, evento) -> None:
        super().showEvent(evento)
        if not self.aparecio:  # la ventana aparece con un fundido corto, como las de macOS
            self.aparecio = True
            if not reducir_movimiento() and not self.testAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen):
                self.setWindowOpacity(0.0)
                self.aparicion = Resorte(self, 0.0, 0.26, 1.0,
                                         al_paso=lambda v: self.setWindowOpacity(max(0.0, min(1.0, v))))
                self.aparicion.ir_a(1.0)

    # armado

    def barra_lateral(self) -> QWidget:
        barra = Lateral()
        barra.setFixedWidth(204)
        caja = QVBoxLayout(barra)
        caja.setContentsMargins(14, 16, 14, 14)
        caja.setSpacing(0)
        marca = QHBoxLayout()
        marca.setSpacing(8)
        self.icono_cabecera = QLabel()
        self.icono_cabecera.setFixedSize(48, 42)
        marca.addWidget(self.icono_cabecera)
        nombre = QVBoxLayout()
        nombre.setSpacing(0)
        nombre.addWidget(QLabel("WaveMascot", objectName="marca"))
        nombre.addWidget(QLabel(f"v{m.__version__}", objectName="detalle"))
        marca.addLayout(nombre, 1)
        caja.addLayout(marca)
        caja.addSpacing(20)
        self.nav = Navegacion([(t(texto), icono) for texto, icono in PAGINAS.values()])
        self.nav.elegido.connect(self.ir_a)
        caja.addWidget(self.nav, 1)
        caja.addSpacing(10)
        self.estado_guardado = TextoSuave(11.5, color="suave")
        caja.addWidget(self.estado_guardado)
        return barra

    def ir_a(self, i: int, animar: bool = True) -> None:
        """Cambia de sección: la marca de la barra se desliza, el título se funde y la página llega desde
        abajo si la nueva está más abajo en la lista (o desde arriba si está más arriba)."""
        i = max(0, min(len(PAGINAS) - 1, i))
        if i == self.pagina:
            return
        direccion = 1 if i > self.pagina else -1
        self.pagina = i
        clave = list(PAGINAS)[i]
        self.nav.elegir(i, animar)
        self.titulo.setText(t(PAGINAS[clave][0]), direccion, animar)
        self.paginas.mostrar(i, direccion, animar, C["fondo"])
        self.columna_vista.plegar(clave == "mascota", animar)

    @staticmethod
    def hoja() -> tuple[QWidget, QVBoxLayout]:
        pagina = QWidget()
        caja = QVBoxLayout(pagina)
        caja.setContentsMargins(0, 4, 14, 28)
        caja.setSpacing(6)
        return pagina, caja

    @staticmethod
    def tarjeta() -> tuple[Grupo, QVBoxLayout]:
        """Una tarjeta con aire adentro, para galerías y botones que no son filas."""
        grupo = Grupo()
        interior = QWidget()
        caja = QVBoxLayout(interior)
        caja.setContentsMargins(12, 12, 12, 12)
        caja.setSpacing(8)
        grupo.agregar(interior)
        return grupo, caja

    # sin la barra del sistema (Windows): la franja de arriba hace de barra para arrastrar la ventana

    def en_cabecera(self, evento) -> bool:
        return (marco.ACTIVO and evento.button() == Qt.MouseButton.LeftButton
                and evento.position().y() < 60)

    def mousePressEvent(self, evento) -> None:
        if self.en_cabecera(evento):
            marco.arrastrar(self)
        else:
            super().mousePressEvent(evento)

    def mouseDoubleClickEvent(self, evento) -> None:
        if self.en_cabecera(evento):
            marco.alternar_maximizada(self)
        else:
            super().mouseDoubleClickEvent(evento)

    def nativeEvent(self, tipo, mensaje):
        # (False, 0) y no super().nativeEvent: en PyQt6 llamar al original rompe el programa.
        respuesta = marco.evento_nativo(self, tipo, mensaje)
        return respuesta if respuesta is not None else (False, 0)

    def franja_version(self) -> QFrame:
        """El cartelito que se abre al tocar la píldora de la versión: qué trae y el botón para actualizar."""
        # Ventana emergente transparente (para las esquinas redondeadas) con el marco dibujado adentro.
        self.franja = QWidget(self)
        self.franja.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.franja.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.franja.setFixedWidth(380)
        exterior = QVBoxLayout(self.franja)
        exterior.setContentsMargins(0, 0, 0, 0)
        marco_franja = QFrame(objectName="franja")
        exterior.addWidget(marco_franja)
        caja = QVBoxLayout(marco_franja)
        caja.setContentsMargins(18, 16, 18, 16)
        caja.setSpacing(6)
        self.franja_titulo = QLabel(objectName="franja_titulo", wordWrap=True)
        self.franja_texto = QLabel(objectName="ayuda", wordWrap=True)
        caja.addWidget(self.franja_titulo)
        caja.addWidget(self.franja_texto)
        caja.addSpacing(6)
        self.boton_actualizar = QPushButton(t("Actualizar ahora"), objectName="primario",
                                            clicked=self.empezar_actualizacion)
        self.boton_novedades = QPushButton(t("Ver novedades"), clicked=lambda: self.abrir_enlace(
            (self.version or {}).get("pagina") or actualizacion.PAGINA))
        self.boton_ahora_no = QPushButton(t("Ahora no"), clicked=self.ignorar_version)
        botones = fila(self.boton_actualizar, self.boton_novedades, self.boton_ahora_no, espacio=6)
        botones.addStretch(1)
        caja.addLayout(botones)
        return self.franja

    def abrir_franja(self) -> None:
        """Abre el cartelito debajo de la píldora de la versión, alineado a su borde derecho."""
        self.franja.adjustSize()
        abajo_derecha = self.boton_novedad.mapToGlobal(self.boton_novedad.rect().bottomRight())
        self.franja.move(abajo_derecha.x() - self.franja.width() + 4, abajo_derecha.y() + 6)
        self.franja.show()
        self.franja.raise_()

    def pagina_avisos(self) -> QWidget:
        pagina, caja = self.hoja()

        caja.addWidget(seccion("Cómo aparece"))
        grupo = Grupo()
        caja.addWidget(grupo)
        self.seg_modo = segmentado({"aviso": "Aviso", "compania": "Compañera"}, self.cambiar_modo)
        grupo.agregar(Fila("Modo", self.seg_modo, info=t(
            "Aviso: aparece desde el borde y se va sola. Compañera: vive sobre el Dock (arrastrala a donde "
            "quieras), crece para avisarte y se duerme si se termina el límite de uso." if m.MAC else
            "Aviso: aparece desde el borde y se va sola. Compañera: vive sobre la barra de tareas (arrastrala a "
            "donde quieras), crece para avisarte y se duerme si se termina el límite de uso.")))
        self.plegable_vida = Plegable(False)  # lo de la compañera: solo se ve en ese modo
        self.vida = {}
        for clave, texto in (("chiquita", "Esperar chiquita, parada sobre el Dock" if m.MAC else
                              "Esperar chiquita, parada sobre la barra de tareas"),
                             ("pasear", "Dar una caminatita de vez en cuando"),
                             ("idle", "Animaciones de reposo al azar"), ("mirada", "Los ojos siguen al cursor")):
            interruptor, fila_vida = opcion(texto, lambda v, c=clave: self.cambiar_grupo("vida", c, v))
            self.vida[clave] = interruptor
            self.plegable_vida.agregar(fila_vida)
        grupo.agregar(self.plegable_vida)
        self.selector = SelectorEsquina()
        self.selector.cambio.connect(lambda e: self.cambiar("esquina", e))
        fila_esquina = grupo.agregar(Fila("Esquina de la pantalla", self.selector, alto=146))
        self.nombre_esquina = fila_esquina.detalle
        self.nombre_esquina.show()
        self.duracion = QSlider(Qt.Orientation.Horizontal, minimum=2, maximum=30)
        self.valor_duracion = valor()
        self.duracion.valueChanged.connect(lambda v: self.cambiar("duracion", v))
        grupo.agregar(Fila("Duración en pantalla", self.duracion, self.valor_duracion))

        caja.addSpacing(16)
        caja.addWidget(seccion("Eventos"))
        grupo = Grupo()
        caja.addWidget(grupo)
        self.sonido = Interruptor()
        self.sonido.toggled.connect(self.al_cambiar_sonido)
        grupo.agregar(Fila("Sonido", self.sonido))
        self.volumen = QSlider(Qt.Orientation.Horizontal, minimum=0, maximum=100, singleStep=5, pageStep=10)
        self.valor_volumen = valor()
        self.volumen.valueChanged.connect(lambda v: self.cambiar("volumen", v))
        self.volumen.sliderReleased.connect(self.escuchar)
        self.fila_volumen = grupo.agregar(Fila("Volumen", self.volumen, self.valor_volumen))
        nombres = {"ninguno": t("Sin sonido"), **{c: t(n) for c, (n, _) in sprites.SONIDOS.items()}}
        self.tabla = grupo.agregar(TablaEventos(nombres))
        self.tabla.elegido.connect(self.ver_estado)
        self.pantalla_estado, self.sonidos_evento, self.cel_estados = self.tabla.pantalla, self.tabla.sonido, \
            self.tabla.celular
        for estado in ESTADOS_ORDEN:
            self.tabla.pantalla[estado].toggled.connect(
                lambda v, e=estado: self.cambiar_grupo("eventos", m.EVENTO_POR_ESTADO[e], v))
            combo = self.tabla.sonido[estado]
            combo.currentIndexChanged.connect(lambda _, e=estado, cb=combo: self.cambiar_sonido(e, cb.currentData()))
            self.tabla.escuchar[estado].clicked.connect(lambda _=False, e=estado: self.escuchar(e))
            if estado in self.tabla.celular:
                self.tabla.celular[estado].toggled.connect(lambda v, e=estado: self.cambiar_estado_celular(e, v))
        for estado in ("limite", "error"):  # los dos salen del mismo hook (StopFailure)
            self.tabla.pantalla[estado].setToolTip(t("Límite y Error se prenden y se apagan juntos en la pantalla."))
        self.fila_sin_celular = grupo.agregar(Fila(
            "", QPushButton(t("Conectar con Telegram"), objectName="enlace", cursor=Qt.CursorShape.PointingHandCursor,
                            clicked=lambda: self.ir_a(list(PAGINAS).index("celular"))),
            detalle=t("Para recibir avisos en el celular, conectá Telegram.")))
        caja.addWidget(ayuda("Tocá un evento para verlo en la vista previa."))

        caja.addSpacing(16)
        caja.addWidget(seccion("Mostrar en el cartel"))
        grupo = Grupo()
        caja.addWidget(grupo)
        self.contenido = {}
        for clave, texto in NOMBRES_CONTENIDO.items():
            interruptor, fila_contenido = opcion(texto, lambda v, c=clave: self.cambiar_grupo("contenido", c, v))
            self.contenido[clave] = interruptor
            grupo.agregar(fila_contenido)
        self.enfocar, fila_enfocar = opcion("Botón «Ir a la terminal» en el cartel",
                                            lambda v: self.cambiar("boton_enfocar", v))
        grupo.agregar(fila_enfocar)

        caja.addSpacing(16)
        caja.addWidget(seccion("Acciones"))
        grupo = Grupo()
        caja.addWidget(grupo)
        self.permisos, fila_permisos = opcion(
            "Aprobar o denegar permisos desde la mascota", lambda v: self.cambiar("permisos_desde_mascota", v),
            info=t("Si no elegís a tiempo, decide el diálogo de permisos de siempre. Las preguntas "
                   "(AskUserQuestion) se contestan en la terminal."))
        grupo.agregar(fila_permisos)
        self.espera = QSlider(Qt.Orientation.Horizontal, minimum=5, maximum=120, singleStep=5, pageStep=15)
        self.valor_espera = valor()
        self.espera.valueChanged.connect(lambda v: self.cambiar("espera_permiso", v))
        self.fila_espera = grupo.agregar(Fila("Esperar mi respuesta", self.espera, self.valor_espera))

        caja.addSpacing(16)
        self.desplegable_mensajes = Desplegable("Mensajes")
        self.textos = {}
        for evento, titulo in (("Stop", "Cuando termina (Stop)"), ("Notification", "Cuando necesita algo (Notification)")):
            campo = QLineEdit(placeholderText=t("Vacío = texto automático"), clearButtonEnabled=True)
            campo.textChanged.connect(lambda texto, ev=evento: self.cambiar_mensaje(ev, texto))
            self.textos[evento] = campo
            self.desplegable_mensajes.agregar_fila(Fila(titulo, campo, debajo=True))
        self.desplegable_mensajes.agregar_fila(Fila("", alto=38, detalle=t(
            "Podés usar {mensaje} (el texto original del aviso, por ejemplo «Necesito permiso para usar Bash»), "
            "{proyecto} y {chat}.")))
        caja.addWidget(self.desplegable_mensajes)

        caja.addSpacing(10)
        self.desplegable_silencio = Desplegable("No molestar")
        self.no_molestar = Interruptor()
        self.no_molestar.toggled.connect(lambda v: self.cambiar_grupo("no_molestar", "activo", v))
        self.desde, self.hasta = QTimeEdit(displayFormat="HH:mm"), QTimeEdit(displayFormat="HH:mm")
        for hora in (self.desde, self.hasta):  # sin los botoncitos: se escribe o se usa la ruedita
            hora.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            hora.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hora.setFixedWidth(66)
            hora.setToolTip(t("Escribí la hora o cambiala con la ruedita del mouse o las flechas"))
        self.desde.timeChanged.connect(lambda h: self.cambiar_grupo("no_molestar", "desde", h.toString("HH:mm")))
        self.hasta.timeChanged.connect(lambda h: self.cambiar_grupo("no_molestar", "hasta", h.toString("HH:mm")))
        self.desplegable_silencio.agregar_fila(Fila("Silenciar entre", self.desde, QLabel(t("y")), self.hasta,
                                                    self.no_molestar))
        self.pantalla_completa, fila_pc = opcion(
            "Silenciar si hay algo en pantalla completa (juegos, videos, presentaciones)",
            lambda v: self.cambiar_grupo("no_molestar", "pantalla_completa", v))
        self.desplegable_silencio.agregar_fila(fila_pc)
        self.enfocada, fila_foco = opcion("No avisar si la terminal o el editor de Claude ya tiene el foco",
                                          lambda v: self.cambiar("omitir_si_enfocada", v))
        self.desplegable_silencio.agregar_fila(fila_foco)
        self.umbral = QSlider(Qt.Orientation.Horizontal, minimum=0, maximum=300, singleStep=5, pageStep=30)
        self.valor_umbral = valor()
        self.umbral.valueChanged.connect(lambda v: self.cambiar("umbral_segundos", v))
        self.desplegable_silencio.agregar_fila(Fila("Avisar «terminó» solo si la tarea duró más de", self.umbral,
                                                    self.valor_umbral, debajo=True))
        caja.addWidget(self.desplegable_silencio)
        caja.addStretch(1)
        return pagina

    def pagina_mascota(self) -> QWidget:
        """El probador: la mascota grande arriba y, abajo, cada cosa que se le puede cambiar en su pestaña."""
        pagina, caja = self.hoja()
        caja.setSpacing(10)

        # Wave Classic (la mascota dibujada, con sus estilos). Wave NextGen (personajes más grandes, con sus
        # propias animaciones y sonidos) se ve en gris: todavía no se puede elegir.
        arriba = QHBoxLayout()
        arriba.setSpacing(8)
        self.seg_familia = segmentado({"clasico": "Wave Classic", "nextgen": "Wave NextGen"}, lambda _: None)
        self.seg_familia.desactivar("nextgen", t("Próximamente"))
        arriba.addWidget(self.seg_familia)
        arriba.addWidget(QLabel(t("Próximamente"), objectName="pronto", alignment=Qt.AlignmentFlag.AlignCenter))
        arriba.addStretch(1)
        self.botones_vestuario = QWidget()
        botones = QHBoxLayout(self.botones_vestuario)
        botones.setContentsMargins(0, 0, 0, 0)
        botones.setSpacing(6)
        botones.addWidget(QPushButton(t("Al azar"), clicked=self.al_azar))
        botones.addWidget(QPushButton(t("Sacar todo"), clicked=self.sacar_todo))
        arriba.addWidget(self.botones_vestuario)
        caja.addLayout(arriba)

        self.escenario = Escenario()
        self.escenario.anterior.connect(lambda: self.ciclar(-1))
        self.escenario.siguiente.connect(lambda: self.ciclar(1))
        caja.addWidget(self.escenario)
        caja.addWidget(ayuda("La mascota de siempre, dibujada a tu gusto: estilo, color, vestuario o una imagen "
                             "propia."))
        grupo = Grupo()
        self.tamano = QSlider(Qt.Orientation.Horizontal, minimum=m.TAMANOS[0], maximum=m.TAMANOS[1], pageStep=1)
        self.valor_tamano = valor()
        self.valor_tamano.setFixedWidth(120)
        self.tamano.valueChanged.connect(lambda v: self.cambiar("tamano", v))
        grupo.agregar(Fila("Tamaño", self.tamano, self.valor_tamano))
        caja.addWidget(grupo)
        caja.addSpacing(8)

        clasico = QWidget()
        cc = QVBoxLayout(clasico)
        cc.setContentsMargins(0, 0, 0, 0)
        cc.setSpacing(10)
        self.seg_partes = segmentado(PARTES, self.ver_parte, suave=True)
        cc.addWidget(self.seg_partes, 0, Qt.AlignmentFlag.AlignLeft)
        self.aviso_imagen = ayuda("Estás usando una imagen propia: elegí cualquier prenda o color para "
                                  "volver a la mascota dibujada.")
        cc.addWidget(self.aviso_imagen)
        self.galerias = {}
        self.partes = Paginas(horizontal=True, distancia=30)
        for clave in PARTES:
            self.partes.agregar(self.parte_probador(clave))
        cc.addWidget(self.partes)
        caja.addWidget(clasico)
        caja.addStretch(1)
        return pagina

    def parte_probador(self, clave: str) -> QWidget:
        """La tarjeta de una pestaña del probador: estilo, color, cada parte del vestuario o una imagen propia."""
        tarjeta, caja = self.tarjeta()
        if clave == "estilo":
            cabeza = QHBoxLayout()
            cabeza.setSpacing(6)
            cabeza.addWidget(QLabel(t("BETA"), objectName="beta"))
            cabeza.addWidget(BotonInfo(t("Cambia la cara de la mascota y cómo aparece, festeja y se va. El vestuario "
                                         "se mantiene.")))
            cabeza.addStretch(1)
            caja.addLayout(cabeza)
            self.galeria_estilos = Galeria(QSize(96, 84), ancho=118)
            self.galeria_estilos.elegido.connect(self.cambiar_estilo)
            caja.addWidget(self.galeria_estilos)
        elif clave == "color":
            cabeza = QHBoxLayout()
            cabeza.setSpacing(6)
            self.nombre_color = QLabel()
            self.color_de = QLabel(objectName="detalle")
            cabeza.addWidget(self.nombre_color)
            cabeza.addWidget(self.color_de)
            cabeza.addWidget(BotonInfo(t("Cada estilo guarda su propio color: cambiar este no cambia el de los otros.")))
            cabeza.addStretch(1)
            caja.addLayout(cabeza)
            self.grupo_color = QButtonGroup(self)
            self.muestras = {}
            filas_color = [[]]  # por tono, y los neutros en otra fila
            for color_id in sprites.ORDEN_COLORES:
                if color_id is None:
                    filas_color.append([])
                else:
                    filas_color[-1].append(color_id)
            for colores in filas_color:
                muestras = QHBoxLayout()
                muestras.setSpacing(4)
                for color_id in colores:
                    muestra = MuestraColor(color_id)
                    muestra.clicked.connect(lambda _, c=color_id: self.cambiar_aspecto("color", c))
                    self.grupo_color.addButton(muestra)
                    self.muestras[color_id] = muestra
                    muestras.addWidget(muestra)
                muestras.addStretch(1)
                caja.addLayout(muestras)
            self.bloque_piel = QWidget()  # solo el Ninja: la cara se le ve por la franja de la máscara
            piel = QVBoxLayout(self.bloque_piel)
            piel.setContentsMargins(0, 8, 0, 0)
            piel.setSpacing(6)
            cabeza_piel = QHBoxLayout()
            cabeza_piel.setSpacing(6)
            cabeza_piel.addWidget(seccion("Piel"))
            self.nombre_piel = QLabel(objectName="detalle")
            cabeza_piel.addWidget(self.nombre_piel)
            cabeza_piel.addStretch(1)
            piel.addLayout(cabeza_piel)
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
            fila_piel.addStretch(1)
            piel.addLayout(fila_piel)
            caja.addWidget(self.bloque_piel)
        elif clave == "imagen":
            self.galeria_imagenes = Galeria(QSize(72, 63), ancho=118)
            self.galeria_imagenes.elegido.connect(self.elegir_imagen)
            caja.addWidget(self.galeria_imagenes)
            botones = QHBoxLayout()
            botones.addWidget(QPushButton(t("Agregar PNG/GIF…"), clicked=self.agregar_imagen))
            self.quitar = QPushButton(t("Quitar"), clicked=self.quitar_imagen)
            botones.addWidget(self.quitar)
            botones.addWidget(BotonInfo(t("Una imagen propia reemplaza a la mascota dibujada en los tres estados (los "
                                          "GIF animados también andan). Se guarda una copia en ~/.wavemascot/imagenes.")))
            botones.addStretch(1)
            caja.addLayout(botones)
        else:  # cabeza, ropa o accesorio
            lados = {"cabeza": QSize(64, 48), "ropa": QSize(72, 50), "accesorio": QSize(64, 36)}
            galeria = Galeria(lados[clave])
            galeria.elegido.connect(lambda opcion_elegida, p=clave: self.cambiar_aspecto(p, opcion_elegida))
            self.galerias[clave] = galeria
            caja.addWidget(galeria)
        return tarjeta

    def pagina_celular(self) -> QWidget:
        pagina, caja = self.hoja()

        caja.addWidget(seccion("Telegram"))
        grupo = Grupo()
        caja.addWidget(grupo)
        self.cel_activo = Interruptor()
        self.cel_activo.toggled.connect(lambda v: self.cambiar_grupo("celular", "activo", v))
        grupo.agregar(Fila("Mandarme los avisos a Telegram", self.cel_activo, detalle=t(
            "Te manda los avisos a Telegram, con Wave animada: te enterás aunque no estés en la compu. Te escribe "
            "el bot oficial, @WaveNotificationBot.")))
        conexion = QWidget()
        cx = QVBoxLayout(conexion)
        cx.setContentsMargins(16, 10, 14, 12)
        cx.setSpacing(8)
        self.cel_estado = QLabel(objectName="valor", wordWrap=True)
        cx.addWidget(self.cel_estado)

        self.cel_desconectado = QWidget()
        boton = fila(QPushButton(t("Conectar con Telegram"), objectName="primario", clicked=self.conectar_telegram))
        boton.setContentsMargins(0, 0, 0, 0)
        boton.addStretch(1)
        self.cel_conectar = boton.itemAt(0).widget()
        self.cel_desconectado.setLayout(boton)
        cx.addWidget(self.cel_desconectado)

        # Mientras espera: el código, el botón que abre el bot y cómo seguir.
        self.cel_esperando = QWidget()
        espera = QVBoxLayout(self.cel_esperando)
        espera.setContentsMargins(0, 0, 0, 0)
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
        cx.addWidget(self.cel_esperando)

        self.cel_conectado = QWidget()
        conectado = fila(QPushButton(t("Mandar un aviso de prueba"), clicked=self.probar_telegram),
                         QPushButton(t("Desconectar"), clicked=self.desconectar_telegram), espacio=8)
        conectado.setContentsMargins(0, 0, 0, 0)
        conectado.addStretch(1)
        self.cel_conectado.setLayout(conectado)
        cx.addWidget(self.cel_conectado)
        grupo.agregar(conexion)

        caja.addSpacing(16)
        caja.addWidget(seccion("Cuándo"))
        grupo = Grupo()
        caja.addWidget(grupo)
        self.cel_ausente, fila_ausente = opcion(
            "Solo si no estoy usando la compu", lambda v: self.cambiar_grupo("celular", "solo_ausente", v),
            info=t("Si estás en la compu te avisa solo la mascota, así no te llega todo dos veces. El silencio y el "
                   "«no molestar» también valen para Telegram."))
        grupo.agregar(fila_ausente)
        self.cel_minutos = QSlider(Qt.Orientation.Horizontal, minimum=1, maximum=30, pageStep=5)
        self.cel_valor_minutos = valor()
        self.cel_minutos.valueChanged.connect(lambda v: self.cambiar_grupo("celular", "minutos", v))
        self.fila_minutos = grupo.agregar(Fila("Sin tocar el mouse ni el teclado por", self.cel_minutos,
                                               self.cel_valor_minutos))

        caja.addSpacing(16)
        caja.addWidget(seccion("Avisos"))
        grupo = Grupo()
        caja.addWidget(grupo)
        self.cel_gif, fila_gif = opcion("Con Wave animada (GIF)", lambda v: self.cambiar_grupo("celular", "gif", v))
        grupo.agregar(fila_gif)
        grupo.agregar(Fila("Qué avisos te llegan", QPushButton(
            t("Elegir en Avisos"), objectName="enlace", cursor=Qt.CursorShape.PointingHandCursor,
            clicked=lambda: self.ir_a(list(PAGINAS).index("avisos")))))

        caja.addSpacing(16)
        caja.addWidget(seccion("Permisos"))
        grupo = Grupo()
        caja.addWidget(grupo)
        self.cel_permisos, fila_permisos = opcion(
            "Aprobar o denegar permisos desde Telegram", lambda v: self.cambiar_grupo("celular", "permisos", v),
            info=t("Te llega el comando completo con los botones Permitir y Denegar. Si no contestás a tiempo, queda "
                   "el diálogo de siempre en la terminal. Las preguntas de Claude se contestan en la terminal."))
        grupo.agregar(fila_permisos)
        self.cel_espera = QSlider(Qt.Orientation.Horizontal, minimum=1, maximum=m.ESPERA_TELEGRAM_MAX // 60, pageStep=1)
        self.cel_valor_espera = valor()
        self.cel_espera.valueChanged.connect(lambda v: self.cambiar_grupo("celular", "espera_permisos", v * 60))
        self.fila_cel_espera = grupo.agregar(Fila("Esperar mi respuesta", self.cel_espera, self.cel_valor_espera))
        caja.addSpacing(8)
        caja.addWidget(ayuda("Los avisos pasan por el servidor de WaveMascot para llegar a Telegram; no se guardan. "
                             "Para dejar de recibirlos: Desconectar, o mandale /stop al bot."))
        caja.addStretch(1)
        return pagina

    def pagina_general(self) -> QWidget:
        pagina, caja = self.hoja()

        caja.addWidget(seccion("Apariencia"))
        grupo = Grupo()
        caja.addWidget(grupo)
        dpr = self.devicePixelRatioF()
        self.seg_idioma = Segmentos(dict(idiomas.IDIOMAS), {c: bandera(c, dpr) for c in idiomas.IDIOMAS}, suave=True)
        self.seg_idioma.elegir(idiomas.actual(), animar=False)
        # un momento para que se vea la marca llegar: después la ventana se rearma con los textos nuevos
        # (un solo temporizador: si se tocan dos idiomas seguidos, vale el último)
        self.timer_idioma = QTimer(self, singleShot=True, interval=280,
                                   timeout=lambda: self.cambiar_idioma(self.seg_idioma.actual))
        self.seg_idioma.elegido.connect(lambda _: self.timer_idioma.start())
        grupo.agregar(Fila("Idioma", self.seg_idioma))
        self.seg_tema = segmentado({"oscuro": "Oscuro", "claro": "Claro", "acento": "Acento"}, self.cambiar_tema)
        grupo.agregar(Fila("Tema", self.seg_tema, info=t(
            "El cartel del aviso y esta ventana. Acento pinta el cartel con el color de cada estado.")))

        caja.addSpacing(16)
        caja.addWidget(seccion("Ícono en la barra de menús" if m.MAC else "Ícono junto al reloj"))
        grupo = Grupo()
        caja.addWidget(grupo)
        self.inicio, fila_inicio = opcion(
            "Abrir al iniciar sesión" if m.MAC else "Abrir al iniciar Windows", self.cambiar_inicio,
            info=t("Click en el ícono de la mascota (en la barra de menús) para volver a estos ajustes, silenciar "
                   "los avisos o cambiar de modo." if m.MAC else
                   "Click en el ícono de la mascota (junto al reloj) para volver a estos ajustes; click derecho "
                   "para silenciar o cambiar de modo."))
        grupo.agregar(fila_inicio)

        caja.addSpacing(16)
        caja.addWidget(seccion("Actualizaciones"))
        grupo = Grupo()
        caja.addWidget(grupo)
        self.buscar_versiones, fila_versiones = opcion("Avisarme cuando haya una versión nueva",
                                                       lambda v: self.cambiar_grupo("actualizaciones", "buscar", v))
        grupo.agregar(fila_versiones)
        self.boton_buscar = QPushButton(t("Buscar ahora"), clicked=lambda: self.buscar_version(forzar=True))
        fila_buscar = grupo.agregar(Fila("", self.boton_buscar, detalle=" "))
        self.estado_version = fila_buscar.detalle
        self.estado_version.show()

        caja.addSpacing(22)
        caja.addWidget(QPushButton(t("Restablecer valores"), clicked=self.restablecer), 0, Qt.AlignmentFlag.AlignLeft)
        caja.addStretch(1)
        return pagina

    def panel_vista(self) -> QWidget:
        self.columna_vista = ColumnaVista(ANCHO_VISTA)
        columna = QVBoxLayout(self.columna_vista.interior)
        columna.setContentsMargins(22, 0, 0, 0)
        columna.setSpacing(10)
        columna.addWidget(seccion("Vista previa"))
        self.vista = VistaPrevia()
        columna.addWidget(self.vista, 1)
        self.probar = QPushButton(objectName="primario", clicked=self.probar_aviso)
        self.probar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.probar.setToolTip(t("Muestra el aviso real en tu pantalla, con lo guardado."))
        columna.addWidget(self.probar)
        return self.columna_vista

    def ver_parte(self, clave: str) -> None:
        """Otra pestaña del probador: la tarjeta nueva llega desde el lado hacia el que se movió la marca."""
        claves = list(PARTES)
        antes, ahora = claves.index(self.parte), claves.index(clave)
        self.parte = clave
        self.partes.mostrar(ahora, 1 if ahora > antes else -1, True, C["fondo"])

    def ciclar(self, paso: int) -> None:
        """Las flechas del probador: el estilo de al lado."""
        estilos = list(sprites.ESTILOS)
        actual = self.config["aspecto"]["estilo"]
        i = estilos.index(actual) if actual in estilos else 0
        self.cambiar_estilo(estilos[(i + paso) % len(estilos)])

    # datos <-> controles

    def cargar_en_controles(self) -> None:
        c = self.config
        grupos = {"contenido": self.contenido, "vida": self.vida}
        controles = [self.duracion, self.sonido, self.volumen, self.tamano, self.inicio, self.no_molestar,
                     self.desde, self.hasta, self.pantalla_completa, self.enfocada, self.umbral, self.permisos,
                     self.espera, self.enfocar, *self.textos.values(), *self.sonidos_evento.values(),
                     self.cel_activo, self.cel_ausente, self.cel_minutos, self.cel_gif, self.buscar_versiones,
                     self.cel_permisos, self.cel_espera,
                     *self.cel_estados.values(), *self.pantalla_estado.values(),
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
        for estado, interruptor in self.pantalla_estado.items():
            interruptor.setChecked(c["eventos"][m.EVENTO_POR_ESTADO[estado]])
        self.seg_modo.elegir(c["modo"], animar=False)
        self.seg_tema.elegir(c["tema"], animar=False)
        self.plegable_vida.abrir(c["modo"] == "compania", animar=False)
        self.tabla.elegir(self.estado_vista, animar=False)
        self.buscar_versiones.setChecked(c["actualizaciones"]["buscar"])
        cel = c["celular"]
        self.cel_activo.setChecked(cel["activo"])
        self.cel_ausente.setChecked(cel["solo_ausente"])
        self.cel_minutos.setValue(cel["minutos"])
        self.cel_gif.setChecked(cel["gif"])
        self.cel_permisos.setChecked(cel["permisos"])
        self.cel_espera.setValue(round(cel["espera_permisos"] / 60))
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
        if usando_imagen:
            icono = miniatura_imagen(m.IMAGENES / self.config["imagen"], QSize(48, 42), dpr)
        else:
            icono = miniatura(aspecto, "entera", dpr, escala=1)
        self.icono_cabecera.setPixmap(icono)
        if usando_imagen:
            nombre = Path(self.config["imagen"]).stem
        else:
            nombre = f"{t(sprites.ESTILOS[aspecto['estilo']])} · {t(sprites.COLORES[aspecto['color']][0])}"
        self.escenario.mostrar(aspecto, self.config["imagen"], nombre)

    def actualizar_etiquetas(self) -> None:
        c = self.config
        self.nombre_esquina.setText(t(NOMBRES_ESQUINA[c["esquina"]]))
        self.valor_duracion.setText(f"{round(c['duracion'])} s")
        self.valor_volumen.setText(f"{c['volumen']} %")
        self.fila_volumen.setEnabled(c["sonido"])
        self.valor_tamano.setText(f"{t(NOMBRES_TAMANO.get(c['tamano'], ''))} · {m.LADO_ARTE * c['tamano']} px")
        self.nombre_color.setText("" if c["imagen"] else t(sprites.COLORES[c["aspecto"]["color"]][0]))
        self.color_de.setText("· " + t("de {estilo}", estilo=t(sprites.ESTILOS[c["aspecto"]["estilo"]])))
        self.nombre_piel.setText(t(sprites.PIELES[c["aspecto"]["piel"]][0]))
        self.probar.setText(t("Probar aviso «{estado}»", estado=t(NOMBRES_ESTADO[self.estado_vista])))
        self.valor_umbral.setText(t("Siempre") if not c["umbral_segundos"] else m.formato_duracion(c["umbral_segundos"]))
        self.valor_espera.setText(f"{c['espera_permiso']} s")
        self.fila_espera.setEnabled(c["permisos_desde_mascota"])
        for control in (self.desde, self.hasta):
            control.setEnabled(c["no_molestar"]["activo"])
        self.plegable_vida.abrir(c["modo"] == "compania", animar=self.isVisible())
        for estado in ESTADOS_ORDEN:  # Límite y Error comparten interruptor en la pantalla
            interruptor = self.pantalla_estado[estado]
            interruptor.blockSignals(True)
            interruptor.setChecked(c["eventos"][m.EVENTO_POR_ESTADO[estado]])
            interruptor.blockSignals(False)
            self.sonidos_evento[estado].setEnabled(c["sonido"])
            self.tabla.escuchar[estado].setEnabled(c["sonido"])
        self.tabla.cabeceras["sonido"].setEnabled(c["sonido"])
        nm = c["no_molestar"]
        self.desplegable_silencio.cabecera.poner_resumen(f"{nm['desde']} – {nm['hasta']}" if nm["activo"] else "")
        self.actualizar_celular()

    def actualizar_celular(self) -> None:
        cel = self.config["celular"]
        conectado = bool(cel["llave"] and cel["conectado"])
        self.cel_desconectado.setVisible(not conectado and not self.codigo)
        self.cel_esperando.setVisible(not conectado and bool(self.codigo))
        self.cel_conectado.setVisible(conectado)
        self.cel_activo.setEnabled(conectado)
        self.fila_sin_celular.setVisible(not conectado)
        self.tabla.cabeceras["celular"].setEnabled(conectado)
        for interruptor in self.cel_estados.values():
            interruptor.setEnabled(conectado)
        self.cel_codigo.setText(celular.codigo_visible(self.codigo))
        if conectado:
            self.cel_estado.setText(t("✓ Conectado al Telegram de {nombre}", nombre=cel["nombre"]) if cel["nombre"]
                                    else t("✓ Conectado a Telegram"))
        elif not self.codigo and self.cel_conectar.isEnabled():
            self.cel_estado.setText(t("Sin conectar: tocá el botón, se abre Telegram y tocás «Iniciar»."))
        self.cel_valor_minutos.setText(f"{cel['minutos']} min")
        self.cel_valor_espera.setText(f"{round(cel['espera_permisos'] / 60)} min")
        self.fila_cel_espera.setEnabled(cel["permisos"])
        self.fila_minutos.setEnabled(cel["solo_ausente"])

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
        # Guardar y abrir la compañera recién cuando terminó de moverse la ventana: lanzar otro programa
        # traba un instante y se notaba como un tirón justo al empezar la animación. (Si se cambia de modo
        # varias veces seguidas, cuenta el último; si se cierra la ventana antes, se aplica al cerrar.)
        self.timer_modo.start()

    def aplicar_modo(self) -> None:
        self.timer_modo.stop()
        if self.timer_guardar.isActive():  # la compañera y el ícono leen config.json
            self.guardar()
        if self.config["modo"] == "compania":  # si ya está abierta, la nueva se cierra sola
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
        self.tabla.elegir(estado)
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
        self.config["actualizaciones"]["ignorada"] = ""
        aplicar_tema(self.config["tema"], self.config["aspecto"]["estilo"])
        self.cargar_en_controles()
        self.cambio()

    def sincronizar(self) -> None:
        """El modo también se cambia desde el ícono o el menú de la compañera: se refleja acá."""
        disco = m.cargar_config()
        if disco["modo"] != self.config["modo"] and not self.timer_guardar.isActive():
            self.config["modo"] = disco["modo"]
            self.seg_modo.elegir(disco["modo"])
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

    # versión nueva

    def buscar_version(self, forzar: bool = False) -> None:
        self.estado_version.setText(t("Buscando…") if forzar else t("Tenés la versión {version}.",
                                                                     version=m.__version__))
        self.boton_buscar.setEnabled(False)

        def correr():
            try:
                tipo, resultado = "buscar", actualizacion.buscar(forzar)
            except actualizacion.ErrorActualizacion as e:
                tipo, resultado = "buscar_error", e
            try:
                self.respuesta_version.emit(tipo, resultado)
            except RuntimeError:
                pass
        threading.Thread(target=correr, daemon=True).start()

    def mostrar_franja(self, info: dict) -> None:
        self.version = info
        self.franja_titulo.setText(t("Hay una versión nueva: {version}", version=info["version"]))
        novedades = info.get("novedades") or []
        self.franja_texto.setText("\n".join(f"• {n}" for n in novedades) if novedades else
                                  t("Tenés la {version}. Mirá qué trae en «Ver novedades».", version=m.__version__))
        self.boton_actualizar.setText(t("Actualizar ahora") if actualizacion.se_instala_sola(info) else t("Descargar"))
        self.boton_novedad.setToolTip(t("Hay una versión nueva: {version}", version=info["version"]))
        self.boton_novedad.poner_version(info["version"])
        self.boton_novedad.setVisible(True)

    def empezar_actualizacion(self) -> None:
        """Baja la versión nueva y la instala (Windows); en macOS o desde el código, abre la descarga."""
        if self.actualizando:
            return
        self.actualizando = True
        self.boton_novedad.setVisible(True)
        QTimer.singleShot(0, self.abrir_franja)  # recién armada la ventana, el botón ya tiene su lugar
        self.franja_titulo.setText(t("Buscando la versión nueva…"))
        self.franja_texto.setText("")
        for boton in (self.boton_actualizar, self.boton_novedades, self.boton_ahora_no):
            boton.setEnabled(False)
        info = self.version

        def correr():
            try:
                datos = info or actualizacion.buscar(forzar=True)
                if not datos:
                    tipo, resultado = "al_dia", None
                elif not actualizacion.se_instala_sola(datos):
                    tipo, resultado = "pagina", datos
                else:
                    self.respuesta_version.emit("bajando", datos)
                    ruta = actualizacion.descargar(datos, lambda f: self.respuesta_version.emit("progreso", f))
                    tipo, resultado = "bajado", ruta
            except actualizacion.ErrorActualizacion as e:
                tipo, resultado = "actualizar_error", e
            try:
                self.respuesta_version.emit(tipo, resultado)
            except RuntimeError:
                pass
        threading.Thread(target=correr, daemon=True).start()

    def al_responder_version(self, tipo: str, resultado) -> None:
        if tipo == "buscar":
            self.boton_buscar.setEnabled(True)
            if resultado:
                self.estado_version.setText(t("Tenés la {actual}; hay una nueva: {version}.", actual=m.__version__,
                                              version=resultado["version"]))
                if not self.actualizando:
                    self.mostrar_franja(resultado)
            else:
                self.estado_version.setText(t("Tenés la versión {version}: es la última.", version=m.__version__))
        elif tipo == "buscar_error":
            self.boton_buscar.setEnabled(True)
            self.estado_version.setText(t("Tenés la versión {version}. No pude buscar si hay una nueva ({error}).",
                                          version=m.__version__, error=resultado))
        elif tipo == "bajando":
            self.version = resultado
            self.franja_titulo.setText(t("Bajando la versión {version}…", version=resultado["version"]))
        elif tipo == "progreso":
            self.franja_texto.setText(t("{porcentaje} % · cuando termine, WaveMascot se cierra y vuelve a abrir sola.",
                                        porcentaje=round(resultado * 100)))
            self.boton_novedad.setToolTip(self.franja_texto.text())
        elif tipo == "bajado":
            self.franja_titulo.setText(t("Instalando la versión {version}…", version=self.version["version"]))
            self.franja_texto.setText(t("WaveMascot se cierra y vuelve a abrir sola en unos segundos."))
            self.guardar()
            actualizacion.instalar(resultado)
            QTimer.singleShot(1500, QApplication.quit)  # el instalador reemplaza también esta ventana
        elif tipo == "pagina":
            self.abrir_enlace(resultado.get("url") or resultado.get("pagina") or actualizacion.PAGINA)
            self.terminar_actualizacion(resultado)
        elif tipo == "al_dia":
            self.actualizando = False
            self.franja.hide()
            self.boton_novedad.setVisible(False)
            self.estado_version.setText(t("Tenés la versión {version}: es la última.", version=m.__version__))
        elif tipo == "actualizar_error":
            self.terminar_actualizacion(self.version)
            self.franja_titulo.setText(t("No se pudo actualizar"))
            self.franja_texto.setText(t("{error}. Probá de nuevo o bajala desde «Ver novedades».", error=resultado))

    def terminar_actualizacion(self, info) -> None:
        self.actualizando = False
        for boton in (self.boton_actualizar, self.boton_novedades, self.boton_ahora_no):
            boton.setEnabled(True)
        if info:
            self.mostrar_franja(info)

    def ignorar_version(self) -> None:
        if self.version:
            self.config["actualizaciones"]["ignorada"] = self.version["version"]
            self.cambio()
        self.franja.hide()
        self.boton_novedad.setVisible(False)

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
        if self.timer_modo.isActive():  # también al rearmarse por un cambio de idioma
            self.aplicar_modo()
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
        s.write(b"actualizar\n" if "--actualizar" in sys.argv[1:] else b"mostrar\n")
        s.flush()
        s.waitForBytesWritten(300)
        return 0
    servidor = QLocalServer()
    m.escuchar(servidor, CANAL_AJUSTES)

    actual = {}

    def abrir(anterior: Ajustes | None = None) -> None:
        """Arma la ventana; al cambiar de idioma se rearma en el mismo lugar y en la misma pestaña."""
        ventana = Ajustes()
        ventana.aparecio = anterior is not None  # rearmada: aparece de una, en el lugar de la anterior
        ventana.idioma_cambiado.connect(lambda idioma: (traducir_qt(app, idioma), abrir(ventana)))
        if anterior is None:
            ventana.resize(1080, 760)
        else:
            ventana.setGeometry(anterior.normalGeometry() if anterior.isMaximized() else anterior.geometry())
            ventana.ir_a(anterior.pagina, animar=False)
            if anterior.isMaximized():
                ventana.setWindowState(Qt.WindowState.WindowMaximized)
        actual["ventana"] = ventana
        traer_al_frente(ventana)
        if anterior is not None:  # recién ahora: si se cerrara antes, la app terminaría
            anterior.close()
            anterior.deleteLater()

    def al_conectarse() -> None:
        conexion = servidor.nextPendingConnection()
        traer_al_frente(actual["ventana"])
        if conexion and (conexion.bytesAvailable() or conexion.waitForReadyRead(300)):
            if bytes(conexion.readAll()).startswith(b"actualizar"):
                actual["ventana"].empezar_actualizacion()

    servidor.newConnection.connect(al_conectarse)
    ventanas.al_reabrir(lambda: traer_al_frente(actual["ventana"]))  # macOS: click en el Dock o abrir la app
    abrir()
    m.log("[ajustes] ventana abierta")
    if "--actualizar" in sys.argv[1:]:  # desde el cartel de Wave o el menú del ícono
        actual["ventana"].empezar_actualizacion()
    return app.exec()


if __name__ == "__main__":
    try:
        codigo = ejecutar_ventana()
    except Exception:
        m.log("[ajustes] error:\n" + traceback.format_exc())
        codigo = 1
    os._exit(codigo)
