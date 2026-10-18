#!/usr/bin/env python3
"""Centro de ajustes de la mascota de Claude Code.

Uso:  pythonw ajustes.py   (o click en el ícono de la mascota junto al reloj)

Se abre en un proceso aparte y vuelve enseguida. Los cambios se guardan solos en
~/.wavemascot/config.json y mascota.py los lee en cada aviso.
"""

from __future__ import annotations

import json
import os
import random
import re
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mascota as m  # noqa: E402
import sprites  # noqa: E402

if __name__ == "__main__" and "--ventana" not in sys.argv[1:]:
    # Lanzador: abre la ventana desacoplada y sale sin cargar Qt.
    m.lanzar_desacoplado([str(Path(__file__).resolve()), "--ventana"])
    os._exit(0)

from PyQt6.QtCore import QElapsedTimer, QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal  # noqa: E402
from PyQt6.QtGui import (QColor, QIcon, QImageReader, QKeySequence, QLinearGradient, QPainter,  # noqa: E402
                         QPainterPath, QPalette, QPen, QPixmap, QShortcut)
from PyQt6.QtNetwork import QLocalServer, QLocalSocket  # noqa: E402
from PyQt6.QtCore import QFileSystemWatcher, QTime  # noqa: E402
from PyQt6.QtWidgets import (QAbstractButton, QAbstractSpinBox, QApplication, QButtonGroup, QCheckBox, QComboBox,  # noqa: E402
                             QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QMessageBox, QPushButton, QScrollArea, QSlider, QTabWidget,
                             QTimeEdit, QVBoxLayout, QWidget)

import bandeja  # noqa: E402

CANAL_AJUSTES = m.CANAL + "-ajustes"
NOMBRES_ESTADO = {"listo": "Listo", "permiso": "Permiso", "pensando": "Pensando", "subagente": "Subagente",
                  "limite": "Límite", "error": "Error"}
NOMBRES_EVENTO = {"Stop": "Cuando termina", "Notification": "Cuando necesita algo (permisos, preguntas)",
                  "UserPromptSubmit": "Mientras piensa", "SubagentStop": "Cuando termina un subagente",
                  "StopFailure": "Límite de uso o error de la API"}
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
            "flecha": f"{UI}/flecha-oscuro.svg"}
C_CLARO = {"fondo": "#F3EDE6", "panel": "#FFFBF7", "campo": "#EFE6DD", "borde": "#D9CBBE",
           "texto": "#2B1A14", "suave": "#7A675C", "acento": "#C8643F", "acento2": "#D97757",
           "flecha": f"{UI}/flecha-claro.svg"}
C = dict(C_OSCURO)  # colores en uso: el tema claro los reemplaza en el lugar
ESTILO = """
QWidget { color: %(texto)s; font-family: "Segoe UI"; font-size: 10pt; }
QWidget#raiz { background: %(fondo)s; }
QLabel#titulo { font-size: 15pt; font-weight: 600; }
QLabel#subtitulo, QLabel#ayuda, QLabel#estado, QLabel#valor { color: %(suave)s; }
QLabel#ayuda { font-size: 9pt; }
QLabel#seccion { color: %(suave)s; font-size: 8pt; font-weight: 700; }
QTabWidget::pane { border: 1px solid %(borde)s; border-radius: 12px; background: %(panel)s; top: -1px; }
QTabBar::tab { background: transparent; color: %(suave)s; padding: 8px 11px; border: none;
               border-bottom: 2px solid transparent; margin-right: 4px; font-weight: 600; }
QTabBar::tab:selected { color: %(texto)s; border-bottom: 2px solid %(acento)s; }
QTabBar::tab:hover { color: %(texto)s; }
QPushButton { background: %(campo)s; border: 1px solid %(borde)s; border-radius: 8px; padding: 7px 14px; }
QPushButton:hover { border-color: %(acento)s; }
QPushButton:pressed { background: %(borde)s; }
QPushButton:disabled { color: #6E605A; border-color: %(borde)s; }
QPushButton#primario { background: %(acento)s; border-color: %(acento)s; color: #1C1513; font-weight: 600; }
QPushButton#primario:hover { background: %(acento2)s; border-color: %(acento2)s; }
QPushButton#segmento { border-radius: 0; padding: 6px 0; min-width: 88px; }
QPushButton#segmento[pos="ini"] { border-top-left-radius: 8px; border-bottom-left-radius: 8px; }
QPushButton#segmento[pos="fin"] { border-top-right-radius: 8px; border-bottom-right-radius: 8px; }
QPushButton#segmento:checked { background: %(acento)s; border-color: %(acento)s; color: #1C1513; font-weight: 600; }
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
                              selection-background-color: %(acento)s; selection-color: #1C1513; }
"""  # se completa con C (ver aplicar_tema)


