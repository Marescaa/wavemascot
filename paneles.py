"""La sección Uso de los ajustes: tarjetas limpias y suaves, un gráfico de área y una dona.

Arriba el lapso (5 horas, hoy, 7 días, 1 mes o 6 meses). Debajo, la curva de tokens con la cifra grande y los
modelos en una dona; abajo, tres números sueltos y los proyectos.

El movimiento es parte del diseño, pero uno solo y tranquilo: al cambiar de lapso la curva se transforma en la
nueva, los números corren hasta su valor y la dona reparte de nuevo. Nada se mueve si no cambió algo (repintar sin
motivo es lo que hace sentir pesada una ventana). Los colores salen siempre del tema.

Todo se actualiza en vivo mientras se mira: los datos los arma estadisticas.py en un hilo aparte (Analista)
leyendo solo lo nuevo de cada transcript; acá solo se dibuja.
"""

from __future__ import annotations

import math
import threading
from datetime import datetime, timedelta

import estadisticas
import mascota as m
import seguimiento
from animacion import Resorte, mezcla
from idiomas import t

from PyQt6.QtCore import QObject, QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import QApplication, QGridLayout, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

# Los colores de la ventana de ajustes: ajustes.py pone acá su mismo diccionario (cambia con el tema).
C: dict = {"fondo": "#1C1513", "panel": "#251D1A", "campo": "#2F2623", "borde": "#43362F", "texto": "#F4EDE8",
           "suave": "#B3A39A", "acento": "#D97757", "acento2": "#E8906F"}
VIDRIO = False  # la ventana desenfoca lo de atrás (ver ajustes.Ajustes.preparar_vidrio)
RADIO = 18      # el de las tarjetas; lo de adentro usa radios más chicos (concéntricos)
VIVO = 5        # segundos entre un análisis y el siguiente mientras se mira Uso
SOMBRA = 10     # el margen de cada tarjeta suave, donde cae su sombra
INTERIOR = 18   # de la tarjeta a su contenido
PUNTOS = 121    # con cuántos puntos se dibuja la curva (siempre los mismos: así una se transforma en otra)
# Los lapsos de Uso (las claves de estadisticas.LAPSOS, más "hoy"): el botón y el título de la tarjeta.
BOTON_LAPSO = {"5h": "5 h", "hoy": "Hoy", "7d": "7 días", "30d": "1 mes", "180d": "6 meses"}
TITULO_LAPSO = {"5h": "Últimas 5 horas", "hoy": "Hoy", "7d": "Últimos 7 días", "30d": "Últimos 30 días",
                "180d": "Últimos 6 meses"}
AGRUPAR = {"5h": 3, "7d": 2}  # de cuántas barras sale cada punto: con tramos tan cortos la curva serían agujas


def con_alfa(color, alfa: float) -> QColor:
    c = QColor(color)
    c.setAlphaF(max(0.0, min(1.0, alfa)))
    return c


def letra(px: float, peso: QFont.Weight = QFont.Weight.Normal) -> QFont:
    fuente = QFont(QApplication.font())
    if not m.MAC:
        fuente.setFamily("Segoe UI")
    fuente.setPixelSize(round(px))
    fuente.setWeight(peso)
    return fuente


def pintar_tarjeta(p: QPainter, rect, radio: float = RADIO) -> None:
    """El fondo de una tarjeta de contenido. El vidrio queda para lo que flota (la barra lateral, los
    controles): el contenido va sobre una superficie pareja y tranquila, apenas más clara que la ventana,
    con un borde finito."""
    r = QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5)
    forma = QPainterPath()
    forma.addRoundedRect(r, radio, radio)
    if VIDRIO:
        p.fillPath(forma, con_alfa(mezcla(C["panel"], C["texto"], 0.05), 0.62))
        p.strokePath(forma, QPen(con_alfa(C["texto"], 0.09), 1))
    else:
        p.fillPath(forma, QColor(C["panel"]))
        p.strokePath(forma, QPen(con_alfa(C["borde"], 0.8), 1))


def pintar_suave(p: QPainter, ancho: float, alto: float, radio: float = RADIO) -> None:
    """Una tarjeta que apenas flota: sombra difusa alrededor, superficie pareja y un borde casi invisible."""
    claro = QColor(C["fondo"]).lightnessF() > 0.5
    caja = QRectF(SOMBRA, SOMBRA, ancho - 2 * SOMBRA, alto - 2 * SOMBRA)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(70, 50, 40, 3) if claro else QColor(0, 0, 0, 12))
    for d in range(SOMBRA - 3, 0, -1):
        p.drawRoundedRect(caja.adjusted(-d, 3 - d, d, 3 + d), radio + d, radio + d)
    forma = QPainterPath()
    forma.addRoundedRect(caja.adjusted(0.5, 0.5, -0.5, -0.5), radio, radio)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)  # la sombra no se ve a través del vidrio
    p.fillPath(forma, QColor(0, 0, 0))
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    if VIDRIO:
        relleno = con_alfa(mezcla(C["panel"], C["texto"], 0.06), 0.74)
    else:
        relleno = QColor(C["panel"]) if claro else mezcla(C["panel"], C["texto"], 0.025)
    p.fillPath(forma, relleno)
    p.strokePath(forma, QPen(con_alfa(C["texto"], 0.05 if claro else 0.07), 1))


def tokens(n: float) -> str:
    return seguimiento.formato_tokens(int(n))


