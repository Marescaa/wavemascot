"""Pruebas del merge de hooks del instalador: python -m unittest discover tests"""

from __future__ import annotations

import json
import os
import plistlib
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import instalador  # noqa: E402

AJENOS = {
    "model": "opus",
    "permissions": {"allow": ["Bash(git status)"]},
    "hooks": {
        "Stop": [{"hooks": [{"type": "command", "command": "echo listo >> ~/log.txt"}]}],
        "Notification": [{"matcher": "permission_prompt",
                          "hooks": [{"type": "command", "command": "notify-send hola", "timeout": 5}]}],
        "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "python ~/guardia.py"}]}],
    },
}
# Los hooks de una instalación anterior de la mascota (a mano, en otra carpeta).
VIEJA = '"C:/Python314/pythonw.exe" "C:/Users/x/.claude/mascota/mascota.py" --estado listo'


def hooks_planos(settings: dict) -> list:
    """Cada hook como (evento, matcher, hook), sin importar cómo estén agrupados."""
    return sorted(json.dumps([evento, grupo.get("matcher"), hook], sort_keys=True)
                  for evento, grupos in (settings.get("hooks") or {}).items()
                  for grupo in grupos for hook in grupo.get("hooks", []))


class Instalador(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        raiz = Path(self.tmp.name)
        self.claude = raiz / ".claude"
        self.destino = raiz / "Programs" / "WaveMascot"
        self.destino.mkdir(parents=True)
        (self.destino / "mascota.py").write_text("")
        entorno = {"APPDATA": str(raiz / "AppData"), "USERPROFILE": str(raiz), "HOME": str(raiz)}
        self.entorno = mock.patch.dict(os.environ, entorno)
        self.entorno.start()
        self.sin_procesos = mock.patch.object(instalador, "detener_procesos", lambda destino: None)
        self.sin_procesos.start()
        self.cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.cwd)
        self.sin_procesos.stop()
        self.entorno.stop()
        self.tmp.cleanup()

    @property
    def settings(self) -> Path:
        return self.claude / "settings.json"

    def escribir(self, datos) -> None:
        self.claude.mkdir(parents=True, exist_ok=True)
        texto = datos if isinstance(datos, str) else json.dumps(datos, indent=2)
        self.settings.write_text(texto, encoding="utf-8")

    def leer(self) -> dict:
        return json.loads(self.settings.read_text(encoding="utf-8"))

    def instalar(self):
        return instalador.configurar("fuente", self.destino, self.claude, sin_inicio=True)

    def desinstalar(self):
        return instalador.desinstalar(self.destino, self.claude)

    def backups(self) -> list[Path]:
        return sorted(self.claude.glob("settings.json.bak-*"))

    def nuestros(self, settings: dict, evento: str) -> list:
        return [h for g in settings["hooks"].get(evento, []) for h in g["hooks"] if instalador.es_hook_nuestro(h)]

    # -----------------------------------------------------------------------------------

    def test_conserva_hooks_existentes_y_hace_backup(self):
        self.escribir(AJENOS)
        self.instalar()
        nuevo = self.leer()
        for evento, grupos in AJENOS["hooks"].items():  # lo tuyo queda primero y sin cambios
            self.assertEqual(nuevo["hooks"][evento][:len(grupos)], grupos)
        self.assertEqual(nuevo["model"], "opus")
        self.assertEqual(nuevo["permissions"], AJENOS["permissions"])
        for evento in instalador.HOOKS:
            self.assertEqual(len(self.nuestros(nuevo, evento)), 1, evento)
        self.assertTrue(self.nuestros(nuevo, "UserPromptSubmit")[0]["async"])
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(json.loads(self.backups()[0].read_text(encoding="utf-8")), AJENOS)

    def test_desinstalar_deja_todo_como_estaba(self):
        self.escribir(AJENOS)
        self.instalar()
        self.desinstalar()
        self.assertEqual(self.leer(), AJENOS)
        self.assertFalse(self.destino.exists())

    def test_respeta_saltos_de_linea_y_formato(self):
        for salto in ("\n", "\r\n"):
            with self.subTest(salto=repr(salto)):
                original = (json.dumps(AJENOS, indent=2) + "\n").replace("\n", salto).encode()
                self.claude.mkdir(parents=True, exist_ok=True)
                self.settings.write_bytes(original)
                self.destino.mkdir(parents=True, exist_ok=True)
                (self.destino / "mascota.py").write_text("")
                self.instalar()
                self.assertEqual(b"\r\n" in self.settings.read_bytes(), salto == "\r\n")
                self.desinstalar()
                self.assertEqual(self.settings.read_bytes(), original)

    def test_reinstalar_no_duplica(self):
        self.escribir(AJENOS)
        self.instalar()
        self.instalar()
        for evento in instalador.HOOKS:
            self.assertEqual(len(self.nuestros(self.leer(), evento)), 1, evento)
        self.desinstalar()
        self.assertEqual(self.leer(), AJENOS)

    def test_sin_settings_lo_crea_y_lo_borra(self):
        self.instalar()
        self.assertEqual(set(self.leer()["hooks"]), set(instalador.HOOKS))
        self.assertEqual(self.backups(), [])
        self.desinstalar()
        self.assertFalse(self.settings.exists())

    def test_settings_creado_y_despues_editado_se_conserva(self):
        self.instalar()
        datos = self.leer()
        datos["model"] = "sonnet"
        self.escribir(datos)
        self.desinstalar()
        self.assertEqual(self.leer(), {"model": "sonnet"})

    def test_hooks_vacios_previos_se_respetan(self):
        self.escribir({"hooks": {"Stop": []}})
        self.instalar()
        self.desinstalar()
        self.assertEqual(self.leer(), {"hooks": {"Stop": []}})

    def test_json_invalido_no_se_toca(self):
        self.escribir('{"hooks": {"Stop": [ }')
        antes = self.settings.read_bytes()
        with self.assertRaises(instalador.ErrorInstalacion):
            self.instalar()
        self.assertEqual(self.settings.read_bytes(), antes)
        self.assertEqual(self.backups(), [])

    def test_reemplaza_una_version_anterior_y_la_repone(self):
        original = json.loads(json.dumps(AJENOS))
        original["hooks"]["Stop"].append({"hooks": [{"type": "command", "command": VIEJA, "timeout": 10}]})
        original["hooks"]["Notification"][0]["hooks"].append(  # mezclado con un hook tuyo
            {"type": "command", "command": VIEJA.replace("listo", "permiso")})
        self.escribir(original)
        self.instalar()
        nuevo = self.leer()
        self.assertNotIn(VIEJA, json.dumps(nuevo))  # una sola mascota por evento
        self.assertEqual(len(self.nuestros(nuevo, "Stop")), 1)
        self.assertIn("notify-send hola", json.dumps(nuevo))
        self.desinstalar()
        self.assertEqual(hooks_planos(self.leer()), hooks_planos(original))

    def test_comando_mascota(self):
        self.escribir(AJENOS)
        self.instalar()
        comando = self.claude / "commands" / "wavemascot.md"
        texto = comando.read_text(encoding="utf-8")
        self.assertIn(instalador.MARCA, texto)
        self.assertIn("ajustes.py", texto)
        self.desinstalar()
        self.assertFalse(comando.exists())

    def test_no_pisa_un_comando_mascota_propio(self):
        comando = self.claude / "commands" / "wavemascot.md"
        comando.parent.mkdir(parents=True)
        comando.write_text("mi comando", encoding="utf-8")
        self.instalar()
        self.desinstalar()
        self.assertEqual(comando.read_text(encoding="utf-8"), "mi comando")

    @unittest.skipUnless(os.name == "nt", "rutas de Windows")
    def test_comando_con_espacios_lleva_comillas(self):
        texto = instalador.linea_de_comando([r"C:\Program Files\Python\pythonw.exe", r"C:\x\mascota.py"],
                                            "--estado", "listo")
        self.assertEqual(texto, '"C:/Program Files/Python/pythonw.exe" "C:/x/mascota.py" --estado listo')

    def test_no_borra_carpetas_que_no_creo(self):
        repo = Path(self.tmp.name) / "repo"
        (repo / ".git").mkdir(parents=True)
        instalador.configurar("fuente", repo, self.claude, sin_inicio=True)
        instalador.desinstalar(repo, self.claude)
        self.assertTrue(repo.exists())



