"""La barra de sesiones: una pastilla de vidrio arriba al centro de la pantalla.

Chiquita muestra cuánto falta para la respuesta que viene, cuántas sesiones hay y una luna si está
prendido "No molestar" (que se prende desde los ajustes o el ícono, no desde acá). Al pasarle el mouse se estira como un líquido (resortes que rebotan apenas, con los bordes
que se abomban según la velocidad) y muestra cada sesión: hace cuánto empezó, cuántos tokens lleva,
cuántos agentes tiene trabajando y la estimación de lo que falta, que se va corrigiendo en vivo.

El vidrio desenfoca de verdad lo que tiene detrás (en Windows): una ventana vacía, justo debajo de la
barra, le pide el desenfoque al sistema. Windows solo desenfoca rectángulos, así que esa ventana va metida
adentro de la forma redondeada y el canto que queda sin desenfocar se pinta más cerrado, como el borde
grueso de un vidrio. Encima van los brillos, el reflejo que sigue al mouse y el borde iluminado. Donde no
hay desenfoque (macOS), el vidrio es casi opaco para que el texto de atrás no se mezcle con el de adentro.

Está siempre a la vista, menos cuando hay algo en pantalla completa; se puede apagar desde el menú del
ícono junto al reloj (bandeja.py). Los datos los lee seguimiento.py en un hilo aparte, así la animación
nunca se traba leyendo transcripts.
"""

from __future__ import annotations

import ctypes
import math
import re
import threading
import time

import json
import os

import animacion
import estadisticas
import mascota as m
import ojos
import pedidos
import seguimiento
import sprites
import ventanas
from idiomas import t

from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer
from PyQt6.QtGui import (QColor, QCursor, QFont, QFontMetricsF, QTextCharFormat, QTextLayout,
                         QTextOption, QGuiApplication, QLinearGradient, QPainter,
                         QPainterPath, QPen, QPixmap, QRadialGradient)
from PyQt6.QtWidgets import QWidget

ARRIBA = 6            # separación del borde de arriba de la pantalla
ALTO_CHICA = 30
ALTO_PEDIDO = 34      # pidiendo permiso crece un poco, para que los botones respiren
BOTON = 24            # el alto de Permitir y Denegar
ANCHO_ABIERTA = 470
CABECERA = 58
FILA = 58
PIE = 12
USO = 38              # el renglón de uso (5 horas y 7 días) al pie de la barra abierta
MAX_FILAS = 8         # las que entran en la ventana; cuántas se listan lo dice la config (3, 5 u 8)
MARGEN = 18           # lugar alrededor para la sombra y los bordes que se abomban
RADIO = 20
K = 0.5523            # curva de Bézier que imita un cuarto de círculo
HISTORIAL = m.CONFIG_DIR / "duraciones.json"
AMARILLO = QColor(255, 209, 102)  # el color de "permiso" de la mascota
VERDE = QColor(52, 199, 89)       # el borde al permitir
ROJO = QColor(255, 69, 58)        # el borde al denegar
ANCHO_DETALLE = 470               # con el pedido desplegado (la flechita), para leerlo entero
MAX_DETALLE = 240                 # lo más alto que se despliega el texto del pedido
RELLENO = 12                      # el aire alrededor del comando, adentro de su recuadro


def corto(segundos: float) -> str:
    """1:20, 45 s, 1 h 05: lo que entra en la pastilla."""
    s = max(0, round(segundos))
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s // 60}:{s % 60:02d}"
    return f"{s // 3600} h {s % 3600 // 60:02d}"


def mezcla(a: QColor, b: QColor, k: float) -> QColor:
    k = min(1.0, max(0.0, k))
    return QColor(round(a.red() + (b.red() - a.red()) * k), round(a.green() + (b.green() - a.green()) * k),
                  round(a.blue() + (b.blue() - a.blue()) * k), round(a.alpha() + (b.alpha() - a.alpha()) * k))


def con_alfa(color: QColor, alfa: float) -> QColor:
    c = QColor(color)
    c.setAlphaF(min(1.0, max(0.0, alfa)))
    return c


def ventana_de(sesion: str) -> int:
    """La ventana (terminal, editor o app) donde corre esa sesión: la anota el hook al mandar un mensaje."""
    try:
        datos = json.loads((m.SESIONES / f"{sesion}.json").read_text(encoding="utf-8"))
        ventana = int(datos.get("ventana") or 0) if isinstance(datos, dict) else 0
        proceso = int(datos.get("proceso") or 0) if ventana else 0
    except (OSError, ValueError, TypeError):
        return 0
    # Si esa ventana se cerró, Windows puede darle el mismo número a otra: tiene que seguir siendo del
    # mismo proceso que la abrió.
    if ventana and ventanas.ES_WINDOWS and proceso and ventanas.pid_de_ventana(ventana) != proceso:
        return 0
    return ventana


class Lector(threading.Thread):
    """Actualiza el Monitor cada segundo y medio, fuera del hilo de la interfaz."""

    def __init__(self, monitor: seguimiento.Monitor):
        super().__init__(daemon=True)
        self.monitor = monitor
        self.foto: tuple[float, list[dict]] = (time.time(), [])
        self.uso: dict | None = None     # tokens de las últimas 5 horas y 7 días (cada medio minuto)
        self.listo = threading.Event()
        self.parar = threading.Event()
        self.analisis = estadisticas.Analisis(monitor.carpeta, m.CONFIG_DIR / "cache" / "uso.json")
        self.analisis.cancelado = self.parar.is_set

    def run(self) -> None:
        self.monitor.cancelado = self.parar.is_set
        try:
            self.monitor.aprender_del_pasado()
        except Exception as e:  # un transcript raro no tiene que dejar la barra sin datos
            m.log(f"[barra] no se pudo leer el historial: {e}")
        vuelta = 0
        while not self.parar.is_set():
            try:
                sesiones = self.monitor.actualizar()
                for s in sesiones:
                    s["ventana"] = ventana_de(s["id"])
                self.foto = (time.time(), sesiones)
                self.listo.set()
            except Exception as e:
                m.log(f"[barra] error leyendo sesiones: {e}")
            if vuelta % 20 == 0:  # cada medio minuto: el uso (solo se lee lo nuevo de cada transcript)
                try:
                    informe = self.analisis.actualizar()
                    if informe:
                        lapsos = informe["lapsos"]
                        self.uso = {"5h": lapsos["5h"]["tokens"], "7d": lapsos["7d"]["tokens"],
                                    "serie": lapsos["5h"]["serie"]}
                except Exception as e:
                    m.log(f"[barra] error leyendo el uso: {e}")
            vuelta += 1
            self.parar.wait(1.5)


FLOTANTE = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus | Qt.WindowType.NoDropShadowWindowHint)