def duracion(segundos: float) -> str:
    s = max(0, round(segundos))
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s // 60} min"
    return f"{s // 3600} h {s % 3600 // 60:02d}"


def cambio(ahora: float, antes: float) -> float | None:
    """Cuánto cambió contra el período anterior (0.16 = +16 %), o None si no hay con qué comparar."""
    return (ahora - antes) / antes if antes else None


def tope(x: float) -> float:
    return max(0.0, min(1.0, x))


class Tarjeta(QWidget):
    """Una tarjeta con un título chico arriba; lo de adentro lo pinta cada una en pintar()."""

    MARGEN = 18

    def __init__(self, titulo: str = "", alto: int = 120):
        super().__init__()
        self.titulo = titulo
        self.alto = alto
        self.setMinimumHeight(alto)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.aparece = Resorte(self, 0.0, 0.55, 0.9, al_paso=lambda _: self.update())  # las barras crecen al llegar
        self.con_datos = False

    def sizeHint(self) -> QSize:
        return QSize(220, self.alto)

    def llegaron_datos(self, de_nuevo: bool = False) -> None:
        if not self.con_datos or de_nuevo:
            self.con_datos = True
            self.aparece.ir_a(1.0, desde=0.0) if self.isVisible() else self.aparece.fijar(1.0)
        self.update()

    def area(self) -> QRectF:
        arriba = 40 if self.titulo else self.MARGEN
        return QRectF(self.rect()).adjusted(self.MARGEN, arriba, -self.MARGEN, -self.MARGEN)

    def pintar_fondo(self, p: QPainter) -> None:
        pintar_tarjeta(p, self.rect())

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.pintar_fondo(p)
        if self.titulo:
            p.setFont(letra(12.5, QFont.Weight.DemiBold))
            p.setPen(QColor(C["suave"]))
            p.drawText(QRectF(self.MARGEN, 14, self.width() - 2 * self.MARGEN, 18),
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self.titulo)
        self.pintar(p, self.area())

    def pintar(self, p: QPainter, r: QRectF) -> None:
        pass

    def sin_datos(self, p: QPainter, r: QRectF, texto: str = "") -> None:
        p.setFont(letra(12.5))
        p.setPen(QColor(C["suave"]))
        p.drawText(r, int(Qt.AlignmentFlag.AlignCenter), texto or t("Todavía no hay datos"))


class TarjetaSuave(Tarjeta):
    """Una tarjeta con sombra difusa. El fondo se pinta una vez y se guarda: mientras algo se mueve, cada cuadro
    solo apoya esa foto. La sombra cae dentro del propio widget (SOMBRA), así que no hay efectos que recalcular."""

    def __init__(self, alto: int = 120):
        super().__init__("", alto)
        self.foto: QPixmap | None = None
        self.clave_foto: tuple | None = None

    def area(self) -> QRectF:
        return QRectF(self.rect()).adjusted(SOMBRA + INTERIOR, SOMBRA + INTERIOR - 2, -SOMBRA - INTERIOR,
                                            -SOMBRA - INTERIOR + 2)

    def pintar_fondo(self, p: QPainter) -> None:
        dpr = self.devicePixelRatioF()
        clave = (self.width(), self.height(), dpr, VIDRIO, C["fondo"], C["panel"], C["texto"])
        if clave != self.clave_foto:
            self.clave_foto = clave
            self.foto = QPixmap(round(self.width() * dpr), round(self.height() * dpr))
            self.foto.setDevicePixelRatio(dpr)
            self.foto.fill(Qt.GlobalColor.transparent)
            lienzo = QPainter(self.foto)
            lienzo.setRenderHint(QPainter.RenderHint.Antialiasing)
            pintar_suave(lienzo, self.width(), self.height())
            lienzo.end()
        p.drawPixmap(QPointF(0, 0), self.foto)

    @staticmethod
    def pintar_titulo(p: QPainter, r: QRectF, texto: str) -> None:
        p.setFont(letra(12.5, QFont.Weight.Medium))
        p.setPen(QColor(C["suave"]))
        p.drawText(QRectF(r.left(), r.top(), r.width(), 18),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                   QFontMetricsF(p.font()).elidedText(texto, Qt.TextElideMode.ElideRight, r.width()))


