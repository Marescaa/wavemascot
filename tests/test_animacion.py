"""Los resortes de animacion.py llegan a destino, se pueden interrumpir y respetan "sin animaciones".

    python -m unittest discover tests
"""

from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # sin PyQt6 (por ejemplo, en un servidor) no hay nada que probar
    QApplication = None


@unittest.skipIf(QApplication is None, "falta PyQt6")
class Resortes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import animacion
        cls.animacion = animacion
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.animacion._reducir = False
        self.pasos = []
        self.resorte = self.animacion.Resorte(self.app, 0.0, 0.2, 1.0, al_paso=self.pasos.append)

    def tearDown(self):
        self.resorte.fijar(self.resorte.x)  # que no siga en el reloj si el test falló a mitad de camino
        self.resorte.deleteLater()
        self.animacion._reducir = None

    def esperar(self, segundos: float = 2.0) -> None:
        fin = time.time() + segundos
        while self.resorte.moviendose and time.time() < fin:
            self.app.processEvents()
            time.sleep(0.002)

    def test_llega_a_destino_y_se_detiene(self):
        self.resorte.ir_a(10.0)
        self.assertTrue(self.resorte.moviendose)
        self.esperar()
        self.assertFalse(self.resorte.moviendose)
        self.assertEqual(self.resorte.x, 10.0)
        self.assertGreater(len(self.pasos), 3)  # pasó por valores intermedios

    def test_interrumpido_sigue_desde_donde_estaba(self):
        self.resorte.ir_a(10.0)
        fin = time.time() + 2
        while self.resorte.x < 2 and time.time() < fin:  # hasta que vaya en camino (en cualquier máquina)
            self.app.processEvents()
            time.sleep(0.001)
        a_mitad, velocidad = self.resorte.x, self.resorte.v
        self.assertTrue(0 < a_mitad < 10, a_mitad)
        self.assertGreater(velocidad, 0)
        self.resorte.ir_a(-5.0)
        self.assertEqual((self.resorte.x, self.resorte.v), (a_mitad, velocidad))  # ni salta ni frena de golpe
        self.esperar()
        self.assertEqual(self.resorte.x, -5.0)

    def test_variable_en_cero_no_apaga_las_animaciones(self):
        anterior = os.environ.get("WAVEMASCOT_SIN_ANIMACIONES")
        try:
            for valor, apaga in (("", False), ("0", False), (" 0 ", False), ("false", False), ("No", False),
                                 ("1", True)):
                os.environ["WAVEMASCOT_SIN_ANIMACIONES"] = valor
                self.assertEqual(self.animacion.pedido_por_variable(), apaga, repr(valor))
            self.animacion._reducir = None  # con "1", ni siquiera se pregunta al sistema
            self.assertTrue(self.animacion.reducir_movimiento())
        finally:
            if anterior is None:
                os.environ.pop("WAVEMASCOT_SIN_ANIMACIONES", None)
            else:
                os.environ["WAVEMASCOT_SIN_ANIMACIONES"] = anterior

    def test_sin_animaciones_llega_al_instante(self):
        self.animacion._reducir = True
        self.resorte.ir_a(3.0)
        self.assertFalse(self.resorte.moviendose)
        self.assertEqual(self.resorte.x, 3.0)
        self.assertEqual(self.pasos, [3.0])

    def test_puede_volver_a_arrancar_al_llegar(self):
        idas = []

        def otra_vez():
            if len(idas) < 1:
                idas.append(1)
                self.resorte.ir_a(0.0)
        self.resorte.al_llegar = otra_vez
        self.resorte.ir_a(1.0)
        self.esperar()
        self.esperar()
        self.assertEqual(self.resorte.x, 0.0)
        self.assertEqual(idas, [1])

    def test_un_error_al_dibujar_lo_para_y_queda_registrado(self):
        registrados = []
        original = self.animacion._registrar
        self.animacion._registrar = registrados.append
        try:
            def falla(_):
                raise ValueError("se rompió el dibujo")
            self.resorte.al_paso = falla
            self.resorte.ir_a(5.0)
            self.esperar(0.5)
            self.assertFalse(self.resorte.moviendose)  # no sigue intentando cada 8 ms
            self.assertEqual(len(registrados), 1)
            self.assertIn("se rompió el dibujo", registrados[0])
        finally:
            self.animacion._registrar = original
            self.resorte.al_paso = None  # que el tearDown no vuelva a romper el dibujo

    def test_fijado_por_otro_en_el_mismo_cuadro_no_avisa_dos_veces(self):
        llegadas = []
        otro = self.animacion.Resorte(self.app, 0.0, 0.2, 1.0, al_llegar=lambda: llegadas.append(1))
        try:
            # el primero, en su primer paso, fija al otro: ese cuadro ya no tiene que avanzarlo
            self.resorte.al_paso = lambda _: otro.moviendose and otro.fijar(otro.x)
            otro.ir_a(3.0)
            self.resorte.ir_a(1.0)
            reloj = self.animacion._reloj()
            reloj.activos = {self.resorte, otro}  # el orden del cuadro: primero el que fija
            reloj.tic()
            self.esperar()
            self.assertEqual(llegadas, [1])
        finally:
            otro.fijar(otro.x)
            otro.deleteLater()


