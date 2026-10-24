"""WaveMascot Pro en los ajustes: el cartel PRO, la tarjeta con tu plan y la guía para desbloquearlo.

La app es gratis y abierta; los avisos y los permisos por Telegram son de Pro. Acá solo se muestra lo que
dice el servidor (servidor/worker.js), que es quien decide si un aviso sale: tocar esto no desbloquea nada.

Los colores son los de la ventana de ajustes (el diccionario C de ajustes.py, que cambia con el tema y el
estilo): ajustes.py lo pasa con usar_colores() y cada control los lee al pintarse.
"""

from __future__ import annotations

import math
import random
from datetime import datetime

from PyQt6.QtCore import QEasingCurve, QElapsedTimer, QEvent, QPointF, QRectF, QSize, Qt, QTimer, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import (QColor, QFont, QFontMetrics, QImage, QLinearGradient, QPainter, QPainterPath, QPen,
                         QPolygonF, QRadialGradient)
from PyQt6.QtWidgets import (QAbstractButton, QButtonGroup, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                             QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

import celular
import idiomas
import mascota as m
import sprites
from idiomas import t

C: dict = {"fondo": "#1C1513", "panel": "#251D1A", "campo": "#2F2623", "borde": "#43362F", "texto": "#F4EDE8",
           "suave": "#B3A39A", "acento": "#D97757", "acento2": "#E8906F", "sobre": "#1C1513"}
PAGOS = ("mensual", "vitalicio", "regalo")  # planes que se pagan (o se regalan): ya sos Pro de verdad
MESES = {
    "es": ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
           "noviembre", "diciembre"),
    "en": ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"),
    "pt": ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
           "novembro", "dezembro"),
}
ORO = ("#FFD95A", "#F5A300")  # la estrella de Telegram Stars
BLANCO = "#FFF7F2"


def usar_colores(colores: dict) -> None:
    """ajustes.py pasa su diccionario de colores (el mismo objeto: los cambios de tema se ven solos)."""
    global C
    C = colores


def color(clave: str, alfa: float | None = None) -> QColor:
    c = QColor(C.get(clave, clave))
    if alfa is not None:
        c.setAlphaF(alfa)
    return c


def mezclar(a, b, k: float) -> QColor:
    """a hacia b, en proporción k (0 = a, 1 = b)."""
    a, b = QColor(a), QColor(b)
    return QColor(round(a.red() + (b.red() - a.red()) * k), round(a.green() + (b.green() - a.green()) * k),
                  round(a.blue() + (b.blue() - a.blue()) * k))


def fuente(base: QFont, puntos: float, peso: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """Una letra de `puntos` (como en la hoja de estilo: en macOS, los mismos píxeles que en Windows)."""
    f = QFont(base)
    if m.MAC:
        f.setPixelSize(round(puntos * 96 / 72))
    else:
        f.setPointSizeF(puntos)
    f.setWeight(peso)
    return f


def tam(puntos: float) -> str:
    """Tamaño de letra para una hoja de estilo (la global pisa setFont): pt en Windows, px en macOS."""
    return f"{round(puntos * 96 / 72)}px" if m.MAC else f"{puntos}pt"


def fecha(ms: float) -> str:
    """23 de noviembre / November 23 / 23 de novembro."""
    d = datetime.fromtimestamp(ms / 1000)
    idioma = idiomas.actual()
    mes = MESES.get(idioma, MESES["en"])[d.month - 1]
    return f"{mes} {d.day}" if idioma == "en" else f"{d.day} de {mes}"


def estrella(p: QPainter, centro: QPointF, radio: float) -> None:
    """La estrella dorada de Telegram Stars."""
    puntos = []
    for i in range(10):
        r = radio if i % 2 == 0 else radio * 0.48
        angulo = -math.pi / 2 + i * math.pi / 5
        puntos.append(QPointF(centro.x() + r * math.cos(angulo), centro.y() + r * math.sin(angulo)))
    degrade = QLinearGradient(centro.x(), centro.y() - radio, centro.x(), centro.y() + radio)
    degrade.setColorAt(0, QColor(ORO[0]))
    degrade.setColorAt(1, QColor(ORO[1]))
    lapiz = QPen(QColor(ORO[1]), radio * 0.22)
    lapiz.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(lapiz)
    p.setBrush(degrade)
    p.drawPolygon(QPolygonF(puntos))


def destello(p: QPainter, centro: QPointF, radio: float, c: QColor) -> None:
    """Brillito de 4 puntas."""
    camino = QPainterPath()
    x, y, r, k = centro.x(), centro.y(), radio, radio * 0.22
    camino.moveTo(x, y - r)
    camino.quadTo(x + k, y - k, x + r, y)
    camino.quadTo(x + k, y + k, x, y + r)
    camino.quadTo(x - k, y + k, x - r, y)
    camino.quadTo(x - k, y - k, x, y - r)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c)
    p.drawPath(camino)