class Area(TarjetaSuave):
    """La tarjeta grande: la cifra y una curva suave con el área fundiéndose hacia abajo. Al cambiar de lapso una
    curva se transforma en la otra; al pasar el mouse, un punto la recorre y dice cuánto hubo ahí."""

    def __init__(self, alto: int = 344):
        super().__init__(alto)
        self.textos: dict = {}
        self.previos: dict | None = None
        self.valor_desde = self.valor = 0.0
        self.valores: list[float] = []
        self.ayudas: list[tuple[str, str]] = []
        self.ultimo = 0                     # el último punto con datos (hoy, la hora actual)
        self.forma_desde = [0.0] * PUNTOS
        self.forma = [0.0] * PUNTOS
        self.fin_desde = self.fin = 1.0     # hasta dónde del ancho llega la curva
        self.encima = -1
        pintar = lambda _: self.update()
        self.morfo = Resorte(self, 1.0, 0.62, 1.0, al_paso=pintar)
        self.fundido = Resorte(self, 1.0, 0.36, 1.0, al_paso=pintar, al_llegar=self.olvidar_previos)
        self.cuenta = Resorte(self, 1.0, 0.62, 1.0, al_paso=pintar)
        self.cursor = Resorte(self, 0.0, 0.18, 1.0, al_paso=pintar)
        self.foco = Resorte(self, 0.0, 0.18, 1.0, al_paso=pintar)
        self.setMouseTracking(True)

    def olvidar_previos(self) -> None:
        self.previos = None

    def forma_visible(self) -> list[float]:
        k = tope(self.morfo.x)
        return [a + (b - a) * k for a, b in zip(self.forma_desde, self.forma)]

    def fin_visible(self) -> float:
        return self.fin_desde + (self.fin - self.fin_desde) * tope(self.morfo.x)

    def valor_visible(self) -> float:
        return self.valor_desde + (self.valor - self.valor_desde) * tope(self.cuenta.x)

    def poner(self, textos: dict, valor: float, valores: list[float], ayudas: list[tuple[str, str]], ultimo: int,
              de_nuevo: bool = False) -> None:
        """textos: titulo, unidad, cambio, contra, detalle y marcas [(fracción del ancho, texto)]."""
        n = len(valores)
        ultimo = max(0, min(n - 1, ultimo))  # a las 00:30 la curva es un solo punto: no se inventa la hora siguiente
        crudo = estadisticas.suavizar(estadisticas.curva(valores[:ultimo + 1], PUNTOS))
        maximo = max(crudo)
        forma = [v / maximo for v in crudo] if maximo else [0.0] * PUNTOS
        fin = ultimo / (n - 1) if n > 1 else 1.0
        primero = not self.con_datos
        moverse = primero or forma != self.forma or fin != self.fin
        animar = self.isVisible()
        if moverse:
            self.forma_desde, self.fin_desde = ([0.0] * PUNTOS, fin) if primero else (self.forma_visible(),
                                                                                       self.fin_visible())
        if primero or de_nuevo:
            self.previos = None if primero else self.textos
            self.encima = -1
            self.foco.ir_a(0.0) if animar else self.foco.fijar(0.0)
        if valor != self.valor:
            self.valor_desde, self.valor = self.valor_visible(), valor
            self.cuenta.ir_a(1.0, desde=0.0) if animar else self.cuenta.fijar(1.0)
        self.textos, self.valores, self.ayudas, self.ultimo = textos, valores, ayudas, ultimo
        self.forma, self.fin = forma, fin
        if self.encima > ultimo:
            self.encima = -1
            self.foco.ir_a(0.0) if animar else self.foco.fijar(0.0)
        self.con_datos = True
        if moverse:
            self.morfo.ir_a(1.0, desde=0.0) if animar else self.morfo.fijar(1.0)
        if primero or de_nuevo:
            self.fundido.ir_a(1.0, desde=0.0) if animar else self.fundido.fijar(1.0)
        self.update()

    def entrar(self) -> None:
        """Al volver a la sección la curva sube desde la base."""
        if self.con_datos:
            self.forma_desde, self.fin_desde = [0.0] * PUNTOS, self.fin
            self.morfo.ir_a(1.0, desde=0.0)

    def zona(self) -> QRectF:
        r = self.area()
        return QRectF(r.left(), r.top() + 106, r.width(), r.height() - 106 - 24)

    def altura_en(self, forma: list[float], x: float, fin: float) -> float:
        """La altura de la curva en x (fracción del ancho total)."""
        j = tope(x / fin if fin else 0.0) * (PUNTOS - 1)
        i = min(PUNTOS - 2, int(j))
        return forma[i] + (forma[i + 1] - forma[i]) * (j - i)

    def mouseMoveEvent(self, evento) -> None:
        zona, n = self.zona(), len(self.valores)
        x, y = evento.position().x(), evento.position().y()
        encima = -1
        if n > 1 and zona.left() - 8 <= x <= zona.right() + 8 and zona.top() - 12 <= y <= zona.bottom() + 8:
            encima = max(0, min(self.ultimo, round((x - zona.left()) / zona.width() * (n - 1))))
        if encima == self.encima:
            return
        self.encima = encima
        if encima < 0:
            self.foco.ir_a(0.0)
            return
        destino = encima / (n - 1)
        self.cursor.fijar(destino) if self.foco.x < 0.05 else self.cursor.ir_a(destino)
        self.foco.ir_a(1.0)

    def leaveEvent(self, evento) -> None:
        self.encima = -1
        self.foco.ir_a(0.0)

    def pintar_textos(self, p: QPainter, r: QRectF, d: dict, alfa: float, dy: float) -> None:
        """Lo que se funde al cambiar de lapso: el título, la línea de abajo, la pastilla y las marcas del eje."""
        if alfa <= 0.01:
            return
        izquierda = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        derecha = int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        centro = int(Qt.AlignmentFlag.AlignCenter)
        p.setOpacity(alfa)
        self.pintar_titulo(p, r.translated(0, dy), d["titulo"])
        p.setFont(letra(12.5))
        p.setPen(QColor(C["suave"]))
        p.drawText(QRectF(r.left(), r.top() + 72 + dy, r.width(), 18), izquierda, d["detalle"])
        if d["cambio"] is not None:
            texto = ("↑ " if d["cambio"] >= 0 else "↓ ") + f"{min(999, abs(round(d['cambio'] * 100)))} %"
            p.setFont(letra(12.5, QFont.Weight.DemiBold))
            ancho = QFontMetricsF(p.font()).horizontalAdvance(texto) + 20
            pastilla = QRectF(r.right() - ancho, r.top() - 2 + dy, ancho, 24)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(con_alfa(C["acento"], 0.15))
            p.drawRoundedRect(pastilla, 12, 12)
            p.setPen(QColor(C["acento"]))
            p.drawText(pastilla, centro, texto)
            p.setFont(letra(11.5))
            p.setPen(QColor(C["suave"]))
            p.drawText(QRectF(r.right() - 240, pastilla.bottom() + 4, 240, 16), derecha, d["contra"])
        zona = self.zona()
        p.setFont(letra(11.5))
        p.setPen(QColor(C["suave"]))
        for fraccion, marca in d["marcas"]:
            x = zona.left() + fraccion * zona.width()
            if fraccion <= 0:
                p.drawText(QRectF(zona.left(), zona.bottom() + 8, 90, 16), izquierda, marca)
            elif fraccion >= 1:
                p.drawText(QRectF(zona.right() - 90, zona.bottom() + 8, 90, 16), derecha, marca)
            else:
                p.drawText(QRectF(x - 45, zona.bottom() + 8, 90, 16), centro, marca)

    def pintar_curva(self, p: QPainter, zona: QRectF) -> None:
        base = zona.bottom()
        util = zona.height() - 10
        p.setPen(QPen(con_alfa(C["texto"], 0.055), 1))
        for k in (0.0, 0.5, 1.0):
            y = round(base - util * k) + 0.5
            p.drawLine(QPointF(zona.left(), y), QPointF(zona.right(), y))
        forma, fin = self.forma_visible(), self.fin_visible()
        puntos = [QPointF(zona.left() + fin * zona.width() * j / (PUNTOS - 1), base - util * h)
                  for j, h in enumerate(forma)]
        linea = QPainterPath(puntos[0])
        for punto in puntos[1:]:
            linea.lineTo(punto)
        area = QPainterPath(linea)
        area.lineTo(puntos[-1].x(), base)
        area.lineTo(puntos[0].x(), base)
        area.closeSubpath()
        tinte = QLinearGradient(0, zona.top(), 0, base)
        tinte.setColorAt(0, con_alfa(C["acento"], 0.36))
        tinte.setColorAt(0.6, con_alfa(C["acento"], 0.12))
        tinte.setColorAt(1, con_alfa(C["acento"], 0.0))
        p.fillPath(area, tinte)
        pluma = QPen(QColor(C["acento"]), 2.2)
        pluma.setCapStyle(Qt.PenCapStyle.RoundCap)
        pluma.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pluma)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(linea)
        foco = tope(self.foco.x)
        self.pintar_punto(p, puntos[-1], 1 - foco)
        if foco > 0.01:
            x = self.cursor.x
            punto = QPointF(zona.left() + x * zona.width(), base - util * self.altura_en(forma, x, fin))
            p.setOpacity(foco)
            p.setPen(QPen(con_alfa(C["texto"], 0.16), 1))
            p.drawLine(QPointF(punto.x(), zona.top()), QPointF(punto.x(), base))
            p.setOpacity(1.0)
            self.pintar_punto(p, punto, foco)
            self.pintar_burbuja(p, zona, punto, foco)

    @staticmethod
    def pintar_punto(p: QPainter, centro: QPointF, alfa: float) -> None:
        if alfa <= 0.01:
            return
        p.setOpacity(alfa)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(con_alfa(C["acento"], 0.20))
        p.drawEllipse(centro, 9.0, 9.0)
        p.setBrush(QColor(C["panel"]))
        p.setPen(QPen(QColor(C["acento"]), 2.2))
        p.drawEllipse(centro, 4.2, 4.2)
        p.setOpacity(1.0)

    def pintar_burbuja(self, p: QPainter, zona: QRectF, punto: QPointF, alfa: float) -> None:
        i = self.encima
        if not 0 <= i < len(self.ayudas):
            return
        cuando, valor = self.ayudas[i]
        chica, fuerte = letra(11.5), letra(12.5, QFont.Weight.DemiBold)
        ancho_c = QFontMetricsF(chica).horizontalAdvance(cuando)
        ancho_v = QFontMetricsF(fuerte).horizontalAdvance(valor)
        ancho = ancho_c + ancho_v + 32
        x = max(zona.left() - 6, min(zona.right() + 6 - ancho, punto.x() - ancho / 2))
        y = max(zona.top() - 16, punto.y() - 42)
        caja = QRectF(x, y, ancho, 28)
        p.setOpacity(alfa)
        p.setPen(QPen(con_alfa(C["texto"], 0.08), 1))
        p.setBrush(mezcla(C["panel"], C["texto"], 0.10))
        p.drawRoundedRect(caja, 14, 14)
        vertical = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        p.setFont(chica)
        p.setPen(QColor(C["suave"]))
        p.drawText(QRectF(caja.left() + 12, caja.top(), ancho_c + 2, caja.height()), vertical, cuando)
        p.setFont(fuerte)
        p.setPen(QColor(C["texto"]))
        p.drawText(QRectF(caja.right() - 12 - ancho_v, caja.top(), ancho_v + 2, caja.height()), vertical, valor)
        p.setOpacity(1.0)

    def pintar(self, p: QPainter, r: QRectF) -> None:
        if not self.con_datos:
            return self.sin_datos(p, r, t("Analizando…"))
        f = tope(self.fundido.x)
        if self.previos:  # primero se va lo viejo y recién después entra lo nuevo: los textos nunca se pisan
            self.pintar_textos(p, r, self.previos, 1 - f / 0.42, -4 * f)
        self.pintar_textos(p, r, self.textos, (f - 0.36) / 0.64 if self.previos else f, 4 * (1 - f))
        p.setOpacity(1.0)
        cifra = tokens(self.valor_visible())
        p.setFont(letra(40, QFont.Weight.DemiBold))
        p.setPen(QColor(C["texto"]))
        ancho = QFontMetricsF(p.font()).horizontalAdvance(cifra)
        p.drawText(QRectF(r.left() - 1, r.top() + 20, ancho + 8, 50), int(Qt.AlignmentFlag.AlignVCenter), cifra)
        p.setFont(letra(14))
        p.setPen(QColor(C["suave"]))
        p.drawText(QRectF(r.left() + ancho + 8, r.top() + 34, 120, 26), int(Qt.AlignmentFlag.AlignVCenter),
                   self.textos.get("unidad", ""))
        self.pintar_curva(p, self.zona())


