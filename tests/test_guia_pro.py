"""Qué muestra la app de WaveMascot Pro según el plan (sin abrir ventanas): python -m unittest discover tests"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
HAY_QT = importlib.util.find_spec("PyQt6") is not None
if HAY_QT:
    _CASA = tempfile.mkdtemp(prefix="wavemascot-pruebas-")
    with mock.patch.dict(os.environ, {"HOME": _CASA, "USERPROFILE": _CASA}):
        import guia_pro  # noqa: E402
        import idiomas  # noqa: E402

INFO = {"cobrando": True, "precios": {"mensual": 100, "vitalicio": 1500}, "dias_prueba": 7}
EN_UNA_SEMANA = (time.time() + 7 * 86400) * 1000


@unittest.skipUnless(HAY_QT, "hace falta PyQt6")
class QueSeMuestra(unittest.TestCase):
    def setUp(self):
        idiomas.usar("es")
        self.addCleanup(idiomas.usar, idiomas.POR_DEFECTO)

    def tipo(self, plan, conectado=True, info=INFO):
        return guia_pro.describir(plan, info, conectado)

    def test_sin_conectar_invita_a_probar(self):
        d = self.tipo(None, conectado=False)
        self.assertEqual(d["tipo"], "nuevo")
        self.assertFalse(d["oculto"])

    def test_plan_desconocido_no_bloquea_ni_muestra(self):
        # Conectado, pero sin internet la primera vez o con un servidor viejo que no manda el plan.
        for plan in ({}, None, {"tipo": "algo-nuevo"}):
            with self.subTest(plan=plan):
                d = self.tipo(plan)
                self.assertEqual(d["tipo"], "desconocido")
                self.assertTrue(d["oculto"])
                self.assertFalse(d["aviso"])

    def test_prueba_pago_y_vencido(self):
        self.assertEqual(self.tipo({"tipo": "prueba", "dias": 5, "hasta": EN_UNA_SEMANA})["tipo"], "prueba")
        self.assertTrue(self.tipo({"tipo": "prueba", "dias": 1, "hasta": EN_UNA_SEMANA})["aviso"])  # último día
        self.assertIn("se renueva", self.tipo({"tipo": "mensual", "hasta": EN_UNA_SEMANA, "renueva": True})["detalle"])
        self.assertIn("termina", self.tipo({"tipo": "mensual", "hasta": EN_UNA_SEMANA, "renueva": False})["detalle"])
        self.assertEqual(self.tipo({"tipo": "vitalicio"})["tipo"], "vitalicio")
        vencido = self.tipo({"tipo": "vencido"})
        self.assertTrue(vencido["aviso"])
        self.assertEqual(vencido["boton"], "Desbloquear Pro")

    def test_con_el_cobro_apagado_no_hay_nada_de_pro(self):
        apagado = dict(INFO, cobrando=False)
        for plan, conectado in (({"tipo": "vencido"}, True), (None, False)):
            self.assertEqual(self.tipo(plan, conectado, apagado)["tipo"], "libre")


if __name__ == "__main__":
    unittest.main()
