"""Pruebas de los avisos a Telegram (sin conectarse de verdad): python -m unittest discover tests"""

from __future__ import annotations

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
    import celular  # noqa: E402
    import sprites  # noqa: E402

LLAVE = "x" * 40


def config_conectada(**cambios) -> dict:
    config = json.loads(json.dumps(m.CONFIG_DEFECTO))
    config["celular"].update({"activo": True, "llave": LLAVE, "conectado": True, **cambios})
    return config


class Config(unittest.TestCase):
    def leer(self, datos) -> dict:
        ruta = Path(tempfile.mkdtemp()) / "config.json"
        ruta.write_text(json.dumps(datos), encoding="utf-8")
        return m.cargar_config(ruta)

    def test_valores_validos_se_respetan_y_los_invalidos_no(self):
        cel = self.leer({"celular": {"activo": True, "llave": LLAVE, "conectado": True, "minutos": 500, "gif": "si",
                                     "token": "viejo", "estados": {"listo": False, "pensando": True}}})["celular"]
        self.assertTrue(cel["activo"] and cel["conectado"])
        self.assertEqual(cel["llave"], LLAVE)
        self.assertNotIn("token", cel)  # lo de la versión con bot propio no se arrastra
        self.assertEqual(cel["minutos"], 60)  # se limita
        self.assertTrue(cel["gif"])           # "si" no es bool: queda el de por defecto
        self.assertFalse(cel["estados"]["listo"])
        self.assertNotIn("pensando", cel["estados"])  # "pensando" nunca va al celular

    def test_sin_seccion_queda_apagado(self):
        self.assertFalse(self.leer({"tema": "claro"})["celular"]["activo"])


class CuandoSeManda(unittest.TestCase):
    evento = {"hook_event_name": "Stop"}

    def motivo(self, config, estado="listo", inactivo=600.0, evento=None):
        return m.motivo_para_no_mandar_al_celular(config, evento or self.evento, estado, inactivo)

    def test_conectado_y_lejos_de_la_compu_se_manda(self):
        self.assertEqual(self.motivo(config_conectada()), "")

    def test_sin_conectar_o_apagado_no(self):
        self.assertTrue(self.motivo(json.loads(json.dumps(m.CONFIG_DEFECTO))))
        self.assertTrue(self.motivo(config_conectada(activo=False)))
        self.assertTrue(self.motivo(config_conectada(conectado=False)))  # mandó /stop o no terminó de vincular

    def test_en_la_compu_no_salvo_que_se_pida_siempre(self):
        self.assertIn("compu", self.motivo(config_conectada(), inactivo=10))
        self.assertEqual(self.motivo(config_conectada(solo_ausente=False), inactivo=10), "")
        self.assertEqual(self.motivo(config_conectada(), inactivo=None), "")  # no se sabe: se manda

    def test_estados_apagados_y_pensando_no(self):
        config = config_conectada()
        config["celular"]["estados"]["listo"] = False
        self.assertTrue(self.motivo(config))
        self.assertTrue(self.motivo(config_conectada(), estado="pensando",
                                    evento={"hook_event_name": "UserPromptSubmit"}))

    def test_silencio_y_evento_desactivado_tambien_valen(self):
        config = config_conectada()
        config["silenciado_hasta"] = 9e12
        self.assertTrue(self.motivo(config))
        config = config_conectada()
        config["eventos"]["Stop"] = False
        self.assertTrue(self.motivo(config))


class Mensaje(unittest.TestCase):
    def test_html_escapado_y_partes_opcionales(self):
        texto = celular.texto({"mensaje": "¡Listo! <b>", "resumen": "a & b", "meta": "proy · 2 min"})
        self.assertEqual(texto, "<b>¡Listo! &lt;b&gt;</b>\na &amp; b\n<i>proy · 2 min</i>")
        self.assertEqual(celular.texto({"mensaje": "Hola"}), "<b>Hola</b>")

    def test_largo_maximo_de_telegram(self):
        self.assertLessEqual(len(celular.texto({"mensaje": "x", "resumen": "y" * 5000})), 1024)

    def test_gif_con_fondo_y_mas_grande(self):
        from PIL import Image

        with mock.patch.object(sprites, "CACHE", Path(tempfile.mkdtemp())):
            ruta = sprites.gif_celular(sprites.ASPECTO_DEFECTO, "listo")
            with Image.open(ruta) as img:
                self.assertEqual(img.size, (sprites.LADO * 6, sprites.LADO * 6))
                self.assertGreater(img.n_frames, 1)
                self.assertNotIn("transparency", img.info)
                self.assertEqual(img.convert("RGB").getpixel((0, 0)), celular.FONDO)