class Dona(TarjetaSuave):
    """En qué modelos se fue: una dona con los segmentos redondeados y su leyenda."""

    GROSOR = 10.0
    LADO = 104.0
    ARRIBA = 28
    FILA = 21

    def __init__(self, titulo: str, alto: int = 288):
        super().__init__(alto)
        self.nombre = titulo
        self.items: list[tuple[str, float]] = []
        self.desde = self.fracciones = [0.0] * 4
        self.corre = Resorte(self, 1.0, 0.62, 1.0, al_paso=lambda _: self.update())

    def visibles(self) -> list[float]:
        k = tope(self.corre.x)
        return [a + (b - a) * k for a, b in zip(self.desde, self.fracciones)]

    def poner(self, modelos: list[tuple[str, int]], total: float) -> None:
        items = [(nombre, valor / total) for nombre, valor in modelos[:3]] if total else []
        resto = 1 - sum(f for _, f in items)
        if items and resto > 0.005:
            items.append((t("Otros"), resto))
        fracciones = [f for _, f in items] + [0.0] * (4 - len(items))
        if items == self.items and self.con_datos:
            return
        self.desde, self.fracciones, self.items = self.visibles(), fracciones, items
        self.con_datos = True
        self.corre.ir_a(1.0, desde=0.0) if self.isVisible() else self.corre.fijar(1.0)
        self.update()

    @staticmethod
    def tonos() -> list[QColor]:
        return [QColor(C["acento"]), mezcla(C["acento"], C["texto"], 0.48), mezcla(C["acento"], C["fondo"], 0.52),
                con_alfa(C["texto"], 0.20)]

    def pintar(self, p: QPainter, r: QRectF) -> None:
        self.pintar_titulo(p, r, self.nombre)
        if not self.items:
            return self.sin_datos(p, r)
        lado = min(self.LADO, r.width() - 8)
        aro = QRectF(r.center().x() - lado / 2, r.top() + self.ARRIBA, lado, lado).adjusted(
            self.GROSOR / 2, self.GROSOR / 2, -self.GROSOR / 2, -self.GROSOR / 2)
        pluma = QPen(con_alfa(C["texto"], 0.07), self.GROSOR)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(pluma)
        p.drawEllipse(aro)
        pluma.setCapStyle(Qt.PenCapStyle.RoundCap)
        hueco = math.degrees(self.GROSOR / (aro.width() / 2)) + 3.0  # lo que ocupan las puntas redondas, y un aire
        angulo = 90.0
        for fraccion, tono in zip(self.visibles(), self.tonos()):
            barrido = 360 * fraccion
            if barrido > 0.2:
                pluma.setColor(tono)
                p.setPen(pluma)
                if fraccion > 0.995:
                    p.drawEllipse(aro)
                else:
                    arco = max(0.4, barrido - hueco)
                    p.drawArc(aro, round((angulo - (barrido - arco) / 2) * 16), -round(arco * 16))
            angulo -= barrido
        principal, parte = self.items[0]
        p.setFont(letra(19, QFont.Weight.DemiBold))
        p.setPen(QColor(C["texto"]))
        p.drawText(aro.adjusted(0, -9, 0, -9), int(Qt.AlignmentFlag.AlignCenter), f"{round(parte * 100)} %")
        p.setFont(letra(10.5))
        p.setPen(QColor(C["suave"]))
        p.drawText(aro.adjusted(8, 15, -8, 15), int(Qt.AlignmentFlag.AlignCenter),
                   QFontMetricsF(p.font()).elidedText(principal, Qt.TextElideMode.ElideRight, aro.width() - 20))
        izquierda = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        derecha = int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        y = r.top() + self.ARRIBA + lado + 10
        for (nombre, fraccion), tono in zip(self.items, self.tonos()):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(tono)
            p.drawEllipse(QPointF(r.left() + 4, y + self.FILA / 2), 3.5, 3.5)
            p.setFont(letra(12.5))
            p.setPen(QColor(C["suave"]))
            porcentaje = f"{round(fraccion * 100)} %"
            ancho = QFontMetricsF(p.font()).horizontalAdvance(porcentaje) + 8
            p.drawText(QRectF(r.left() + 15, y, r.width() - 15 - ancho, self.FILA), izquierda,
                       QFontMetricsF(p.font()).elidedText(nombre, Qt.TextElideMode.ElideRight, r.width() - 15 - ancho))
            p.setPen(QColor(C["texto"]))
            p.drawText(QRectF(r.left(), y, r.width(), self.FILA), derecha, porcentaje)
            y += self.FILA


