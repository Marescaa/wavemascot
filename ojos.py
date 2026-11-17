"""Los ojos de la mascota elegida, solos y vivos: miran para los costados, parpadean y siguen al mouse.

Se usan donde no entra la mascota entera: arriba en la ventana de ajustes y en la barra de sesiones.
Los cuatro estilos comparten el mismo "display": una pastillita redondeada con la cara adentro, el
contorno oscuro de la mascota y, por fuera, su filo claro (el mismo borde que tiene el dibujo completo de
sprites.py), así se despega de cualquier fondo, claro u oscuro. Adentro cambia la cara: el Clásico y
Sakura, sobre el color del cuerpo (Sakura con pestañas y rubor); el Ninja, sobre la piel, con cejas
decididas y la vincha roja; el Robot, el visor con ojos de luz; la Hamburguesa, el pan con sésamo, ojos
redondos y la lechuga asomando abajo.

Mirada lleva la animación (no depende de Qt más que para el reloj): hacia dónde mira, cuándo parpadea y
qué ánimo tiene ("despierta", "tranquila" o "dormida").
"""

from __future__ import annotations

import math
import random
import time

import sprites

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPainterPath
from PyQt6.QtWidgets import QWidget

# Lo que ocupa el display, en píxeles de arte: la cara (13 x 6), su contorno (1) y el filo claro (0,75).
CARA_ANCHO, CARA_ALTO, CONTORNO, FILO = 13.0, 6.0, 1.0, 0.75
ANCHO = CARA_ANCHO + 2 * (CONTORNO + FILO)
ALTO = CARA_ALTO + 2 * (CONTORNO + FILO)


class Mirada:
    """Hacia dónde miran los ojos y si están abiertos, cuadro a cuadro."""

    def __init__(self, semilla: int | None = None):
        self.azar = random.Random(semilla)
        self.x = self.y = 0.0            # dónde miran ahora (-1..1)
        self.destino = (0.0, 0.0)
        self.proximo_destino = 0.0
        self.proximo_parpadeo = 0.0
        self.parpadeo_desde = -1.0
        self.animo = "tranquila"
        self.seguir: tuple[float, float] | None = None  # algo a lo que mirar (el mouse), en -1..1
        self.reloj = time.monotonic()

    def avanzar(self, ahora: float | None = None) -> bool:
        """Avanza hasta ahora. True si algo se movió (hay que repintar)."""
        ahora = time.monotonic() if ahora is None else ahora
        dt = min(0.25, max(0.0, ahora - self.reloj))
        self.reloj = ahora
        despierta = self.animo == "despierta"
        if self.seguir is not None:
            self.destino = self.seguir
        elif ahora >= self.proximo_destino:
            # Despierta mira para todos lados seguido; tranquila, cada tanto y casi siempre al frente.
            if self.animo == "dormida" or (not despierta and self.azar.random() < 0.45):
                self.destino = (0.0, 0.0)
            else:
                self.destino = (self.azar.choice((-1.0, -0.6, 0.6, 1.0)), self.azar.choice((-0.6, 0.0, 0.0, 0.5)))
            self.proximo_destino = ahora + (self.azar.uniform(0.7, 1.8) if despierta else self.azar.uniform(2.2, 5.0))
        if ahora >= self.proximo_parpadeo and self.parpadeo_desde < 0:
            if self.proximo_parpadeo:
                self.parpadeo_desde = ahora
            self.proximo_parpadeo = ahora + self.azar.uniform(2.4, 6.0)
        if self.parpadeo_desde >= 0 and ahora - self.parpadeo_desde > 0.16:
            self.parpadeo_desde = -1.0
            cambio = True
        else:
            cambio = self.parpadeo_desde >= 0
        k = 1 - math.exp(-dt * (14 if self.seguir is not None else 9))  # se acerca rápido y frena suave
        nx, ny = self.x + (self.destino[0] - self.x) * k, self.y + (self.destino[1] - self.y) * k
        if abs(nx - self.x) > 0.004 or abs(ny - self.y) > 0.004:
            cambio = True
        self.x, self.y = nx, ny
        return cambio

    @property
    def cerrados(self) -> bool:
        return self.animo == "dormida" or self.parpadeo_desde >= 0


def colores(aspecto: dict) -> dict:
    """Los colores del display de ese aspecto."""
    estilo = aspecto.get("estilo", "clasico")
    estilo = estilo if estilo in sprites.PALETA_ESTILO else "clasico"
    paleta = sprites.PALETA_ESTILO[estilo]

    def de_paleta(indice: int) -> QColor:
        return QColor(*paleta.get(indice, sprites.PALETA[indice]))

    _, cuerpo, _, brillo = sprites.COLORES.get(aspecto.get("color"), sprites.COLORES["terracota"])
    fondo = {"ninja": QColor(*sprites.PIELES.get(aspecto.get("piel"), sprites.PIELES["clara"])[1]),
             "robot": QColor(*sprites.PALETA[sprites.OSCURO])}.get(estilo, QColor(*cuerpo))
    return {"estilo": estilo, "fondo": fondo, "brillo": QColor(*brillo), "contorno": de_paleta(sprites.CONT),
            "filo": de_paleta(sprites.CREMA), "rubor": de_paleta(sprites.RUBOR),
            "led": QColor(*sprites.PALETA[sprites.LED]), "rojo": QColor(*sprites.PALETA[sprites.ROJO]),
            "reflejo": QColor(*sprites.PALETA[sprites.NUBE_OSC]), "blanco": QColor(255, 255, 255),
            "hoja": QColor(*sprites.PALETA[sprites.HOJA]), "verde": QColor(*sprites.PALETA[sprites.VERDE])}


