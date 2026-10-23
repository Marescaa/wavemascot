"""Pruebas de la búsqueda de versiones nuevas (sin conectarse a GitHub): python -m unittest discover tests"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
_CASA = tempfile.mkdtemp(prefix="wavemascot-pruebas-")
with mock.patch.dict(os.environ, {"HOME": _CASA, "USERPROFILE": _CASA}):  # nada de tocar tu ~/.wavemascot
    import mascota as m  # noqa: E402
    import actualizacion as a  # noqa: E402

CUERPO = """## What's new

- **Notifications on your phone through Telegram**, with Wave animated (a GIF of each state), from the official bot
  **@WaveNotificationBot**. New **Phone** tab in the settings.
  - By default it only sends when you're away from the computer.
- **Updates**: WaveMascot tells you when there's a new version and installs it with one click.

### Changed

- The Windows build keeps `libssl`.

## Download

| Your computer | File |
"""

RELEASE = {"tag_name": "v9.0.0", "html_url": "https://github.com/x/y/releases/tag/v9.0.0", "body": CUERPO,
           "assets": [{"name": n, "browser_download_url": f"https://d/{n}"} for n in
                      ("SHA256SUMS.txt", "WaveMascot-Mac-AppleSilicon.dmg", "WaveMascot-Mac-Intel.dmg",
                       "WaveMascot-Setup.exe")]}


class Versiones(unittest.TestCase):
    def test_comparar(self):
        self.assertTrue(a.es_mas_nueva("1.10.0", "1.9.9"))
        self.assertTrue(a.es_mas_nueva("v2", "1.9"))
        self.assertFalse(a.es_mas_nueva("1.2.0", "1.2.0"))
        self.assertFalse(a.es_mas_nueva("", "1.2.0"))

    def test_novedades_cortas_y_solo_lo_nuevo(self):
        self.assertEqual(a.novedades(CUERPO), [
            "Notifications on your phone through Telegram",
            "Updates: WaveMascot tells you when there's a new version and installs it with one click"])
        self.assertEqual(a.novedades("**Full Changelog**: https://github.com/..."), [])

    def test_instalador_de_cada_compu(self):
        nombres = [x["name"] for x in RELEASE["assets"]]
        with mock.patch.object(m, "MAC", False):
            self.assertEqual(a.archivo_para_esta_compu(nombres), "WaveMascot-Setup.exe")
        with mock.patch.object(m, "MAC", True), mock.patch("platform.machine", return_value="arm64"):
            self.assertEqual(a.archivo_para_esta_compu(nombres), "WaveMascot-Mac-AppleSilicon.dmg")
        with mock.patch.object(m, "MAC", True), mock.patch("platform.machine", return_value="x86_64"):
            self.assertEqual(a.archivo_para_esta_compu(nombres), "WaveMascot-Mac-Intel.dmg")


class Buscar(unittest.TestCase):
    def setUp(self):
        self.estado = Path(tempfile.mkdtemp()) / "actualizacion.json"
        self.parches = [mock.patch.object(a, "ESTADO", self.estado), mock.patch.object(m, "MAC", False)]
        for p in self.parches:
            p.start()

    def tearDown(self):
        for p in self.parches:
            p.stop()

    def test_encuentra_y_no_vuelve_a_preguntar_enseguida(self):
        with mock.patch.object(a, "bajar", return_value=json.dumps(RELEASE).encode()) as bajar:
            info = a.buscar()
            self.assertEqual(info["version"], "9.0.0")
            self.assertEqual(info["url"], "https://d/WaveMascot-Setup.exe")
            self.assertEqual(info["sumas"], "https://d/SHA256SUMS.txt")
            a.buscar()  # dentro de las 20 horas: usa lo guardado
            self.assertEqual(bajar.call_count, 1)
            a.buscar(forzar=True)
            self.assertEqual(bajar.call_count, 2)

    def test_al_dia(self):
        vieja = {**RELEASE, "tag_name": "v" + m.__version__}
        with mock.patch.object(a, "bajar", return_value=json.dumps(vieja).encode()):
            self.assertIsNone(a.buscar(forzar=True))

    def test_sin_conexion(self):
        with mock.patch.object(a, "bajar", side_effect=OSError("sin red")), self.assertRaises(a.ErrorActualizacion):
            a.buscar(forzar=True)

    def test_avisa_una_sola_vez_y_respeta_ahora_no(self):
        config = json.loads(json.dumps(m.CONFIG_DEFECTO))
        with mock.patch.object(a, "bajar", return_value=json.dumps(RELEASE).encode()), \
                mock.patch.object(m, "cargar_config", return_value=config), \
                mock.patch("ventanas.pantalla_completa", return_value=False), \
                mock.patch.object(m, "lanzar_ventana") as ventana:
            a.revisar_y_avisar(forzar=True)
            a.revisar_y_avisar(forzar=True)
            self.assertEqual(ventana.call_count, 1)
            aviso = ventana.call_args.args[0]
            self.assertEqual(aviso["novedad"], "9.0.0")
            self.assertEqual(aviso["sonido"], "")
            self.assertIn("Telegram", aviso["resumen"])
            a.guardar_estado({})  # como si nunca hubiera avisado...
            config["actualizaciones"]["ignorada"] = "9.0.0"  # ...pero le dijiste "Ahora no"
            a.revisar_y_avisar(forzar=True)
            self.assertEqual(ventana.call_count, 1)

    def test_en_pantalla_completa_espera(self):
        config = json.loads(json.dumps(m.CONFIG_DEFECTO))
        with mock.patch.object(a, "bajar", return_value=json.dumps(RELEASE).encode()), \
                mock.patch.object(m, "cargar_config", return_value=config), \
                mock.patch("ventanas.pantalla_completa", return_value=True), \
                mock.patch.object(m, "lanzar_ventana") as ventana:
            self.assertEqual(a.revisar_y_avisar(forzar=True)["version"], "9.0.0")
        ventana.assert_not_called()
        self.assertFalse(a.ya_avisada("9.0.0"))


class Descargar(unittest.TestCase):
    def test_comprueba_sha256(self):
        origen = Path(tempfile.mkdtemp()) / "WaveMascot-Setup.exe"
        origen.write_bytes(b"instalador de prueba")
        bien = hashlib.sha256(b"instalador de prueba").hexdigest()
        info = {"instalador": origen.name, "url": origen.as_uri(), "sumas": "https://d/SHA256SUMS.txt"}
        with mock.patch.object(a, "bajar", return_value=f"{bien}  WaveMascot-Setup.exe\n".encode()):
            self.assertEqual(a.descargar(info).read_bytes(), b"instalador de prueba")
        with mock.patch.object(a, "bajar", return_value=f"{'0' * 64}  WaveMascot-Setup.exe\n".encode()), \
                self.assertRaises(a.ErrorActualizacion):
            a.descargar(info)


if __name__ == "__main__":
    unittest.main()