class Dato(TarjetaSuave):
    """Un número suelto con su nombre arriba. Corre hasta su valor."""

    def __init__(self, nombre: str, formato, alto: int = 124):
        super().__init__(alto)
        self.nombre, self.formato = nombre, formato
        self.desde = self.valor = 0.0
        self.corre = Resorte(self, 1.0, 0.62, 1.0, al_paso=lambda _: self.update())

    def visible(self) -> float:
        return self.desde + (self.valor - self.desde) * tope(self.corre.x)

    def poner(self, valor: float) -> None:
        if valor == self.valor and self.con_datos:
            return
        self.desde, self.valor = self.visible(), valor
        self.con_datos = True
        self.corre.ir_a(1.0, desde=0.0) if self.isVisible() else self.corre.fijar(1.0)
        self.update()

    def pintar(self, p: QPainter, r: QRectF) -> None:
        self.pintar_titulo(p, r, self.nombre)
        texto = self.formato(self.visible()) if self.con_datos else "—"
        px = 30.0
        while px > 16 and QFontMetricsF(letra(px, QFont.Weight.DemiBold)).horizontalAdvance(texto) > r.width():
            px -= 1  # en una ventana angosta el número se achica antes que cortarse
        p.setFont(letra(px, QFont.Weight.DemiBold))
        p.setPen(QColor(C["texto"]))
        p.drawText(QRectF(r.left(), r.top() + 22, r.width(), r.height() - 22),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), texto)


