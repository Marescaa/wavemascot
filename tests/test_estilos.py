"""Estilos de la mascota (Clásico, Sakura, Ninja, Robot): python -m unittest discover tests

Se dibuja todo en memoria con Pillow; no se escribe nada en ~/.wavemascot.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sprites  # noqa: E402

try:
    import PIL  # noqa: F401
    HAY_PIL = True
except ImportError:
    HAY_PIL = False


class Aspecto(unittest.TestCase):
    def test_config_vieja_queda_en_clasico_con_su_color(self):
        a = sprites.normalizar({"color": "menta", "cabeza": "gorra"})
        self.assertEqual((a["estilo"], a["color"], a["cabeza"], a["piel"]), ("clasico", "menta", "gorra", "clara"))
        self.assertEqual(a["colores"]["clasico"], "menta")
        self.assertEqual(a["colores"]["ninja"], sprites.COLOR_SUGERIDO["ninja"])

    def test_cada_estilo_guarda_su_color(self):
        a = sprites.normalizar({"estilo": "ninja", "color": "carmesi"})
        clasico = sprites.con_estilo(a, "clasico")
        self.assertEqual(clasico["color"], "terracota")  # cambiar el del ninja no tocó el del Clásico
        de_vuelta = sprites.con_estilo({**clasico, "color": "menta"}, "ninja")
        self.assertEqual(de_vuelta["color"], "carmesi")
        self.assertEqual(sprites.normalizar(de_vuelta)["colores"]["clasico"], "menta")

    def test_valores_desconocidos(self):
        a = sprites.normalizar({"estilo": "pirata", "piel": "verde", "colores": {"ninja": "fucsia", "x": "menta"}})
        self.assertEqual((a["estilo"], a["piel"]), ("clasico", "clara"))
        self.assertEqual(set(a["colores"]), set(sprites.ESTILOS))
        self.assertEqual(a["colores"]["ninja"], sprites.COLOR_SUGERIDO["ninja"])

    def test_orden_de_colores_tiene_todos(self):
        self.assertEqual(sorted(c for c in sprites.ORDEN_COLORES if c), sorted(sprites.COLORES))

    def test_solo_el_clasico_entra_sin_animacion_propia(self):
        self.assertFalse(sprites.tiene_entrada({"estilo": "clasico"}))
        for estilo in ("sakura", "ninja", "robot"):
            self.assertTrue(sprites.tiene_entrada({"estilo": estilo}))


@unittest.skipUnless(HAY_PIL, "hace falta Pillow para dibujar")
class Dibujo(unittest.TestCase):
    ESTADOS = ("listo", "permiso", "pensando", "subagente", "limite", "error", "idle", "caminar")

    def test_todos_los_estados_en_todos_los_estilos_y_con_vestuario(self):
        for estilo in sprites.ESTILOS:
            for vestuario in ({}, {"cabeza": "galera", "ropa": "capa", "accesorio": "lentes"},
                              {"cabeza": "orejas", "ropa": "corbata", "accesorio": "flor"}):
                a = sprites.con_estilo({**vestuario, "piel": "morena"}, estilo)
                for estado in self.ESTADOS + (("entrada", "salida") if sprites.tiene_entrada(a) else ()):
                    with self.subTest(estilo=estilo, estado=estado, vestuario=vestuario):
                        cuadros, ms = sprites.ESTADOS[estado](a)
                        self.assertTrue(cuadros and ms > 0)
                        self.assertTrue(all(c.size == (sprites.LADO, sprites.LADO) for c in cuadros))

    def test_entradas_y_salidas_tienen_el_tramo_que_se_desliza(self):
        for estilo in ("sakura", "ninja", "robot"):
            a = sprites.con_estilo({}, estilo)
            for estado in ("entrada", "salida"):
                cuadros, _ = sprites.ESTADOS[estado](a)
                self.assertGreater(len(cuadros), sprites.CUADROS_DESLIZ, (estilo, estado))

    def test_el_clasico_se_dibuja_igual_que_antes(self):
        """El estilo no cambia nada del Clásico: misma cara y mismo orden de dibujo."""
        a = sprites.normalizar({})
        lz = sprites.lienzo(a)
        sprites.mascota(lz, a)
        self.assertNotIn(sprites.PIEL, lz.img.tobytes())
        self.assertNotIn(sprites.LED, lz.img.tobytes())

    def test_cada_estilo_tiene_su_cara(self):
        caras = {"ninja": sprites.PIEL, "robot": sprites.LED}
        for estilo, color in caras.items():
            a = sprites.con_estilo({}, estilo)
            lz = sprites.lienzo(a)
            sprites.mascota(lz, a)
            self.assertIn(color, lz.img.tobytes(), estilo)

    def test_la_piel_del_ninja_cambia_el_color_de_la_cara(self):
        for piel, (_, rgb) in sprites.PIELES.items():
            lz = sprites.lienzo(sprites.con_estilo({"piel": piel}, "ninja"))
            paleta = lz.img.getpalette()
            self.assertEqual(tuple(paleta[sprites.PIEL * 3:sprites.PIEL * 3 + 3]), rgb)


if __name__ == "__main__":
    unittest.main()