def describir(plan: dict | None, info: dict, conectado: bool) -> dict:
    """Qué decir del plan: título, detalle, la etiqueta corta (chip), el botón y si es un aviso (vencido)."""
    dias_prueba = info.get("dias_prueba", celular.DIAS_PRUEBA)
    tipo = (plan or {}).get("tipo") if conectado else None
    if not info.get("cobrando", True) or tipo == "libre":
        return {"tipo": "libre", "oculto": True, "titulo": "", "detalle": "", "chip": "", "boton": "", "aviso": False}
    d = {"tipo": tipo or "nuevo", "oculto": False, "aviso": False}
    if tipo is None:
        d.update(titulo=t("Telegram es parte de WaveMascot Pro"),
                 detalle=t("Conectalo y probalo gratis {dias} días. Todo lo demás es gratis para siempre.",
                           dias=dias_prueba),
                 chip=t("{dias} días de prueba gratis", dias=dias_prueba), boton=t("Cómo funciona"))
    elif tipo == "prueba":
        dias = plan.get("dias") or 0
        ultimo = dias <= 1
        d.update(titulo=t("Prueba gratis de Pro"),
                 detalle=t("Te queda menos de un día de prueba.") if ultimo
                 else t("Te quedan {dias} días (hasta el {fecha}).", dias=dias, fecha=fecha(plan["hasta"])),
                 chip=t("Prueba gratis · último día") if ultimo else t("Prueba gratis · quedan {dias} días", dias=dias),
                 boton=t("Pasarme a Pro"), aviso=ultimo)
    elif tipo == "mensual":
        d.update(titulo=t("Sos Pro"), chip=t("Sos Pro ✓"), boton=t("Mi plan"),
                 detalle=(t("Plan mensual · se renueva el {fecha}", fecha=fecha(plan["hasta"])) if plan.get("renueva")
                          else t("Plan mensual · termina el {fecha}", fecha=fecha(plan["hasta"]))))
    elif tipo == "regalo":
        d.update(titulo=t("Sos Pro"), chip=t("Sos Pro ✓"), boton=t("Mi plan"),
                 detalle=t("De regalo hasta el {fecha}", fecha=fecha(plan["hasta"])))
    elif tipo == "vitalicio":
        d.update(titulo=t("Sos Pro de por vida"), chip=t("Pro de por vida ✓"), boton=t("Mi plan"),
                 detalle=t("Es tuyo para siempre, en todas tus compus. ¡Gracias por bancar el proyecto!"))
    else:  # vencido
        d.update(titulo=t("Los avisos a Telegram están en pausa"),
                 detalle=t("Terminó tu prueba de Pro. Activalo y vuelven al instante."),
                 chip=t("Tu prueba terminó"), boton=t("Desbloquear Pro"), aviso=True)
    return d


# --- el cartel PRO ---------------------------------------------------------------------

