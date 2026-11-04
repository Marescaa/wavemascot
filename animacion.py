"""El movimiento de la ventana de ajustes: resortes y transiciones, a la manera de Apple.

Lo que se copia de Apple (UIKit y SwiftUI) no es el dibujo sino la física:

- Todo se mueve con resortes, no con duraciones fijas. Un resorte se define por cuánto tarda en llegar
  (respuesta, en segundos) y cuánto rebota (amortiguación: 1 = llega sin pasarse, menos = rebota un poco).
- Las animaciones se pueden interrumpir: si cambia el destino a mitad de camino, el resorte sigue desde
  donde está y con la velocidad que traía, así nada salta.
- Se mueve poco y rápido: la mayoría llega en un tercio de segundo; los rebotes quedan para lo que se toca.
- Si Windows tiene apagado "Mostrar animaciones" (o macOS "Reducir movimiento"), todo llega al instante.
"""

from __future__ import annotations

import math
import os
import sys

from PyQt6 import sip
from PyQt6.QtCore import QElapsedTimer, QObject, QPointF, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import QWidget

_reducir: bool | None = None


def pedido_por_variable() -> bool:
    """WAVEMASCOT_SIN_ANIMACIONES=1 apaga las animaciones; vacía, 0, false o no, no."""
    return os.environ.get("WAVEMASCOT_SIN_ANIMACIONES", "").strip().lower() not in ("", "0", "false", "no")


def reducir_movimiento() -> bool:
    """True si el sistema pide no animar (o WAVEMASCOT_SIN_ANIMACIONES=1, para las capturas)."""
    global _reducir
    if _reducir is None:
        _reducir = pedido_por_variable()
        try:
            if not _reducir and os.name == "nt":
                import ctypes
                valor = ctypes.c_int(1)
                # SPI_GETCLIENTAREAANIMATION: "Mostrar animaciones en Windows"
                if ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(valor), 0):
                    _reducir = not valor.value
            elif not _reducir and sys.platform == "darwin":
                import subprocess
                salida = subprocess.run(["defaults", "read", "com.apple.universalaccess", "reduceMotion"],
                                        capture_output=True, text=True, timeout=2).stdout.strip()
                _reducir = salida == "1"
        except Exception:
            pass
    return _reducir


def mezcla(a, b, k: float) -> QColor:
    """El color que queda entre a y b (k = 0 es a, 1 es b)."""
    a, b = QColor(a), QColor(b)
    k = min(1.0, max(0.0, k))
    return QColor.fromRgbF(a.redF() + (b.redF() - a.redF()) * k, a.greenF() + (b.greenF() - a.greenF()) * k,
                           a.blueF() + (b.blueF() - a.blueF()) * k, a.alphaF() + (b.alphaF() - a.alphaF()) * k)


class _Reloj(QObject):
    """Un solo reloj para todos los resortes (como el CADisplayLink de Apple): avanza los que se están
    moviendo y se apaga solo cuando todos llegaron."""

    def __init__(self):
        super().__init__()
        self.activos: set[Resorte] = set()
        self.timer = QTimer(self, interval=8, timeout=self.tic)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.reloj = QElapsedTimer()

    def agregar(self, resorte: "Resorte") -> None:
        if not self.activos:
            self.reloj.start()
            self.timer.start()
        self.activos.add(resorte)

    def sacar(self, resorte: "Resorte") -> None:
        self.activos.discard(resorte)
        if not self.activos:
            self.timer.stop()

    def tic(self) -> None:
        dt = min(0.05, self.reloj.restart() / 1000)  # si la compu se trabó, no se teletransporta
        for resorte in list(self.activos):
            if resorte not in self.activos:  # otro lo fijó en este mismo cuadro: ya llegó
                continue
            if sip.isdeleted(resorte):
                self.activos.discard(resorte)
                continue
            try:
                resorte.avanzar(dt)  # al llegar se saca solo (antes de avisar, por si vuelve a arrancar)
            except RuntimeError as e:
                self.sacar(resorte)
                if "has been deleted" not in str(e):  # que el widget ya no exista es normal; lo demás, no
                    _registrar(f"[animacion] un resorte se detuvo por un error: {e!r}")
            except Exception as e:  # un error al dibujar no se repite cada 8 ms: se para y queda en el log
                self.sacar(resorte)
                _registrar(f"[animacion] un resorte se detuvo por un error: {e!r}")
        if not self.activos:
            self.timer.stop()