@unittest.skipIf(QApplication is None, "falta PyQt6")
class Plegables(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        import tempfile
        from unittest import mock
        casa = tempfile.mkdtemp(prefix="wave-test-")
        with mock.patch.dict(os.environ, {"HOME": casa, "USERPROFILE": casa}):  # nada de tocar tu ~/.wavemascot
            import ajustes
        cls.ajustes = ajustes
        ajustes.aplicar_tema("oscuro")

    def test_cerrado_no_ocupa_lugar_ni_recibe_foco(self):
        from PyQt6.QtWidgets import QLineEdit
        plegable = self.ajustes.Plegable(False)
        campo = QLineEdit()
        plegable.agregar(self.ajustes.Fila("Prueba", campo))
        plegable.resize(400, 0)
        plegable.abrir(False, animar=False)
        self.assertEqual(plegable.height(), 0)
        self.assertTrue(plegable.filas.isHidden())
        self.assertIsNone(plegable.filas.graphicsEffect())
        plegable.abrir(True, animar=False)
        self.assertGreater(plegable.height(), 0)
        self.assertFalse(plegable.filas.isHidden())
        self.assertIsNone(plegable.filas.graphicsEffect())  # el fundido solo existe mientras se mueve
        plegable.deleteLater()

    def test_darse_vuelta_a_mitad_de_camino_no_salta(self):
        from PyQt6.QtWidgets import QLineEdit
        import animacion
        animacion._reducir = False
        plegable = self.ajustes.Plegable(False)
        for texto in ("Uno", "Dos", "Tres"):
            plegable.agregar(self.ajustes.Fila(texto, QLineEdit()))
        plegable.resize(400, 0)
        plegable.show()
        reloj = animacion._reloj()
        # Los cuadros los avanzo yo, de a 1/60 s: sin processEvents el reloj de verdad no corre.
        try:
            alfas = []

            def cuadros(n):
                for _ in range(n):  # lo mismo que hace el reloj en cada cuadro
                    for resorte in (plegable.apertura, plegable.opacidad):
                        if resorte.moviendose:
                            resorte.avanzar(1 / 60)
                    alfas.append(plegable.alfa)
            plegable.abrir(True)
            cuadros(14)                 # a mitad de abrirse...
            plegable.abrir(False)
            cuadros(10)                 # ...se cierra...
            plegable.abrir(True)
            cuadros(60)                 # ...se vuelve a abrir hasta el final...
            plegable.abrir(False)
            cuadros(60)                 # ...y se cierra de corrido
            saltos = [abs(b - a) for a, b in zip(alfas, alfas[1:])]
            # El cierre es un fundido rápido a propósito, pero ningún cuadro cambia más de un cuarto de golpe.
            self.assertLess(max(saltos), 0.25, [round(s, 3) for s in saltos])
            self.assertEqual(plegable.alfa, 0.0)
            # quieta y cerrada: filas ocultas, sin efecto, y ningún resorte sigue en el reloj
            self.assertTrue(plegable.filas.isHidden())
            self.assertIsNone(plegable.filas.graphicsEffect())
            self.assertNotIn(plegable.apertura, reloj.activos)
            self.assertNotIn(plegable.opacidad, reloj.activos)
        finally:
            plegable.apertura.fijar(0.0)
            plegable.opacidad.fijar(0.0)
            animacion._reducir = None
            plegable.deleteLater()


if __name__ == "__main__":
    unittest.main()
