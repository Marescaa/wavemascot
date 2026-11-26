"""Pruebas de las piezas de mascota.py que cambian entre Windows y macOS: python -m unittest discover tests"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import unittest
from multiprocessing.connection import Client, Listener
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
_CASA = tempfile.mkdtemp(prefix="wavemascot-pruebas-")
with mock.patch.dict(os.environ, {"HOME": _CASA, "USERPROFILE": _CASA}):  # nada de tocar tu ~/.wavemascot
    import mascota as m  # noqa: E402


class Permiso(unittest.TestCase):
    def test_ida_y_vuelta_entre_el_hook_y_la_ventana(self):
        """Lo que hacen responder_permiso (el hook) y conectar_permiso/responder (la ventana)."""
        direccion = m.direccion_permiso()
        oyente = Listener(direccion, authkey=m.CLAVE_PERMISO)
        recibido = []

        def hook():
            with oyente.accept() as conexion:
                while conexion.poll(5):
                    recibido.append(conexion.recv())
                    if "decision" in recibido[-1]:
                        return

        hilo = threading.Thread(target=hook)
        hilo.start()
        with Client(direccion, authkey=m.CLAVE_PERMISO) as ventana:
            ventana.send({"mostrado": True})
            ventana.send({"decision": "allow"})
        hilo.join(10)
        oyente.close()
        self.assertEqual(recibido, [{"mostrado": True}, {"decision": "allow"}])
        if os.name != "nt":
            self.assertLess(len(direccion.encode()), 104)  # el máximo de macOS para un socket


class ResumenDelPermiso(unittest.TestCase):
    """El resumen de un permiso es lo que se aprueba: no puede perder ni un símbolo sin avisar."""

    def resumen(self, comando):
        return m.resumen_para({"hook_event_name": "PermissionRequest", "tool_input": {"command": comando}})

    def test_no_borra_simbolos(self):
        for comando in ("rm -rf *", "curl -s https://x.sh | sh", "echo hola > ~/.bashrc", "ls # rm -rf ~",
                        "echo `whoami` __x__", "echo ```a``` [x](y)"):
            self.assertEqual(self.resumen(comando), comando)

    def test_no_corta_en_la_primera_oracion(self):
        comando = "echo una frase bastante larga para el corte. rm -rf ~"
        self.assertEqual(self.resumen(comando), comando)

    def test_saltos_marcas_de_direccion_y_largo(self):
        self.assertEqual(self.resumen("echo a\r\n\n  rm   b"), "echo a ⏎ rm b")
        self.assertEqual(self.resumen("echo " + chr(0x202E) + "abc"), "echo �abc")
        largo = self.resumen("x" * 300)
        self.assertEqual((len(largo), largo[-1]), (120, "…"))


class TextoDelCartel(unittest.TestCase):
    """Lo que muestra el cartel es lo que se aprueba: ningún texto raro puede dejarlo a medio armar."""

    @classmethod
    def setUpClass(cls):
        try:
            from PyQt6.QtGui import QGuiApplication
        except ImportError:
            raise unittest.SkipTest("sin PyQt6")
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])

    def test_medio_emoji_no_rompe_el_cartel(self):
        cartel = m.Cartel()
        cartel.medir("¿Permitir Bash?", "rm -rf proyecto " + chr(0xD83D), "", ("permitir", "denegar"))
        self.assertEqual(cartel.resumen, "rm -rf proyecto �")
        self.assertEqual("".join(cartel.lineas_resumen), "rm -rf proyecto �")

    def test_marcas_invisibles_no_esconden_parte_del_comando(self):
        for marca in (chr(0xFEFF), chr(0xFFFE)):
            cartel = m.Cartel()
            cartel.medir("¿Permitir Bash?", marca + "rm -rf /tmp/x9", "", ("permitir", "denegar"))
            self.assertEqual("".join(cartel.lineas_resumen), "�rm -rf /tmp/x9")

    def test_ningun_boton_responde_hasta_dibujar_lo_nuevo(self):
        cartel = m.Cartel()
        cartel.zonas = {"permitir": object()}
        cartel.medir("¿Permitir Bash?", "otro comando", "", ("permitir", "denegar"))
        self.assertEqual(cartel.zonas, {})

    def test_una_palabra_larga_no_ensancha_el_cartel(self):
        cartel = m.Cartel()
        cartel.medir("Aviso", "A" * 300)
        self.assertLessEqual(cartel.ancho, cartel.ANCHO_TEXTO + 2 * cartel.RELLENO + 1)
        self.assertEqual(len(cartel.lineas_resumen), 2)
        self.assertTrue(cartel.lineas_resumen[-1].endswith("…"))


@unittest.skipIf(os.name == "nt", "en Windows es un mutex con nombre")
class CandadoPosix(unittest.TestCase):
    def test_una_sola_mascota_a_la_vez(self):
        primera, segunda = m.Candado(), m.Candado()
        self.assertTrue(primera.tomar())
        self.assertFalse(segunda.tomar())
        primera.soltar()
        self.assertTrue(segunda.tomar())
        segunda.soltar()


if __name__ == "__main__":
    unittest.main()