def _registrar(texto: str) -> None:
    try:
        import mascota
        mascota.log(texto)
    except Exception:
        print(texto, file=sys.stderr)


_RELOJ: _Reloj | None = None


def _reloj() -> _Reloj:
    global _RELOJ
    if _RELOJ is None:
        _RELOJ = _Reloj()
    return _RELOJ


class Resorte(QObject):
    """Un valor que va hacia su destino como un resorte (masa 1, la fórmula de SwiftUI).

    respuesta: segundos que tarda, más o menos, en llegar. amortiguacion: 1 llega sin pasarse; 0,7 rebota
    apenas (para lo que se toca); menos de 0,5 ya es un juguete. al_paso(valor) se llama en cada cuadro."""

    def __init__(self, padre: QObject, valor: float = 0.0, respuesta: float = 0.35, amortiguacion: float = 1.0,
                 al_paso=None, al_llegar=None):
        super().__init__(padre)
        self.x = self.objetivo = float(valor)
        self.v = 0.0
        self.al_paso, self.al_llegar = al_paso, al_llegar
        self.escala = 1.0
        self.configurar(respuesta, amortiguacion)

    def configurar(self, respuesta: float, amortiguacion: float) -> None:
        self.k = (2 * math.pi / respuesta) ** 2
        self.c = 4 * math.pi * amortiguacion / respuesta

    @property
    def moviendose(self) -> bool:
        return self in _reloj().activos

    def ir_a(self, objetivo: float, desde: float | None = None) -> None:
        if desde is not None:
            self.x, self.v = float(desde), 0.0
        self.objetivo = float(objetivo)
        if reducir_movimiento():
            self.fijar(objetivo)
            return
        self.escala = max(abs(self.objetivo - self.x), 1e-3)
        if abs(self.objetivo - self.x) < 1e-6 and abs(self.v) < 1e-6:
            self.fijar(objetivo)
            return
        _reloj().agregar(self)

    def fijar(self, valor: float) -> None:
        """Llega ya, sin animar."""
        self.x = self.objetivo = float(valor)
        self.v = 0.0
        _reloj().sacar(self)
        self._avisar(llego=True)

    def avanzar(self, dt: float) -> bool:
        """Avanza dt segundos (en pasitos chicos, así no se descontrola). True si ya llegó."""
        pasos = max(1, math.ceil(dt * 480))
        h = dt / pasos
        for _ in range(pasos):
            a = -self.k * (self.x - self.objetivo) - self.c * self.v
            self.v += a * h
            self.x += self.v * h
        llego = abs(self.x - self.objetivo) < 0.0015 * self.escala + 1e-4 and abs(self.v) < 0.02 * self.escala + 1e-3
        if llego:
            self.x, self.v = self.objetivo, 0.0
            _reloj().sacar(self)
        self._avisar(llego)
        return llego

    def _avisar(self, llego: bool) -> None:
        if self.al_paso:
            self.al_paso(self.x)
        if llego and self.al_llegar:
            self.al_llegar()


class Velo(QWidget):
    """La foto de lo que había, encima de lo nuevo, desvaneciéndose: un fundido sin tocar los widgets."""

    def __init__(self, padre: QWidget, respuesta: float = 0.24):
        super().__init__(padre)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.foto: QPixmap | None = None
        self.fondo: QColor | None = None
        self.alfa = Resorte(self, 0.0, respuesta, 1.0, al_paso=lambda _: self.update(), al_llegar=self._fin)
        self.hide()

    def tapar(self, foto: QPixmap, fondo=None) -> None:
        self.foto, self.fondo = foto, (QColor(fondo) if fondo is not None else None)
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self.alfa.ir_a(0.0, desde=1.0)

    def _fin(self) -> None:
        if self.alfa.x <= 0:
            self.hide()
            self.foto = None

    def paintEvent(self, evento) -> None:
        if self.foto is None:
            return
        p = QPainter(self)
        p.setOpacity(max(0.0, min(1.0, self.alfa.x)))
        if self.fondo is not None:
            p.fillRect(self.rect(), self.fondo)
        p.drawPixmap(QPointF(0, 0), self.foto)