class Cifra(Tarjeta):
    """Un número con su nombre arriba: nada más."""

    def __init__(self, titulo: str):
        super().__init__(t(titulo), 96)
        self.numero = "—"

    def poner(self, numero: str) -> None:
        self.numero = numero
        self.llegaron_datos()

    def pintar(self, p: QPainter, r: QRectF) -> None:
        p.setFont(letra(28, QFont.Weight.DemiBold))
        p.setPen(QColor(C["texto"]))
        p.drawText(r, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self.numero)


class Filas(TarjetaSuave):
    """Una lista corta con una barra finita debajo de cada nombre. Al cambiar, cada fila viaja a su lugar nuevo;
    las que entran y salen se funden."""

    FILA = 34
    ARRIBA = 26
    CUANTAS = 3

    def __init__(self, nombre: str, alto: int = 180):
        super().__init__(alto)
        self.nombre = nombre
        self.datos: list[tuple[str, float, str]] = []
        self.filas: dict[str, dict] = {}
        self.corre = Resorte(self, 1.0, 0.55, 1.0, al_paso=lambda _: self.update(), al_llegar=self.limpiar)

    def limpiar(self) -> None:
        self.filas = {k: f for k, f in self.filas.items() if f["a1"] > 0}

    def actual(self, f: dict) -> tuple[float, float, float]:
        k = tope(self.corre.x)
        if f["a1"] <= 0:  # la que se va, rápido; la que entra espera un poco: los textos no se pisan
            alfa = f["a0"] * (1 - tope(k / 0.36))
        else:
            alfa = f["a0"] + (1 - f["a0"]) * tope((k - 0.3) / 0.7)
        return f["y0"] + (f["y1"] - f["y0"]) * k, f["f0"] + (f["f1"] - f["f0"]) * k, alfa

    def poner(self, items: list[tuple[str, float, str]]) -> None:
        items = items[:self.CUANTAS]
        if items == self.datos and self.con_datos:
            return
        self.datos = items
        maximo = max((v for _, v, _ in items), default=0) or 1
        viejas = {k: (self.actual(f), f) for k, f in self.filas.items()}
        filas: dict[str, dict] = {}
        for i, (nombre, valor, detalle) in enumerate(items):
            y1 = float(i * self.FILA)
            (y0, f0, a0), _ = viejas.pop(nombre, ((y1 + 6, 0.0, 0.0), None))
            filas[nombre] = {"nombre": nombre, "detalle": detalle, "y0": y0, "y1": y1, "f0": f0, "f1": valor / maximo,
                             "a0": a0, "a1": 1.0}
        for nombre, ((y, fraccion, a), vieja) in viejas.items():
            if a > 0.01:
                filas[nombre] = dict(vieja, y0=y, y1=y - 4, f0=fraccion, f1=fraccion, a0=a, a1=0.0)
        self.filas = filas
        self.con_datos = True
        self.corre.ir_a(1.0, desde=0.0) if self.isVisible() else self.corre.fijar(1.0)
        self.update()

    def pintar(self, p: QPainter, r: QRectF) -> None:
        self.pintar_titulo(p, r, self.nombre)
        lista = QRectF(r.left(), r.top() + self.ARRIBA, r.width(), r.height() - self.ARRIBA)
        if not self.datos and not self.filas:
            return self.sin_datos(p, lista)
        izquierda = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        derecha = int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        for f in self.filas.values():
            dy, fraccion, alfa = self.actual(f)
            if alfa <= 0.01:
                continue
            y = lista.top() + dy
            p.setOpacity(tope(alfa))
            p.setFont(letra(12.5))
            ancho_detalle = QFontMetricsF(p.font()).horizontalAdvance(f["detalle"]) + 8
            p.setPen(QColor(C["texto"]))
            p.drawText(QRectF(lista.left(), y, lista.width() - ancho_detalle, 18), izquierda,
                       QFontMetricsF(p.font()).elidedText(f["nombre"], Qt.TextElideMode.ElideRight,
                                                          lista.width() - ancho_detalle - 4))
            p.setPen(QColor(C["suave"]))
            p.drawText(QRectF(lista.left(), y, lista.width(), 18), derecha, f["detalle"])
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(con_alfa(C["texto"], 0.07))
            p.drawRoundedRect(QRectF(lista.left(), y + 22, lista.width(), 4), 2, 2)
            p.setBrush(QColor(C["acento"]))
            p.drawRoundedRect(QRectF(lista.left(), y + 22, max(4.0, lista.width() * max(0.0, fraccion)), 4), 2, 2)
        p.setOpacity(1.0)