class InsigniaPro(QAbstractButton):
    """Píldora «PRO» con el degradé del acento, un brillito y un reflejo que la cruza cada tanto."""

    def __init__(self, alto: int = 18):
        super().__init__()
        self.alto = alto
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reloj = QElapsedTimer()
        self.reloj.start()
        self.timer = QTimer(self, interval=40, timeout=self.update)
        self.letra = fuente(self.font(), self.alto * 0.42, QFont.Weight.Black)
        self.letra.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, self.alto * 0.05)
        ancho = QFontMetrics(self.letra).horizontalAdvance("PRO")
        self.setFixedSize(round(self.alto * 0.45 + self.alto * 0.62 + ancho + self.alto * 0.5), self.alto)

    def sizeHint(self) -> QSize:
        return self.size()

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        forma = QPainterPath()
        forma.addRoundedRect(r, r.height() / 2, r.height() / 2)
        degrade = QLinearGradient(r.topLeft(), r.bottomRight())
        degrade.setColorAt(0, mezclar(C["acento2"], "#FFFFFF", 0.18))
        degrade.setColorAt(1, QColor(C["acento"]))
        p.fillPath(forma, degrade)
        # El reflejo: una franja clara que cruza en diagonal durante 0,7 s de cada 3,6 s.
        fase = (self.reloj.elapsed() % 3600) / 700
        if fase < 1:
            p.save()
            p.setClipPath(forma)
            x = -r.height() + (r.width() + 2 * r.height()) * fase
            brillo = QLinearGradient(x - r.height(), 0, x + r.height(), 0)
            brillo.setColorAt(0, QColor(255, 255, 255, 0))
            brillo.setColorAt(0.5, QColor(255, 255, 255, 120))
            brillo.setColorAt(1, QColor(255, 255, 255, 0))
            p.fillRect(r, brillo)
            p.restore()
        if self.underMouse() or self.isDown():
            p.setPen(QPen(QColor(255, 255, 255, 110), 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(forma)
        tinta = QColor(C["sobre"])
        destello(p, QPointF(self.alto * 0.45 + self.alto * 0.2, r.center().y()), self.alto * 0.24, tinta)
        p.setFont(self.letra)
        p.setPen(tinta)
        p.drawText(r.adjusted(self.alto * 0.45 + self.alto * 0.52, 0, 0, 0),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), "PRO")

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


# --- la tarjeta del plan (arriba de la pestaña Celular) ------------------------------------------

class TarjetaPlan(QFrame):
    """Cómo está tu Pro, en una línea, con el cartel PRO y un botón. Tocarla abre la guía."""

    abrir = pyqtSignal()

    def __init__(self):
        super().__init__(objectName="tarjeta_plan")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        caja = QHBoxLayout(self)
        caja.setContentsMargins(14, 12, 14, 12)
        caja.setSpacing(12)
        self.insignia = InsigniaPro(22)
        self.insignia.clicked.connect(self.abrir)
        caja.addWidget(self.insignia, 0, Qt.AlignmentFlag.AlignVCenter)
        textos = QVBoxLayout()
        textos.setSpacing(1)
        self.titulo = QLabel(objectName="plan_titulo", wordWrap=True)
        self.detalle = QLabel(objectName="ayuda", wordWrap=True)
        textos.addWidget(self.titulo)
        textos.addWidget(self.detalle)
        caja.addLayout(textos, 1)
        self.boton = QPushButton(clicked=self.abrir)
        caja.addWidget(self.boton, 0, Qt.AlignmentFlag.AlignVCenter)

    def mostrar(self, d: dict) -> None:
        self.setVisible(not d["oculto"])
        self.titulo.setText(d["titulo"])
        self.detalle.setText(d["detalle"])
        self.boton.setText(d["boton"])
        self.boton.setObjectName("primario" if d["tipo"] in ("vencido", "prueba", "nuevo") else "")
        self.setProperty("aviso", d["aviso"])
        for w in (self, self.boton):
            w.style().unpolish(w)
            w.style().polish(w)

    def mousePressEvent(self, evento) -> None:
        self.abrir.emit()


# --- piezas de la guía ---------------------------------------------------------------------

def cuadros_qt(aspecto: dict, estado: str) -> tuple[list[QImage], int]:
    """Los cuadros de la mascota (los mismos de los avisos) como imágenes de Qt."""
    cuadros, ms = sprites.ESTADOS[estado](sprites.normalizar(aspecto))
    imagenes = []
    for cuadro in cuadros:
        c = cuadro.convert("RGBA")
        imagenes.append(QImage(c.tobytes("raw", "RGBA"), c.width, c.height, QImage.Format.Format_RGBA8888).copy())
    return imagenes, ms if isinstance(ms, int) else ms[0]


class Hero(QWidget):
    """La cabecera de la guía: un celular donde Wave pide permiso, alguien toca «Permitir» y después avisa
    que terminó; al lado, el título. Siempre oscura (en tema claro también), con el acento del estilo."""

    ALTO = 200
    CICLO = 7200  # ms

    def __init__(self, aspecto: dict):
        super().__init__()
        self.setFixedHeight(self.ALTO)
        self.aspecto = aspecto
        self.cuadros: dict[str, tuple[list[QImage], int]] = {}
        self.reloj = QElapsedTimer()
        self.reloj.start()
        self.timer = QTimer(self, interval=33, timeout=self.update)
        azar = random.Random(7)
        self.estrellitas = [(azar.random(), azar.random(), azar.uniform(0.6, 1.6), azar.random()) for _ in range(26)]

        caja = QHBoxLayout(self)
        caja.setContentsMargins(250, 26, 64, 22)
        textos = QVBoxLayout()
        textos.setSpacing(6)
        textos.addStretch(1)
        self.insignia = InsigniaPro(24)
        self.insignia.setCursor(Qt.CursorShape.ArrowCursor)
        textos.addWidget(self.insignia)
        self.titulo = QLabel("WaveMascot Pro")
        self.subtitulo = QLabel(t("Claude Code te avisa en el celular, y le das permiso desde donde estés."),
                                wordWrap=True)
        self.chip = QLabel()
        self.titulo.setStyleSheet(f"color: {BLANCO}; background: transparent; font-size: {tam(21)}; font-weight: 700;")
        self.subtitulo.setStyleSheet(f"color: rgba(255, 247, 242, 0.78); background: transparent; "
                                     f"font-size: {tam(10.5)};")
        self.chip.setStyleSheet(f"color: {BLANCO}; background: rgba(255, 255, 255, 0.13); border: 1px solid "
                                f"rgba(255, 255, 255, 0.22); border-radius: 11px; padding: 3px 11px; "
                                f"font-size: {tam(9)}; font-weight: 600;")
        textos.addWidget(self.titulo)
        textos.addWidget(self.subtitulo)
        textos.addSpacing(4)
        textos.addWidget(self.chip, 0, Qt.AlignmentFlag.AlignLeft)
        textos.addStretch(1)
        caja.addLayout(textos, 1)

    def preparar(self, aspecto: dict) -> None:
        if aspecto != self.aspecto or not self.cuadros:
            self.aspecto = aspecto
            self.cuadros = {estado: cuadros_qt(aspecto, estado) for estado in ("permiso", "listo")}

    def showEvent(self, evento) -> None:
        self.preparar(self.aspecto)
        self.reloj.restart()
        self.timer.start()
        super().showEvent(evento)

    def hideEvent(self, evento) -> None:
        self.timer.stop()
        super().hideEvent(evento)

    # dibujo

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        w, h = self.width(), self.height()
        forma = QPainterPath()  # esquinas de arriba redondeadas, como la tarjeta
        forma.addRoundedRect(QRectF(0, 0, w, h + 20), 17, 17)
        p.setClipPath(forma)
        oscuro = mezclar(C["acento"], "#0B0807", 0.86)
        degrade = QLinearGradient(0, 0, w, h)
        degrade.setColorAt(0, mezclar(C["acento"], "#0B0807", 0.62))
        degrade.setColorAt(0.55, oscuro)
        degrade.setColorAt(1, mezclar(C["acento"], "#0B0807", 0.92))
        p.fillRect(self.rect(), degrade)
        brillo = QRadialGradient(QPointF(130, h + 30), 260)
        brillo.setColorAt(0, color("acento", 0.55))
        brillo.setColorAt(1, color("acento", 0))
        p.fillRect(self.rect(), brillo)
        tiempo = self.reloj.elapsed()
        for x, y, r, fase in self.estrellitas:  # estrellitas que titilan
            alfa = 0.18 + 0.5 * (0.5 + 0.5 * math.sin(tiempo / 900 + fase * 6.3))
            destello(p, QPointF(x * w, y * h), r * 1.6, QColor(255, 247, 242, round(alfa * 255)))
        self.pintar_celular(p, tiempo % self.CICLO)

    def pintar_celular(self, p: QPainter, t_ms: float) -> None:
        cuerpo = QRectF(52, 24, 168, 240)
        p.setPen(QPen(QColor("#33333B"), 2))
        p.setBrush(QColor("#0A0A0D"))
        p.drawRoundedRect(cuerpo, 30, 30)
        pantalla = cuerpo.adjusted(7, 7, -7, -7)
        recorte = QPainterPath()
        recorte.addRoundedRect(pantalla, 23, 23)
        p.save()
        p.setClipPath(recorte, Qt.ClipOperation.IntersectClip)
        p.fillRect(pantalla, QColor("#0E1621"))  # el fondo oscuro de Telegram
        # La historia: llega el pedido (0 s), tocás Permitir (1,7 s), llega «¡Listo!» (3,2 s), se borra (6,6 s).
        def avance(desde, dura):
            return QEasingCurve(QEasingCurve.Type.OutCubic).valueForProgress(min(1, max(0, (t_ms - desde) / dura)))

        ancho = pantalla.width() - 22
        alto1, alto2 = 78, 56
        fondo = min(pantalla.bottom(), self.height()) - 12
        sube = avance(3200, 420) * (alto2 + 8)
        desvanecer = 1 - avance(6600, 500)
        p.setOpacity(desvanecer)
        llegada1 = avance(0, 420)
        y1 = fondo - alto1 - sube + (1 - llegada1) * 24
        p.setOpacity(desvanecer * llegada1)
        self.burbuja(p, QRectF(pantalla.left() + 8, y1, ancho, alto1), "permiso", t_ms,
                     t("¿Permitir {herramienta}?", herramienta="Bash"), "npm test", botones=True)
        if t_ms > 3200:
            llegada2 = avance(3200, 420)
            p.setOpacity(desvanecer * llegada2)
            y2 = fondo - alto2 + (1 - llegada2) * 24
            self.burbuja(p, QRectF(pantalla.left() + 8, y2, ancho, alto2), "listo", t_ms - 3200,
                         t("¡Listo! Terminé"), t("Los tests pasan ✓"))
        p.setOpacity(1)
        # El encabezado del chat va encima: los mensajes viejos se esconden debajo, como al desplazarse.
        barra = QRectF(pantalla.left(), pantalla.top(), pantalla.width(), 40)
        p.fillRect(barra, QColor("#17212B"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#0A0A0D"))
        p.drawRoundedRect(QRectF(pantalla.center().x() - 22, pantalla.top() + 5, 44, 10), 5, 5)  # la isla
        p.setBrush(QColor(C["acento"]))
        p.drawEllipse(QPointF(barra.left() + 22, barra.top() + 26), 9, 9)
        wave = self.cuadros.get("listo")
        if wave:
            self.dibujar_wave(p, wave[0][0], QRectF(barra.left() + 14, barra.top() + 18, 16, 16))
        p.setPen(QColor("#F5F7FA"))
        p.setFont(fuente(self.font(), 7.5, QFont.Weight.Bold))
        p.drawText(QRectF(barra.left() + 36, barra.top() + 17, 120, 12),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), "WaveNotificationBot")
        p.setPen(QColor("#7D8B99"))
        p.setFont(fuente(self.font(), 6.5))
        p.drawText(QRectF(barra.left() + 36, barra.top() + 27, 120, 10),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), "bot")

        p.restore()

    def burbuja(self, p: QPainter, r: QRectF, estado: str, t_ms: float, titulo: str, detalle: str,
                botones: bool = False) -> None:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#182533"))
        p.drawRoundedRect(r, 11, 11)
        cuadros = self.cuadros.get(estado)
        if cuadros:
            lista, ms = cuadros
            self.dibujar_wave(p, lista[int(t_ms // max(ms, 1)) % len(lista)], QRectF(r.left() + 4, r.top() + 2, 38, 38))
        texto = QRectF(r.left() + 44, r.top() + 7, r.width() - 50, 13)
        p.setPen(QColor("#F5F7FA"))
        p.setFont(fuente(self.font(), 7.2, QFont.Weight.Bold))
        p.drawText(texto, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                   QFontMetrics(p.font()).elidedText(titulo, Qt.TextElideMode.ElideRight, round(texto.width())))
        p.setPen(QColor("#8FA3B5"))
        letra = fuente(self.font(), 6.8)
        if estado == "permiso":
            letra.setFamily("Consolas" if not m.MAC else "Menlo")
        p.setFont(letra)
        p.drawText(texto.translated(0, 14), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                   QFontMetrics(letra).elidedText(detalle, Qt.TextElideMode.ElideRight, round(texto.width())))
        if not botones:
            return
        fila = QRectF(r.left() + 6, r.bottom() - 24, r.width() - 12, 18)
        if t_ms < 2050:
            mitad = (fila.width() - 5) / 2
            for i, (etiqueta, x) in enumerate(((t("Permitir"), fila.left()), (t("Denegar"), fila.left() + mitad + 5))):
                boton = QRectF(x, fila.top(), mitad, fila.height())
                tocado = i == 0 and 1700 < t_ms < 2050
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor("#2E4A63" if tocado else "#22364A"))
                p.drawRoundedRect(boton, 6, 6)
                p.setPen(QColor("#D6E4F0"))
                p.setFont(fuente(self.font(), 6.8, QFont.Weight.DemiBold))
                p.drawText(boton, int(Qt.AlignmentFlag.AlignCenter), etiqueta)
                if i == 0 and 1500 < t_ms < 2050:  # el dedo que toca: un aro que se abre
                    k = (t_ms - 1500) / 550
                    p.setPen(QPen(QColor(255, 255, 255, round(200 * (1 - k))), 1.5))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawEllipse(boton.center(), 4 + 12 * k, 4 + 12 * k)
        else:
            p.setPen(QColor("#6FCF97"))
            p.setFont(fuente(self.font(), 6.8, QFont.Weight.DemiBold))
            p.drawText(fila, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                       QFontMetrics(p.font()).elidedText(t("Permitido desde Telegram ✓"), Qt.TextElideMode.ElideRight,
                                                         round(fila.width())))

    @staticmethod
    def dibujar_wave(p: QPainter, imagen: QImage, caja: QRectF) -> None:
        p.save()
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)  # pixel art nítido
        p.drawImage(caja, imagen)
        p.restore()


class BotonCerrar(QAbstractButton):
    """La cruz de arriba a la derecha, sobre la cabecera oscura."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(30, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(t("Cerrar"))

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 60 if self.underMouse() else 26))
        p.drawEllipse(QRectF(1, 1, 28, 28))
        lapiz = QPen(QColor(BLANCO), 1.8)
        lapiz.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(lapiz)
        p.drawLine(QPointF(10.5, 10.5), QPointF(19.5, 19.5))
        p.drawLine(QPointF(19.5, 10.5), QPointF(10.5, 19.5))

    def enterEvent(self, evento) -> None:
        self.update()

    def leaveEvent(self, evento) -> None:
        self.update()


class IconoBeneficio(QWidget):
    """Íconos simples dibujados a mano: campana, escudo con tilde, compus y corazón."""

    def __init__(self, tipo: str):
        super().__init__()
        self.tipo = tipo
        self.setFixedSize(36, 36)

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color("acento", 0.16))
        p.drawRoundedRect(QRectF(0, 0, 36, 36), 10, 10)
        lapiz = QPen(QColor(C["acento"]), 1.8)
        lapiz.setCapStyle(Qt.PenCapStyle.RoundCap)
        lapiz.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(lapiz)
        p.setBrush(Qt.BrushStyle.NoBrush)
        camino = QPainterPath()
        if self.tipo == "campana":
            camino.moveTo(11, 23)
            camino.lineTo(25, 23)
            camino.moveTo(12.5, 23)
            camino.cubicTo(12.5, 18, 12, 11, 18, 11)
            camino.cubicTo(24, 11, 23.5, 18, 23.5, 23)
            p.drawPath(camino)
            p.drawLine(QPointF(18, 8.5), QPointF(18, 11))
            p.drawArc(QRectF(15.5, 23, 5, 4), 180 * 16, 180 * 16)
        elif self.tipo == "escudo":
            camino.moveTo(18, 8)
            camino.lineTo(26, 11)
            camino.cubicTo(26, 19, 23, 25, 18, 28)
            camino.cubicTo(13, 25, 10, 19, 10, 11)
            camino.closeSubpath()
            p.drawPath(camino)
            p.drawPolyline([QPointF(14.5, 17.5), QPointF(17, 20.5), QPointF(21.5, 14.5)])
        elif self.tipo == "compus":
            p.drawRoundedRect(QRectF(8, 11, 15, 10), 2, 2)
            p.drawLine(QPointF(6.5, 24), QPointF(24.5, 24))
            p.drawRoundedRect(QRectF(23, 13, 7, 12), 1.8, 1.8)
            p.drawLine(QPointF(25.5, 22.5), QPointF(27.5, 22.5))
        else:  # corazón
            camino.moveTo(18, 26)
            camino.cubicTo(8, 19, 9, 11, 14, 11)
            camino.cubicTo(16.5, 11, 18, 13, 18, 14.5)
            camino.cubicTo(18, 13, 19.5, 11, 22, 11)
            camino.cubicTo(27, 11, 28, 19, 18, 26)
            p.setBrush(color("acento", 0.35))
            p.drawPath(camino)


class OpcionPlan(QAbstractButton):
    """Una tarjeta de plan para elegir: nombre, precio en Stars y cuánto es en dólares, más o menos."""

    def __init__(self, plan: str, nombre: str):
        super().__init__()
        self.plan, self.nombre = plan, nombre
        self.precio, self.unidad, self.pie = "", "", ""
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(150, 100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def poner(self, precio: str, unidad: str, pie: str) -> None:
        self.precio, self.unidad, self.pie = precio, unidad, pie
        self.setToolTip(pie)
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(180, 100)

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        elegido = self.isChecked()
        p.setPen(QPen(QColor(C["acento"]) if elegido else color("acento", 0.6) if self.underMouse()
                      else QColor(C["borde"]), 1.6 if elegido else 1))
        p.setBrush(mezclar(C["campo"], C["acento"], 0.10) if elegido else QColor(C["campo"]))
        p.drawRoundedRect(r, 12, 12)
        # el circulito de la derecha
        centro = QPointF(r.right() - 17, r.top() + 18)
        if elegido:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(C["acento"]))
            p.drawEllipse(centro, 8, 8)
            p.setBrush(QColor(C["sobre"]))
            p.drawEllipse(centro, 3, 3)
        else:
            p.setPen(QPen(QColor(C["borde"]), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(centro, 7.5, 7.5)
        base = self.font()
        p.setPen(QColor(C["texto"]))
        p.setFont(fuente(base, 9.5, QFont.Weight.Bold))
        p.drawText(QRectF(r.left() + 14, r.top() + 9, r.width() - 50, 18),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self.nombre)
        grande = fuente(base, 18, QFont.Weight.Bold)
        ancho = QFontMetrics(grande).horizontalAdvance(self.precio)
        p.setFont(grande)
        p.drawText(QRectF(r.left() + 14, r.top() + 30, ancho + 4, 32),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self.precio)
        p.setPen(QColor(C["suave"]))
        p.setFont(fuente(base, 8.5))
        p.drawText(QRectF(r.left() + 14 + ancho + 6, r.top() + 30, r.width(), 34),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self.unidad)
        # Abajo, lo que se paga de verdad: las Stars de Telegram (con su estrellita) y el detalle.
        estrella(p, QPointF(r.left() + 20, r.top() + 79), 6)
        p.setPen(QColor(C["suave"]))
        letra = fuente(base, 8)
        p.setFont(letra)
        p.drawText(QRectF(r.left() + 31, r.top() + 68, r.width() - 41, 22),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                   QFontMetrics(letra).elidedText(self.pie, Qt.TextElideMode.ElideRight, round(r.width() - 41)))

    def enterEvent(self, evento) -> None:
        self.update()

    def leaveEvent(self, evento) -> None:
        self.update()


class Paso(QWidget):
    """Un paso de la guía: el circulito con el número (o la tilde), la línea al siguiente, título y detalle."""

    def __init__(self, numero: int, titulo: str, ultimo: bool = False):
        super().__init__()
        self.numero, self.ultimo, self.estado = numero, ultimo, "pendiente"
        caja = QVBoxLayout(self)
        caja.setContentsMargins(44, 3, 0, 0 if ultimo else 20)
        caja.setSpacing(5)
        self.titulo = QLabel(titulo, objectName="paso_titulo")
        self.detalle = QLabel(objectName="ayuda", wordWrap=True)
        self.detalle.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        caja.addWidget(self.titulo)
        caja.addWidget(self.detalle)
        self.extra = QVBoxLayout()
        self.extra.setSpacing(8)
        self.extra.setContentsMargins(0, 4, 0, 0)
        caja.addLayout(self.extra)

    def poner(self, estado: str, detalle: str) -> None:
        self.estado = estado
        self.detalle.setText(detalle)
        self.detalle.setVisible(bool(detalle))
        self.titulo.setProperty("apagado", estado == "pendiente")
        self.titulo.style().unpolish(self.titulo)
        self.titulo.style().polish(self.titulo)
        self.update()

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        centro = QPointF(15, 15)
        if not self.ultimo:
            p.setPen(QPen(QColor(C["acento"]) if self.estado == "hecho" else QColor(C["borde"]), 2))
            p.drawLine(QPointF(15, 33), QPointF(15, self.height() - 4))
        if self.estado == "hecho":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(C["acento"]))
            p.drawEllipse(centro, 14, 14)
            lapiz = QPen(QColor(C["sobre"]), 2.2)
            lapiz.setCapStyle(Qt.PenCapStyle.RoundCap)
            lapiz.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(lapiz)
            p.drawPolyline([QPointF(9.5, 15.5), QPointF(13.5, 19.5), QPointF(20.5, 11.5)])
            return
        actual = self.estado == "actual"
        if actual:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color("acento", 0.18))
            p.drawEllipse(centro, 18, 18)
        p.setPen(QPen(QColor(C["acento"] if actual else C["borde"]), 2))
        p.setBrush(QColor(C["panel"]))
        p.drawEllipse(centro, 13, 13)
        p.setPen(QColor(C["acento"] if actual else C["suave"]))
        p.setFont(fuente(self.font(), 10, QFont.Weight.Bold))
        p.drawText(QRectF(0, 0, 30, 30), int(Qt.AlignmentFlag.AlignCenter), str(self.numero))


class Confeti(QWidget):
    """Papelitos que caen sobre la guía cuando el pago se confirma."""

    def __init__(self, padre: QWidget):
        super().__init__(padre)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.papelitos: list[list[float]] = []
        self.reloj = QElapsedTimer()
        self.timer = QTimer(self, interval=16, timeout=self.avanzar)
        self.hide()

    def lanzar(self, origen: QPointF) -> None:
        self.setGeometry(self.parentWidget().rect())
        colores = [C["acento"], C["acento2"], ORO[0], ORO[1], BLANCO, "#7AD3A8", "#8EC5FF"]
        azar = random.Random()
        self.papelitos = []
        for _ in range(140):
            angulo = azar.uniform(-math.pi * 0.95, -math.pi * 0.05)
            v = azar.uniform(5, 13)
            self.papelitos.append([origen.x() + azar.uniform(-60, 60), origen.y(), v * math.cos(angulo),
                                   v * math.sin(angulo), azar.uniform(0, 360), azar.uniform(-12, 12),
                                   azar.uniform(5, 10), azar.randrange(len(colores))])
        self.colores = colores
        self.reloj.restart()
        self.show()
        self.raise_()
        self.timer.start()

    def avanzar(self) -> None:
        for papel in self.papelitos:
            papel[0] += papel[2]
            papel[1] += papel[3]
            papel[2] *= 0.985
            papel[3] = papel[3] * 0.985 + 0.32  # gravedad
            papel[4] += papel[5]
        if self.reloj.elapsed() > 2800:
            self.timer.stop()
            self.hide()
        self.update()

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        alfa = max(0.0, min(1.0, (2800 - self.reloj.elapsed()) / 600))
        p.setOpacity(alfa)
        for x, y, _, _, giro, _, lado, c in self.papelitos:
            p.save()
            p.translate(x, y)
            p.rotate(giro)
            p.setBrush(QColor(self.colores[int(c)]))
            p.drawRect(QRectF(-lado / 2, -lado / 4, lado, lado / 2 * abs(math.cos(math.radians(giro))) + 1))
            p.restore()


# --- la guía -------------------------------------------------------------------------------------

class GuiaPro(QWidget):
    """Capa sobre la ventana de ajustes: oscurece el fondo y muestra la guía para desbloquear Pro.

    No habla con el servidor: pide cosas con sus señales (conectar, pagar, gestionar) y la ventana le
    cuenta cómo quedó todo con actualizar()."""

    conectar = pyqtSignal()
    pagar = pyqtSignal(str)
    gestionar = pyqtSignal()
    cerrada = pyqtSignal()

    def __init__(self, padre: QWidget, aspecto: dict):
        super().__init__(padre)
        self.hide()
        self.progreso = 0.0
        self.esperando = False
        self.exito = False
        self.puntos = 0
        padre.installEventFilter(self)

        self.tarjeta = QFrame(self, objectName="guia")
        tarjeta = QVBoxLayout(self.tarjeta)
        tarjeta.setContentsMargins(1, 1, 1, 1)
        tarjeta.setSpacing(0)
        self.hero = Hero(aspecto)
        tarjeta.addWidget(self.hero)
        self.cerrar_x = BotonCerrar()
        self.cerrar_x.setParent(self.hero)
        self.cerrar_x.clicked.connect(self.cerrar)

        self.area = QScrollArea(widgetResizable=True, frameShape=QFrame.Shape.NoFrame)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cuerpo = QWidget()
        self.area.setWidget(self.cuerpo)
        tarjeta.addWidget(self.area, 1)
        caja = QVBoxLayout(self.cuerpo)
        caja.setContentsMargins(28, 22, 28, 20)
        caja.setSpacing(16)
        columnas = QHBoxLayout()
        columnas.setSpacing(34)
        caja.addLayout(columnas)

        # Izquierda: qué incluye y qué sigue gratis.
        izquierda = QWidget()
        izquierda.setFixedWidth(300)
        col = QVBoxLayout(izquierda)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(12)
        col.addWidget(self.seccion(t("Qué incluye")))
        for icono, titulo, detalle in (
                ("campana", t("Avisos en tu celular"),
                 t("Cuando Claude Code termina, necesita algo o llega al límite, te escribe Wave.")),
                ("escudo", t("Permisos a distancia"), t("Permitir o Denegar con un toque, sin volver a la compu.")),
                ("compus", t("Todas tus compus"), t("Un solo Pro para todas las compus que conectes a tu Telegram.")),
                ("corazon", t("Bancás el open source"),
                 t("Mantenés el bot y el servidor, y la app sigue gratis para todos."))):
            fila = QHBoxLayout()
            fila.setSpacing(12)
            fila.addWidget(IconoBeneficio(icono), 0, Qt.AlignmentFlag.AlignTop)
            textos = QVBoxLayout()
            textos.setSpacing(1)
            textos.addWidget(QLabel(titulo, objectName="beneficio"))
            textos.addWidget(self.ayuda(detalle))
            fila.addLayout(textos, 1)
            col.addLayout(fila)
        col.addSpacing(6)
        gratis = QFrame(objectName="gratis")
        caja_gratis = QVBoxLayout(gratis)
        caja_gratis.setContentsMargins(14, 11, 14, 12)
        caja_gratis.setSpacing(3)
        caja_gratis.addWidget(self.seccion(t("Siempre gratis")))
        caja_gratis.addWidget(self.ayuda(t("La mascota, los avisos en pantalla, los estilos, el vestuario y todo lo "
                                          "demás. Sin cuentas ni límites.")))
        col.addWidget(gratis)
        col.addStretch(1)
        columnas.addWidget(izquierda)

        # Derecha: los pasos (o, si ya sos Pro, tu plan).
        derecha = QVBoxLayout()
        derecha.setSpacing(12)
        self.titulo_derecha = self.seccion(t("Cómo desbloquearlo"))
        derecha.addWidget(self.titulo_derecha)
        self.pasos = QWidget()
        pasos = QVBoxLayout(self.pasos)
        pasos.setContentsMargins(0, 4, 0, 0)
        pasos.setSpacing(0)
        self.paso1 = Paso(1, t("Conectá tu Telegram"))
        self.boton_conectar = QPushButton(t("Conectar con Telegram"), objectName="primario", clicked=self.conectar)
        self.paso1.extra.addLayout(self.izquierda(self.boton_conectar))
        self.paso2 = Paso(2, t("Elegí tu plan"))
        self.opciones = {"mensual": OpcionPlan("mensual", t("Mensual")),
                         "vitalicio": OpcionPlan("vitalicio", t("De por vida"))}
        grupo = QButtonGroup(self)
        fila_planes = QHBoxLayout()
        fila_planes.setSpacing(10)
        for opcion in self.opciones.values():
            grupo.addButton(opcion)
            fila_planes.addWidget(opcion)
            opcion.clicked.connect(self.refrescar_pago)
        self.opciones["mensual"].setChecked(True)
        self.paso2.extra.addLayout(fila_planes)
        self.paso3 = Paso(3, t("Pagá con Telegram Stars"), ultimo=True)
        self.boton_pagar = QPushButton(objectName="primario", clicked=lambda: self.pagar.emit(self.plan_elegido()))
        self.boton_pagar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.paso3.extra.addLayout(self.izquierda(self.boton_pagar))
        for paso in (self.paso1, self.paso2, self.paso3):
            pasos.addWidget(paso)
        derecha.addWidget(self.pasos)

        self.panel_pro = QWidget()
        panel = QVBoxLayout(self.panel_pro)
        panel.setContentsMargins(0, 6, 0, 0)
        panel.setSpacing(8)
        self.pro_titulo = QLabel(objectName="guia_estado", wordWrap=True)
        self.pro_detalle = self.ayuda("")
        self.boton_gestionar = QPushButton(t("Ver mi plan en Telegram"), objectName="primario", clicked=self.gestionar)
        self.pro_nota = self.ayuda("")
        panel.addWidget(self.pro_titulo)
        panel.addWidget(self.pro_detalle)
        panel.addSpacing(4)
        panel.addLayout(self.izquierda(self.boton_gestionar, QPushButton(t("Listo"), clicked=self.cerrar)))
        panel.addWidget(self.pro_nota)
        derecha.addWidget(self.panel_pro)
        derecha.addStretch(1)
        columnas.addLayout(derecha, 1)

        linea = QFrame(objectName="linea")
        linea.setFixedHeight(1)
        caja.addWidget(linea)
        pie = self.ayuda(t("¿Por qué es pago? WaveMascot es y va a seguir siendo gratis y open source. Pro paga el bot "
                           "y el servidor que llevan los avisos hasta tu celular, y te deja cancelar cuando quieras."))
        caja.addWidget(pie)

        self.confeti = Confeti(self)
        self.animacion = QVariantAnimation(self, duration=260, startValue=0.0, endValue=1.0,
                                           easingCurve=QEasingCurve(QEasingCurve.Type.OutCubic))
        self.animacion.valueChanged.connect(self.al_animar)
        self.animacion.finished.connect(self.al_terminar_animacion)
        self.timer_puntos = QTimer(self, interval=450, timeout=self.latir)
        self.estado: dict = {}

    # armado

    @staticmethod
    def seccion(texto: str) -> QLabel:
        return QLabel(texto.upper(), objectName="seccion")

    @staticmethod
    def ayuda(texto: str) -> QLabel:
        etiqueta = QLabel(texto, objectName="ayuda", wordWrap=True)
        return etiqueta

    @staticmethod
    def izquierda(*widgets) -> QHBoxLayout:
        fila = QHBoxLayout()
        fila.setSpacing(8)
        for w in widgets:
            fila.addWidget(w)
        fila.addStretch(1)
        return fila

    def plan_elegido(self) -> str:
        return "vitalicio" if self.opciones["vitalicio"].isChecked() else "mensual"

    # abrir y cerrar

    def abrir(self, aspecto: dict) -> None:
        if self.isVisible() and self.animacion.endValue() == 1.0:
            return
        self.exito = False
        self.hero.preparar(aspecto)
        self.setGeometry(self.parentWidget().rect())
        self.colocar()
        efecto = QGraphicsOpacityEffect(self.tarjeta)
        self.tarjeta.setGraphicsEffect(efecto)
        self.show()
        self.raise_()
        self.setFocus()
        self.animar(1.0)

    def cerrar(self) -> None:
        if not self.isVisible():
            return
        if not isinstance(self.tarjeta.graphicsEffect(), QGraphicsOpacityEffect):
            self.tarjeta.setGraphicsEffect(QGraphicsOpacityEffect(self.tarjeta))
        self.animar(0.0)

    def animar(self, hasta: float) -> None:
        self.animacion.stop()
        self.animacion.setStartValue(self.progreso)
        self.animacion.setEndValue(hasta)
        self.animacion.setDuration(260 if hasta else 170)
        self.animacion.start()

    def al_animar(self, valor) -> None:
        self.progreso = float(valor)
        efecto = self.tarjeta.graphicsEffect()
        if isinstance(efecto, QGraphicsOpacityEffect):
            efecto.setOpacity(self.progreso)
        self.colocar()
        self.update()

    def al_terminar_animacion(self) -> None:
        if self.progreso <= 0.001:
            self.hide()
            self.esperando = False
            self.timer_puntos.stop()
            self.cerrada.emit()
        else:
            self.tarjeta.setGraphicsEffect(None)  # sin el efecto, la animación del celular no recalcula todo

    def colocar(self) -> None:
        """La tarjeta centrada, tan alta como su contenido (o la ventana), entrando desde un poco más abajo."""
        ancho = min(860, self.width() - 40)
        self.tarjeta.setFixedWidth(max(320, ancho))
        interior = self.cuerpo.layout()
        alto_cuerpo = (interior.totalHeightForWidth(ancho - 2) if interior.hasHeightForWidth()
                       else interior.totalSizeHint().height())
        alto = min(Hero.ALTO + alto_cuerpo + 4, self.height() - 32)
        self.tarjeta.setFixedHeight(max(260, alto))
        x = (self.width() - self.tarjeta.width()) // 2
        y = (self.height() - self.tarjeta.height()) // 2 + round((1 - self.progreso) * 22)
        self.tarjeta.move(x, y)
        self.cerrar_x.move(self.tarjeta.width() - 46, 14)

    def eventFilter(self, objeto, evento) -> bool:
        if objeto is self.parentWidget() and evento.type() == QEvent.Type.Resize and self.isVisible():
            self.setGeometry(self.parentWidget().rect())
            self.colocar()
        return False

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(8, 5, 4, round(160 * self.progreso)))

    def mousePressEvent(self, evento) -> None:
        if not self.tarjeta.geometry().contains(evento.position().toPoint()):
            self.cerrar()

    def keyPressEvent(self, evento) -> None:
        if evento.key() == Qt.Key.Key_Escape:
            self.cerrar()
        else:
            super().keyPressEvent(evento)

    # estado

    def actualizar(self, conectado: bool, nombre: str, codigo: str, plan: dict | None, info: dict) -> None:
        """Lo que sabe la ventana de ajustes: si Telegram está conectado (o esperando el código) y el plan."""
        self.estado = {"conectado": conectado, "nombre": nombre, "codigo": codigo, "plan": plan, "info": info}
        d = describir(plan, info, conectado)
        self.hero.chip.setText(d["chip"] or t("Sos Pro ✓"))
        precios = info.get("precios") or celular.PRECIOS
        self.opciones["mensual"].poner(celular.precio(precios["mensual"]), t("/ mes"),
                                       t("{stars} Stars · mes a mes",
                                         stars=celular.estrellas(precios["mensual"])))
        self.opciones["vitalicio"].poner(celular.precio(precios["vitalicio"]), t("una vez"),
                                         t("{stars} Stars · un solo pago", stars=celular.estrellas(precios["vitalicio"])))
        ya_pro = d["tipo"] in PAGOS or d["tipo"] == "libre"
        self.pasos.setVisible(not ya_pro)
        self.panel_pro.setVisible(ya_pro)
        self.titulo_derecha.setText((t("Tu plan") if ya_pro else t("Cómo desbloquearlo")).upper())
        if ya_pro:
            self.esperando = False
            self.timer_puntos.stop()
            self.pro_titulo.setText(t("¡Ya sos Pro!") if self.exito else d["titulo"] or t("Sos Pro"))
            self.pro_detalle.setText(d["detalle"])
            self.pro_nota.setText(t("Desde el bot ves tu plan y cancelás o reactivás la renovación cuando quieras.")
                                  if d["tipo"] in ("mensual", "regalo") else
                                  t("Los avisos y los permisos por Telegram ya andan en todas tus compus."))
            self.boton_gestionar.setVisible(d["tipo"] != "libre")
        else:
            dias = info.get("dias_prueba", celular.DIAS_PRUEBA)
            if conectado:
                self.paso1.poner("hecho", t("Conectado al Telegram de {nombre}", nombre=nombre) if nombre
                                 else t("Conectado a Telegram"))
            elif codigo:
                self.paso1.poner("actual", t("Tocá «Iniciar» en Telegram (o mandale el código {codigo} al bot).",
                                             codigo=celular.codigo_visible(codigo)))
            else:
                self.paso1.poner("actual", t("Se abre Telegram y tocás «Iniciar». Ahí arranca tu prueba gratis de "
                                             "{dias} días.", dias=dias))
            self.boton_conectar.setVisible(not conectado)
            self.boton_conectar.setText(t("Abrir Telegram de nuevo") if codigo else t("Conectar con Telegram"))
            # Con Telegram conectado ya hay un plan elegido (el mensual, o el que toques): falta pagar.
            self.paso2.poner("hecho" if conectado else "pendiente", "")
            self.refrescar_pago()
        self.colocar()

    def refrescar_pago(self) -> None:
        conectado = self.estado.get("conectado")
        precios = (self.estado.get("info") or {}).get("precios") or celular.PRECIOS
        precio = celular.precio(precios[self.plan_elegido()])
        if self.esperando:
            self.paso3.poner("actual", t("Esperando el pago") + "." * (1 + self.puntos % 3) + "\n" +
                             t("Cuando Telegram lo confirme, WaveMascot se da cuenta solo."))
            self.boton_pagar.setText(t("Abrir el pago de nuevo"))
        else:
            self.paso3.poner("actual" if conectado else "pendiente",
                             t("Te abro el chat del bot con el botón de pago. Pagás desde el celular o la compu, y "
                               "las Stars se compran ahí mismo."))
            self.boton_pagar.setText(t("Pagar {precio} en Telegram", precio=precio))
        self.boton_pagar.setEnabled(bool(conectado))
        self.boton_pagar.setToolTip("" if conectado else t("Primero conectá tu Telegram"))

    def esperar_pago(self) -> None:
        """Se tocó «Pagar»: la guía queda esperando hasta que la ventana avise que llegó el pago."""
        self.esperando = True
        self.puntos = 0
        self.timer_puntos.start()
        self.paso2.poner("hecho", "")
        self.refrescar_pago()

    def latir(self) -> None:
        self.puntos += 1
        if self.esperando and self.isVisible():
            self.refrescar_pago()

    def festejar(self) -> None:
        """¡Pagó! El panel de «Ya sos Pro» y una lluvia de papelitos."""
        self.exito = True
        self.esperando = False
        self.timer_puntos.stop()
        e = self.estado
        self.actualizar(e.get("conectado", True), e.get("nombre", ""), "", e.get("plan"), e.get("info") or {})
        if self.isVisible():
            self.confeti.lanzar(QPointF(self.tarjeta.geometry().center().x(), self.tarjeta.geometry().top() + 60))