class InstaladorMac(Instalador):
    """Lo mismo para WaveMascot.app (macOS). Corre en cualquier sistema: solo cambian rutas y archivos."""

    def setUp(self):
        super().setUp()
        self.mac = mock.patch.object(instalador, "MAC", True)
        self.mac.start()
        self.app = Path(self.tmp.name) / "Applications" / "WaveMascot.app"
        self.crear_app(self.app)

    def tearDown(self):
        self.mac.stop()
        super().tearDown()

    @staticmethod
    def crear_app(app: Path) -> None:
        (app / "Contents" / "MacOS").mkdir(parents=True)
        (app / "Contents" / "MacOS" / "WaveMascot").write_text("")

    def instalar_app(self, app=None, sin_inicio=False):
        return instalador.configurar("exe", app or self.app, self.claude, sin_inicio=sin_inicio)

    def test_hooks_de_la_app_no_fallan_si_la_borran(self):
        self.escribir(AJENOS)
        self.instalar_app()
        hooks = self.nuestros(self.leer(), "Stop")
        self.assertEqual(len(hooks), 1)
        comando = hooks[0]["command"]
        exe = (self.app.resolve() / "Contents" / "MacOS" / "WaveMascot").as_posix()
        self.assertTrue(comando.startswith(f"[ -e {shlex.quote(exe)} ] && "), comando)
        self.assertTrue(comando.endswith("--estado listo || true"), comando)

    def test_agente_de_inicio_manifiesto_y_desinstalar(self):
        self.escribir(AJENOS)
        self.instalar_app()
        agente = Path(self.tmp.name) / "Library" / "LaunchAgents" / f"{instalador.BUNDLE_ID}.plist"
        datos = plistlib.loads(agente.read_bytes())
        self.assertEqual(datos["Label"], instalador.BUNDLE_ID)
        self.assertEqual(datos["ProgramArguments"][1:], ["bandeja"])
        self.assertEqual(Path(datos["ProgramArguments"][0]), self.app.resolve() / "Contents" / "MacOS" / "WaveMascot")
        manifiesto = Path(self.tmp.name) / ".wavemascot" / "instalacion.json"
        self.assertTrue(manifiesto.exists())  # fuera de la app: modificarla por dentro rompería su firma
        self.assertEqual(list(self.app.rglob("instalacion.json")), [])
        with mock.patch.object(instalador.subprocess, "run") as correr:
            instalador.desinstalar(self.app, self.claude)
        self.assertEqual(self.leer(), AJENOS)
        self.assertFalse(agente.exists())
        self.assertFalse(manifiesto.exists())
        self.assertFalse(self.app.exists())
        self.assertIn("launchctl", " ".join(correr.call_args[0][0]))

    def test_app_movida_de_lugar_no_repone_sus_hooks_viejos(self):
        self.escribir(AJENOS)
        self.instalar_app()
        nueva = Path(self.tmp.name) / "Users" / "x" / "Applications" / "WaveMascot.app"
        self.crear_app(nueva)
        self.instalar_app(nueva)
        texto = json.dumps(self.leer())
        self.assertNotIn(self.app.resolve().as_posix(), texto)
        self.assertEqual(len(self.nuestros(self.leer(), "Stop")), 1)
        with mock.patch.object(instalador.subprocess, "run"):
            instalador.desinstalar(nueva, self.claude)
        self.assertEqual(self.leer(), AJENOS)  # sin hooks que apunten a la app que ya no está

    def test_no_borra_una_app_que_no_instalo(self):
        otra = Path(self.tmp.name) / "Otra" / "WaveMascot.app"
        self.crear_app(otra)
        self.instalar_app()  # el manifiesto de ~/.wavemascot es de self.app
        with mock.patch.object(instalador.subprocess, "run"):
            informe = instalador.desinstalar(otra, self.claude)
        self.assertTrue(otra.exists())
        self.assertTrue(any("no la creó" in linea or "didn't create" in linea for linea in informe))

    @unittest.skipIf(os.name == "nt", "usa sh")
    def test_hook_con_espacios_corre_en_sh(self):
        app = Path(self.tmp.name) / "Con espacios" / "WaveMascot.app"
        self.crear_app(app)
        exe = app / "Contents" / "MacOS" / "WaveMascot"
        exe.write_text('#!/bin/sh\necho "corrio $*"\n')
        exe.chmod(0o755)
        comando = instalador.comando_hook("exe", app, "listo")
        r = subprocess.run(["/bin/sh", "-c", comando], capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "corrio --estado listo"))
        exe.unlink()  # la app ya no está: el hook no hace nada y no falla
        r = subprocess.run(["/bin/sh", "-c", comando], capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))


if __name__ == "__main__":
    unittest.main()