def aplicar_tema(tema: str) -> None:
    """Tema de la ventana: el claro usa colores claros; oscuro y acento, los oscuros."""
    C.clear()
    C.update(C_CLARO if tema == "claro" else C_OSCURO)
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
    etiqueta = QLabel(texto.upper())
    etiqueta.setObjectName("seccion")
    return etiqueta


def ayuda(texto: str) -> QLabel:
    etiqueta = QLabel(texto)
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
    caja = fila(interruptor, QLabel(texto), espacio=10)
    caja.addStretch(1)
    return interruptor, caja


def segmentado(opciones: dict[str, str], al_elegir, padre) -> tuple[dict[str, QPushButton], QHBoxLayout]:
    """Botones pegados de los que se elige uno (como un selector de pestañas)."""
    caja, botones, grupo = QHBoxLayout(), {}, QButtonGroup(padre)
    caja.setSpacing(0)
    for i, (clave, texto) in enumerate(opciones.items()):
        boton = QPushButton(texto, objectName="segmento", checkable=True)
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


def traer_al_frente(ventana: QWidget) -> None:
    """La ventana la pidió el usuario: que aparezca adelante y con foco."""
    ventana.setWindowState(ventana.windowState() & ~Qt.WindowState.WindowMinimized)
    ventana.show()
    ventana.raise_()
    ventana.activateWindow()
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
        self.setToolTip("Escuchar")

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
    """Un círculo de color para elegir el color de la mascota."""

    def __init__(self, color_id: str):
        super().__init__()
        nombre, cuerpo, sombra, _ = sprites.COLORES[color_id]
        self.color_id, self.cuerpo, self.sombra = color_id, QColor(*cuerpo), QColor(*sombra)
        self.setCheckable(True)
        self.setToolTip(nombre)
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
        for clave, nombre, pixmap in opciones:
            icono = QIcon(pixmap)
            icono.addPixmap(pixmap, QIcon.Mode.Selected)  # sin el tinte que Qt le pone al elegido
            item = QListWidgetItem(icono, nombre)
            item.setData(Qt.ItemDataRole.UserRole, clave)
            item.setToolTip(nombre)
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