class Desenfoque(QWidget):
    """Una ventana vacía que desenfoca lo que tiene detrás (Windows). Va justo debajo de la barra y sigue
    a su cuerpo cuadro a cuadro; no recibe el mouse."""

    def __init__(self):
        super().__init__(None, FLOTANTE | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("WaveMascot")
        self.caja: tuple[int, int, int, int] | None = None
        self.activo = False

    def prender(self, encima: QWidget, r: QRectF) -> bool:
        """Se muestra debajo de la barra y pide el desenfoque. False si el sistema no lo da."""
        self.caja = None
        self.resize(1, 1)
        self.show()
        self.activo = ventanas.desenfocar_detras(int(self.winId()))
        if self.activo:
            self.seguir(encima, r)
        else:
            self.hide()
        return self.activo

    def seguir(self, encima: QWidget, r: QRectF, forzar: bool = False) -> None:
        if not self.activo:
            return
        k = encima.devicePixelRatioF()  # Windows mueve ventanas en píxeles de pantalla
        origen = encima.mapToGlobal(QPoint(0, 0))
        caja = (round((origen.x() + r.left()) * k), round((origen.y() + r.top()) * k),
                max(1, round(r.width() * k)), max(1, round(r.height() * k)))
        if caja != self.caja or forzar:
            self.caja = caja
            ventanas.poner_debajo(int(self.winId()), int(encima.winId()), *caja)


class Barra(QWidget):
    def __init__(self, monitor: seguimiento.Monitor | None = None, leer: bool = True, desenfocar: bool = True):
        super().__init__(None, FLOTANTE)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        if m.MAC:
            self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.setWindowTitle("WaveMascot")
        self.setMouseTracking(True)
        # (30 px de más abajo: el rebote y la sombra de la isla más alta no se cortan)
        self.resize(ANCHO_ABIERTA + 2 * MARGEN, ARRIBA + CABECERA + MAX_FILAS * FILA + PIE + USO + 14 + MARGEN + 30)

        self.lector = Lector(monitor or seguimiento.Monitor(HISTORIAL))
        if leer:
            self.lector.start()
        self.sesiones: list[dict] = []        # las que se muestran (sin las quitadas con la ×)
        self.crudas: list[dict] = []          # todas las que leyó el Lector
        self.quitadas: dict[str, float] = {}  # {id: su última línea al quitarla}: vuelven si se mueven
        self.foto_hora = time.time()
        self.eta: dict[str, float] = {}       # lo que se muestra de cada sesión, suavizado
        self.config = m.cargar_config()
        self.config_guardada = -1              # la fecha del config.json que se leyó (para releerlo si cambia)
        self.abierta = False
        self.encima = False
        self.cursor = QPointF(-999, -999)
        self.reloj = self.arranque = time.monotonic()
        self.fase = 0.0                        # segundos desde que arrancó: el latido y los brillos
        self.trabajando = False
        self.zona = QRect()                    # lo último que se pintó: solo se repinta eso y lo nuevo
        self.desenfoque_previo = QRectF()      # dónde quedó el desenfoque en el cuadro anterior
        self.clave_quieto, self.foto_quieto = None, (QPoint(), QPixmap())
        self.desenfoque_posible = desenfocar and ventanas.ES_WINDOWS
        self.vidrio = Desenfoque() if self.desenfoque_posible and self.config["barra"]["desenfoque"] else None
        self.mirada = ojos.Mirada()            # los ojos de la mascota, en vez de un punto de estado
        self.boton_ajustes = QRectF()          # dónde quedaron pintados, para los clics
        self.zona_uso = QRectF()
        self.filas: list[tuple[QRectF, dict]] = []
        self.cruces: list[tuple[QRectF, dict]] = []   # la × de la fila con el mouse encima
        self.cruz_suave: dict[str, tuple[float, float]] = {}  # por sesión: (cuánto se ve la ×, cuánto está encima)
        self.cruz_reloj = time.monotonic()
        # Recién quitada una: el segundo clic de un doble clic no toca la fila que subió (ni la quita ni salta
        # a su ventana), y esa fila no muestra su × hasta que el mouse se aleje unos píxeles.
        self.quitada_en = -999.0
        self.punto_quitar = QPointF(-999, -999)
        # Pedidos de permiso (pedidos.py): el que se muestra, los que esperan y lo que ya se contestó acá.
        self.pedido: dict | None = None
        self.en_cola = 0
        self.tomados: dict[str, dict] = {}              # clave -> pedido: los que la isla dijo que muestra
        self.respondidos: set[str] = set()
        self.hecho: tuple[str, float, str] | None = None  # (texto, hasta, decisión) un momento después del clic
        self.detalle_abierto = False                    # la flechita: el pedido completo, desplegado
        self.mostrado: tuple[str, object] | None = None  # lo último que se pintó (para que se vaya suave)
        self.pedido_desde = 0.0
        self.ultimo_latido = 0.0
        self.en_pantalla_completa = False
        self.zonas_pedido: dict[str, QRectF] = {}
        self.mano = False
        self.detalle_maquetado: tuple[tuple, list, float] = ((), [], 0.0)  # (clave, renglones armados, alto)
        self.sonidos = m.Sonidos(self)

        # El cuerpo líquido: ancho y alto rebotan distinto, así no se estira como una caja.
        repintar = self.repintar
        self.r_ancho = animacion.Resorte(self, 140, 0.42, 0.66, al_paso=repintar)
        self.r_alto = animacion.Resorte(self, ALTO_CHICA, 0.50, 0.70, al_paso=repintar)
        self.r_contenido = animacion.Resorte(self, 0.0, 0.28, 1.0, al_paso=repintar)
        self.r_brillo = animacion.Resorte(self, 0.0, 0.30, 1.0, al_paso=repintar)
        self.r_pedido = animacion.Resorte(self, 0.0, 0.28, 1.0, al_paso=repintar)
        # Cuánto se tapa el vidrio mientras cambia de tamaño (ver alfa_vidrio): sube rápido, baja suave.
        self.r_tapar = animacion.Resorte(self, 0.0, 0.10, 1.0, al_paso=repintar)

        self.timer_abrir = QTimer(self, singleShot=True, interval=110, timeout=lambda: self.abrir(True))
        self.timer_cerrar = QTimer(self, singleShot=True, interval=420, timeout=lambda: self.abrir(False))
        # Dos relojes: el de los cuadros (mouse, latido, brillos: 60 por segundo mientras algo se mueve) y
        # el de los datos, más lento. Los resortes tienen el suyo (animacion.py).
        self.timer_cuadro = QTimer(self, interval=16, timeout=self.cuadro)
        self.timer_cuadro.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer_tic = QTimer(self, interval=250, timeout=self.tic)
        self.timer_pantalla = QTimer(self, interval=1000, timeout=self.revisar_pantalla)
        self.timer_pedidos = QTimer(self, interval=300, timeout=self.revisar_pedidos)
        self.oculta = False                    # escondida sola: pantalla completa o ningún chat activo
        self.ultima_chat = time.time()         # cuándo se movió algún chat (la cuenta arranca al abrir)
        pantalla = QGuiApplication.primaryScreen()
        if pantalla:  # cambió la resolución o se movió la barra de tareas: vuelve al centro de arriba
            pantalla.availableGeometryChanged.connect(lambda _: (self.ubicar(), self.repintar()))

    # --- vida -------------------------------------------------------------------

    def mostrar(self) -> None:
        self.ubicar()
        self.oculta = self.debe_esconderse()
        if not self.oculta:
            self.aparecer()
        for timer in (self.timer_cuadro, self.timer_tic, self.timer_pantalla, self.timer_pedidos):
            timer.start()
        self.aplicar_opciones()
        self.tic()

    def aparecer(self) -> None:
        self.show()
        if m.MAC:
            ventanas.ventana_flotante(int(self.winId()))
        if not self.vidrio and self.desenfoque_posible and self.isla["desenfoque"]:
            self.vidrio = Desenfoque()  # se pidió mientras estaba escondida
        if self.vidrio and not self.vidrio.prender(self, self.rect_desenfoque()):
            m.log("[barra] Windows no dio el desenfoque: vidrio pintado")
            self.vidrio.deleteLater()
            self.vidrio, self.desenfoque_posible = None, False

    def esconder(self) -> None:
        self.hide()
        # Vuelve chiquita y sin el mouse encima: al reaparecer no tiene que estar abierta.
        self.timer_abrir.stop()
        self.timer_cerrar.stop()
        self.encima = self.abierta = False
        self.r_contenido.fijar(0.0)
        self.r_brillo.fijar(0.0)
        if self.vidrio:
            self.vidrio.hide()

    def cerrar(self) -> None:
        self.soltar_pedidos()
        for timer in (self.timer_cuadro, self.timer_tic, self.timer_pantalla, self.timer_pedidos, self.timer_abrir,
                      self.timer_cerrar):
            timer.stop()
        self.esconder()

    def apagar(self) -> None:
        self.cerrar()
        self.lector.parar.set()
        if self.vidrio:
            self.vidrio.deleteLater()
            self.vidrio = None

    @property
    def isla(self) -> dict:
        """Las opciones de la isla (sección Dynamic Island de los ajustes)."""
        return self.config["barra"]

    def ubicar(self) -> None:
        pantalla = QGuiApplication.primaryScreen()
        if not pantalla:
            return
        area = pantalla.availableGeometry()  # si la barra de tareas está arriba, queda debajo de ella
        # A los costados el cuerpo va pegado a ese lado de la ventana (ver rect_cuerpo) y queda a 10 px del
        # borde de la pantalla, chica o abierta: nunca se sale.
        x = {"izquierda": area.left() + 10 - MARGEN, "derecha": area.right() + 1 - self.width() + MARGEN - 10}.get(
            self.isla["posicion"], area.center().x() - self.width() // 2)
        self.move(x, area.top())

    def aplicar_opciones(self) -> None:
        """Lo que cambia al tocar las opciones en los ajustes: dónde va, el desenfoque y el rebote."""
        self.ubicar()
        if self.vidrio and not self.isla["desenfoque"]:
            self.vidrio.hide()
            self.vidrio.deleteLater()
            self.vidrio = None
        elif (not self.vidrio and self.isla["desenfoque"] and self.desenfoque_posible and self.isVisible()):
            self.vidrio = Desenfoque()
            if not self.vidrio.prender(self, self.rect_desenfoque()):
                self.vidrio.deleteLater()
                self.vidrio, self.desenfoque_posible = None, False
        rebote = self.isla["rebote"]
        self.r_ancho.configurar(0.42, 0.66 if rebote else 1.0)
        self.r_alto.configurar(0.50, 0.70 if rebote else 1.0)
        self.clave_quieto = None
        self.zona = self.rect()  # que se repinte todo: pudo cambiar de lugar o de tamaño
        self.repintar()

    def hay_pantalla_completa(self) -> bool:
        # Una ventana maximizada no cuenta (aunque tape todo porque la barra de tareas se esconde sola).
        return self.isla["pantalla_completa"] and ventanas.pantalla_completa(maximizada_no_cuenta=True)

    def sin_chats(self) -> bool:
        """Ningún chat se movió en los minutos elegidos (o Claude está cerrado): se va hasta que vuelva uno."""
        if not self.isla["esconder_sin_chats"] or not self.lector.listo.is_set():
            return False  # (hasta la primera lectura no se sabe nada: que no parpadee al arrancar)
        if self.encima or self.abierta:
            return False  # no se le va de abajo del mouse
        return seguimiento.sin_chats(self.ultima_chat, time.time(), self.isla["minutos_sin_chats"])

    def debe_esconderse(self) -> bool:
        # Un chat esperando permiso puede no moverse en un rato: con un pedido a la vista no se va.
        return self.hay_pantalla_completa() or (self.sin_chats() and not (self.pedido or self.hecho))

    def revisar_pantalla(self) -> None:
        """Está siempre, menos sobre un video, un juego o una presentación en pantalla completa y (si se
        eligió) cuando hace rato que no hay ningún chat activo."""
        self.en_pantalla_completa = self.hay_pantalla_completa()
        esconder = self.debe_esconderse()
        if esconder and not self.oculta:
            self.oculta = True
            self.esconder()
        elif not esconder and self.oculta:
            self.oculta = False
            self.aparecer()
            self.repintar()
        elif not esconder and self.vidrio:
            self.vidrio.seguir(self, self.rect_desenfoque(), forzar=True)  # que siga justo debajo

    def puede_pedir(self) -> bool:
        """¿La isla puede mostrar pedidos de permiso? (prendida, con la opción y no en pantalla completa)"""
        return self.timer_pedidos.isActive() and self.isla["permisos"] and not self.en_pantalla_completa

    def revisar_pedidos(self) -> None:
        """Cada 300 ms: ¿hay algún pedido de permiso esperando? La isla los toma todos (así el hook no saca el
        cartel de la mascota) y muestra el más viejo; los otros esperan su turno con un "+1". Cada pedido se
        reconoce por su clave (un pid se puede repetir)."""
        ahora = time.time()
        if self.hecho and time.monotonic() > self.hecho[1]:
            self.hecho = None
        puede = self.puede_pedir()
        if puede and ahora - self.ultimo_latido > pedidos.LATIDO:
            pedidos.latir(m.PEDIDOS)  # "acá estoy": si no, el hook ni la espera
            self.ultimo_latido = ahora
        if not puede:
            self.soltar_pedidos()
            return
        lista = pedidos.pendientes(m.PEDIDOS, ahora)
        claves = {d["clave"] for d in lista}
        self.tomados = {c: d for c, d in self.tomados.items() if c in claves}
        self.respondidos &= claves
        lista = [d for d in lista if d["clave"] not in self.respondidos]
        for d in lista:
            if d["clave"] not in self.tomados:
                try:
                    pedidos.contestar(m.PEDIDOS, d, visto=True)
                    self.tomados[d["clave"]] = d
                except OSError as e:
                    m.log(f"[barra] no se pudo tomar el pedido de permiso: {e}")
        lista = [d for d in lista if d["clave"] in self.tomados]
        antes = self.pedido
        if self.pedido and self.pedido["clave"] not in self.tomados:
            self.pedido = None  # se contestó en otro lado (terminal, cartel, Telegram) o se le pasó el tiempo
        if not self.pedido and not self.hecho and lista:
            self.mostrar_pedido(lista[0])
        self.en_cola = max(0, len(lista) - (1 if self.pedido else 0))
        if antes and not self.pedido and not self.hecho:
            m.log("[barra] pedido de permiso cerrado")
        self.r_pedido.ir_a(1.0 if self.pedido or self.hecho else 0.0)
        self.medir()

    def mostrar_pedido(self, pedido: dict) -> None:
        self.pedido, self.mostrado = pedido, ("pedido", pedido)
        self.detalle_abierto = False
        self.pedido_desde = time.monotonic()  # un clic que iba para el anterior no cae en este
        self.sonidos.tocar(pedido.get("sonido") or "", self.config["volumen"])
        self.timer_abrir.stop()
        self.abrir(False)  # si estaba estirada mostrando las sesiones, vuelve a pastilla
        if self.oculta:
            self.revisar_pantalla()  # escondida por falta de chats: vuelve
        m.log(f"[barra] pedido de permiso a la vista: {pedido['etiqueta']}")

    def soltar_pedidos(self) -> None:
        """La isla no los puede mostrar más (se apagó, se sacó la opción o hay pantalla completa): les avisa a
        los hooks, que dejan de esperarla."""
        if self.ultimo_latido:
            pedidos.callar(m.PEDIDOS)
            self.ultimo_latido = 0.0
        if not self.tomados and not self.pedido:
            return
        for d in self.tomados.values():
            try:
                pedidos.contestar(m.PEDIDOS, d, visto=False)
            except OSError:
                pass
        m.log(f"[barra] suelta {len(self.tomados)} pedido(s) de permiso")
        self.tomados, self.pedido, self.en_cola = {}, None, 0
        self.detalle_abierto = False
        self.r_pedido.ir_a(1.0 if self.hecho else 0.0)
        self.medir()

    def decidir(self, decision: str) -> None:
        """Un clic en Permitir o Denegar: se le contesta al hook, que se lo devuelve a Claude Code."""
        pedido = self.pedido
        if not pedido:
            return
        try:
            pedidos.contestar(m.PEDIDOS, pedido, visto=True, decision=decision)
        except OSError as e:  # (ya se reintentó): los botones quedan, se puede volver a tocar
            m.log(f"[barra] no se pudo contestar el permiso: {e}")
            return
        m.log(f"[barra] permiso {decision}: {pedido['etiqueta']}")
        self.respondidos.add(pedido["clave"])
        self.tomados.pop(pedido["clave"], None)
        self.pedido = None
        texto = t("Permitido") if decision == "allow" else t("Denegado")
        self.hecho, self.mostrado = (texto, time.monotonic() + 1.4, decision), ("hecho", (texto, decision))
        self.detalle_abierto = False
        self.medir()
        self.repintar()

    def tic(self) -> None:
        """Los datos: sesiones nuevas, la cuenta regresiva y el ancho que hace falta."""
        ahora = time.monotonic()
        dt = min(1.5, ahora - self.reloj)
        self.reloj = ahora
        foto_hora, sesiones = self.lector.foto
        if foto_hora != self.foto_hora or sesiones is not self.crudas:
            self.foto_hora, self.crudas = foto_hora, sesiones
        self.sesiones = seguimiento.visibles(self.crudas, self.quitadas)
        try:  # la config se vuelve a leer apenas cambia el archivo: las opciones se ven al instante
            guardada = m.CONFIG.stat().st_mtime_ns
        except OSError:
            guardada = 0
        if guardada != self.config_guardada:
            self.config_guardada = guardada
            antes, self.config = self.config["barra"], m.cargar_config()
            if self.config["barra"] != antes:
                self.aplicar_opciones()
        self.trabajando = any(s["trabajando"] for s in self.sesiones)
        ahora_reloj, minutos = time.time(), self.isla["minutos_sin_chats"]
        antes = self.ultima_chat
        self.ultima_chat = seguimiento.ultima_actividad(self.sesiones, antes, ahora_reloj)
        if (self.oculta and seguimiento.sin_chats(antes, ahora_reloj, minutos)
                and not seguimiento.sin_chats(self.ultima_chat, ahora_reloj, minutos)):
            self.revisar_pantalla()  # se activó un chat: vuelve ya, sin esperar el repaso de cada segundo
        self.suavizar(dt)
        self.medir()
        self.repintar()
        # Sin nada trabajando ni el mouse encima, alcanza con un repaso por segundo (los relojes de "hace").
        self.timer_tic.setInterval(250 if self.encima or self.abierta or self.trabajando else 1000)

    def cuadro(self) -> None:
        """Los cuadros: dónde está el mouse y, si algo se mueve (latido, brillos, reflejo), repintar."""
        if not self.isVisible():  # escondida por la pantalla completa: nada que animar
            if self.timer_cuadro.interval() != 500:
                self.timer_cuadro.setInterval(500)
            return
        self.revisar_encima()
        cerca = self.encima or self.abierta
        pidiendo = bool(self.pedido or self.hecho)
        self.mirada.animo = ("despierta" if self.trabajando or pidiendo else "tranquila" if self.sesiones
                             else "dormida")
        r = self.rect_cuerpo()
        dx, dy = self.cursor.x() - (r.left() + 30), self.cursor.y() - (r.top() + 15)
        if (self.isla["seguir_mouse"] and abs(dx) < 420 and -40 < dy < 320
                and self.mirada.animo != "dormida"):  # el mouse anda cerca: lo miran
            self.mirada.seguir = (max(-1.0, min(1.0, dx / 120)), max(-1.0, min(1.0, dy / 80)))
        else:
            self.mirada.seguir = None
        if self.mirada.avanzar() or cerca or self.trabajando or pidiendo:
            self.repintar()
        # 60 por segundo con el mouse encima, 30 para el latido solo, y casi nada si no pasa nada.
        intervalo = 16 if cerca else 33 if self.trabajando or pidiendo else 60
        if self.timer_cuadro.interval() != intervalo:
            self.timer_cuadro.setInterval(intervalo)

    def repintar(self, _valor: float | None = None) -> None:
        """Repinta solo el cuerpo (y lo que ocupaba antes), no la ventana entera, y corre el desenfoque."""
        if not self.isVisible():
            return
        zona = self.rect_cuerpo().adjusted(-MARGEN, -ARRIBA, MARGEN, MARGEN).toAlignedRect()
        self.update(zona.united(self.zona))
        self.zona = zona
        cambiando = self.r_ancho.moviendose or self.r_alto.moviendose
        if cambiando and self.r_tapar.objetivo != 1.0:
            self.r_tapar.configurar(0.10, 1.0)
            self.r_tapar.ir_a(1.0)
        elif not cambiando and self.r_tapar.objetivo != 0.0:
            self.r_tapar.configurar(0.45, 1.0)
            self.r_tapar.ir_a(0.0)
        # (el desenfoque se mueve en paintEvent, junto con lo que se dibuja: si se movía acá, iba un cuadro
        # adelantado y al achicarse asomaba un rectángulo borroso al costado de la pastilla)

    def suavizar(self, dt: float) -> None:
        """La cuenta regresiva baja de a un segundo y se acerca de a poco a la estimación nueva."""
        atraso = time.time() - self.foto_hora
        vivas = set()
        for s in self.sesiones:
            if not s["trabajando"] or s["falta"] is None:
                continue
            vivas.add(s["id"])
            objetivo = max(1.0, s["falta"] - atraso)
            actual = self.eta.get(s["id"])
            if actual is None or abs(actual - objetivo) > 600:
                self.eta[s["id"]] = objetivo
                continue
            actual = max(1.0, actual - dt)
            self.eta[s["id"]] = actual + (objetivo - actual) * min(1.0, dt * 0.9)
        for ident in list(self.eta):
            if ident not in vivas:
                del self.eta[ident]

    def transcurrido(self, s: dict) -> float:
        return s["transcurrido"] + (time.time() - self.foto_hora) if s["trabajando"] else 0.0

    # --- tamaño y mouse -----------------------------------------------------------

    def texto_chica(self) -> tuple[str, str]:
        """(lo principal, lo de al lado) para la pastilla chica."""
        trabajando = [s for s in self.sesiones if s["trabajando"]]
        n = len(self.sesiones)
        resto = []
        if n and self.isla["sesiones"]:
            resto.append(t("1 sesión") if n == 1 else t("{n} sesiones", n=n))
        agentes = sum(s["agentes"] for s in self.sesiones)
        if agentes:
            resto.append(t("1 agente") if agentes == 1 else t("{n} agentes", n=agentes))
        if not trabajando:
            return (t("Sin sesiones activas") if not n else t("En espera")), " · ".join(resto)
        if not self.isla["tiempo"]:
            return t("Trabajando"), " · ".join(resto)
        con_eta = [s for s in trabajando if s["id"] in self.eta]
        if con_eta:
            proxima = min(con_eta, key=lambda s: self.eta[s["id"]])
            return "~" + corto(self.eta[proxima["id"]]), " · ".join(resto)
        return t("Pensando {tiempo}", tiempo=corto(self.transcurrido(trabajando[0]))), " · ".join(resto)

    def medir(self) -> None:
        if self.pedido or self.hecho:  # se alarga para el permiso (y no se estira con el mouse)
            ancho = math.ceil(self.ancho_pedido() / 2) * 2
            alto = ALTO_PEDIDO + (self.alto_detalle(ancho) if self.pedido and self.detalle_abierto else 0)
            if abs(self.r_ancho.objetivo - ancho) > 0.5:
                self.r_ancho.ir_a(ancho)
            if abs(self.r_alto.objetivo - alto) > 0.5:
                self.r_alto.ir_a(alto)
            return
        if self.abierta:
            alto = self.alto_abierta()
            if self.r_ancho.objetivo != ANCHO_ABIERTA:
                self.r_ancho.ir_a(ANCHO_ABIERTA)
            if abs(self.r_alto.objetivo - alto) > 0.5:
                self.r_alto.ir_a(alto)
            return
        principal, resto = self.texto_chica()
        fm1 = QFontMetricsF(m.fuente(9, QFont.Weight.DemiBold))
        fm2 = QFontMetricsF(m.fuente(9))
        # Lo mismo que ocupa en pintar_chica: los ojos, el texto principal, el resto y la luna.
        ancho = 12 + self.ancho_ojos() + 8 + fm1.horizontalAdvance(principal) + 18
        if resto:
            ancho += 10 + fm2.horizontalAdvance(resto)
        if m.silenciada(self.config):
            ancho += 18
        # De a 6 px: que el ancho no se re-anime cada vez que cambia un número de la cuenta regresiva.
        ancho = math.ceil(max(110, min(ancho, ANCHO_ABIERTA - 60)) / 6) * 6 + (8 if self.encima else 0)
        if abs(self.r_ancho.objetivo - ancho) > 0.5:
            self.r_ancho.ir_a(ancho)
        if abs(self.r_alto.objetivo - ALTO_CHICA) > 0.5:
            self.r_alto.ir_a(ALTO_CHICA)

    def ancho_pedido(self) -> float:
        """Lo que ocupa la pastilla pidiendo permiso: ojos, la etiqueta, "+1" y los dos botones."""
        inicio = 12 + self.ancho_ojos() + 9
        fuerte = QFontMetricsF(m.fuente(9, QFont.Weight.DemiBold))
        if self.hecho or not self.pedido:
            return inicio + fuerte.horizontalAdvance(self.hecho[0] if self.hecho else "") + 18
        etiqueta = min(190.0, fuerte.horizontalAdvance(self.pedido["etiqueta"]) + 2)
        mas = QFontMetricsF(m.fuente(8)).horizontalAdvance(f"+{self.en_cola}") + 6 if self.en_cola else 0
        ancho = (inicio + etiqueta + mas + 14 + self.ancho_boton("deny") + 5 + self.ancho_boton("allow") + 5
                 + BOTON + 5)  # (la flechita)
        return max(ancho, ANCHO_DETALLE) if self.detalle_abierto else ancho

    @staticmethod
    def fuente_detalle():
        """La letra del pedido desplegado: la misma de la isla, un punto más grande que la de los datos."""
        return m.fuente(9)

    def texto_detalle(self) -> tuple[str, str, list[str]]:
        """(la herramienta, el proyecto y el chat, los renglones del pedido completo). Un comando encadenado va
        de a un comando por renglón."""
        pedido = self.pedido or {}
        herramienta = pedido.get("herramienta") or ""
        contexto = " · ".join(d for d in (pedido.get("proyecto"), pedido.get("chat")) if d)
        texto = pedido.get("detalle") or pedido.get("etiqueta") or ""
        lineas = pedidos.renglones(texto) if herramienta in ("Bash", "PowerShell") else [texto]
        # el operador del final nunca queda solo en un renglón: va pegado (espacio duro) a lo anterior
        lineas = [re.sub(r" (&&|\|\||\|)$", "\u00a0\\1", linea) for linea in lineas]
        return herramienta, contexto, lineas or [texto]

    def maquetar_detalle(self, ancho: float) -> tuple[list, float]:
        """Arma los renglones del pedido para un ancho: sin cortar palabras (salvo que una sola no entre), lo que
        no entra sigue abajo con sangría, y en cada comando el programa resaltado y los argumentos más tenues.
        Se guarda: se pinta 60 veces por segundo y no cambia."""
        herramienta, _, lineas = self.texto_detalle()
        claro = self.config["tema"] == "claro"
        clave = (tuple(lineas), herramienta, round(ancho), claro)
        if clave == self.detalle_maquetado[0]:
            return self.detalle_maquetado[1], self.detalle_maquetado[2]
        letra = self.fuente_detalle()
        fm = QFontMetricsF(letra)
        texto = QColor(22, 22, 30) if claro else QColor(246, 246, 250)
        util = max(40.0, ancho - 2 * RELLENO)
        sangria = fm.horizontalAdvance("    ")
        opciones = QTextOption()
        opciones.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        armados, y = [], 0.0
        for linea in lineas:
            # Que corte solo en los espacios: después de un guion o una barra va una "unión" invisible (U+2060),
            # así "--maxfail=1" o "build/dist" no se parten (salvo que una palabra sola no entre).
            linea = re.sub(r"([-/])(?=\S)", "\\1\u2060", linea)
            capa = QTextLayout(linea, letra)
            capa.setTextOption(opciones)
            if herramienta in ("Bash", "PowerShell"):
                capa.setFormats(self.formatos_comando(linea, texto))
            capa.beginLayout()
            primera = True
            while True:
                renglon = capa.createLine()
                if not renglon.isValid():
                    break
                x = 0.0 if primera else sangria
                renglon.setLineWidth(util - x)
                renglon.setPosition(QPointF(x, y))
                y += fm.lineSpacing() + 3
                primera = False
            capa.endLayout()
            armados.append(capa)
            y += 5  # un respiro entre comando y comando
        alto = max(0.0, y - 5)
        self.detalle_maquetado = (clave, armados, alto)
        return armados, alto

    @staticmethod
    def formatos_comando(linea: str, texto: QColor) -> list:
        """El programa (y su subcomando) bien visible, los argumentos un poco más tenues y el operador del final
        (&&, |, ;) apagado."""
        def formato(color: QColor, negrita: bool = False):
            f = QTextCharFormat()
            f.setForeground(color)
            if negrita:
                f.setFontWeight(QFont.Weight.DemiBold)
            return f

        def rango(inicio: int, largo: int, f) -> QTextLayout.FormatRange:
            r = QTextLayout.FormatRange()
            r.start, r.length, r.format = inicio, largo, f
            return r

        rangos = [rango(0, len(linea), formato(con_alfa(texto, 0.72)))]
        programa = re.match(r"\s*((?:\w+=\S+\s+)*)(\S+)(\s+[a-z][\w:-]*)?", linea)
        if programa:
            inicio = programa.start(2)
            fin = programa.end(3) if programa.group(3) else programa.end(2)
            rangos.append(rango(inicio, fin - inicio, formato(texto, negrita=True)))
        operador = re.search(r"\s*(&&|\|\||\||;)$", linea)
        if operador:
            rangos.append(rango(operador.start(1), len(operador.group(1)), formato(con_alfa(texto, 0.40))))
        return rangos

    def alto_detalle(self, ancho: float) -> float:
        """Lo que crece hacia abajo con el pedido desplegado: la cabecera y el recuadro del comando (con tope)."""
        _, alto = self.maquetar_detalle(ancho - 36)
        return 10 + 22 + 10 + min(MAX_DETALLE, alto) + 2 * RELLENO + 14

    @staticmethod
    def ancho_boton(decision: str) -> float:
        texto = t("Permitir") if decision == "allow" else t("Denegar")
        return QFontMetricsF(m.fuente(8, QFont.Weight.DemiBold)).horizontalAdvance(texto) + 24

    def ancho_ojos(self) -> float:
        """Lo que ocupa el display de los ojos en la pastilla, a 2 px por píxel de arte (o el punto)."""
        return 2.0 * ojos.ANCHO if self.isla["ojos"] else 10.0

    def alto_abierta(self) -> float:
        filas = max(1, min(len(self.sesiones), self.max_filas()))
        return (CABECERA + filas * FILA + PIE + (USO if self.isla["uso"] else 0)
                + (14 if len(self.sesiones) > self.max_filas() else 0))

    def max_filas(self) -> int:
        return min(MAX_FILAS, self.isla["filas"])

    def rect_cuerpo(self) -> QRectF:
        w, h = self.r_ancho.x, self.r_alto.x
        x = {"izquierda": float(MARGEN), "derecha": self.width() - MARGEN - w}.get(
            self.isla["posicion"], (self.width() - w) / 2)
        return QRectF(x, ARRIBA, w, h)

    def canto(self) -> float:
        """Cuánto se mete el desenfoque (un rectángulo) adentro de la forma redondeada: lo justo para que
        sus esquinas no asomen más de un par de píxeles, que quedan debajo del borde y la sombra."""
        r = self.rect_cuerpo()
        return 0.22 * min(r.height() / 2, RADIO, r.width() / 2)

    def rect_desenfoque(self) -> QRectF:
        c = self.canto()
        return self.rect_cuerpo().adjusted(c, c, -c, -c)

    def revisar_encima(self) -> None:
        if not self.isVisible():
            return
        self.cursor = QPointF(self.mapFromGlobal(QCursor.pos()))
        holgura = 10 if self.abierta else 4
        adentro = self.rect_cuerpo().adjusted(-holgura, -ARRIBA, holgura, holgura).contains(self.cursor)
        if adentro != self.encima:
            self.encima = adentro
            self.r_brillo.ir_a(1.0 if adentro else 0.0)
            if adentro:
                self.timer_cerrar.stop()
                # (pidiendo permiso no se estira: los botones no se le pueden ir de abajo del mouse)
                if self.isla["abrir"] == "mouse" and not (self.pedido or self.hecho):  # si no, recién al tocarla
                    self.timer_abrir.start()
            else:
                self.timer_abrir.stop()
                self.timer_cerrar.start()
            self.medir()
        # La manito sobre los botones (self.cursor es dónde está el mouse, no el cursor de Qt).
        zona = next((c for c, z in self.zonas_pedido.items() if z.contains(self.cursor)), None) if self.pedido else None
        mano = zona in ("allow", "deny", "flecha") or (zona == "etiqueta" and bool(self.pedido.get("ventana")))
        if mano != self.mano:
            self.mano = mano
            self.setCursor(Qt.CursorShape.PointingHandCursor if mano else Qt.CursorShape.ArrowCursor)

    def abrir(self, abrir: bool) -> None:
        if abrir == self.abierta:
            return
        self.abierta = abrir
        self.r_contenido.ir_a(1.0 if abrir else 0.0)
        self.medir()

    def mousePressEvent(self, evento) -> None:
        punto = evento.position()
        if self.pedido or self.hecho:
            if not self.pedido or self.r_pedido.x < 0.8 or time.monotonic() - self.pedido_desde < 0.45:
                return  # todavía se está alargando, recién cambió de pedido o ya se contestó
            for clave, zona in self.zonas_pedido.items():
                if zona.contains(punto):
                    if clave in ("allow", "deny"):
                        self.decidir(clave)
                    elif clave == "flecha":  # despliega (o pliega) el pedido completo
                        self.detalle_abierto = not self.detalle_abierto
                        self.medir()
                        self.repintar()
                    elif clave == "etiqueta" and self.pedido.get("ventana"):  # trae la ventana de esa sesión
                        ventanas.enfocar(int(self.pedido["ventana"]))
                    return
            return
        if not self.abierta:
            if self.rect_cuerpo().contains(punto):
                self.timer_abrir.stop()
                self.abrir(True)
        elif time.monotonic() - self.quitada_en < self.intervalo_doble_clic():
            return  # el segundo clic de un doble clic sobre la ×
        elif self.r_contenido.x < 0.9:
            return  # todavía se está abriendo: lo de adentro no está pintado (ni donde va a quedar)
        elif self.boton_ajustes.contains(punto):
            self.abrir_ajustes()
        elif cruz := next((s for caja, s in self.cruces if caja.contains(punto)), None):
            self.quitar(cruz, punto)
        elif self.zona_uso.contains(punto):
            self.abrir_ajustes("uso")
        elif (punto - self.punto_quitar).manhattanLength() < 8:
            return  # otro clic donde estaba la × que usaste: la fila que subió no es la que querías abrir
        else:  # una sesión: saltar a la ventana donde corre
            for caja, s in self.filas:
                if caja.contains(punto) and s.get("ventana") and self.isla["saltar"]:
                    if ventanas.enfocar(s["ventana"]):
                        self.abrir(False)
                    break

    @staticmethod
    def intervalo_doble_clic() -> float:
        return max(0.2, QGuiApplication.styleHints().mouseDoubleClickInterval() / 1000)

    def quitar(self, s: dict, punto: QPointF) -> None:
        """La × de una sesión en espera: sale de la isla hasta que se vuelva a mover."""
        self.quitadas[s["id"]] = s.get("ultima") or time.time()
        self.sesiones = seguimiento.visibles(self.crudas, self.quitadas)
        self.cruces = []
        self.quitada_en = time.monotonic()
        self.punto_quitar = QPointF(punto)
        self.medir()
        self.repintar()

    @staticmethod
    def abrir_ajustes(seccion: str = "") -> None:
        if os.name == "nt":  # el clic es nuestro: dejamos que la ventana de ajustes tome el foco
            ctypes.windll.user32.AllowSetForegroundWindow(-1)
        m.lanzar_desacoplado([str(m.DIR / "ajustes.py"), *([f"--seccion={seccion}"] if seccion else [])])

    # --- dibujo -------------------------------------------------------------------

    def forma(self) -> QPainterPath:
        """El cuerpo: un rectángulo redondeado cuyos bordes se abomban con la velocidad, como un líquido."""
        r = self.rect_cuerpo()
        x, y, w, h = r.x(), r.y(), r.width(), r.height()
        rad = min(h / 2, RADIO, w / 2)
        abajo = max(-7.0, min(7.0, self.r_alto.v * 0.010))     # crece hacia abajo: la panza se adelanta
        if not self.isla["rebote"]:
            abajo = 0.0
        # Los costados solo se abomban si tienen un tramo recto: en la pastilla chica harían un pico.
        lados = max(-5.0, min(5.0, self.r_ancho.v * 0.006)) * min(1.0, max(0.0, (h - 2 * rad) / 40))
        tercio_h, tercio_w = (h - 2 * rad) / 3, (w - 2 * rad) / 3
        c = rad * K
        p = QPainterPath(QPointF(x + rad, y))
        p.lineTo(x + w - rad, y)
        p.cubicTo(x + w - rad + c, y, x + w, y + rad - c, x + w, y + rad)
        p.cubicTo(x + w + lados, y + rad + tercio_h, x + w + lados, y + h - rad - tercio_h, x + w, y + h - rad)
        p.cubicTo(x + w, y + h - rad + c, x + w - rad + c, y + h, x + w - rad, y + h)
        p.cubicTo(x + w - rad - tercio_w, y + h + abajo, x + rad + tercio_w, y + h + abajo, x + rad, y + h)
        p.cubicTo(x + rad - c, y + h, x, y + h - rad + c, x, y + h - rad)
        p.cubicTo(x - lados, y + h - rad - tercio_h, x - lados, y + rad + tercio_h, x, y + rad)
        p.cubicTo(x, y + rad - c, x + rad - c, y, x + rad, y)
        p.closeSubpath()
        return p

    def colores(self) -> dict:
        claro = self.config["tema"] == "claro"
        cuerpo = QColor(*sprites.COLORES.get(self.config["aspecto"]["color"], sprites.COLORES["terracota"])[1])
        return {
            "claro": claro,
            "acento": cuerpo,
            # Con el desenfoque de atrás alcanza con un tinte; sin él, el vidrio tiene que tapar casi todo
            # para que el texto de atrás no se mezcle con el de adentro.
            "fondo": (QColor(246, 246, 250, self.alfa_vidrio() if self.vidrio else 242) if claro
                      else QColor(20, 21, 28, self.alfa_vidrio() if self.vidrio else 240)),
            "texto": QColor(22, 22, 30) if claro else QColor(246, 246, 250),
            "tenue": QColor(22, 22, 30, 150) if claro else QColor(236, 236, 245, 150),
            "linea": QColor(0, 0, 0, 22) if claro else QColor(255, 255, 255, 20),
        }

    def alfa_vidrio(self) -> int:
        """Cuánto tapa el vidrio. Mientras la pastilla cambia de tamaño, tapa más: Windows redibuja el desenfoque
        de atrás con atraso al redimensionarlo (y a veces se saltea un par de cuadros), y el fondo titilaba entre
        nítido y borroso. Sube rápido apenas empieza a moverse (y más si va rápido) y vuelve suave al quedarse
        quieta, así el cambio no se nota."""
        alfa = 255 * self.isla["opacidad"] / 100
        if self.vidrio:
            rapidez = min(1.0, max(abs(self.r_ancho.v), abs(self.r_alto.v)) / 220.0)  # píxeles por segundo
            alfa += (238 - alfa) * max(rapidez, min(1.0, self.r_tapar.x))
        return round(alfa)

    def paintEvent(self, evento) -> None:
        self.fase = time.monotonic() - self.arranque
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        col = self.colores()
        forma = self.forma()
        cuerpo = self.rect_cuerpo()
        # Con la pantalla al 125 % o 150 % la foto guardada caería a medio píxel: ahí se pinta siempre.
        if (self.r_ancho.moviendose or self.r_alto.moviendose or self.r_tapar.moviendose
                or not self.devicePixelRatioF().is_integer()):
            self.pintar_vidrio(p, forma, cuerpo, col, bool(self.vidrio))
        else:  # quieto, el vidrio es siempre el mismo: se pinta una vez y se guarda
            p.drawPixmap(*self.vidrio_quieto(forma, cuerpo, col))
        self.pintar_luces(p, forma, cuerpo, col, self.trabajando or bool(self.pedido))
        p.save()
        p.setClipPath(forma)
        # Lo de la pastilla chica se va rápido; lo de adentro aparece recién cuando el cuerpo ya casi creció,
        # así nunca se ven las dos cosas encimadas.
        k = self.r_contenido.x
        base = ALTO_PEDIDO if self.r_pedido.x > 0.01 else ALTO_CHICA
        crecio = max(0.0, (self.r_alto.x - base) / max(1.0, self.alto_abierta() - base))
        chica = max(0.0, 1 - k * 2.5) * max(0.0, 1 - crecio * 3)
        adentro = min(max(0.0, (k - 0.5) / 0.5), max(0.0, min(1.0, (crecio - 0.55) / 0.4)))
        # Lo del permiso entra cuando la pastilla ya casi se alargó; lo de siempre se va antes.
        pedido = max(0.0, (self.r_pedido.x - 0.4) / 0.6)
        chica *= max(0.0, 1 - self.r_pedido.x * 2.5)
        if chica > 0.01:
            p.setOpacity(chica)
            self.pintar_chica(p, cuerpo, col)
        if pedido > 0.01 and self.mostrado:
            p.setOpacity(pedido)
            self.pintar_pedido(p, cuerpo, col)
            if self.mostrado[0] == "hecho":  # completado: un borde verde (permitido) o rojo (denegado)
                p.restore()
                p.save()
                self.pintar_borde(p, forma, VERDE if self.mostrado[1][1] == "allow" else ROJO, pedido)
                p.setClipPath(forma)
        if adentro > 0.01:
            p.setOpacity(adentro)
            self.pintar_abierta(p, cuerpo, col)
        p.restore()
        p.end()
        self.seguir_vidrio()

    def seguir_vidrio(self) -> None:
        """El desenfoque va debajo de lo que se acaba de dibujar. Mientras cambia de tamaño, nunca más grande que
        el cuadro anterior, este ni el que viene (se calcula siguiendo la misma velocidad): Windows puede mostrar
        la ventana del desenfoque un cuadro antes o después que la pastilla, y así nunca asoma por fuera (adentro,
        el borde sin desenfocar lo tapa el canto del vidrio)."""
        if not self.vidrio:
            return
        actual = self.rect_desenfoque()
        moviendose = self.r_ancho.moviendose or self.r_alto.moviendose
        previo = self.desenfoque_previo
        self.desenfoque_previo = actual
        if moviendose and not previo.isEmpty():
            siguiente = QRectF(QPointF(2 * actual.left() - previo.left(), 2 * actual.top() - previo.top()),
                               QPointF(2 * actual.right() - previo.right(), 2 * actual.bottom() - previo.bottom()))
            destino = actual.intersected(previo)
            if siguiente.isValid():
                destino = destino.intersected(siguiente)
            if destino.isEmpty():
                destino = actual
        else:
            destino = actual
        self.vidrio.seguir(self, destino)

    def vidrio_quieto(self, forma: QPainterPath, r: QRectF, col: dict) -> tuple[QPoint, QPixmap]:
        escala = self.devicePixelRatioF()
        clave = (r.x(), r.y(), r.width(), r.height(), col["claro"], bool(self.vidrio), escala, self.alfa_vidrio())
        if clave != self.clave_quieto:
            zona = r.adjusted(-MARGEN, -ARRIBA, MARGEN, MARGEN).toAlignedRect()
            foto = QPixmap(round(zona.width() * escala), round(zona.height() * escala))
            foto.setDevicePixelRatio(escala)
            foto.fill(Qt.GlobalColor.transparent)
            q = QPainter(foto)
            q.setRenderHint(QPainter.RenderHint.Antialiasing)
            q.translate(-zona.x(), -zona.y())
            self.pintar_vidrio(q, forma, r, col, bool(self.vidrio))
            q.end()
            self.clave_quieto, self.foto_quieto = clave, (zona.topLeft(), foto)
        return self.foto_quieto

    def pintar_vidrio(self, p: QPainter, forma: QPainterPath, r: QRectF, col: dict, desenfocado: bool) -> None:
        """El vidrio en sí (lo que no cambia de un cuadro a otro): sombra, tinte, canto, brillo y borde."""
        # Sombra suave, sin cajas: el mismo contorno, cada vez más ancho y más transparente.
        sombra = forma.translated(0, 3)
        for i in range(6, 0, -1):
            p.strokePath(sombra, QPen(QColor(0, 0, 0, 7 if not col["claro"] else 5), i * 2.4))
        p.fillPath(forma, col["fondo"])
        p.save()
        p.setClipPath(forma)
        if desenfocado:
            # El canto: ahí atrás no hay desenfoque, así que el vidrio se cierra hacia el borde (en tres
            # pasadas, para que no se note el escalón), como el espesor de un vidrio de verdad.
            c = self.canto()
            for ancho, alfa in ((c * 2.6, 0.42), (c * 1.5, 0.42), (c * 0.7, 0.36)):
                p.strokePath(forma, QPen(con_alfa(col["fondo"], alfa), ancho))
        # El brillo de arriba, como la luz sobre una gota.
        brillo = QLinearGradient(0, r.top(), 0, r.bottom())
        brillo.setColorAt(0.0, QColor(255, 255, 255, 46 if not col["claro"] else 90))
        brillo.setColorAt(0.42, QColor(255, 255, 255, 6))
        brillo.setColorAt(1.0, QColor(0, 0, 0, 26 if not col["claro"] else 6))
        p.fillRect(r.adjusted(-10, -10, 10, 10), brillo)
        p.restore()
        # Borde: claro arriba y apagado abajo, como el canto de un vidrio.
        borde = QLinearGradient(0, r.top(), 0, r.bottom())
        borde.setColorAt(0.0, QColor(255, 255, 255, 120 if not col["claro"] else 230))
        borde.setColorAt(0.55, QColor(255, 255, 255, 26 if not col["claro"] else 120))
        borde.setColorAt(1.0, QColor(255, 255, 255, 60 if not col["claro"] else 200))
        p.strokePath(forma, QPen(borde, 1.1))
        if col["claro"]:
            p.strokePath(forma, QPen(QColor(0, 0, 0, 28), 0.6))

    def pintar_luces(self, p: QPainter, forma: QPainterPath, r: QRectF, col: dict, trabajando: bool) -> None:
        """Lo que se mueve sobre el vidrio: el latido, el reflejo del mouse y la línea de luz de arriba."""
        p.save()
        p.setClipPath(forma)
        # Si hay algo trabajando, el color de la mascota late desde abajo.
        if trabajando and self.isla["latido"]:
            latido = 0.5 + 0.5 * math.sin(self.fase * 2.4)
            luz = QRadialGradient(QPointF(r.center().x(), r.bottom() + 6), max(r.width() * 0.55, 60))
            # Pidiendo permiso, el amarillo de "permiso", más suave: que se note sin molestar.
            color, fuerza = (AMARILLO, 0.6) if self.pedido else (col["acento"], 1.0)
            luz.setColorAt(0.0, con_alfa(color, (0.20 + 0.16 * latido) * fuerza))
            luz.setColorAt(1.0, con_alfa(color, 0.0))
            p.fillRect(r.adjusted(-10, -10, 10, 10), luz)
        # El reflejo que sigue al mouse.
        b = self.r_brillo.x
        if b > 0.01:
            cx = min(r.right() - 12, max(r.left() + 12, self.cursor.x()))
            reflejo = QRadialGradient(QPointF(cx, r.top() + min(r.height(), 60) * 0.35), 110)
            reflejo.setColorAt(0.0, QColor(255, 255, 255, round(48 * b)))
            reflejo.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.fillRect(r.adjusted(-10, -10, 10, 10), reflejo)
        # La línea de luz del borde de arriba, más fuerte donde está el mouse (o al centro).
        centro = self.cursor.x() if b > 0.01 else r.center().x()
        linea = QLinearGradient(r.left(), 0, r.right(), 0)
        k = min(0.98, max(0.02, (centro - r.left()) / max(1.0, r.width())))
        linea.setColorAt(0.0, QColor(255, 255, 255, 0))
        linea.setColorAt(max(0.0, k - 0.35), QColor(255, 255, 255, 30))
        linea.setColorAt(k, QColor(255, 255, 255, 140 + round(60 * b)))
        linea.setColorAt(min(1.0, k + 0.35), QColor(255, 255, 255, 30))
        linea.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setPen(QPen(linea, 1.2))
        p.drawLine(QPointF(r.left() + 10, r.top() + 0.8), QPointF(r.right() - 10, r.top() + 0.8))
        p.restore()

    def punto_estado(self, p: QPainter, centro: QPointF, s: dict | None, col: dict, radio: float = 4.0) -> None:
        if s is None:
            color, latido = QColor(150, 150, 160), 0.0
        elif s["trabajando"]:
            color, latido = col["acento"], 0.5 + 0.5 * math.sin(self.fase * 4.0)
        else:
            color, latido = QColor(96, 200, 140), 0.0
        if latido:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(con_alfa(color, 0.28 * (1 - latido)))
            p.drawEllipse(centro, radio + 4 * latido, radio + 4 * latido)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawEllipse(centro, radio, radio)

    def pintar_luna(self, p: QPainter, centro: QPointF, color: QColor, tam: float = 6.0) -> None:
        luna = QPainterPath()
        luna.addEllipse(centro, tam, tam)
        hueco = QPainterPath()
        hueco.addEllipse(centro + QPointF(tam * 0.55, -tam * 0.45), tam * 0.85, tam * 0.85)
        p.fillPath(luna.subtracted(hueco), color)

    def pintar_chica(self, p: QPainter, r: QRectF, col: dict) -> None:
        principal, resto = self.texto_chica()
        cy = r.top() + ALTO_CHICA / 2
        ancho_ojos = self.ancho_ojos()
        if self.isla["ojos"]:
            ojos.pintar(p, QPointF(r.left() + 12 + ancho_ojos / 2, cy), 2, self.config["aspecto"], self.mirada)
        else:
            trabajando = next((s for s in self.sesiones if s["trabajando"]), None)
            self.punto_estado(p, QPointF(r.left() + 12 + ancho_ojos / 2, cy),
                              trabajando or (self.sesiones[0] if self.sesiones else None), col)
        x = r.left() + 12 + ancho_ojos + 8
        p.setFont(m.fuente(9, QFont.Weight.DemiBold))
        p.setPen(col["texto"])
        fm = QFontMetricsF(p.font())
        p.drawText(QRectF(x, r.top(), fm.horizontalAdvance(principal) + 2, ALTO_CHICA),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, principal)
        x += fm.horizontalAdvance(principal) + 10
        if resto:
            p.setFont(m.fuente(9))
            p.setPen(col["tenue"])
            lugar = max(0.0, r.right() - x - 14 - (18 if m.silenciada(self.config) else 0))
            p.drawText(QRectF(x, r.top(), lugar + 2, ALTO_CHICA), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       QFontMetricsF(p.font()).elidedText(resto, Qt.TextElideMode.ElideRight, lugar + 2))
        if m.silenciada(self.config):
            self.pintar_luna(p, QPointF(r.right() - 17, cy), col["tenue"], 5.0)

    @staticmethod
    def pintar_borde(p: QPainter, forma: QPainterPath, color: QColor, fuerza: float) -> None:
        """El borde de color de "completado": un tinte apenas adentro, el filo y un halo suave afuera."""
        p.setOpacity(1.0)
        p.save()
        p.setClipPath(forma)
        p.fillPath(forma, con_alfa(color, 0.10 * fuerza))
        p.restore()
        for ancho, alfa in ((7.0, 0.10), (4.0, 0.18)):
            p.strokePath(forma, QPen(con_alfa(color, alfa * fuerza), ancho))
        p.strokePath(forma, QPen(con_alfa(color, 0.95 * fuerza), 1.6))

    def pintar_pedido(self, p: QPainter, r: QRectF, col: dict) -> None:
        """Pidiendo permiso: los ojos, el permiso en una o dos palabras y, a la derecha, Denegar y Permitir.
        Al lado, una flechita que despliega el pedido completo. Abajo de todo, una línea finita que se acorta con
        el tiempo que queda para contestar."""
        cy = r.top() + ALTO_PEDIDO / 2
        fila = QRectF(r.left(), r.top(), r.width(), ALTO_PEDIDO)
        ancho_ojos = self.ancho_ojos()
        if self.isla["ojos"]:
            ojos.pintar(p, QPointF(r.left() + 12 + ancho_ojos / 2, cy), 2, self.config["aspecto"], self.mirada)
        else:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(AMARILLO)
            p.drawEllipse(QPointF(r.left() + 12 + ancho_ojos / 2, cy), 4, 4)
        x = r.left() + 12 + ancho_ojos + 9
        fuerte = m.fuente(9, QFont.Weight.DemiBold)
        tipo, valor = self.mostrado  # (lo último, así se va suave aunque ya no esté)
        if tipo == "hecho":
            p.setFont(fuerte)
            p.setPen(col["texto"])
            p.drawText(QRectF(x, r.top(), r.right() - x, ALTO_PEDIDO), Qt.AlignmentFlag.AlignVCenter, valor[0])
            self.zonas_pedido = {}
            return
        pedido = valor
        # Los botones, de derecha a izquierda: Permitir (el que resalta) y Denegar (apenas un vidrio).
        derecha = r.right() - 5
        zonas: dict[str, QRectF] = {"flecha": QRectF(derecha - BOTON, cy - BOTON / 2, BOTON, BOTON)}
        derecha -= BOTON + 5
        for decision in ("allow", "deny"):
            ancho = self.ancho_boton(decision)
            zonas[decision] = QRectF(derecha - ancho, cy - BOTON / 2, ancho, BOTON)
            derecha -= ancho + 5
        abierto = self.detalle_abierto and self.pedido is pedido
        zona = zonas["flecha"]
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(con_alfa(col["texto"], 0.20 if zona.contains(self.cursor) or abierto else 0.11))
        p.drawEllipse(zona)
        self.pintar_flecha(p, zona.center(), col["texto"], arriba=abierto)
        p.setFont(m.fuente(8, QFont.Weight.DemiBold))
        for decision in ("allow", "deny"):
            zona = zonas[decision]
            encima = zona.contains(self.cursor)
            p.setPen(Qt.PenStyle.NoPen)
            if decision == "allow":
                p.setBrush(con_alfa(col["texto"], 1.0 if encima else 0.88))
                tinta = QColor(20, 21, 28) if not col["claro"] else QColor(250, 250, 252)
            else:
                p.setBrush(con_alfa(col["texto"], 0.20 if encima else 0.11))
                tinta = col["texto"]
            p.drawRoundedRect(zona, BOTON / 2, BOTON / 2)
            p.setPen(tinta)
            p.drawText(zona, Qt.AlignmentFlag.AlignCenter, t("Permitir") if decision == "allow" else t("Denegar"))
        # La etiqueta (y cuántos más esperan); un clic ahí trae la ventana de esa sesión.
        mas = f"+{self.en_cola}" if self.en_cola else ""
        ancho_mas = QFontMetricsF(m.fuente(8)).horizontalAdvance(mas) + 6 if mas else 0
        lugar = max(0.0, zonas["deny"].left() - 14 - ancho_mas - x)
        p.setFont(fuerte)
        texto = QFontMetricsF(fuerte).elidedText(pedido["etiqueta"], Qt.TextElideMode.ElideRight, lugar)
        ancho_texto = QFontMetricsF(fuerte).horizontalAdvance(texto)
        p.setPen(col["texto"])
        p.drawText(QRectF(x, r.top(), lugar + 2, ALTO_PEDIDO), Qt.AlignmentFlag.AlignVCenter, texto)
        if mas:
            p.setFont(m.fuente(8))
            p.setPen(col["tenue"])
            p.drawText(QRectF(x + ancho_texto + 6, r.top(), ancho_mas, ALTO_PEDIDO), Qt.AlignmentFlag.AlignVCenter, mas)
        # (la etiqueta: con un clic, la ventana de esa sesión)
        zonas["etiqueta"] = QRectF(r.left(), r.top(), x + ancho_texto + 4 - r.left(), ALTO_PEDIDO)
        self.zonas_pedido = zonas if self.pedido is pedido else {}
        if abierto and r.height() > ALTO_PEDIDO + 12:
            self.pintar_detalle(p, QRectF(r.left() + 18, fila.bottom(), r.width() - 36, r.bottom() - fila.bottom()), col)
        # El tiempo que queda para contestar (después decide la terminal).
        creado, vence = pedido.get("creado") or 0, pedido.get("vence") or 0
        queda = max(0.0, min(1.0, (vence - time.time()) / max(1.0, vence - creado)))
        if queda > 0:
            largo = (r.width() - 2 * RADIO) * queda
            pluma = QPen(con_alfa(AMARILLO, 0.75), 1.6)
            pluma.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pluma)
            p.drawLine(QPointF(r.center().x() - largo / 2, r.bottom() - 1.6),
                       QPointF(r.center().x() + largo / 2, r.bottom() - 1.6))

    def pintar_detalle(self, p: QPainter, r: QRectF, col: dict) -> None:
        """El pedido completo, desplegado debajo de los botones (se va descubriendo mientras crece): una
        pastillita con la herramienta, el proyecto y el chat, y el comando en un recuadro como de terminal."""
        herramienta, contexto, _ = self.texto_detalle()
        ancho = max(40.0, self.r_ancho.objetivo - 36)  # el ancho final: que no se re-acomode en cada rebote
        y = r.top() + 10
        x = r.left()
        if herramienta:
            p.setFont(m.fuente(8, QFont.Weight.DemiBold))
            insignia = QRectF(x, y, QFontMetricsF(p.font()).horizontalAdvance(herramienta) + 20, 22)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(con_alfa(col["texto"], 0.12))
            p.drawRoundedRect(insignia, 11, 11)
            p.setPen(col["texto"])
            p.drawText(insignia, Qt.AlignmentFlag.AlignCenter, herramienta)
            x = insignia.right() + 10
        if contexto:
            p.setFont(m.fuente(9))
            p.setPen(col["tenue"])
            lugar = r.left() + ancho - x
            p.drawText(QRectF(x, y, lugar, 22), Qt.AlignmentFlag.AlignVCenter,
                       QFontMetricsF(p.font()).elidedText(contexto, Qt.TextElideMode.ElideRight, lugar))
        armados, alto = self.maquetar_detalle(ancho)
        recuadro = QRectF(r.left(), y + 22 + 10, ancho, min(MAX_DETALLE, alto) + 2 * RELLENO)
        p.setPen(QPen(con_alfa(col["texto"], 0.07), 1))
        p.setBrush(QColor(0, 0, 0, 16) if col["claro"] else QColor(0, 0, 0, 72))
        p.drawRoundedRect(recuadro, 10, 10)
        p.save()
        p.setClipRect(recuadro.adjusted(1, RELLENO - 2, -1, -RELLENO + 2))
        p.setPen(col["texto"])
        origen = QPointF(recuadro.left() + RELLENO, recuadro.top() + RELLENO)
        for capa in armados:
            capa.draw(p, origen)
        p.restore()

    @staticmethod
    def pintar_flecha(p: QPainter, centro: QPointF, color: QColor, arriba: bool) -> None:
        pluma = QPen(color, 1.6)
        pluma.setCapStyle(Qt.PenCapStyle.RoundCap)
        pluma.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pluma)
        p.setBrush(Qt.BrushStyle.NoBrush)
        d = -1.0 if arriba else 1.0
        flecha = QPainterPath(centro + QPointF(-4.0, -2.0 * d))
        flecha.lineTo(centro + QPointF(0.0, 2.2 * d))
        flecha.lineTo(centro + QPointF(4.0, -2.0 * d))
        p.drawPath(flecha)

    def pintar_abierta(self, p: QPainter, r: QRectF, col: dict) -> None:
        izq, der = r.left() + 18, r.right() - 18
        # Cabecera: los ojos, el título y el resumen; a la derecha, el botón de ajustes.
        izq_texto = izq
        if self.isla["ojos"]:
            ancho_ojos = self.ancho_ojos() * 1.5
            ojos.pintar(p, QPointF(izq + ancho_ojos / 2, r.top() + 28), 3, self.config["aspecto"], self.mirada)
            izq_texto = izq + ancho_ojos + 12
        p.setFont(m.fuente(10, QFont.Weight.DemiBold))
        p.setPen(col["texto"])
        p.drawText(QRectF(izq_texto, r.top() + 10, 260, 20), Qt.AlignmentFlag.AlignVCenter, t("Sesiones de Claude Code"))
        self.boton_ajustes = QRectF(der - 30, r.top() + 13, 30, 30)
        encima = self.boton_ajustes.contains(self.cursor)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(con_alfa(col["texto"], 0.20 if encima else 0.10))
        p.drawEllipse(self.boton_ajustes)
        self.pintar_engranaje(p, self.boton_ajustes.center(), col["texto"] if encima else col["tenue"])
        der_cabecera = self.boton_ajustes.left() - 10
        total = sum(s["tokens"] for s in self.sesiones)
        agentes = sum(s["agentes"] for s in self.sesiones)
        partes = [t("1 sesión") if len(self.sesiones) == 1 else t("{n} sesiones", n=len(self.sesiones)),
                  t("{tokens} tokens", tokens=seguimiento.formato_tokens(total))]
        if agentes:
            partes.append(t("1 agente") if agentes == 1 else t("{n} agentes", n=agentes))
        p.setFont(m.fuente(8))
        p.setPen(col["tenue"])
        p.drawText(QRectF(izq_texto, r.top() + 30, 260, 16), Qt.AlignmentFlag.AlignVCenter, " · ".join(partes))

        # No molestar se prende desde los ajustes o el ícono; acá solo se avisa que está puesto.
        if m.silenciada(self.config):
            self.pintar_luna(p, QPointF(der_cabecera - 6, r.top() + 28), col["tenue"], 5.5)

        y = r.top() + CABECERA
        self.filas = []
        self.cruces = []
        ahora = time.monotonic()
        # La × entra y sale con un fundido (~150 ms), no de golpe: cuánto avanza depende del tiempo del cuadro.
        paso = 1.0 - math.exp(-min(0.1, ahora - self.cruz_reloj) * 16)
        self.cruz_reloj = ahora
        suave, self.cruz_suave = self.cruz_suave, {}
        self.zona_uso = QRectF()
        if self.isla["uso"]:
            self.pintar_uso(p, QRectF(izq, r.top() + self.alto_abierta() - PIE - USO + 4, der - izq, USO), col)
        if not self.sesiones:
            p.setFont(m.fuente(9))
            p.setPen(col["tenue"])
            p.drawText(QRectF(izq, y, der - izq, FILA - 8), Qt.AlignmentFlag.AlignCenter,
                       t("Quitaste las sesiones en espera: vuelven solas si se mueven") if self.crudas
                       else t("No hay sesiones de Claude Code en la última media hora"))
            return
        for i, s in enumerate(self.sesiones[:self.max_filas()]):
            fila = QRectF(izq, y, der - izq, FILA)
            self.filas.append((fila, s))
            if s.get("ventana") and self.isla["saltar"] and fila.contains(self.cursor):  # se puede saltar
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(con_alfa(col["texto"], 0.07))
                p.drawRoundedRect(fila.adjusted(-8, 3, 8, -3), 12, 12)
            cruz = self.pintar_cruz(p, fila, s, col, suave.get(s["id"], (0.0, 0.0)), paso)
            self.pintar_fila(p, fila, s, col, primera=i == 0, cruz=cruz)
            y += FILA
        if len(self.sesiones) > self.max_filas():
            p.setFont(m.fuente(8))
            p.setPen(col["tenue"])
            p.drawText(QRectF(izq, y - 4, der - izq, 16), Qt.AlignmentFlag.AlignCenter,
                       t("y {n} más", n=len(self.sesiones) - self.max_filas()))

    def pintar_cruz(self, p: QPainter, fila: QRectF, s: dict, col: dict, antes: tuple[float, float],
                    paso: float) -> float:
        """La × para quitar una sesión en espera, a la derecha de su fila, solo con el mouse encima.

        Aparece y se va con un fundido y crece un poco al entrar; devuelve cuánto se corre (0 a 1) el texto
        de la derecha para dejarle lugar."""
        quiere = (not s["trabajando"] and not s["agentes"] and fila.contains(self.cursor)
                  and (self.cursor - self.punto_quitar).manhattanLength() >= 8)  # no justo donde quitaste otra
        if quiere:
            self.punto_quitar = QPointF(-999, -999)  # ya se alejó: la × vuelve hasta la próxima que quites
        caja = QRectF(fila.right() - 24, fila.top() + (FILA - 24) / 2, 24, 24)
        encima_ya = quiere and caja.contains(self.cursor)
        visible = antes[0] + ((1.0 if quiere else 0.0) - antes[0]) * paso
        encima = antes[1] + ((1.0 if encima_ya else 0.0) - antes[1]) * paso
        if visible < 0.01 and not quiere:
            return 0.0  # ya se fue del todo: se olvida
        self.cruz_suave[s["id"]] = (visible, encima)
        if quiere:
            self.cruces.append((caja, s))
        lleno = visible * visible * (3 - 2 * visible)  # que arranque y frene suave
        tam = 0.7 + 0.3 * lleno
        c = caja.center()
        p.save()
        p.setOpacity(p.opacity() * lleno)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(con_alfa(col["texto"], 0.10 + 0.10 * encima))
        p.drawEllipse(c, 12 * tam, 12 * tam)
        pluma = QPen(mezcla(col["tenue"], col["texto"], encima), 1.5)
        pluma.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pluma)
        d = 3.6 * tam
        p.drawLine(c + QPointF(-d, -d), c + QPointF(d, d))
        p.drawLine(c + QPointF(-d, d), c + QPointF(d, -d))
        p.restore()
        return 1 - (1 - visible) ** 3  # el texto se corre antes de que la × termine de aparecer: no se pisan

    @staticmethod
    def pintar_engranaje(p: QPainter, centro: QPointF, color: QColor) -> None:
        pluma = QPen(color, 1.5)
        pluma.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pluma)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(8):
            a = i * math.pi / 4
            p.drawLine(centro + QPointF(4.9 * math.cos(a), 4.9 * math.sin(a)),
                       centro + QPointF(6.9 * math.cos(a), 6.9 * math.sin(a)))
        p.drawEllipse(centro, 4.7, 4.7)
        p.drawEllipse(centro, 1.7, 1.7)

    def pintar_uso(self, p: QPainter, r: QRectF, col: dict) -> None:
        """Al pie: cuánto se gastó en las últimas 5 horas (con su curvita) y en 7 días. Un clic abre Uso."""
        self.zona_uso = r.adjusted(-8, 0, 8, 2)
        p.setPen(QPen(col["linea"], 1))
        p.drawLine(QPointF(r.left(), r.top()), QPointF(r.right(), r.top()))
        if self.zona_uso.contains(self.cursor):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(con_alfa(col["texto"], 0.07))
            p.drawRoundedRect(self.zona_uso.adjusted(0, 4, 0, -2), 12, 12)
        uso = self.lector.uso
        cy = r.top() + 6 + (r.height() - 6) / 2
        x = r.left()
        for etiqueta, clave in ((t("5 h"), "5h"), (t("7 días"), "7d")):
            p.setFont(m.fuente(8))
            p.setPen(col["tenue"])
            ancho = QFontMetricsF(p.font()).horizontalAdvance(etiqueta)
            p.drawText(QRectF(x, cy - 10, ancho + 2, 20), Qt.AlignmentFlag.AlignVCenter, etiqueta)
            x += ancho + 7
            valor = seguimiento.formato_tokens(uso[clave]) if uso else "…"
            p.setFont(m.fuente(9, QFont.Weight.DemiBold))
            p.setPen(col["texto"])
            ancho = QFontMetricsF(p.font()).horizontalAdvance(valor)
            p.drawText(QRectF(x, cy - 10, ancho + 2, 20), Qt.AlignmentFlag.AlignVCenter, valor)
            x += ancho + 22
        serie = uso["serie"] if uso else []
        tope = max(serie) if serie else 0
        if tope:  # la curvita de las 5 horas, a la derecha
            zona = QRectF(r.right() - 150, cy - 9, 150, 18)
            paso = zona.width() / len(serie)
            p.setPen(Qt.PenStyle.NoPen)
            for i, valor in enumerate(serie):
                alto = max(1.5, zona.height() * valor / tope)
                p.setBrush(con_alfa(col["acento"], 0.95 if i == len(serie) - 1 else 0.55) if valor
                           else con_alfa(col["texto"], 0.12))
                p.drawRoundedRect(QRectF(zona.left() + i * paso, zona.bottom() - alto, max(1.0, paso - 1), alto), 0.8, 0.8)

    def pintar_fila(self, p: QPainter, f: QRectF, s: dict, col: dict, primera: bool, cruz: float = 0.0) -> None:
        p.setPen(QPen(col["linea"], 1))
        p.drawLine(QPointF(f.left(), f.top()), QPointF(f.right(), f.top()))
        self.punto_estado(p, QPointF(f.left() + 4, f.top() + 19), s, col, 3.6)
        ahora = time.time()
        # Derecha: cuánto falta (o desde cuándo espera).
        if s["trabajando"]:
            if s["id"] in self.eta:
                grande, chico = "~" + corto(self.eta[s["id"]]), t("faltan")
            else:
                grande = m.formato_duracion(self.transcurrido(s))
                # Sin historial todavía no es "más de lo normal": es que no hay con qué comparar.
                chico = t("más de lo normal") if s.get("historial") else t("aprendiendo tus tiempos")
        else:
            grande, chico = t("en espera"), t("hace {tiempo}", tiempo=corto(ahora - s["ultima"]))
        if cruz:  # la × ocupa la punta derecha: lo de la derecha se corre a su lado, a la par de su fundido
            f = QRectF(f.left(), f.top(), f.width() - 32 * cruz, f.height())
        p.setFont(m.fuente(10, QFont.Weight.DemiBold))
        fm = QFontMetricsF(p.font())
        ancho_der = max(fm.horizontalAdvance(grande), QFontMetricsF(m.fuente(7)).horizontalAdvance(chico)) + 4
        p.setPen(col["texto"] if s["trabajando"] else col["tenue"])
        p.drawText(QRectF(f.right() - ancho_der, f.top() + 9, ancho_der, 20),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, grande)
        p.setFont(m.fuente(7))
        p.setPen(col["tenue"])
        p.drawText(QRectF(f.right() - ancho_der - 40, f.top() + 28, ancho_der + 40, 14),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, chico)
        # Título del chat y los datos.
        titulo = s["titulo"] or s["proyecto"]
        ancho_txt = f.width() - 14 - ancho_der - 12
        p.setFont(m.fuente(9, QFont.Weight.DemiBold))
        p.setPen(col["texto"])
        p.drawText(QRectF(f.left() + 14, f.top() + 9, ancho_txt, 20), Qt.AlignmentFlag.AlignVCenter,
                   QFontMetricsF(p.font()).elidedText(titulo, Qt.TextElideMode.ElideRight, ancho_txt))
        datos = []
        if s["titulo"] and s["proyecto"]:
            datos.append(s["proyecto"])
        datos.append(t("sesión {tiempo}", tiempo=m.formato_duracion(ahora - s["inicio"])))
        datos.append(t("{tokens} tokens", tokens=seguimiento.formato_tokens(s["tokens"])))
        if s.get("plan") and s["plan"][1]:  # por dónde va la lista de tareas de Claude
            datos.append(f"{s['plan'][0]}/{s['plan'][1]}")
        if s["agentes"]:
            datos.append(t("1 agente") if s["agentes"] == 1 else t("{n} agentes", n=s["agentes"]))
        if s["herramienta"]:
            datos.append(s["herramienta"])
        p.setFont(m.fuente(8))
        p.setPen(col["tenue"])
        p.drawText(QRectF(f.left() + 14, f.top() + 28, ancho_txt, 14), Qt.AlignmentFlag.AlignVCenter,
                   QFontMetricsF(p.font()).elidedText(" · ".join(datos), Qt.TextElideMode.ElideRight, ancho_txt))
        # Barra de progreso: lo que lleva sobre lo que se estima en total, con un brillo que corre.
        if not s["trabajando"]:
            return
        barra = QRectF(f.left() + 14, f.top() + 46, f.width() - 14, 3)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(col["linea"])
        p.drawRoundedRect(barra, 1.5, 1.5)
        lleva = self.transcurrido(s)
        falta = self.eta.get(s["id"])
        avance = lleva / (lleva + falta) if falta else 1.0
        lleno = QRectF(barra.left(), barra.top(), max(3.0, barra.width() * min(1.0, avance)), barra.height())
        p.setBrush(con_alfa(col["acento"], 0.95 if falta else 0.45))
        p.drawRoundedRect(lleno, 1.5, 1.5)
        corre = (self.fase * 0.6) % 1.0
        brillo = QLinearGradient(lleno.left() + lleno.width() * (corre - 0.25), 0,
                                 lleno.left() + lleno.width() * (corre + 0.25), 0)
        brillo.setColorAt(0.0, QColor(255, 255, 255, 0))
        brillo.setColorAt(0.5, QColor(255, 255, 255, 150))
        brillo.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(brillo)
        p.drawRoundedRect(lleno, 1.5, 1.5)


def main() -> int:
    """Para probarla sola: python barra.py"""
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv[:1])
    import idiomas
    idiomas.usar(m.cargar_config()["idioma"])
    barra = Barra()

    def seguir_config() -> None:
        """Sola (sin el ícono, que es quien la prende y apaga): obedece "Mostrar la Dynamic Island"."""
        activa = m.cargar_config()["barra"]["activa"]
        if activa and not barra.timer_tic.isActive():
            barra.mostrar()
        elif not activa and barra.timer_tic.isActive():
            barra.cerrar()

    reloj = QTimer(interval=700, timeout=seguir_config)
    reloj.start()
    seguir_config()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
