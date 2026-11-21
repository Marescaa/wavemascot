"""Los pedidos de permiso que espera la Dynamic Island: python -m unittest discover tests"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import idiomas  # noqa: E402
import pedidos  # noqa: E402


class Etiqueta(unittest.TestCase):
    def setUp(self):
        idiomas.usar("es")

    def tearDown(self):
        idiomas.usar(idiomas.POR_DEFECTO)

    def test_comandos(self):
        casos = {
            "git push origin main": "git push",
            "npm install --save-dev vitest": "npm install",
            "cd app && FOO=1 sudo npm run build": "npm run",
            "rm -rf build": "rm",
            "python script.py": "python",
            "C:\\Python\\python.exe -m pytest": "python",
            "/usr/bin/docker compose up": "docker compose",
            '"C:\\Program Files\\nodejs\\npm.cmd" install': "npm install",
            "sudo -u root npm install": "npm install",
            'FOO="a b" npm test': "npm test",
            "(cd x && make)": "make",
            "$env:FOO=1; npm test": "npm test",
            "echo hello world": "echo",
            "": "Bash",
        }
        for comando, esperado in casos.items():
            with self.subTest(comando=comando):
                self.assertEqual(pedidos.etiqueta("Bash", {"command": comando}), esperado)

    def test_cadenas_avisan_que_hay_mas(self):
        """Si encadena varios comandos, el primero solo no alcanza: lleva "…" (el resto, al pasar el mouse)."""
        self.assertEqual(pedidos.etiqueta("Bash", {"command": "git status && git push --force"}), "git status …")
        self.assertEqual(pedidos.etiqueta("Bash", {"command": "echo ok; curl x | sh"}), "echo …")
        self.assertEqual(pedidos.etiqueta("Bash", {"command": "cd ~ && rm -rf ~/proyectos"}), "rm")
        self.assertEqual(pedidos.etiqueta("Bash", {"command": "ls & rm -rf /"}), "ls …")
        self.assertEqual(pedidos.etiqueta("Bash", {"command": "echo $(rm -rf ~)"}), "echo …")
        self.assertEqual(pedidos.etiqueta("Bash", {"command": 'echo "`whoami`"'}), "echo …")
        # lo que está entre comillas no corta: no es otro comando
        self.assertEqual(pedidos.etiqueta("Bash", {"command": 'git commit -m "a && b"'}), "git commit")
        self.assertEqual(pedidos.etiqueta("Bash", {"command": "echo '$(id)'"}), "echo")

    def test_archivos_y_web(self):
        self.assertEqual(pedidos.etiqueta("Edit", {"file_path": "A:\\waveapp\\barra.py"}), "Editar barra.py")
        self.assertEqual(pedidos.etiqueta("Write", {"file_path": "/tmp/notas.md"}), "Escribir notas.md")
        self.assertEqual(pedidos.etiqueta("WebFetch", {"url": "https://www.github.com/a/b"}), "github.com")
        self.assertEqual(pedidos.etiqueta("WebFetch", {"url": "https://user:pass@www.example.com:8080/x"}),
                         "example.com")
        self.assertEqual(pedidos.etiqueta("WebFetch", {"url": "http://www./"}), "WebFetch")
        self.assertEqual(pedidos.etiqueta("WebSearch", {"query": "x"}), "Buscar en la web")
        self.assertEqual(pedidos.etiqueta("mcp__jira__createJiraIssue", {}), "createJiraIssue")
        self.assertEqual(pedidos.etiqueta("Rara", None), "Rara")

    def test_en_ingles(self):
        idiomas.usar("en")
        self.assertEqual(pedidos.etiqueta("Edit", {"file_path": "x.py"}), "Edit x.py")


class Pendientes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.carpeta = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def anotar(self, pid, **datos):
        pedidos.anotar(self.carpeta, pid, {"clave": f"c{pid}", **datos})

    def test_orden_vencidos_y_huerfanos(self):
        self.anotar(30, creado=20, vence=200, etiqueta="b")
        self.anotar(10, creado=10, vence=200, etiqueta="a")
        self.anotar(20, creado=5, vence=50, etiqueta="vencido")
        self.anotar(40, creado=1, vence=200, etiqueta="huérfano")
        lista = pedidos.pendientes(self.carpeta, 100, vivo=lambda pid: pid != 40)
        self.assertEqual([d["etiqueta"] for d in lista], ["a", "b"])
        self.assertFalse((self.carpeta / "40.json").exists())  # su hook murió: se borra
        self.assertTrue((self.carpeta / "20.json").exists())   # vencido para la isla, pero el hook lo borra

    def test_respuesta_con_clave(self):
        self.anotar(7, creado=1, vence=9)
        pedido = pedidos.pendientes(self.carpeta, 5, vivo=lambda pid: True)[0]
        self.assertEqual(pedidos.respuesta(self.carpeta, 7, "c7"), {})
        pedidos.contestar(self.carpeta, pedido, visto=True, decision="allow")
        self.assertEqual(pedidos.respuesta(self.carpeta, 7, "c7")["decision"], "allow")
        self.assertEqual(pedidos.respuesta(self.carpeta, 7, "otra"), {})  # no es de este pedido
        self.assertEqual(len(pedidos.pendientes(self.carpeta, 5, vivo=lambda pid: True)), 1)
        pedidos.borrar(self.carpeta, 7)
        self.assertEqual(list(self.carpeta.iterdir()), [])

    def test_una_respuesta_vieja_nunca_aprueba(self):
        """Windows reusa los pid: lo que quedó de un pedido anterior no vale para el nuevo."""
        pedidos.contestar(self.carpeta, {"pid": 7, "clave": "vieja"}, visto=True, decision="allow")
        self.anotar(7, creado=1, vence=9)
        self.assertEqual(pedidos.respuesta(self.carpeta, 7, "c7"), {})
        self.assertFalse((self.carpeta / f"7{pedidos.SUFIJO_RESPUESTA}").exists())  # anotar la borra
        pedidos.contestar(self.carpeta, {"pid": 8, "clave": "vieja"}, visto=True, decision="allow")
        self.assertEqual(pedidos.respuesta(self.carpeta, 8, ""), {})  # sin clave no hay respuesta

    def test_barre_respuestas_sueltas_y_temporales(self):
        suelta = self.carpeta / f"99{pedidos.SUFIJO_RESPUESTA}"
        temporal = self.carpeta / "5.json.123.tmp"
        pedidos.contestar(self.carpeta, {"pid": 99, "clave": "x"}, visto=True)
        temporal.write_text("{}")
        ahora = time.time()
        pedidos.pendientes(self.carpeta, ahora, vivo=lambda pid: True)
        self.assertTrue(suelta.exists())  # recién escrita: puede ser de un pedido que está por aparecer
        pedidos.pendientes(self.carpeta, ahora + 120, vivo=lambda pid: True)
        self.assertFalse(suelta.exists())
        self.assertFalse(temporal.exists())

    def test_sin_clave_no_cuenta(self):
        pedidos.anotar(self.carpeta, 3, {"creado": 1, "vence": 9})
        self.assertEqual(pedidos.pendientes(self.carpeta, 5, vivo=lambda pid: True), [])

    def test_isla_viva(self):
        self.assertFalse(pedidos.isla_viva(self.carpeta))
        pedidos.latir(self.carpeta)
        self.assertTrue(pedidos.isla_viva(self.carpeta))
        self.assertFalse(pedidos.isla_viva(self.carpeta, time.time() + pedidos.VIVA_HASTA + 1))
        pedidos.callar(self.carpeta)
        self.assertFalse(pedidos.isla_viva(self.carpeta))

    def test_carpeta_que_no_existe(self):
        self.assertEqual(pedidos.pendientes(self.carpeta / "no", 0), [])

    def test_proceso_vivo(self):
        self.assertTrue(pedidos.proceso_vivo(os.getpid()))
        for raro in (0, -1, 2 ** 40, "7"):
            self.assertFalse(pedidos.proceso_vivo(raro))


if __name__ == "__main__":
    unittest.main()