def pintar(p: QPainter, centro: QPointF, px: float, aspecto: dict, mirada: Mirada, alfa: float = 1.0) -> None:
    """Dibuja el display con los dos ojos centrado en `centro`; px es el lado de cada píxel de arte."""
    c = colores(aspecto)
    estilo = c["estilo"]
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.setOpacity(p.opacity() * alfa)
    p.translate(centro)

    def pastilla(margen: float, color: QColor) -> QPainterPath:
        """La cara agrandada `margen` píxeles de arte para cada lado, con las esquinas a tono."""
        ancho, alto = (CARA_ANCHO + 2 * margen) * px, (CARA_ALTO + 2 * margen) * px
        radio = (2.4 + margen) * px
        forma = QPainterPath()
        forma.addRoundedRect(QRectF(-ancho / 2, -alto / 2, ancho, alto), radio, radio)
        p.fillPath(forma, color)
        return forma

    # De afuera hacia adentro: el filo claro, el contorno y la cara.
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pastilla(CONTORNO + FILO, c["filo"])
    pastilla(CONTORNO, c["contorno"])
    cara = pastilla(0, c["fondo"])
    p.setClipPath(cara)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)

    def cuadro(x: float, y: float, ancho: float, alto: float, color: QColor) -> None:
        p.fillRect(QRectF(x * px, y * px, ancho * px, alto * px), color)

    arriba = -CARA_ALTO / 2
    if estilo == "ninja":
        cuadro(-CARA_ANCHO / 2, arriba, CARA_ANCHO, 1, c["rojo"])            # la vincha
    elif estilo == "robot":
        cuadro(-CARA_ANCHO / 2 + 1.5, arriba + 0.6, 2, 0.6, c["reflejo"])    # el reflejo del vidrio
    elif estilo == "hamburguesa":
        for x, y in ((-4.5, 0.5), (-1.0, 0.2), (2.5, 0.6), (5.0, 1.4), (-6.0, 1.6)):   # el sésamo del pan
            cuadro(x, arriba + y, 1.2, 0.6, c["filo"])
        for i in range(int(CARA_ANCHO) + 1):                                 # la lechuga asoma abajo
            cuadro(-CARA_ANCHO / 2 + i, CARA_ALTO / 2 - 0.9, 1, 0.9, c["verde"] if i % 3 == 0 else c["hoja"])
    else:
        cuadro(-CARA_ANCHO / 2 + 1.2, arriba + 0.6, 2.4, 0.8, c["brillo"])   # el brillo del cuerpo
    separacion = 3.0  # del centro de la cara al centro de cada ojo
    corre_x, corre_y = 1.4 * mirada.x, 0.6 * mirada.y
    base = {"ninja": 0.4, "hamburguesa": -0.2}.get(estilo, 0.0)  # debajo de la vincha; arriba de la lechuga
    cerrados = mirada.cerrados
    tinta = c["led"] if estilo == "robot" else c["contorno"]
    for lado in (-1, 1):
        x, y = lado * separacion + corre_x, base + corre_y
        if cerrados:
            cuadro(x - 1.5, y + 0.4, 3, 0.7, c["reflejo"] if estilo == "robot" else tinta)
            continue
        if estilo == "robot":
            cuadro(x - 1, y - 1, 2, 2, tinta)
            continue
        if estilo == "hamburguesa":   # ojos redondos y brillosos
            cuadro(x - 1.5, y - 1.0, 3, 2, tinta)
            cuadro(x - 1.0, y - 1.5, 2, 3, tinta)
            cuadro(x - 1.0, y - 1.0, 1, 1, c["blanco"])
            continue
        alto = 2.0 if estilo == "ninja" else 3.0
        cuadro(x - 1, y - alto / 2, 2, alto, tinta)
        cuadro(x - 1, y - alto / 2, 1, 1, c["blanco"])                        # el brillo del ojo
        if estilo == "ninja":   # la ceja decidida: baja hacia el centro de la cara
            cuadro(x - 1.5, y - 2.1 + (0.5 if lado > 0 else 0), 1.5, 0.7, tinta)
            cuadro(x, y - 2.1 + (0.5 if lado < 0 else 0), 1.5, 0.7, tinta)
        elif estilo == "sakura":
            cuadro(x + lado * 1.0 - 0.5 + lado * 0.5, y - 2.2, 1, 0.8, tinta)  # la pestaña, hacia afuera
            cuadro(x + lado * 2.2 - 0.5, y + 0.9, 1.4, 0.8, c["rubor"])         # el rubor
    p.restore()


class Ojos(QWidget):
    """Un lugarcito con los ojos de la mascota, que se mueven solos mientras está a la vista."""

    def __init__(self, ancho: int = 52, alto: int = 42):
        super().__init__()
        self.setFixedSize(ancho, alto)
        self.aspecto = dict(sprites.ASPECTO_DEFECTO)
        self.mirada = Mirada()
        self.timer = QTimer(self, interval=40, timeout=self.cuadro)

    def sizeHint(self) -> QSize:
        return self.size()

    def poner(self, aspecto: dict) -> None:
        self.aspecto = dict(aspecto)
        self.update()

    def showEvent(self, evento) -> None:
        self.timer.start()

    def hideEvent(self, evento) -> None:
        self.timer.stop()

    def cuadro(self) -> None:
        if self.mirada.avanzar():
            self.update()

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        px = max(1.0, math.floor(min(self.width() / ANCHO, self.height() / ALTO)))
        pintar(p, QPointF(self.width() / 2, self.height() / 2), px, self.aspecto, self.mirada)