class VistaPrevia(QWidget):
    """Dibuja la mascota y el cartel tal como se ven en el aviso real."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(330, 410)
        self.cartel = m.Cartel()
        self.cuadros: list = []
        self.cuadro, self.clave, self.estado, self.duracion = 0, None, "listo", 5.0
        self.reloj = QElapsedTimer()
        self.reloj.start()
        self.timer_cuadro = QTimer(self, singleShot=True, timeout=self.siguiente_cuadro)
        self.tic = QTimer(self, interval=40, timeout=self.update)
        self.tic.start()

    def mostrar(self, config: dict, estado: str, mensaje: str, resumen: str, meta: str, botones=()) -> None:
        dpr = self.devicePixelRatioF()
        clave = (json.dumps(config["aspecto"], sort_keys=True), config["imagen"], estado, config["tamano"], dpr)
        if clave != self.clave:
            self.clave = clave
            self.cuadros = m.cargar_cuadros(config["aspecto"], config["imagen"], estado, config["tamano"], dpr)
            self.cuadro = -1
            self.siguiente_cuadro()
        if config["duracion"] != self.duracion:
            self.duracion = config["duracion"]
            self.reloj.restart()
        self.estado = estado
        self.cartel.tema = config["tema"]
        self.cartel.medir(mensaje, resumen, meta, botones)
        self.update()

    def siguiente_cuadro(self) -> None:
        self.cuadro = (self.cuadro + 1) % len(self.cuadros)
        self.update()
        self.timer_cuadro.start(self.cuadros[self.cuadro][1])

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
        pm = self.cuadros[self.cuadro][0]
        sw, sh = pm.width() / pm.devicePixelRatio(), pm.height() / pm.devicePixelRatio()
        arriba = r.top() + (r.height() - sh - 2 - self.cartel.alto) / 2
        cx = r.center().x()
        p.setClipPath(forma)
        m.pintar_sombra(p, cx, arriba + sh, sw)
        p.drawPixmap(QPointF(cx - sw / 2, arriba), pm)
        ms = max(1000, int(self.duracion * 1000))
        self.cartel.pintar(p, cx, arriba + sh + 2, QColor(m.ESTADOS[self.estado]["acento"]),
                           1 - (self.reloj.elapsed() % ms) / ms)


# --- ventana principal -------------------------------------------------------------

class Ajustes(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("raiz")
        self.setWindowTitle("Ajustes de la mascota")
        self.setWindowIcon(bandeja.icono_mascota("terracota"))
        self.config = m.cargar_config()
        self.estado_vista = "listo"
        self.sonidos = m.Sonidos(self)
        self.timer_guardar = QTimer(self, singleShot=True, interval=300, timeout=self.guardar)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(22, 18, 22, 16)
        raiz.setSpacing(14)
        raiz.addLayout(self.cabecera())
        cuerpo = QHBoxLayout()
        cuerpo.setSpacing(18)
        self.pestanas = QTabWidget()
        for pagina, titulo in ((self.pestana_notificacion(), "Notificación"),
                               (self.pestana_comportamiento(), "Comportamiento"), (self.pestana_mascota(), "Mascota"),
                               (self.pestana_vestuario(), "Vestuario"), (self.pestana_estilo(), "Sonido y estilo")):
            area = QScrollArea(widgetResizable=True, frameShape=QFrame.Shape.NoFrame)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            area.setWidget(pagina)  # si la pantalla es chica, la pestaña se desplaza en vez de cortarse
            self.pestanas.addTab(area, titulo)
        cuerpo.addWidget(self.pestanas, 1)
        cuerpo.addLayout(self.panel_vista())
        raiz.addLayout(cuerpo, 1)
        raiz.addLayout(self.pie())
        QShortcut(QKeySequence("Esc"), self, activated=self.close)

        self.cargar_en_controles()
        self.estado_guardado.setText("Los cambios se guardan solos")
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
        textos.addWidget(QLabel("Cómo y dónde te avisa cuando Claude Code termina o necesita algo",
                                objectName="subtitulo"))
        caja.addWidget(self.icono_cabecera)
        caja.addLayout(textos, 1)
        return caja

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
            campo = QLineEdit(placeholderText="Vacío = texto automático", clearButtonEnabled=True)
            campo.textChanged.connect(lambda texto, ev=evento: self.cambiar_mensaje(ev, texto))
            self.textos[evento] = campo
            bloque = QVBoxLayout()
            bloque.setSpacing(4)
            bloque.addWidget(QLabel(titulo))
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
        caja.addWidget(ayuda("Aviso: aparece desde el borde y se va sola. Compañera: vive sobre la barra de "
                             "tareas (arrastrala a donde quieras), crece para avisarte y se duerme si se "
                             "termina el límite de uso."))
        self.vida = {}
        for clave, texto in (("chiquita", "Esperar chiquita, parada sobre la barra de tareas"),
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
            hora.setToolTip("Escribí la hora o cambiala con la ruedita del mouse o las flechas")
        self.desde.timeChanged.connect(lambda t: self.cambiar_grupo("no_molestar", "desde", t.toString("HH:mm")))
        self.hasta.timeChanged.connect(lambda t: self.cambiar_grupo("no_molestar", "hasta", t.toString("HH:mm")))
        fila_nm.insertWidget(2, self.desde)
        fila_nm.insertWidget(3, QLabel("y"))
        fila_nm.insertWidget(4, self.hasta)
        caja.addLayout(fila_nm)
        self.pantalla_completa, fila_pc = opcion("Silenciar si hay algo en pantalla completa (juegos, videos, "
                                                 "presentaciones)",
                                                 lambda v: self.cambiar_grupo("no_molestar", "pantalla_completa", v))
        caja.addLayout(fila_pc)
        self.enfocada, fila_foco = opcion("No avisar si la terminal o el editor de Claude ya tiene el foco",
                                          lambda v: self.cambiar("omitir_si_enfocada", v))
        caja.addLayout(fila_foco)
        caja.addWidget(QLabel("Avisar «terminó» solo si la tarea duró más de"))
        self.umbral = QSlider(Qt.Orientation.Horizontal, minimum=0, maximum=300, singleStep=5, pageStep=30)
        self.valor_umbral = valor()
        self.umbral.valueChanged.connect(lambda v: self.cambiar("umbral_segundos", v))
        caja.addLayout(fila(self.umbral, self.valor_umbral))

        caja.addSpacing(10)
        caja.addWidget(seccion("Acciones"))
        self.permisos, fila_permisos = opcion("Aprobar o denegar permisos desde la mascota",
                                              lambda v: self.cambiar("permisos_desde_mascota", v))
        caja.addLayout(fila_permisos)
        self.etiqueta_espera = QLabel("Esperar mi respuesta")
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
        self.etiqueta_volumen = QLabel("Volumen")
        caja.addLayout(fila(self.etiqueta_volumen, self.volumen, self.valor_volumen))

        caja.addSpacing(10)
        caja.addWidget(seccion("Sonido de cada evento"))
        grilla = QGridLayout()
        grilla.setHorizontalSpacing(10)
        grilla.setVerticalSpacing(6)
        self.sonidos_evento = {}
        nombres = {"ninguno": "Sin sonido", **{c: n for c, (n, _) in sprites.SONIDOS.items()}}
        for numero, estado in enumerate(("listo", "permiso", "pensando", "subagente", "limite", "error")):
            combo = QComboBox()
            for clave, nombre in nombres.items():
                combo.addItem(nombre, clave)
            combo.currentIndexChanged.connect(lambda _, e=estado, cb=combo: self.cambiar_sonido(e, cb.currentData()))
            escuchar = BotonEscuchar()
            escuchar.clicked.connect(lambda _=False, e=estado: self.escuchar(e))
            self.sonidos_evento[estado] = combo
            grilla.addWidget(QLabel(NOMBRES_ESTADO[estado]), numero, 0)
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
        caja.addWidget(seccion("Ícono junto al reloj"))
        self.inicio, fila_inicio = opcion("Abrir al iniciar Windows", self.cambiar_inicio)
        caja.addLayout(fila_inicio)
        caja.addWidget(ayuda("Click en el ícono de la mascota (junto al reloj) para volver a estos ajustes; "
                             "click derecho para silenciar o cambiar de modo."))
        caja.addStretch(1)
        return pagina

    def pestana_mascota(self) -> QWidget:
        pagina = QWidget()
        caja = QVBoxLayout(pagina)
        caja.setContentsMargins(22, 18, 22, 18)
        caja.setSpacing(8)

        caja.addWidget(seccion("Color"))
        muestras = QHBoxLayout()
        muestras.setSpacing(4)
        self.grupo_color = QButtonGroup(self)
        self.muestras = {}
        for color_id in sprites.COLORES:
            muestra = MuestraColor(color_id)
            muestra.clicked.connect(lambda _, c=color_id: self.cambiar_aspecto("color", c))
            self.grupo_color.addButton(muestra)
            self.muestras[color_id] = muestra
            muestras.addWidget(muestra)
        self.nombre_color = QLabel(objectName="valor")
        muestras.addSpacing(10)
        muestras.addWidget(self.nombre_color)
        muestras.addStretch(1)
        caja.addLayout(muestras)

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
        botones.addWidget(QPushButton("Agregar PNG/GIF…", clicked=self.agregar_imagen))
        self.quitar = QPushButton("Quitar", clicked=self.quitar_imagen)
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
        botones.addWidget(QPushButton("Al azar", clicked=self.al_azar))
        botones.addWidget(QPushButton("Sacar todo", clicked=self.sacar_todo))
        botones.addStretch(1)
        caja.addLayout(botones)
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
                boton = QPushButton(NOMBRES_ESTADO[estado], objectName="segmento", checkable=True)
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
        caja.addWidget(QPushButton("Restablecer valores", clicked=self.restablecer))
        caja.addWidget(QPushButton("Cerrar", clicked=self.close))
        return caja

    # datos <-> controles

    def cargar_en_controles(self) -> None:
        c = self.config
        grupos = {"contenido": self.contenido, "eventos": self.eventos, "vida": self.vida}
        controles = [self.duracion, self.sonido, self.volumen, self.tamano, self.inicio, self.no_molestar,
                     self.desde, self.hasta, self.pantalla_completa, self.enfocada, self.umbral, self.permisos,
                     self.espera, self.enfocar, *self.textos.values(), *self.sonidos_evento.values(),
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
            opciones = [(clave, nombre, miniatura({**aspecto, parte: clave}, parte, dpr))
                        for clave, nombre in sprites.OPCIONES[parte].items()]
            galeria.cargar(opciones, None if usando_imagen else aspecto[parte])
        imagenes = [("", "Mascota dibujada", miniatura(aspecto, "entera", dpr, escala=1.5))]
        imagenes += [(ruta.name, ruta.stem, miniatura_imagen(ruta, QSize(72, 63), dpr)) for ruta in m.listar_imagenes()]
        self.galeria_imagenes.cargar(imagenes, self.config["imagen"])
        self.quitar.setEnabled(usando_imagen)
        self.aviso_imagen.setVisible(usando_imagen)
        self.grupo_color.setExclusive(False)  # un grupo exclusivo no deja des-elegir a todos
        for color_id, muestra in self.muestras.items():
            muestra.setChecked(color_id == aspecto["color"] and not usando_imagen)
        self.grupo_color.setExclusive(True)
        icono = (miniatura_imagen(m.IMAGENES / self.config["imagen"], QSize(48, 42), dpr) if usando_imagen
                 else miniatura(aspecto, "entera", dpr, escala=1))
        self.icono_cabecera.setPixmap(icono)

    def actualizar_etiquetas(self) -> None:
        c = self.config
        self.nombre_esquina.setText(NOMBRES_ESQUINA[c["esquina"]])
        self.valor_duracion.setText(f"{round(c['duracion'])} s")
        self.texto_sonido.setText("Activado" if c["sonido"] else "Desactivado")
        self.valor_volumen.setText(f"{c['volumen']} %")
        for control in (self.volumen, self.valor_volumen, self.etiqueta_volumen):
            control.setEnabled(c["sonido"])
        self.valor_tamano.setText(f"{NOMBRES_TAMANO.get(c['tamano'], c['tamano'])} · {m.LADO_ARTE * c['tamano']} px")
        self.nombre_color.setText("" if c["imagen"] else sprites.COLORES[c["aspecto"]["color"]][0])
        self.probar.setText(f"Probar aviso «{NOMBRES_ESTADO[self.estado_vista]}»")
        self.valor_umbral.setText("Siempre" if not c["umbral_segundos"] else m.formato_duracion(c["umbral_segundos"]))
        self.valor_espera.setText(f"{c['espera_permiso']} s")
        for control in (self.espera, self.valor_espera, self.etiqueta_espera):
            control.setEnabled(c["permisos_desde_mascota"])
        for control in (self.desde, self.hasta):
            control.setEnabled(c["no_molestar"]["activo"])
        for interruptor in self.vida.values():
            interruptor.setEnabled(c["modo"] == "compania")
        for combo in self.sonidos_evento.values():
            combo.setEnabled(c["sonido"])

    def mensaje_de_ejemplo(self) -> str:
        automatico = AUTOMATICO[self.estado_vista]
        plantilla = self.config["mensajes"].get(m.EVENTO_POR_ESTADO.get(self.estado_vista), "")
        if not plantilla.strip():
            return automatico
        return m.aplicar_plantilla(plantilla, {"mensaje": automatico, **EJEMPLO}) or automatico

    def refrescar_vista(self) -> None:
        c, estado = self.config, self.estado_vista
        datos = ["2 min 05 s" if c["contenido"]["duracion"] and estado == "listo" else "",
                 EJEMPLO["proyecto"] if c["contenido"]["proyecto"] else "",
                 EJEMPLO["chat"] if c["contenido"]["chat"] else ""]
        botones = ["permitir", "denegar"] if estado == "permiso" and c["permisos_desde_mascota"] else []
        if c["boton_enfocar"]:
            botones.append("enfocar")
        self.vista.mostrar(c, estado, self.mensaje_de_ejemplo()[:120],
                           RESUMEN_EJEMPLO[estado] if c["contenido"]["resumen"] else "",
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

    def cambiar_sonido(self, estado: str, sonido: str) -> None:
        self.config["sonidos"][estado] = sonido
        self.cambio()
        self.escuchar(estado)

    def cambiar_tema(self, tema: str) -> None:
        aplicar_tema(tema)
        self.cambiar("tema", tema)

    def cambiar_modo(self, modo: str) -> None:
        self.cambiar("modo", modo)
        self.guardar()  # la compañera y el ícono leen config.json
        if modo == "compania":  # si ya está abierta, la nueva se cierra sola
            m.lanzar_desacoplado([str(m.DIR / "mascota.py"), "--compania"])

    def cambiar_aspecto(self, parte: str, opcion: str) -> None:
        """Elegir un color o una prenda vuelve a la mascota dibujada si había una imagen propia."""
        self.config["aspecto"][parte] = opcion
        self.config["imagen"] = ""
        self.cargar_galerias()
        self.cambio()

    def cambio(self) -> None:
        self.actualizar_etiquetas()
        self.refrescar_vista()
        self.estado_guardado.setText("Guardando…")
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
        self.config["imagen"] = ""
        self.cargar_galerias()
        self.cambio()

    def sacar_todo(self) -> None:
        self.config["aspecto"] = {**sprites.ASPECTO_DEFECTO, "color": self.config["aspecto"]["color"]}
        self.config["imagen"] = ""
        self.cargar_galerias()
        self.cambio()

    def elegir_imagen(self, nombre: str) -> None:
        self.config["imagen"] = nombre
        self.cargar_galerias()
        self.cambio()

    def agregar_imagen(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(self, "Elegí una imagen para la mascota", str(Path.home()),
                                              "Imágenes (*.png *.gif)")
        if not ruta:
            return
        origen = Path(ruta)
        if origen.stat().st_size > 20_000_000 or not QImageReader(str(origen)).canRead():
            QMessageBox.warning(self, "Imagen no válida",
                                "No pude leer esa imagen. Probá con un PNG o GIF de menos de 20 MB.")
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
        respuesta = QMessageBox.question(self, "Quitar imagen",
                                         f"¿Quitar «{Path(nombre).stem}»? Tu archivo original no se toca.")
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
            self.estado_guardado.setText("No se pudo crear el acceso directo de inicio")
        finally:
            self.unsetCursor()
            self.inicio.blockSignals(True)
            self.inicio.setChecked(bandeja.inicio_automatico())
            self.inicio.blockSignals(False)

    def restablecer(self) -> None:
        if QMessageBox.question(self, "Restablecer", "¿Volver a los valores por defecto? "
                                "Las imágenes propias quedan guardadas.") != QMessageBox.StandardButton.Yes:
            return
        self.config = json.loads(json.dumps(m.CONFIG_DEFECTO))  # copia profunda
        aplicar_tema(self.config["tema"])
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
            self.estado_guardado.setText(f"No se pudo guardar: {e}")
            m.log(f"[ajustes] no se pudo guardar: {e}")
            return
        self.estado_guardado.setText(f"✓ Guardado en {m.CONFIG.parent.name}/{m.CONFIG.name}")

    def probar_aviso(self) -> None:
        self.guardar()  # el aviso de prueba lee config.json, igual que uno real
        m.lanzar_desacoplado([str(m.DIR / "mascota.py"), f"--estado={self.estado_vista}", "--forzar",
                              "--detalle=Prueba desde ajustes"])

    def closeEvent(self, evento) -> None:
        if self.timer_guardar.isActive():
            self.guardar()
        super().closeEvent(evento)


def ejecutar_ventana() -> int:
    # Un error se registra en el log; no cierra la ventana (PyQt6 aborta ante errores no atrapados).
    sys.excepthook = lambda tipo, valor, tb: m.log("[ajustes] error:\n" + "".join(
        traceback.format_exception(tipo, valor, tb)))
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    aplicar_tema(m.cargar_config()["tema"])

    # Una sola ventana de ajustes: si ya hay una abierta, se la trae al frente.
    s = QLocalSocket()
    s.connectToServer(CANAL_AJUSTES)
    if s.waitForConnected(300):
        s.write(b"mostrar\n")
        s.flush()
        s.waitForBytesWritten(300)
        return 0
    servidor = QLocalServer()
    servidor.listen(CANAL_AJUSTES)

    ventana = Ajustes()
    ventana.resize(940, 760)
    servidor.newConnection.connect(lambda: (servidor.nextPendingConnection(), traer_al_frente(ventana)))
    traer_al_frente(ventana)
    m.log("[ajustes] ventana abierta")
    return app.exec()


if __name__ == "__main__":
    try:
        codigo = ejecutar_ventana()
    except Exception:
        m.log("[ajustes] error:\n" + traceback.format_exc())
        codigo = 1
    os._exit(codigo)