class EnVivo(QWidget):
    """Un puntito que late y "En vivo": pulsa cada vez que llegan datos nuevos."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(32)
        self.setMinimumWidth(110)
        self.pulso = Resorte(self, 0.0, 0.9, 1.0, al_paso=lambda _: self.update())
        self.vivo = False

    def latir(self, vivo: bool = True) -> None:
        self.vivo = vivo
        self.pulso.ir_a(0.0, desde=1.0) if self.isVisible() else self.pulso.fijar(0.0)
        self.update()

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        texto = t("En vivo") if self.vivo else t("Analizando…")
        p.setFont(letra(12.5, QFont.Weight.DemiBold))
        ancho = QFontMetricsF(p.font()).horizontalAdvance(texto)
        x = self.width() - ancho - 2
        color = QColor("#5DC98D") if self.vivo else QColor(C["suave"])
        centro = QPointF(x - 12, self.height() / 2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(con_alfa(color, 0.35 * self.pulso.x))
        p.drawEllipse(centro, 4 + 7 * (1 - self.pulso.x), 4 + 7 * (1 - self.pulso.x))
        p.setBrush(color)
        p.drawEllipse(centro, 4, 4)
        p.setPen(QColor(C["suave"]))
        p.drawText(QRectF(x, 0, ancho + 2, self.height()), int(Qt.AlignmentFlag.AlignVCenter), texto)


class Analista(QObject):
    """Corre el análisis en un hilo y avisa con el informe. Uno por vez: si ya hay uno corriendo, espera."""

    listo = pyqtSignal(object)

    def __init__(self, padre: QObject | None = None, analisis: estadisticas.Analisis | None = None):
        super().__init__(padre)
        self.analisis = analisis or estadisticas.Analisis(cache=m.CONFIG_DIR / "cache" / "uso.json")
        self.ocupado = False
        self.cerrado = threading.Event()
        self.analisis.cancelado = self.cerrado.is_set

    def pedir(self) -> bool:
        if self.ocupado or self.cerrado.is_set():
            return False
        self.ocupado = True
        threading.Thread(target=self.correr, daemon=True).start()
        return True

    def correr(self) -> None:
        informe = None
        try:
            informe = self.analisis.actualizar()
        except Exception as e:  # un transcript raro no puede dejar la sección colgada en "Analizando…"
            m.log(f"[paneles] error analizando el uso: {e!r}")
        self.avisar(informe)
        self.ocupado = False

    def avisar(self, informe) -> None:
        if not self.cerrado.is_set():
            try:
                self.listo.emit(informe)
            except RuntimeError:  # la ventana se cerró mientras tanto
                pass

    def cerrar(self) -> None:
        self.cerrado.set()


def columnas(*widgets, pesos: tuple[int, ...] = ()) -> QHBoxLayout:
    caja = QHBoxLayout()
    caja.setSpacing(14)
    for i, w in enumerate(widgets):
        caja.addWidget(w, pesos[i] if i < len(pesos) else 1, Qt.AlignmentFlag.AlignTop)
    return caja


def lista_de(pares: list[tuple[str, int]]) -> list[tuple[str, float, str]]:
    return [(nombre, valor, tokens(valor)) for nombre, valor in pares]


class Uso(QWidget):
    """¿Cómo vengo? La curva del lapso elegido y los modelos; abajo tres números y los proyectos."""

    ANGOSTA, ANCHA = 720, 760  # dos medidas: que una barra de scroll no la haga saltar de una forma a la otra

    def __init__(self, selector: QWidget, lapso: str = "hoy"):
        super().__init__()
        self.lapso = lapso if lapso in BOTON_LAPSO else "hoy"
        self.informe: dict | None = None
        self.angosta: bool | None = None
        # Lo que va a medir al terminar de acomodarse: al entrar, la columna de la vista previa se está plegando y
        # la forma se elige por cómo va a quedar, no por cada paso del camino (ajustes.py conecta esto).
        self.ancho_final = self.width
        caja = QVBoxLayout(self)
        caja.setContentsMargins(0, 0, 0, 0)
        caja.setSpacing(2)
        arriba = QHBoxLayout()
        arriba.setContentsMargins(SOMBRA, 0, SOMBRA, 0)
        arriba.addWidget(selector)  # el selector lo arma ajustes.py (sus segmentos)
        arriba.addStretch(1)
        self.vivo = EnVivo()
        arriba.addWidget(self.vivo)
        caja.addLayout(arriba)
        self.curva = Area()
        self.dona = Dona(t("Modelos"))
        self.sesiones = Dato(t("Sesiones"), lambda x: str(round(x)))
        self.trabajo = Dato(t("Claude trabajando"), duracion)
        self.cache = Dato(t("Desde la caché"), lambda x: f"{round(x * 100)} %")
        self.proyectos = Filas(t("Proyectos"))
        self.datos = QWidget()
        fila = QHBoxLayout(self.datos)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(0)
        for dato in (self.sesiones, self.trabajo, self.cache):
            fila.addWidget(dato)
        self.derecha = QWidget()  # la dona arriba de los proyectos: juntas miden lo mismo que la curva y los números
        columna = QVBoxLayout(self.derecha)
        columna.setContentsMargins(0, 0, 0, 0)
        columna.setSpacing(0)
        columna.addWidget(self.dona)
        columna.addWidget(self.proyectos)
        self.rejilla = QGridLayout()
        self.rejilla.setSpacing(0)
        caja.addLayout(self.rejilla)
        caja.addStretch(1)
        self.acomodar(900)

    def acomodar(self, ancho: int) -> None:
        """Dos columnas si entra; si la ventana es angosta, una sola."""
        angosta = ancho < self.ANGOSTA if self.angosta is None or not self.angosta else ancho < self.ANCHA
        if angosta == self.angosta:
            return
        self.angosta = angosta
        for w in (self.curva, self.datos, self.derecha):
            self.rejilla.removeWidget(w)
        self.rejilla.addWidget(self.curva, 0, 0)
        self.rejilla.addWidget(self.datos, 1, 0)
        if angosta:
            self.rejilla.addWidget(self.derecha, 2, 0)
            self.rejilla.setColumnStretch(0, 1)
            self.rejilla.setColumnStretch(1, 0)
        else:
            self.rejilla.addWidget(self.derecha, 0, 1, 2, 1, Qt.AlignmentFlag.AlignTop)
            self.rejilla.setColumnStretch(0, 2)
            self.rejilla.setColumnStretch(1, 1)

    def resizeEvent(self, evento) -> None:
        super().resizeEvent(evento)
        self.acomodar(self.ancho_final())

    def showEvent(self, evento) -> None:
        super().showEvent(evento)
        self.acomodar(self.ancho_final())
        if not evento.spontaneous():  # volver de minimizada no repite la entrada
            self.curva.entrar()

    def elegir(self, lapso: str) -> None:
        if lapso in BOTON_LAPSO and lapso != self.lapso:
            self.lapso = lapso
            self.pintar_lapso(de_nuevo=True)

    def mostrar(self, informe: dict | None) -> None:
        self.vivo.latir(bool(informe))
        if informe:
            self.informe = informe
            self.pintar_lapso()

    @staticmethod
    def ayudas(cuantas: int, paso: int, serie: list[float]) -> list[tuple[str, str]]:
        """Lo que dice la burbuja de cada punto: (cuándo, cuánto)."""
        ahora = datetime.now()
        formato = "%H:%M" if paso < 3600 else "%d/%m %H h" if paso < 86400 else "%d/%m"
        return [(f"{ahora - timedelta(seconds=(cuantas - i) * paso):{formato}}", tokens(valor))
                for i, valor in enumerate(serie)]

    @staticmethod
    def marcas(cuantas: int, paso: int) -> list[tuple[float, str]]:
        """Las fechas u horas debajo de la curva, repartidas parejo; la última es "ahora"."""
        ahora = datetime.now()
        formato = "%H:%M" if cuantas * paso <= 86400 else "%d/%m"
        salida = []
        for k in (0.0, 0.25, 0.5, 0.75):
            i = round(k * (cuantas - 1))
            salida.append((i / (cuantas - 1), f"{ahora - timedelta(seconds=(cuantas - i) * paso):{formato}}"))
        return salida + [(1.0, t("ahora"))]

    def pintar_lapso(self, de_nuevo: bool = False) -> None:
        if not self.informe:
            return
        v = self.informe["lapsos"][self.lapso]
        if self.lapso == "hoy":
            valores = v["serie"]
            ultimo = datetime.now().hour
            ayudas = [(f"{i:02d}:00", tokens(valor)) for i, valor in enumerate(valores)]
            marcas = [(h / 23, f"{h:02d}:00") for h in (0, 6, 12, 18, 23)]
            contra = t("contra ayer a esta hora")
        else:
            _, paso, _ = estadisticas.LAPSOS[self.lapso]
            cada = AGRUPAR.get(self.lapso, 1)
            valores = estadisticas.agrupar(v["serie"], cada)
            paso *= cada
            ultimo = len(valores) - 1
            ayudas = self.ayudas(len(valores), paso, valores)
            marcas = self.marcas(len(valores), paso)
            contra = t("contra el lapso anterior")
        textos = {"titulo": t(TITULO_LAPSO[self.lapso]), "unidad": "tokens", "contra": contra,
                  "cambio": cambio(v["tokens"], v["anterior"]), "marcas": marcas,
                  "detalle": t("{entrada} de entrada · {salida} de salida", entrada=tokens(v["entrada"]),
                               salida=tokens(v["salida"]))}
        self.curva.poner(textos, v["tokens"], valores, ayudas, ultimo, de_nuevo)
        self.dona.poner(v["modelos"], v["tokens"])
        self.sesiones.poner(float(v["sesiones"]))
        self.trabajo.poner(float(v["trabajo"]))
        self.cache.poner(float(v["acierto_cache"]))
        self.proyectos.poner(lista_de(v["proyectos"]))