class Envio(unittest.TestCase):
    def falso(self, respuestas):
        """Reemplaza pedir(): guarda cada llamada y contesta en orden."""
        llamadas = []

        def pedir(metodo, ruta, llave="", datos=None, archivo=None, espera=20):
            llamadas.append({"metodo": metodo, "ruta": ruta, "llave": llave, "datos": datos, "archivo": archivo})
            return respuestas.pop(0)
        return pedir, llamadas

    def test_gif_por_clave_y_se_sube_solo_si_falta(self):
        pedir, llamadas = self.falso([{"ok": False, "falta_gif": True}, {"ok": True}, {"ok": True}])
        with mock.patch.object(celular, "pedir", pedir), mock.patch.object(sprites, "CACHE", Path(tempfile.mkdtemp())):
            aviso = {"estado": "listo", "mensaje": "Listo", "aspecto": {}}
            celular.enviar(LLAVE, aviso)  # el servidor no lo tenía: segunda llamada con el archivo
            celular.enviar(LLAVE, aviso)  # ahora sí: solo la clave
        self.assertEqual([c["ruta"] for c in llamadas], ["/v1/aviso"] * 3)
        self.assertIsNone(llamadas[0]["archivo"])
        self.assertEqual(llamadas[1]["archivo"][0], "archivo")
        self.assertIsNone(llamadas[2]["archivo"])
        self.assertEqual(llamadas[0]["datos"]["tipo"], "animation")
        self.assertTrue(llamadas[0]["datos"]["gif"].endswith("/celular-listo-1c1513-6"))
        self.assertEqual(llamadas[0]["llave"], LLAVE)

    def test_sin_gif_va_solo_texto(self):
        pedir, llamadas = self.falso([{"ok": True}])
        with mock.patch.object(celular, "pedir", pedir):
            celular.enviar(LLAVE, {"estado": "listo", "mensaje": "Listo", "gif": False})
        self.assertEqual(llamadas[0]["datos"], {"texto": "<b>Listo</b>"})

    def test_error_del_servidor_se_avisa(self):
        pedir, _ = self.falso([{"ok": False, "error": "Telegram no lo aceptó"}])
        with mock.patch.object(celular, "pedir", pedir), self.assertRaises(celular.ErrorCelular):
            celular.enviar(LLAVE, {"estado": "listo", "mensaje": "Listo", "gif": False})

    def test_codigo_y_enlace(self):
        self.assertEqual(celular.codigo_visible("ENRHPK"), "ENR-HPK")
        self.assertEqual(celular.enlace_bot("ENRHPK"), "https://t.me/WaveNotificationBot?start=ENRHPK")

    def test_permiso_repetido_no_se_manda_dos_veces(self):
        with mock.patch.object(celular, "ULTIMOS", Path(tempfile.mkdtemp()) / "u.json"):
            self.assertFalse(celular.repetido("sesion|permiso"))
            self.assertTrue(celular.repetido("sesion|permiso"))
            self.assertFalse(celular.repetido("otra|permiso"))


class PermisosPorTelegram(unittest.TestCase):
    """responder_permiso con Telegram y sin la mascota en pantalla (la terminal tiene el foco)."""

    def correr(self, esperar, espera=60):
        import io
        cerrados = []
        telegram = {"llave": LLAVE, "texto": "🔐 x", "idioma": "es", "espera": espera}
        salida = io.StringIO()
        with mock.patch.object(celular, "pedir_permiso", return_value="I" * 20) as pedir, \
                mock.patch.object(celular, "esperar_permiso", side_effect=esperar), \
                mock.patch.object(celular, "cerrar_permiso", side_effect=lambda *a, **k: cerrados.append(a)), \
                mock.patch.object(m.sys, "stdout", salida):
            m.responder_permiso(None, 30, telegram)
        pedir.assert_called_once_with(LLAVE, "🔐 x", "es", espera)
        return salida.getvalue(), cerrados

    def test_permitir_desde_telegram(self):
        respuestas = iter([None, "allow"])
        texto, cerrados = self.correr(lambda *a: next(respuestas))
        self.assertEqual(json.loads(texto)["hookSpecificOutput"]["decision"], {"behavior": "allow"})
        self.assertEqual(cerrados, [])  # el mensaje lo edita el servidor al tocar el botón

    def test_denegar_dice_desde_donde(self):
        texto, _ = self.correr(lambda *a: "deny")
        decision = json.loads(texto)["hookSpecificOutput"]["decision"]
        self.assertEqual(decision["behavior"], "deny")
        self.assertIn("Telegram", decision["message"])

    def test_sin_respuesta_se_vence_y_decide_la_terminal(self):
        import itertools
        reloj = itertools.count(0, 100)  # cada consulta de la hora avanza 100 s: la espera de 60 s se agota enseguida
        with mock.patch.object(m.time, "time", side_effect=lambda: next(reloj)):
            texto, cerrados = self.correr(lambda *a: None, espera=60)
        self.assertEqual(texto, "")
        self.assertEqual(cerrados, [(LLAVE, "I" * 20, "vencido", None)])

    def test_texto_del_pedido(self):
        texto = celular.texto_permiso("¿Permitir Bash?", "rm -rf <carpeta> && echo 'ok'", "waveapp · chat")
        self.assertEqual(texto, "🔐 <b>¿Permitir Bash?</b>\n<pre>rm -rf &lt;carpeta&gt; &amp;&amp; echo &#x27;ok&#x27;</pre>"
                                "\n<i>waveapp · chat</i>")

    def test_espera_se_limita(self):
        ruta = Path(tempfile.mkdtemp()) / "config.json"
        ruta.write_text(json.dumps({"celular": {"espera_permisos": 5000}}), encoding="utf-8")
        self.assertEqual(m.cargar_config(ruta)["celular"]["espera_permisos"], m.ESPERA_TELEGRAM_MAX)


if __name__ == "__main__":
    unittest.main()
