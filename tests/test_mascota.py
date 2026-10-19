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
