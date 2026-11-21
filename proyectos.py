"""La sección Proyectos de los ajustes: cada repo con sus ramas, sus carpetas y qué está subido a GitHub.

Liviana a la vista: arriba tres cifras (lo que falta subir, lo que falta commitear y lo que se puede limpiar)
y debajo una tarjeta por proyecto. Cerrada, la tarjeta dice en una pastilla si está todo al día; abierta, dibuja
las ramas como un mapa de git: la principal es el tronco y cada rama sale de él con un nodo del color de su
estado. Las ramas que ya están enteras en main se esconden detrás de una sola fila.

Todo en vivo mientras se mira: repos.py lee git en un hilo aparte (Revisor) y acá solo se dibuja. Cuando algo
cambia (un push, un commit, una rama nueva), el nodo de esa rama late una vez.
"""

from __future__ import annotations

import math
import threading
import time
from urllib.parse import quote

import mascota as m
import paneles
import repos
from animacion import Resorte, reducir_movimiento
from idiomas import t
from paneles import con_alfa, letra, pintar_tarjeta

from PyQt6.QtCore import QObject, QPointF, QRectF, QSize, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QFont, QFontMetricsF, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QToolTip, QVBoxLayout, QWidget

VIVO = 6  # segundos entre una lectura y la siguiente mientras se mira la sección


def tono(nombre: str) -> QColor:
    """Verde (al día) y ámbar (sin commitear), un poco más oscuros en el tema claro para que se lean."""
    claro = QColor(paneles.C["fondo"]).lightnessF() > 0.5
    return QColor({"verde": ("#5DC98D", "#2E9E62"), "ambar": ("#E3B341", "#B7851B")}[nombre][claro])


