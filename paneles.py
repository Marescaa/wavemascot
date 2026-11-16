"""Las secciones Dashboard y Uso de los ajustes: pocas cosas, grandes, y un solo gráfico por pantalla.

Las dos tienen la misma forma (como Tiempo de uso o Batería en iOS): una tarjeta protagonista con la cifra
bien grande, cuánto cambió contra el período anterior y un gráfico de barras; debajo, tres cifras chicas y
dos tarjetas cortas.

- Dashboard: hoy. Las barras son los últimos 14 días.
- Uso: el lapso que elijas (5 horas, 1 día, 7 días, 1 mes o 6 meses), siempre terminando ahora.

Todo se actualiza en vivo mientras se mira: los datos los arma estadisticas.py en un hilo aparte (Analista)
leyendo solo lo nuevo de cada transcript; acá solo se dibuja.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta

import estadisticas
import mascota as m
import seguimiento
from animacion import Resorte, mezcla
from idiomas import t

from PyQt6.QtCore import QObject, QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QSizePolicy, QToolTip, QVBoxLayout, QWidget

# Los colores de la ventana de ajustes: ajustes.py pone acá su mismo diccionario (cambia con el tema).
C: dict = {"fondo": "#1C1513", "panel": "#251D1A", "campo": "#2F2623", "borde": "#43362F", "texto": "#F4EDE8",
           "suave": "#B3A39A", "acento": "#D97757", "acento2": "#E8906F"}
VIDRIO = False  # la ventana desenfoca lo de atrás (ver ajustes.Ajustes.preparar_vidrio)
RADIO = 18      # el de las tarjetas; lo de adentro usa radios más chicos (concéntricos)
HISTORIAL = m.CONFIG_DIR / "duraciones.json"
VIVO = 5        # segundos entre un análisis y el siguiente mientras se mira Dashboard o Uso
# Los lapsos de Uso (las claves de estadisticas.LAPSOS): el botón, el título de la tarjeta y desde cuándo.
BOTON_LAPSO = {"5h": "5 h", "1d": "1 día", "7d": "7 días", "30d": "1 mes", "180d": "6 meses"}
TITULO_LAPSO = {"5h": "Últimas 5 horas", "1d": "Últimas 24 horas", "7d": "Últimos 7 días", "30d": "Últimos 30 días",
                "180d": "Últimos 6 meses"}
DESDE_LAPSO = {"5h": "hace 5 h", "1d": "hace 24 h", "7d": "hace 7 días", "30d": "hace 30 días",
               "180d": "hace 6 meses"}


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

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pintar_tarjeta(p, self.rect())
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


class Protagonista(Tarjeta):
    """La tarjeta grande: una cifra enorme, cuánto cambió contra el período anterior y un gráfico de barras
    (la última, la de ahora, con todo el color). Al pasar el mouse, cada barra dice lo suyo."""

    def __init__(self, alto: int = 318):
        super().__init__("", alto)
        self.cifra, self.unidad, self.cambio, self.detalle, self.contra = "—", "", None, "", ""
        self.serie: list[float] = []
        self.ayudas: list[str] = []
        self.desde, self.hasta = "", ""
        self.encima = -1
        self.setMouseTracking(True)

    def poner(self, titulo: str, cifra: str, unidad: str, cambio_: float | None, contra: str, detalle: str,
              serie: list[float], ayudas: list[str], desde: str, hasta: str, de_nuevo: bool = False) -> None:
        """contra: con qué se compara el cambio ("contra ayer"); detalle: una línea bajo la cifra."""
        self.titulo, self.cifra, self.unidad, self.cambio, self.detalle = titulo, cifra, unidad, cambio_, detalle
        self.contra = contra
        self.serie, self.ayudas, self.desde, self.hasta = serie, ayudas, desde, hasta
        self.llegaron_datos(de_nuevo)

    def zona(self) -> QRectF:
        r = self.area()
        return QRectF(r.left(), r.top() + 96, r.width(), r.height() - 96 - 20)

    def barras(self) -> list[QRectF]:
        zona, n = self.zona(), max(1, len(self.serie))
        paso = zona.width() / n
        ancho = max(3.0, min(30.0, paso * 0.66))
        return [QRectF(zona.left() + i * paso + (paso - ancho) / 2, zona.top(), ancho, zona.height()) for i in range(n)]

    def mouseMoveEvent(self, evento) -> None:
        zona, n = self.zona(), len(self.serie)
        x, y = evento.position().x(), evento.position().y()
        encima = -1
        if n and zona.left() <= x < zona.right() and y > zona.top() - 12:
            encima = min(n - 1, int((x - zona.left()) / (zona.width() / n)))
        if encima != self.encima:
            self.encima = encima
            self.update()
            if 0 <= encima < len(self.ayudas):
                QToolTip.showText(evento.globalPosition().toPoint(), self.ayudas[encima], self)
            else:
                QToolTip.hideText()

    def leaveEvent(self, evento) -> None:
        self.encima = -1
        self.update()

    def pintar(self, p: QPainter, r: QRectF) -> None:
        if not self.con_datos:
            return self.sin_datos(p, r, t("Analizando…"))
        # la cifra
        p.setFont(letra(54, QFont.Weight.Bold))
        p.setPen(QColor(C["texto"]))
        ancho = QFontMetricsF(p.font()).horizontalAdvance(self.cifra)
        p.drawText(QRectF(r.left() - 2, r.top() - 4, ancho + 8, 62), int(Qt.AlignmentFlag.AlignVCenter), self.cifra)
        p.setFont(letra(15, QFont.Weight.Medium))
        p.setPen(QColor(C["suave"]))
        p.drawText(QRectF(r.left() + ancho + 8, r.top() + 22, 160, 26), int(Qt.AlignmentFlag.AlignVCenter), self.unidad)
        # el cambio, en una pastillita a la derecha
        if self.cambio is not None:
            texto = ("▲ " if self.cambio >= 0 else "▼ ") + f"{min(999, abs(round(self.cambio * 100)))} %"
            p.setFont(letra(12.5, QFont.Weight.DemiBold))
            ancho_p = QFontMetricsF(p.font()).horizontalAdvance(texto) + 22
            pastilla = QRectF(r.right() - ancho_p, r.top() + 12, ancho_p, 26)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(con_alfa(C["texto"], 0.09))
            p.drawRoundedRect(pastilla, 13, 13)
            p.setPen(QColor(C["texto"]))
            p.drawText(pastilla, int(Qt.AlignmentFlag.AlignCenter), texto)
            p.setFont(letra(12))
            p.setPen(QColor(C["suave"]))
            p.drawText(QRectF(r.right() - 220, pastilla.bottom() + 4, 220, 18),
                       int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), self.contra)
        p.setFont(letra(12.5))
        p.setPen(QColor(C["suave"]))
        p.drawText(QRectF(r.left(), r.top() + 60, r.width(), 20),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self.detalle)
        # las barras
        zona = self.zona()
        tope = max(self.serie) if self.serie else 0
        p.setPen(QPen(con_alfa(C["texto"], 0.10), 1))
        p.drawLine(QPointF(zona.left(), zona.bottom() + 0.5), QPointF(zona.right(), zona.bottom() + 0.5))
        if tope:
            crece = max(0.0, min(1.06, self.aparece.x))
            ultima = len(self.serie) - 1
            p.setPen(Qt.PenStyle.NoPen)
            for i, (valor, b) in enumerate(zip(self.serie, self.barras())):
                if not valor:
                    continue
                alto = max(2.0, (zona.height() - 6) * valor / tope * crece)
                p.setBrush(QColor(C["acento"]) if i in (ultima, self.encima) else con_alfa(C["acento"], 0.42))
                radio = min(5.0, b.width() / 2)
                p.drawRoundedRect(QRectF(b.left(), zona.bottom() - alto, b.width(), alto), radio, radio)
        p.setFont(letra(11.5))
        p.setPen(QColor(C["suave"]))
        p.drawText(QRectF(zona.left(), zona.bottom() + 5, 200, 16),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self.desde)
        p.drawText(QRectF(zona.right() - 200, zona.bottom() + 5, 200, 16),
                   int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), self.hasta)


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


class Ranking(Tarjeta):
    """Una lista corta de (nombre, valor, texto del valor) con una barra proporcional debajo de cada nombre."""

    FILA = 38

    def __init__(self, titulo: str, filas: int = 3):
        super().__init__(t(titulo), 40 + filas * self.FILA + 10)
        self.items: list[tuple[str, float, str]] = []
        self.cuantas = filas

    def poner(self, items: list[tuple[str, float, str]]) -> None:
        self.items = items[:self.cuantas]
        self.llegaron_datos()

    def pintar(self, p: QPainter, r: QRectF) -> None:
        if not self.items:
            return self.sin_datos(p, r)
        tope = max(v for _, v, _ in self.items) or 1
        crece = max(0.0, min(1.0, self.aparece.x))
        for i, (nombre, valor, detalle) in enumerate(self.items):
            y = r.top() + i * self.FILA
            ancho_detalle = QFontMetricsF(letra(13)).horizontalAdvance(detalle) + 8
            p.setFont(letra(13.5, QFont.Weight.DemiBold if i == 0 else QFont.Weight.Normal))
            p.setPen(QColor(C["texto"]))
            p.drawText(QRectF(r.left(), y, r.width() - ancho_detalle, 20),
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                       QFontMetricsF(p.font()).elidedText(nombre, Qt.TextElideMode.ElideRight, r.width() - ancho_detalle - 8))
            p.setFont(letra(13))
            p.setPen(QColor(C["suave"]))
            p.drawText(QRectF(r.left(), y, r.width(), 20),
                       int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), detalle)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(con_alfa(C["texto"], 0.09))
            p.drawRoundedRect(QRectF(r.left(), y + 25, r.width(), 5), 2.5, 2.5)
            p.setBrush(con_alfa(C["acento"], 1.0 if i == 0 else 0.55))
            p.drawRoundedRect(QRectF(r.left(), y + 25, max(5.0, r.width() * valor / tope * crece), 5), 2.5, 2.5)


class Anillo(Tarjeta):
    """Un porcentaje en un anillo, con una línea al lado."""

    def __init__(self, titulo: str, alto: int = 164):
        super().__init__(t(titulo), alto)
        self.fraccion: float | None = None
        self.linea = ""

    def poner(self, fraccion: float | None, linea: str = "") -> None:
        self.fraccion, self.linea = fraccion, linea
        self.llegaron_datos()

    def pintar(self, p: QPainter, r: QRectF) -> None:
        if self.fraccion is None:
            return self.sin_datos(p, r, self.linea)
        lado = min(r.height(), 96.0)
        caja = QRectF(r.left() + 5, r.center().y() - lado / 2, lado, lado).adjusted(5, 5, -5, -5)
        pluma = QPen(con_alfa(C["texto"], 0.10), 10)
        pluma.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(pluma)
        p.drawEllipse(caja)
        pluma.setColor(QColor(C["acento"]))
        p.setPen(pluma)
        p.drawArc(caja, 90 * 16, -round(360 * 16 * self.fraccion * max(0.0, min(1.0, self.aparece.x))))
        p.setFont(letra(21, QFont.Weight.Bold))
        p.setPen(QColor(C["texto"]))
        p.drawText(caja, int(Qt.AlignmentFlag.AlignCenter), f"{round(self.fraccion * 100)}%")
        p.setFont(letra(13))
        p.setPen(QColor(C["suave"]))
        p.drawText(QRectF(caja.right() + 22, r.top(), r.right() - caja.right() - 22, r.height()),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap), self.linea)


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

    def __init__(self, padre: QObject | None = None, analisis: estadisticas.Analisis | None = None,
                 historial=HISTORIAL):
        super().__init__(padre)
        self.analisis = analisis or estadisticas.Analisis(cache=m.CONFIG_DIR / "cache" / "uso.json")
        self.historial = historial
        self.ocupado = False
        self.cerrado = threading.Event()
        self.analisis.cancelado = self.cerrado.is_set
        self.precision: dict | None = None
        self.precision_hora = 0.0

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
            if informe is not None:
                informe["precision"] = self.precision
                informe["midiendo"] = self.precision is None and time.time() - self.precision_hora > 600
        except Exception as e:  # un transcript raro no puede dejar la sección colgada en "Analizando…"
            m.log(f"[paneles] error analizando el uso: {e!r}")
        self.avisar(informe)
        # La precisión tarda unos segundos: los números llegan primero y ella después. Cada 10 minutos alcanza.
        if informe is not None and time.time() - self.precision_hora > 600 and not self.cerrado.is_set():
            self.precision_hora = time.time()
            try:
                self.medir_precision()
                self.avisar(dict(informe, precision=self.precision, midiendo=False))
            except Exception as e:
                m.log(f"[paneles] no se pudo medir la precisión: {e!r}")
        self.ocupado = False

    def avisar(self, informe) -> None:
        if not self.cerrado.is_set():
            try:
                self.listo.emit(informe)
            except RuntimeError:  # la ventana se cerró mientras tanto
                pass

    def medir_precision(self) -> None:
        estimador = seguimiento.Estimador(self.historial)
        if estimador.vacio and self.historial:  # la barra todavía no armó el historial: se arma acá, igual
            monitor = seguimiento.Monitor(self.historial, self.analisis.carpeta)
            monitor.cancelado = self.cerrado.is_set
            monitor.aprender_del_pasado()
            estimador = monitor.estimador
        self.precision = estimador.precision(150, self.cerrado.is_set)

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


class Dashboard(QWidget):
    """¿Cómo vengo hoy? La cifra de hoy y los últimos 14 días; abajo, tres números y dos tarjetas."""

    def __init__(self):
        super().__init__()
        caja = QVBoxLayout(self)
        caja.setContentsMargins(0, 0, 0, 0)
        caja.setSpacing(14)
        self.hoy = Protagonista()
        caja.addWidget(self.hoy)
        self.sesiones, self.trabajo, self.semana = Cifra("Sesiones"), Cifra("Claude trabajando"), Cifra("7 días")
        caja.addLayout(columnas(self.sesiones, self.trabajo, self.semana))
        self.proyectos = Ranking("Proyectos de la semana")
        self.precision = Anillo("Precisión del tiempo estimado")
        caja.addLayout(columnas(self.proyectos, self.precision))
        caja.addStretch(1)

    def mostrar(self, informe: dict | None) -> None:
        if not informe:
            return
        hoy, ayer, dias = informe["hoy"], informe["ayer"], informe["dias"]
        self.hoy.poner(t("Hoy"), tokens(hoy["tokens"]), "tokens", cambio(hoy["tokens"], ayer["tokens"] if ayer else 0),
                       t("contra ayer"), t("{n} por minuto ahora", n=tokens(informe["ritmo"])) if informe["ritmo"] else "",
                       [d["tokens"] for d in dias], [f"{d['dia']:%d/%m} · {tokens(d['tokens'])}" for d in dias],
                       f"{dias[0]['dia']:%d/%m}", t("hoy"))
        self.sesiones.poner(str(hoy["sesiones"]))
        self.trabajo.poner(duracion(hoy["trabajo"]))
        self.semana.poner(tokens(informe["semana"]))
        self.proyectos.poner([(nombre, valor, tokens(valor)) for nombre, valor, _ in informe["proyectos"]])
        medida = informe.get("precision")
        if medida:
            self.precision.poner(medida["dentro_del_doble"],
                                 t("Error típico: {n}", n=duracion(medida["error_mediano"])))
        else:
            self.precision.poner(None, t("Analizando…") if informe.get("midiendo")
                                 else t("Hacen falta más turnos para medirla"))


class Uso(QWidget):
    """¿Cuánto llevo gastado? El lapso elegido en grande, con su gráfico; abajo entrada, salida, caché y
    en qué modelos y proyectos se fue."""

    def __init__(self, selector: QWidget, lapso: str = "5h"):
        super().__init__()
        self.lapso = lapso if lapso in estadisticas.LAPSOS else "5h"
        self.informe: dict | None = None
        caja = QVBoxLayout(self)
        caja.setContentsMargins(0, 0, 0, 0)
        caja.setSpacing(14)
        arriba = QHBoxLayout()
        arriba.addWidget(selector)  # el selector de lapso lo arma ajustes.py (sus segmentos)
        arriba.addStretch(1)
        self.vivo = EnVivo()
        arriba.addWidget(self.vivo)
        caja.addLayout(arriba)
        self.total = Protagonista()
        caja.addWidget(self.total)
        self.entrada, self.salida, self.cache = Cifra("Entrada"), Cifra("Salida"), Cifra("Desde la caché")
        caja.addLayout(columnas(self.entrada, self.salida, self.cache))
        self.modelos, self.proyectos = Ranking("Modelos"), Ranking("Proyectos")
        caja.addLayout(columnas(self.modelos, self.proyectos))
        caja.addStretch(1)

    def elegir(self, lapso: str) -> None:
        if lapso in estadisticas.LAPSOS and lapso != self.lapso:
            self.lapso = lapso
            self.pintar_lapso(de_nuevo=True)

    def mostrar(self, informe: dict | None) -> None:
        self.vivo.latir(bool(informe))
        if informe:
            self.informe = informe
            self.pintar_lapso()

    @staticmethod
    def ayudas(cuantas: int, paso: int, serie: list[float]) -> list[str]:
        ahora = datetime.now()
        formato = "%H:%M" if paso < 3600 else "%d/%m %H h" if paso < 86400 else "%d/%m"
        return [f"{ahora - timedelta(seconds=(cuantas - i) * paso):{formato}} · {tokens(valor)}"
                for i, valor in enumerate(serie)]

    def pintar_lapso(self, de_nuevo: bool = False) -> None:
        if not self.informe:
            return
        v = self.informe["lapsos"][self.lapso]
        titulo, desde = TITULO_LAPSO[self.lapso], DESDE_LAPSO[self.lapso]
        _, paso, cuantas = estadisticas.LAPSOS[self.lapso]
        ritmo = self.informe["ritmo"]
        detalle = t("{n} por minuto ahora", n=tokens(ritmo)) if ritmo else ""
        self.total.poner(t(titulo), tokens(v["tokens"]), "tokens", cambio(v["tokens"], v["anterior"]),
                         t("contra el lapso anterior"), detalle,
                         v["serie"], self.ayudas(cuantas, paso, v["serie"]), t(desde), t("ahora"), de_nuevo)
        self.entrada.poner(tokens(v["entrada"]))
        self.salida.poner(tokens(v["salida"]))
        self.cache.poner(f"{round(v['acierto_cache'] * 100)} %")
        self.modelos.poner(lista_de(v["modelos"]))
        self.proyectos.poner(lista_de(v["proyectos"]))
