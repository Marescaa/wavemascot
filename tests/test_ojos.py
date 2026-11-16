"""Los ojos de la mascota (ojos.py) y lo que la barra lee de cada sesión: python -m unittest discover tests"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import ojos  # noqa: E402
import sprites  # noqa: E402


class Mirada(unittest.TestCase):
    def test_mira_parpadea_y_se_queda_en_rango(self):
        mirada = ojos.Mirada(semilla=3)
        mirada.animo = "despierta"
        se_movio = parpadeo = False
        t = 0.0
        for _ in range(1500):  # un minuto, a 25 cuadros por segundo
            t += 0.04
            se_movio |= mirada.avanzar(mirada.reloj + 0.04)
            parpadeo |= mirada.parpadeo_desde >= 0
            self.assertLessEqual(abs(mirada.x), 1.0001)
            self.assertLessEqual(abs(mirada.y), 1.0001)
        self.assertTrue(se_movio and parpadeo)

    def test_dormida_y_siguiendo_al_mouse(self):
        mirada = ojos.Mirada(semilla=1)
        mirada.animo = "dormida"
        self.assertTrue(mirada.cerrados)
        mirada.animo = "tranquila"
        mirada.seguir = (1.0, -1.0)
        for _ in range(40):
            mirada.avanzar(mirada.reloj + 0.04)
        self.assertAlmostEqual(mirada.x, 1.0, delta=0.02)
        self.assertAlmostEqual(mirada.y, -1.0, delta=0.02)

    def test_cada_estilo_tiene_sus_colores_y_su_ancho(self):
        for estilo in sprites.ESTILOS:
            aspecto = dict(sprites.ASPECTO_DEFECTO, estilo=estilo)
            self.assertEqual(ojos.colores(aspecto)["estilo"], estilo)
        for raro in ({"color": "no-existe"}, {"estilo": "no-existe"}, {}):  # un aspecto raro no rompe
            self.assertEqual(ojos.colores(raro)["estilo"], "clasico")

    def test_se_pintan_los_cuatro_estilos(self):
        from PyQt6.QtCore import QPointF
        from PyQt6.QtGui import QImage, QPainter
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        for estilo in sprites.ESTILOS:
            for cerrados in (False, True):
                imagen = QImage(60, 40, QImage.Format.Format_ARGB32_Premultiplied)
                imagen.fill(0)
                mirada = ojos.Mirada(semilla=1)
                mirada.animo = "dormida" if cerrados else "tranquila"
                p = QPainter(imagen)
                ojos.pintar(p, QPointF(30, 20), 3, dict(sprites.ASPECTO_DEFECTO, estilo=estilo), mirada)
                p.end()
                pintados = sum(1 for x in range(60) for y in range(40) if imagen.pixelColor(x, y).alpha())
                self.assertGreater(pintados, 600, (estilo, cerrados))  # el display entero, igual en los cuatro
                # el filo claro por fuera y el contorno oscuro enseguida: se despega de cualquier fondo
                borde, adentro = imagen.pixelColor(30, 20 - 13), imagen.pixelColor(30, 20 - 11)
                self.assertGreater(borde.lightness(), 100, estilo)
                self.assertLess(adentro.lightness(), 90, estilo)
        del app


class VentanaDeSesion(unittest.TestCase):
    def test_lee_la_ventana_que_anoto_el_hook(self):
        import barra
        import mascota as m
        carpeta = Path(tempfile.mkdtemp())
        original, m.SESIONES = m.SESIONES, carpeta
        try:
            (carpeta / "a.json").write_text(json.dumps({"inicio": 1.0, "ventana": 1234}), encoding="utf-8")
            # de otro proceso que el que la anotó (la ventana se cerró y el número se recicló): no se salta
            (carpeta / "ajena.json").write_text(json.dumps({"ventana": 1234, "proceso": 99999999}), encoding="utf-8")
            if barra.ventanas.ES_WINDOWS:
                self.assertEqual(barra.ventana_de("ajena"), 0)
            (carpeta / "vieja.json").write_text(json.dumps({"inicio": 1.0}), encoding="utf-8")
            (carpeta / "rota.json").write_text("{roto", encoding="utf-8")
            (carpeta / "rara.json").write_text('{"ventana": "x"}', encoding="utf-8")
            self.assertEqual(barra.ventana_de("a"), 1234)
            for sesion in ("vieja", "rota", "rara", "no-existe"):
                self.assertEqual(barra.ventana_de(sesion), 0, sesion)
        finally:
            m.SESIONES = original


class OpcionesDeLaIsla(unittest.TestCase):
    """Las opciones de la sección Dynamic Island cambian lo que la barra muestra (sin abrir ninguna ventana)."""

    def setUp(self):
        import copy
        import barra
        import mascota as m
        import seguimiento
        from PyQt6.QtWidgets import QApplication
        import idiomas
        idiomas.usar("es")
        self.app = QApplication.instance() or QApplication([])
        self.barra = barra.Barra(seguimiento.Monitor(None, Path(tempfile.mkdtemp())), leer=False, desenfocar=False)
        self.barra.config = copy.deepcopy(m.CONFIG_DEFECTO)
        sesion = {"id": "a", "proyecto": "p", "titulo": "Una sesión", "inicio": 0.0, "ultima": 0.0, "trabajando": True,
                  "transcurrido": 30.0, "falta": 60.0, "historial": True, "tokens": 1000, "turno": 10, "salida": 5,
                  "cache": 0, "contexto": 0, "agentes": 0, "herramienta": "Bash", "plan": (1, 3), "ventana": 0}
        self.barra.sesiones = [dict(sesion, id=str(i)) for i in range(9)]
        self.barra.eta = {"0": 60.0}
        self.barra.trabajando = True

    def test_pastilla(self):
        b, isla = self.barra, self.barra.config["barra"]
        self.assertEqual(b.texto_chica(), ("~1:00", "9 sesiones"))
        isla["tiempo"], isla["sesiones"] = False, False
        principal, resto = b.texto_chica()
        self.assertNotIn("~", principal)
        self.assertEqual(resto, "")
        con_ojos = b.ancho_ojos()
        isla["ojos"] = False
        self.assertLess(b.ancho_ojos(), con_ojos)

    def test_abierta(self):
        import barra
        b, isla = self.barra, self.barra.config["barra"]
        altos = {}
        for filas in (3, 5, 8):
            isla["filas"] = filas
            altos[filas] = b.alto_abierta()
            self.assertEqual(b.max_filas(), filas)
            self.assertLessEqual(barra.ARRIBA + altos[filas] + 10, b.height())  # entra en la ventana, con la sombra
        self.assertLess(altos[3], altos[5])
        self.assertLess(altos[5], altos[8])
        isla["uso"] = False
        self.assertEqual(b.alto_abierta(), altos[8] - barra.USO)

    def test_a_los_costados_no_se_sale_de_la_pantalla(self):
        from PyQt6.QtGui import QGuiApplication
        b, isla = self.barra, self.barra.config["barra"]
        area = QGuiApplication.primaryScreen().availableGeometry()
        for posicion in ("izquierda", "centro", "derecha"):
            isla["posicion"] = posicion
            b.ubicar()
            for ancho in (140.0, 470.0):  # chica y abierta
                b.r_ancho.fijar(ancho)
                cuerpo = b.rect_cuerpo()
                izquierda = b.x() + cuerpo.left()
                self.assertGreaterEqual(izquierda, area.left(), posicion)
                self.assertLessEqual(izquierda + cuerpo.width(), area.right() + 1, posicion)
        isla["posicion"] = "izquierda"
        b.ubicar()
        b.r_ancho.fijar(140.0)
        self.assertLess(b.x() + b.rect_cuerpo().left() - area.left(), 20)  # la pastilla queda en la esquina

    def test_se_pinta_con_cualquier_combinacion(self):
        b, isla = self.barra, self.barra.config["barra"]
        for abierta in (False, True):
            for valor in (True, False):
                for clave in ("ojos", "seguir_mouse", "tiempo", "sesiones", "uso", "saltar", "rebote", "latido"):
                    isla[clave] = valor
                b.abierta = abierta
                b.r_contenido.fijar(1.0 if abierta else 0.0)
                b.medir()
                b.r_ancho.fijar(b.r_ancho.objetivo)
                b.r_alto.fijar(b.r_alto.objetivo)
                self.assertFalse(b.grab().isNull())
        self.assertFalse(b.hay_pantalla_completa() and not isla["pantalla_completa"])
        isla["pantalla_completa"] = False
        self.assertFalse(b.hay_pantalla_completa())


if __name__ == "__main__":
    unittest.main()