def hace(cuando: float | None) -> str:
    if not cuando:
        return ""
    s = max(0, time.time() - cuando)
    if s < 60:
        return t("recién")
    if s < 3600:
        tiempo = f"{int(s // 60)} min"
    elif s < 86400:
        tiempo = f"{int(s // 3600)} h"
    elif s < 86400 * 60:
        tiempo = t("{n} d", n=int(s // 86400))
    else:
        tiempo = t("{n} meses", n=int(s // (86400 * 30)))
    return t("hace {tiempo}", tiempo=tiempo)


def abrir_carpeta(ruta: str) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(ruta))


def ancho_de(fuente: QFont, texto: str) -> float:
    return QFontMetricsF(fuente).horizontalAdvance(texto)


def pastilla(p: QPainter, derecha: float, centro_y: float, texto: str, color: QColor, fondo: float = 0.13,
             fuente: QFont | None = None) -> QRectF:
    """Una cápsula chica alineada a la derecha; devuelve dónde quedó."""
    fuente = fuente or letra(11.5, QFont.Weight.DemiBold)
    ancho = ancho_de(fuente, texto) + 18
    caja = QRectF(derecha - ancho, centro_y - 11, ancho, 22)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(con_alfa(color, fondo))
    p.drawRoundedRect(caja, 11, 11)
    p.setFont(fuente)
    p.setPen(color)
    p.drawText(caja, int(Qt.AlignmentFlag.AlignCenter), texto)
    return caja


# --------------------------------------------------------------------------------------------- el hilo

class Revisor(QObject):
    """Lee los repos en un hilo y avisa con la lista. Uno por vez; al cerrar la ventana se corta."""

    listo = pyqtSignal(object)     # {"repos": [...], "error": ""}
    buscando = pyqtSignal(bool)    # preguntando a GitHub (git fetch)

    def __init__(self, padre: QObject | None = None, proyectos: repos.Proyectos | None = None):
        super().__init__(padre)
        self.proyectos = proyectos or repos.Proyectos()
        self.cerrado = threading.Event()
        self.proyectos.cancelado = self.cerrado.is_set
        self.proyectos.al_preguntar = lambda: self.avisar(self.buscando, True)  # solo si de verdad va a la red
        self.ocupado = False
        self.pendiente: tuple[bool, bool] | None = None  # (github, forzar) del pedido que llegó mientras tanto
        self.cerrojo = threading.Lock()

    def pedir(self, github: bool = True, forzar: bool = False) -> bool:
        """Si ya hay una lectura corriendo, el pedido espera a que termine (y se junta con otros)."""
        if self.cerrado.is_set():
            return False
        with self.cerrojo:
            if self.ocupado:
                antes = self.pendiente or (False, False)
                self.pendiente = (antes[0] or github, antes[1] or forzar)
                return False
            self.ocupado = True
        threading.Thread(target=self.correr, args=(github, forzar), daemon=True).start()
        return True

    def correr(self, github: bool, forzar: bool) -> None:
        while True:
            try:
                primera = not self.proyectos.raices
                if primera or not github:  # lo local llega enseguida; GitHub, después
                    self.avisar(self.listo, self.leer(False, False, primera))
                if github:
                    self.avisar(self.listo, self.leer(True, forzar))
            finally:
                self.avisar(self.buscando, False)
            with self.cerrojo:
                if self.pendiente is None or self.cerrado.is_set():
                    self.ocupado = False
                    return
                (github, forzar), self.pendiente = self.pendiente, None

    def leer(self, github: bool, forzar: bool, de_a_uno: bool = False) -> dict:
        """de_a_uno: la primera vez cada proyecto aparece apenas está leído. (Después no: una lista a medias
        haría desaparecer y volver las tarjetas que faltan.)"""
        avance = (lambda lista: self.avisar(self.listo, {"repos": lista, "error": ""})) if de_a_uno else None
        try:
            lista = self.proyectos.leer(github, forzar, avance)
            return {"repos": lista, "error": "sin_git" if self.proyectos.sin_git and not lista else ""}
        except Exception as e:  # un repo raro no puede dejar la sección colgada
            m.log(f"[proyectos] error leyendo los repos: {e!r}")
            return {"repos": [], "error": "otro"}

    def avisar(self, senal, valor) -> None:
        if not self.cerrado.is_set():
            try:
                senal.emit(valor)
            except RuntimeError:  # la ventana se cerró mientras tanto
                pass

    def cerrar(self) -> None:
        self.cerrado.set()


# ------------------------------------------------------------------------------------------ arriba

class Sincro(QWidget):
    """"Revisado en GitHub hace 2 min" y una flechita circular que gira mientras pregunta. Tocarla, revisa ya."""

    tocado = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setFixedHeight(32)
        self.setMinimumWidth(200)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(t("Preguntar a GitHub ahora"))
        self.revisado: float | None = None
        self.girando = False
        self.angulo = 0.0
        self.encima = False
        self.reloj = QTimer(self, interval=16, timeout=self.girar)
        self.frenar = Resorte(self, 0.0, 0.5, 1.0, al_paso=lambda _: self.update())

    def poner(self, revisado: float | None) -> None:
        self.revisado = revisado
        self.update()

    def buscar(self, si: bool) -> None:
        self.girando = si
        if si and not reducir_movimiento():
            self.reloj.start()
        elif not si:
            self.reloj.stop()
            # la flecha termina la vuelta en lugar de quedar torcida
            self.frenar.x = self.angulo
            self.frenar.ir_a(math.ceil(self.angulo / 360) * 360)
        self.update()

    def girar(self) -> None:
        self.angulo += 7
        self.update()

    def enterEvent(self, evento) -> None:
        self.encima = True
        self.update()

    def leaveEvent(self, evento) -> None:
        self.encima = False
        self.update()

    def mouseReleaseEvent(self, evento) -> None:
        if evento.button() == Qt.MouseButton.LeftButton and not self.girando:
            self.tocado.emit()

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.girando:
            texto = t("Revisando GitHub…")
        elif self.revisado:
            texto = t("GitHub revisado {cuando}", cuando=hace(self.revisado))
        else:
            texto = t("Sin revisar en GitHub")
        p.setFont(letra(12.5, QFont.Weight.DemiBold))
        ancho = ancho_de(p.font(), texto)
        x = self.width() - ancho - 2
        p.setPen(QColor(paneles.C["texto"] if self.encima else paneles.C["suave"]))
        p.drawText(QRectF(x, 0, ancho + 2, self.height()), int(Qt.AlignmentFlag.AlignVCenter), texto)
        # la flecha circular
        angulo = self.angulo if self.girando else self.frenar.x
        p.translate(x - 14, self.height() / 2)
        p.rotate(angulo)
        pluma = QPen(QColor(paneles.C["acento"] if self.girando else paneles.C["suave"]), 1.6)
        pluma.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pluma)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(-5.5, -5.5, 11, 11), 40 * 16, 290 * 16)
        punta = QPainterPath(QPointF(4.2, -6.4))
        punta.lineTo(4.6, -3.0)
        punta.lineTo(1.3, -3.6)
        p.drawPath(punta)


# ----------------------------------------------------------------------------------------- las ramas

class Fila:
    """Lo que se dibuja de una rama (o de una carpeta en un commit suelto)."""

    def __init__(self, rama: repos.Rama | None, carpeta: repos.Carpeta | None = None, apagada: bool = False):
        self.rama, self.carpeta, self.apagada = rama, carpeta or (rama.carpeta if rama else None), apagada
        self.chip = QRectF()  # dónde quedó la etiqueta de la carpeta (se puede tocar)

    @property
    def clave(self) -> str:
        return self.rama.nombre if self.rama else f"@{self.carpeta.ruta if self.carpeta else ''}"

    def firma(self) -> tuple:
        """Lo que, si cambia, hace latir el nodo."""
        r, c = self.rama, self.carpeta
        return ((r.estado, r.sin_subir, r.sin_bajar, r.adelante, r.atras) if r else (),
                c.cambios if c else 0)


class TarjetaRepo(QWidget):
    """Un proyecto. Cerrada: nombre, de dónde es y cómo está. Abierta: el mapa de sus ramas."""

    CABEZA, FILA, PIE = 74, 42, 12
    TRONCO = 30  # x del tronco (la rama principal)

    def __init__(self, repo: repos.Repo, abierta: bool = False, al_mover=None):
        super().__init__()
        self.repo = repo
        self.al_mover = al_mover
        self.filas: list[Fila] = []
        self.mostrar_viejas = False
        self.encima: int | str | None = None  # índice de fila, "cabeza", "web", "viejas"
        self.firmas: dict[str, tuple] = {}
        self.latidos: dict[str, Resorte] = {}
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.apertura = Resorte(self, 1.0 if abierta else 0.0, 0.42, 0.86, al_paso=self.ubicar)
        self.contenido = Resorte(self, 1.0 if abierta else 0.0, 0.5, 1.0, al_paso=lambda _: self.update())
        self.poner(repo, latir=False)

    # datos

    @property
    def abierta(self) -> bool:
        return self.apertura.objetivo > 0.5

    def poner(self, repo: repos.Repo, latir: bool = True) -> None:
        self.repo = repo
        en_uso = [r for r in repo.ramas if r.en_uso]
        viejas = [r for r in repo.ramas if not r.en_uso]
        filas = [Fila(r) for r in en_uso]
        nombres = {r.nombre for r in repo.ramas}
        # commits sueltos, y carpetas en una rama que todavía no tiene ningún commit (un repo recién creado)
        filas += [Fila(None, c) for c in repo.carpetas if not c.perdida and (not c.rama or c.rama not in nombres)]
        self.viejas = len(viejas)
        if self.mostrar_viejas:
            filas += [Fila(r, apagada=True) for r in viejas]
        self.filas = filas
        for fila in filas:
            firma, antes = fila.firma(), self.firmas.get(fila.clave)
            if latir and antes is not None and antes != firma:
                self.latir(fila.clave)
            self.firmas[fila.clave] = firma
        self.updateGeometry()
        self.ubicar()

    def latir(self, clave: str) -> None:
        if reducir_movimiento() or not self.isVisible():
            return
        latido = self.latidos.get(clave) or Resorte(self, 0.0, 0.9, 1.0, al_paso=lambda _: self.update())
        self.latidos[clave] = latido
        latido.ir_a(0.0, desde=1.0)

    # tamaño

    def alto_cuerpo(self) -> int:
        if self.repo.error:
            return 52
        extra = 1 if self.viejas else 0
        return 6 + (len(self.filas) + extra) * self.FILA + self.PIE

    def alto(self) -> int:
        return round(self.CABEZA + self.alto_cuerpo() * max(0.0, self.apertura.x))

    def sizeHint(self) -> QSize:
        return QSize(400, self.alto())

    def ubicar(self, _=None) -> None:
        self.setFixedHeight(max(self.CABEZA, self.alto()))
        self.update()
        if self.al_mover:
            self.al_mover()

    def alternar(self) -> None:
        abrir = not self.abierta
        self.apertura.configurar(0.42 if abrir else 0.34, 0.86 if abrir else 1.0)
        self.apertura.ir_a(1.0 if abrir else 0.0)
        self.contenido.ir_a(1.0 if abrir else 0.0)

    # dónde está cada cosa

    def rect_fila(self, i: int) -> QRectF:
        return QRectF(8, self.CABEZA + 6 + i * self.FILA, self.width() - 16, self.FILA)

    def boton_web(self) -> QRectF:
        return QRectF(self.width() - 18 - 30 - 34, (self.CABEZA - 30) / 2, 30, 30)

    def que_hay(self, pos: QPointF) -> int | str | None:
        if pos.y() < self.CABEZA:
            return "web" if self.repo.web and self.boton_web().contains(pos) else "cabeza"
        if not self.abierta or self.repo.error:
            return None
        for i, fila in enumerate(self.filas):
            if self.rect_fila(i).contains(pos):
                return f"chip{i}" if fila.carpeta and fila.chip.contains(pos) else i
        if self.viejas and self.rect_fila(len(self.filas)).contains(pos):
            return "viejas"
        return None

    # mouse

    def mouseMoveEvent(self, evento) -> None:
        encima = self.que_hay(evento.position())
        if encima != self.encima:
            self.encima = encima
            self.setCursor(Qt.CursorShape.PointingHandCursor if self.se_puede_tocar(encima)
                           else Qt.CursorShape.ArrowCursor)
            self.update()
            ayuda = self.ayuda(encima)
            if ayuda:
                QToolTip.showText(evento.globalPosition().toPoint(), ayuda, self)
            else:
                QToolTip.hideText()

    def se_puede_tocar(self, que) -> bool:
        if que in ("cabeza", "web", "viejas") or (isinstance(que, str) and que.startswith("chip")):
            return True
        return isinstance(que, int) and self.url_rama(self.filas[que]) != ""

    def leaveEvent(self, evento) -> None:
        self.encima = None
        self.update()

    def mouseReleaseEvent(self, evento) -> None:
        if evento.button() != Qt.MouseButton.LeftButton:
            return
        que = self.que_hay(evento.position())
        if que == "cabeza":
            self.alternar()
        elif que == "web":
            QDesktopServices.openUrl(QUrl(self.repo.web))
        elif que == "viejas":
            self.mostrar_viejas = not self.mostrar_viejas
            self.poner(self.repo, latir=False)
        elif isinstance(que, str) and que.startswith("chip"):
            carpeta = self.filas[int(que[4:])].carpeta
            if carpeta:
                abrir_carpeta(carpeta.ruta)
        elif isinstance(que, int):
            url = self.url_rama(self.filas[que])
            if url:
                QDesktopServices.openUrl(QUrl(url))

    def url_rama(self, fila: Fila) -> str:
        r = fila.rama
        if not (r and r.en_remoto and self.repo.web and "github.com" in self.repo.web):
            return ""
        return f"{self.repo.web}/tree/{quote(r.nombre, safe='/')}"

    def ayuda(self, que) -> str:
        if que == "web":
            return t("Abrir en GitHub")
        if que == "cabeza":
            return self.explicar_resumen()
        if isinstance(que, str) and que.startswith("chip"):
            carpeta = self.filas[int(que[4:])].carpeta
            return t("Abrir la carpeta {ruta}", ruta=carpeta.ruta) if carpeta else ""
        if not isinstance(que, int):
            return ""
        r = self.filas[que].rama
        if not r:
            carpeta = self.filas[que].carpeta
            return (t("Esta rama todavía no tiene commits") if carpeta and carpeta.rama
                    else t("Esta carpeta está en un commit suelto, sin rama"))
        partes = []
        if r.incierta:
            partes.append(t("git no pudo comparar esta rama con {base} (puede que haya tardado demasiado)",
                            base=self.nombre_base()))
        if not r.base and (r.adelante or r.atras):
            base = self.repo.base or "main"
            partes.append(t("{a} adelante y {b} atrás de {base}", a=r.adelante, b=r.atras, base=base))
        if r.sin_subir:
            partes.append(t("1 commit sin subir a GitHub" if r.sin_subir == 1 else "{n} commits sin subir a GitHub",
                            n=r.sin_subir))
        if r.sin_bajar:
            partes.append(t("1 commit en GitHub que no tenés" if r.sin_bajar == 1
                            else "{n} commits en GitHub que no tenés", n=r.sin_bajar))
        if self.url_rama(self.filas[que]):
            partes.append(t("Tocá para verla en GitHub"))
        return "\n".join(partes)

    # dibujo

    def paintEvent(self, evento) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pintar_tarjeta(p, self.rect())
        self.pintar_cabeza(p)
        if self.apertura.x > 0.01:
            p.save()
            p.setClipRect(QRectF(0, self.CABEZA - 1, self.width(), self.height() - self.CABEZA))
            separador = con_alfa(paneles.C["texto"], 0.07 * min(1.0, self.apertura.x))
            p.setPen(QPen(separador, 1))
            p.drawLine(QPointF(18, self.CABEZA - 0.5), QPointF(self.width() - 18, self.CABEZA - 0.5))
            if self.repo.error:
                self.pintar_error(p)
            else:
                self.pintar_ramas(p)
            p.restore()

    def resumen(self) -> list[tuple[str, QColor]]:
        """Las pastillas de la cabeza: lo que falta hacer, o "Al día"."""
        r, C = self.repo, paneles.C
        if r.error == "wsl":
            return [(t("WSL apagado"), QColor(C["suave"]))]
        if r.error:
            return [(t("No se pudo leer"), QColor(C["suave"]))]
        res = []
        if r.sin_subir:
            res.append((f"↑ {r.sin_subir}", QColor(C["acento"])))
        if r.cambios:
            res.append((f"● {r.cambios}", tono("ambar")))
        base = next((b for b in r.ramas if b.base), None)
        if base and base.sin_bajar:
            res.append((f"↓ {base.sin_bajar}", QColor(C["suave"])))
        if not res and not r.remoto:
            return [(t("Solo en tu compu"), QColor(C["suave"]))]
        return res or [(t("Al día"), tono("verde"))]

    def explicar_resumen(self) -> str:
        r = self.repo
        partes = []
        if r.sin_subir:
            partes.append(t("1 commit sin subir a GitHub" if r.sin_subir == 1 else "{n} commits sin subir a GitHub",
                            n=r.sin_subir))
        if r.cambios:
            partes.append(t("1 archivo sin commitear" if r.cambios == 1 else "{n} archivos sin commitear", n=r.cambios))
        base = next((b for b in r.ramas if b.base), None)
        if base and base.sin_bajar:
            partes.append(t("1 commit en GitHub que no tenés" if base.sin_bajar == 1
                            else "{n} commits en GitHub que no tenés", n=base.sin_bajar))
        return "\n".join(partes)

    def pintar_cabeza(self, p: QPainter) -> None:
        C, r = paneles.C, self.repo
        if self.encima == "cabeza":
            forma = QPainterPath()
            forma.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, 0).intersected(
                QRectF(0, 0, self.width(), self.CABEZA)), paneles.RADIO, paneles.RADIO)
            p.fillPath(forma, con_alfa(C["texto"], 0.025))
        izquierda, derecha = 20.0, self.width() - 18.0
        # el chevron, que gira al abrir
        p.save()
        p.translate(derecha - 10, self.CABEZA / 2)
        p.rotate(90 * max(0.0, min(1.0, self.apertura.x)))
        pluma = QPen(QColor(C["suave"]), 1.7)
        pluma.setCapStyle(Qt.PenCapStyle.RoundCap)
        pluma.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pluma)
        flecha = QPainterPath(QPointF(-2.5, -5))
        flecha.lineTo(2.5, 0)
        flecha.lineTo(-2.5, 5)
        p.drawPath(flecha)
        p.restore()
        derecha -= 30
        if r.web:  # GitHub, en una burbuja de vidrio
            boton = self.boton_web()
            p.setPen(QPen(con_alfa(C["texto"], 0.12 if self.encima == "web" else 0.07), 1))
            p.setBrush(con_alfa(C["texto"], 0.09 if self.encima == "web" else 0.04))
            p.drawEllipse(boton.adjusted(2, 2, -2, -2))
            centro = boton.center()
            pluma = QPen(QColor(C["texto"] if self.encima == "web" else C["suave"]), 1.5)
            pluma.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pluma)
            p.drawLine(centro + QPointF(-3.5, 3.5), centro + QPointF(3.5, -3.5))
            p.drawLine(centro + QPointF(-1, -3.5), centro + QPointF(3.5, -3.5))
            p.drawLine(centro + QPointF(3.5, -3.5), centro + QPointF(3.5, 1))
            derecha = boton.left() - 8
        for texto, color in reversed(self.resumen()):
            caja = pastilla(p, derecha, self.CABEZA / 2, texto, color, fuente=letra(12, QFont.Weight.DemiBold))
            derecha = caja.left() - 6
        espacio = derecha - izquierda - 10
        p.setFont(letra(16, QFont.Weight.Bold))
        p.setPen(QColor(C["texto"]))
        p.drawText(QRectF(izquierda, 15, espacio, 24), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                   QFontMetricsF(p.font()).elidedText(r.nombre, Qt.TextElideMode.ElideRight, espacio))
        carpetas = [c for c in r.carpetas if not c.perdida]
        principal = next((c for c in carpetas if c.principal), None)
        partes = [r.remoto or (principal.ruta if principal else r.ruta or t("Sin GitHub"))]
        if carpetas:
            partes.append(t("1 carpeta" if len(carpetas) == 1 else "{n} carpetas", n=len(carpetas)))
        if r.ramas:
            partes.append(t("1 rama" if len(r.ramas) == 1 else "{n} ramas", n=len(r.ramas)))
        if r.aviso == "fetch":
            partes.append(t("no se pudo revisar GitHub"))
        p.setFont(letra(12))
        p.setPen(QColor(C["suave"]))
        p.drawText(QRectF(izquierda, 40, espacio, 18), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                   QFontMetricsF(p.font()).elidedText("  ·  ".join(partes), Qt.TextElideMode.ElideRight, espacio))

    def pintar_error(self, p: QPainter) -> None:
        if self.repo.error == "wsl":
            texto = t("WSL está apagado: este proyecto aparece cuando lo prendas.")
        else:
            texto = t("No se pudo leer este repo: {error}", error=self.repo.error)
        p.setOpacity(min(1.0, max(0.0, self.contenido.x)))
        p.setFont(letra(12.5))
        p.setPen(QColor(paneles.C["suave"]))
        p.drawText(QRectF(22, self.CABEZA + 8, self.width() - 44, 36),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap), texto)
        p.setOpacity(1.0)

    def aparicion(self, i: int) -> float:
        """Las filas aparecen una detrás de otra, apenas escalonadas."""
        return max(0.0, min(1.0, self.contenido.x * 1.35 - i * 0.05))

    def pintar_ramas(self, p: QPainter) -> None:
        C = paneles.C
        n = len(self.filas)
        if not n:
            return
        x0 = self.TRONCO
        centro = [self.rect_fila(i).center().y() for i in range(n)]
        # el tronco: de la principal a la última rama, crece al abrir
        largo = (centro[-1] - centro[0]) * max(0.0, min(1.0, self.contenido.x))
        if n > 1:
            pluma = QPen(con_alfa(C["texto"], 0.13), 2)
            pluma.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pluma)
            p.drawLine(QPointF(x0, centro[0]), QPointF(x0, centro[0] + largo))
        maximo = max([max(f.rama.adelante, f.rama.atras) for f in self.filas if f.rama] + [1])
        for i, fila in enumerate(self.filas):
            alfa = self.aparicion(i)
            if alfa <= 0:
                continue
            p.save()
            p.setOpacity(alfa * (0.55 if fila.apagada else 1.0))
            p.translate(0, (1 - alfa) * 6)
            self.pintar_fila(p, i, fila, centro[i], maximo)
            p.restore()
        if self.viejas:
            self.pintar_viejas(p, n)

    def color_nodo(self, fila: Fila) -> tuple[QColor, bool]:
        """(color, relleno)."""
        C, r = paneles.C, fila.rama
        if r is None:
            return QColor(C["suave"]), False
        if r.sin_subir and self.repo.remoto:  # lo sabido de GitHub vale aunque no se haya podido medir contra main
            return QColor(C["acento"]), True
        if r.incierta:
            return (tono("verde"), True) if r.sin_bajar and self.repo.remoto else (QColor(C["suave"]), False)
        if not self.repo.remoto:  # sin GitHub no hay nada que subir: sin colores de alerta
            return QColor(C["suave"]), not r.mergeada
        if r.pendientes:
            return QColor(C["acento"]), True
        if r.mergeada and not r.carpeta:
            return QColor(C["suave"]), False
        if r.estado in ("subida", "sin_bajar"):
            return tono("verde"), True
        return QColor(C["suave"]), r.base

    def estado_rama(self, r: repos.Rama) -> tuple[str, QColor, float]:
        """El texto, el color y la intensidad del fondo de la pastilla de una rama."""
        C = paneles.C
        if r.incierta and not (self.repo.remoto and (r.sin_subir or r.sin_bajar)):
            return t("Sin comparar"), QColor(C["suave"]), 0.08
        if not self.repo.remoto:
            if r.base:
                return t("Sin GitHub"), QColor(C["suave"]), 0.08
            if r.mergeada:
                return t("Ya está en {base}", base=self.nombre_base()), QColor(C["suave"]), 0.08
            return t("{n} propios" if r.adelante != 1 else "1 propio", n=r.adelante), QColor(C["texto"]), 0.08
        if r.estado == "borrada":  # seguía una rama que ya no está en GitHub
            return t("Borrada en GitHub"), QColor(C["acento"] if r.pendientes else C["suave"]), (0.14 if r.pendientes
                                                                                                 else 0.08)
        if r.sin_subir and r.sin_bajar:
            return f"↑ {r.sin_subir}  ↓ {r.sin_bajar}", QColor(C["acento"]), 0.14
        if r.sin_subir:
            return t("↑ {n} sin subir", n=r.sin_subir), QColor(C["acento"]), 0.14
        if r.estado == "local" and r.pendientes:
            return t("Solo en tu compu"), QColor(C["acento"]), 0.14
        if r.sin_bajar:
            return t("↓ {n} para bajar", n=r.sin_bajar), QColor(C["texto"]), 0.08
        if r.base:
            return (t("Al día"), tono("verde"), 0.13) if r.en_remoto else (t("Sin GitHub"), QColor(C["suave"]), 0.08)
        if r.mergeada:
            return (t("Igual que {base}", base=self.nombre_base()) if not r.atras
                    else t("Ya está en {base}", base=self.nombre_base())), QColor(C["suave"]), 0.08
        if r.estado == "local":
            return t("Solo en tu compu"), QColor(C["suave"]), 0.08
        return t("Subida"), tono("verde"), 0.13

    def nombre_base(self) -> str:
        return self.repo.base_rama or "main"

    def pintar_fila(self, p: QPainter, i: int, fila: Fila, y: float, maximo: int) -> None:
        C, r = paneles.C, fila.rama
        caja = self.rect_fila(i)
        if self.encima in (i, f"chip{i}"):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(con_alfa(C["texto"], 0.045))
            p.drawRoundedRect(caja.adjusted(0, 3, 0, -3), 12, 12)
        x0 = self.TRONCO
        color, relleno = self.color_nodo(fila)
        es_tronco = bool(r and r.base)
        nodo = QPointF(x0, y) if es_tronco else QPointF(x0 + 18, y)
        if not es_tronco:  # la curva que sale del tronco
            curva = QPainterPath(QPointF(x0, y - self.FILA * 0.62))
            curva.cubicTo(QPointF(x0, y - 4), QPointF(x0 + 4, y), nodo)
            pluma = QPen(con_alfa(color, 0.55), 2)
            pluma.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pluma)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(curva)
        latido = self.latidos.get(fila.clave)
        if latido and latido.x > 0.01:  # algo cambió: un anillo que se abre y se apaga
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(con_alfa(color, 0.4 * latido.x))
            radio = 5 + 9 * (1 - latido.x)
            p.drawEllipse(nodo, radio, radio)
        p.setPen(QPen(color, 2))
        p.setBrush(color if relleno else QColor(C["panel"]))
        radio = 5.5 if es_tronco else 4.5
        p.drawEllipse(nodo, radio, radio)
        # a la derecha: cuándo, el estado y cuánto se separó de main
        derecha = caja.right() - 10
        if r:
            p.setFont(letra(11.5))
            p.setPen(QColor(C["suave"]))
            cuando = hace(r.fecha)
            p.drawText(QRectF(derecha - 70, y - 9, 70, 18),
                       int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), cuando)
            derecha -= 78
            texto, color_estado, fondo = self.estado_rama(r)
            derecha = pastilla(p, derecha, y, texto, color_estado, fondo).left() - 12
            if not r.base and not r.mergeada and derecha > 320:
                derecha = self.pintar_divergencia(p, derecha, y, r, maximo) - 12
        # el nombre y la etiqueta de la carpeta
        izquierda = nodo.x() + 16
        nombre = r.nombre if r else (fila.carpeta.rama if fila.carpeta and fila.carpeta.rama else t("commit suelto"))
        p.setFont(letra(13.5, QFont.Weight.DemiBold if fila.carpeta else QFont.Weight.Normal))
        p.setPen(QColor(C["texto"] if r else C["suave"]))
        espacio = derecha - izquierda
        chip_ancho = 0.0
        if fila.carpeta:
            chip_ancho = min(170.0, ancho_de(letra(11.5, QFont.Weight.Medium), fila.carpeta.nombre) + 34
                             + (ancho_de(letra(11.5, QFont.Weight.DemiBold), f"{fila.carpeta.cambios}") + 12
                                if fila.carpeta.cambios else 0))
        texto = QFontMetricsF(p.font()).elidedText(nombre, Qt.TextElideMode.ElideMiddle,
                                                   max(40.0, espacio - chip_ancho - 10))
        ancho = ancho_de(p.font(), texto)
        p.drawText(QRectF(izquierda, y - 10, ancho + 4, 20), int(Qt.AlignmentFlag.AlignVCenter), texto)
        fila.chip = QRectF()
        if fila.carpeta and izquierda + ancho + 10 + 60 < derecha:
            fila.chip = self.pintar_chip(p, izquierda + ancho + 10, y, fila.carpeta,
                                         min(chip_ancho, derecha - izquierda - ancho - 10), self.encima == f"chip{i}")

    def pintar_chip(self, p: QPainter, x: float, y: float, carpeta: repos.Carpeta, ancho: float,
                    encima: bool) -> QRectF:
        """La carpeta donde está puesta la rama: una cápsula de vidrio con su nombre (y los cambios sin
        commitear, si hay). Tocarla abre la carpeta."""
        C = paneles.C
        caja = QRectF(x, y - 11, ancho, 22)
        p.setPen(QPen(con_alfa(C["texto"], 0.16 if encima else 0.09), 1))
        p.setBrush(con_alfa(C["texto"], 0.10 if encima else 0.05))
        p.drawRoundedRect(caja, 11, 11)
        # la carpetita
        p.setPen(QPen(QColor(C["suave"]), 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        icono = QPainterPath(QPointF(x + 9, y - 3.5))
        icono.lineTo(x + 12.5, y - 3.5)
        icono.lineTo(x + 13.8, y - 2)
        icono.lineTo(x + 19, y - 2)
        icono.lineTo(x + 19, y + 4)
        icono.lineTo(x + 9, y + 4)
        icono.closeSubpath()
        p.drawPath(icono)
        derecha = caja.right() - 9
        if carpeta.cambios:
            numero = f"{carpeta.cambios}"
            p.setFont(letra(11.5, QFont.Weight.DemiBold))
            ancho_n = ancho_de(p.font(), numero)
            p.setPen(tono("ambar"))
            p.drawText(QRectF(derecha - ancho_n, y - 9, ancho_n + 1, 18), int(Qt.AlignmentFlag.AlignVCenter), numero)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(tono("ambar"))
            p.drawEllipse(QPointF(derecha - ancho_n - 6, y), 2.6, 2.6)
            derecha -= ancho_n + 12
        p.setFont(letra(11.5, QFont.Weight.Medium))
        p.setPen(QColor(C["texto"] if encima else C["suave"]))
        izquierda = x + 25
        p.drawText(QRectF(izquierda, y - 9, max(0.0, derecha - izquierda), 18), int(Qt.AlignmentFlag.AlignVCenter),
                   QFontMetricsF(p.font()).elidedText(carpeta.nombre, Qt.TextElideMode.ElideRight,
                                                      max(0.0, derecha - izquierda)))
        return caja

    def pintar_divergencia(self, p: QPainter, derecha: float, y: float, r: repos.Rama, maximo: int) -> float:
        """Una barrita centrada: a la izquierda lo que le falta de main, a la derecha lo suyo propio."""
        C = paneles.C
        medio, alcance = derecha - 34, 30.0

        def largo(n: int) -> float:
            return 0.0 if not n else max(3.0, alcance * math.log1p(n) / math.log1p(maximo))

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(con_alfa(C["texto"], 0.07))
        p.drawRoundedRect(QRectF(medio - alcance, y - 2, 2 * alcance, 4), 2, 2)
        if r.atras:
            p.setBrush(con_alfa(C["texto"], 0.32))
            p.drawRoundedRect(QRectF(medio - largo(r.atras), y - 2, largo(r.atras), 4), 2, 2)
        if r.adelante:
            p.setBrush(QColor(C["acento"]))
            p.drawRoundedRect(QRectF(medio, y - 2, largo(r.adelante), 4), 2, 2)
        p.setBrush(QColor(C["texto"]))
        p.drawRoundedRect(QRectF(medio - 0.75, y - 5, 1.5, 10), 0.75, 0.75)
        return medio - alcance

    def pintar_viejas(self, p: QPainter, n: int) -> None:
        C = paneles.C
        caja = self.rect_fila(n)
        alfa = self.aparicion(n)
        if alfa <= 0:
            return
        p.save()
        p.setOpacity(alfa)
        if self.encima == "viejas":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(con_alfa(C["texto"], 0.045))
            p.drawRoundedRect(caja.adjusted(0, 3, 0, -3), 12, 12)
        y = caja.center().y()
        p.setPen(QPen(QColor(C["suave"]), 1.4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for k in (-5, 0, 5):  # tres puntitos sobre el tronco
            p.drawEllipse(QPointF(self.TRONCO, y + k), 1.0, 1.0)
        if self.mostrar_viejas:
            texto = t("Esconder las ramas que ya están en {base}", base=self.nombre_base())
        else:
            texto = t("1 rama más ya está en {base}" if self.viejas == 1 else "{n} ramas más ya están en {base}",
                      n=self.viejas,
                      base=self.nombre_base())
        p.setFont(letra(12.5, QFont.Weight.Medium))
        p.setPen(QColor(C["texto"] if self.encima == "viejas" else C["suave"]))
        p.drawText(QRectF(self.TRONCO + 34, y - 10, caja.width() - 60, 20), int(Qt.AlignmentFlag.AlignVCenter), texto)
        p.restore()


# --------------------------------------------------------------------------------------- la sección

class Mensaje(paneles.Tarjeta):
    """Una tarjeta con una sola línea, para cuando no hay nada que mostrar."""

    def __init__(self):
        super().__init__("", 92)
        self.texto = t("Buscando tus proyectos…")

    def poner(self, texto: str) -> None:
        self.texto = texto
        self.update()

    def pintar(self, p: QPainter, r: QRectF) -> None:
        p.setFont(letra(12.5))
        p.setPen(QColor(paneles.C["suave"]))
        p.drawText(r, int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), self.texto)


class Proyectos(QWidget):
    """La página: arriba cuándo se revisó GitHub y tres cifras; debajo, un proyecto por tarjeta."""

    revisar = pyqtSignal()  # "preguntá a GitHub ya" (lo atiende ajustes.py con el Revisor)

    def __init__(self):
        super().__init__()
        caja = QVBoxLayout(self)
        caja.setContentsMargins(0, 0, 0, 0)
        caja.setSpacing(14)
        arriba = QHBoxLayout()
        arriba.addStretch(1)
        self.sincro = Sincro()
        self.sincro.tocado.connect(self.revisar)
        arriba.addWidget(self.sincro)
        caja.addLayout(arriba)
        self.sin_subir = paneles.Cifra("Commits sin subir")
        self.cambios = paneles.Cifra("Archivos sin commitear")
        self.limpiar = paneles.Cifra("Ramas para limpiar")
        self.limpiar.setToolTip(t("Ramas que ya están enteras en la principal y no tienen carpeta: se pueden borrar"))
        caja.addLayout(paneles.columnas(self.sin_subir, self.cambios, self.limpiar))
        self.lista = QVBoxLayout()
        self.lista.setSpacing(10)
        caja.addLayout(self.lista)
        self.mensaje = Mensaje()
        self.lista.addWidget(self.mensaje)
        caja.addStretch(1)
        self.tarjetas: dict[str, TarjetaRepo] = {}
        self.primera = True

    def mostrar(self, informe: dict | None) -> None:
        if not informe:
            return
        lista: list[repos.Repo] = informe["repos"]
        if informe["error"] == "sin_git":
            self.mensaje.poner(t("Para ver tus proyectos hace falta tener git instalado."))
        elif informe["error"]:
            self.mensaje.poner(t("No se pudieron leer los proyectos. Probá de nuevo en un rato."))
        else:
            self.mensaje.poner(t("Todavía no hay proyectos: aparecen acá cuando usás Claude Code en una carpeta con git."))
        self.mensaje.setVisible(not lista)
        if not lista and informe["error"]:
            return  # se queda lo que había
        self.sin_subir.poner(str(sum(r.sin_subir for r in lista)))
        self.cambios.poner(str(sum(r.cambios for r in lista)))
        self.limpiar.poner(str(sum(r.para_limpiar for r in lista)))
        revisados = [r.revisado for r in lista if r.revisado and r.remoto]
        self.sincro.poner(max(revisados) if revisados else None)
        claves = [r.clave for r in lista]
        for clave in list(self.tarjetas):
            if clave not in claves:
                tarjeta = self.tarjetas.pop(clave)
                self.lista.removeWidget(tarjeta)
                tarjeta.deleteLater()
        for i, repo in enumerate(lista):
            tarjeta = self.tarjetas.get(repo.clave)
            if tarjeta is None:
                # el primero (el que usaste último) llega abierto
                tarjeta = self.tarjetas[repo.clave] = TarjetaRepo(repo, abierta=self.primera and i == 0)
            else:
                tarjeta.poner(repo)
            if self.lista.indexOf(tarjeta) != i + 1:  # +1: el mensaje va primero
                self.lista.removeWidget(tarjeta)
                self.lista.insertWidget(i + 1, tarjeta)
        self.primera = False

    def buscar(self, si: bool) -> None:
        self.sincro.buscar(si)
