"""La lectura de la salida de git de repos.py (sin correr git): python -m unittest discover tests"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
import repos  # noqa: E402

WORKTREES = """worktree A:/waveapp/mascota-claude
HEAD c61e64a66c27ec95d6f1042b207880faf5002795
branch refs/heads/main

worktree A:/waveapp/mascota-isla
HEAD 0664ffd2cc34adbd49c81e5299ae25934873941a
detached

worktree A:/waveapp/mascota-vieja
HEAD 41ce0ab0000000000000000000000000000000000
branch refs/heads/remaster-sobrio
prunable gitdir file points to non-existent location
"""

REFS = "\n".join([
    "refs/heads/main\x00refs/remotes/origin/main\x00[behind 3]\x001792806612\x00",
    "refs/heads/nueva\x00refs/remotes/origin/main\x00[ahead 2]\x001792806000\x00",
    "refs/heads/vieja\x00refs/remotes/origin/vieja\x00[gone]\x001792000000\x00",
    "refs/heads/subida\x00refs/remotes/origin/subida\x00[ahead 1, behind 4]\x001792800000\x00",
    "refs/remotes/origin/HEAD\x00\x00\x001792806612\x00refs/remotes/origin/main",
    "refs/remotes/origin/main\x00\x00\x001792806612\x00",
    "refs/remotes/origin/subida\x00\x00\x001792800000\x00",
])


class Parsear(unittest.TestCase):
    def test_worktrees(self):
        lista = repos.parsear_worktrees(WORKTREES)
        self.assertEqual([w["ruta"] for w in lista], ["A:/waveapp/mascota-claude", "A:/waveapp/mascota-isla",
                                                       "A:/waveapp/mascota-vieja"])
        self.assertEqual(lista[0]["rama"], "main")
        self.assertTrue(lista[1]["detached"])
        self.assertEqual(lista[1]["rama"], "")
        self.assertTrue(lista[2]["prunable"])

    def test_track(self):
        self.assertEqual(repos.parsear_track("[ahead 2, behind 1]"), (2, 1, False))
        self.assertEqual(repos.parsear_track("[behind 17]"), (0, 17, False))
        self.assertEqual(repos.parsear_track("[gone]"), (0, 0, True))
        self.assertEqual(repos.parsear_track(""), (0, 0, False))

    def test_refs_y_base(self):
        locales, remotas = repos.parsear_refs(REFS)
        self.assertEqual([r["nombre"] for r in locales], ["main", "nueva", "vieja", "subida"])
        self.assertEqual(locales[3]["sin_subir"], 1)
        self.assertEqual(locales[3]["sin_bajar"], 4)
        self.assertTrue(locales[2]["borrada"])
        self.assertEqual(repos.elegir_base(remotas, ["main"]), "refs/remotes/origin/main")
        # sin origin/HEAD: main o master, del remoto antes que local
        self.assertEqual(repos.elegir_base({"refs/remotes/origin/master": ""}, ["master"]), "refs/remotes/origin/master")
        self.assertEqual(repos.elegir_base({}, ["dev", "master"]), "refs/heads/master")
        self.assertEqual(repos.elegir_base({}, ["dev"]), "refs/heads/dev")
        self.assertEqual(repos.elegir_base({}, []), "")

    def test_divergencia(self):
        texto = "refs/heads/main\x000 3\nrefs/heads/nueva\x002 0\nrefs/heads/rota\x00\n"
        self.assertEqual(repos.parsear_divergencia(texto), {"main": (0, 3), "nueva": (2, 0)})

    def test_remoto(self):
        self.assertEqual(repos.nombre_remoto("https://github.com/Marescaa/wavemascot.git"),
                         ("Marescaa/wavemascot", "https://github.com/Marescaa/wavemascot"))
        self.assertEqual(repos.nombre_remoto("git@github.com:Marescaa/catfolio.git\n"),
                         ("Marescaa/catfolio", "https://github.com/Marescaa/catfolio"))
        self.assertEqual(repos.nombre_remoto("git@gitlab.com:alguien/cosa.git"), ("gitlab.com/alguien/cosa", ""))
        self.assertEqual(repos.nombre_remoto(r"C:\repos\app.git"), ("app", ""))
        self.assertEqual(repos.nombre_remoto("/srv/git/app.git"), ("app", ""))
        self.assertEqual(repos.nombre_remoto("https://gitlab.com/alguien/cosa.git"),
                         ("gitlab.com/alguien/cosa", "https://gitlab.com/alguien/cosa"))

    def test_cwd_y_wsl(self):
        texto = '{"type":"user","cwd":"A:\\\\waveapp","sessionId":"x"}\n'
        self.assertEqual(repos.cwd_de(texto), "A:\\waveapp")
        self.assertEqual(repos.cwd_de('{"type":"summary"}'), "")
        self.assertEqual(repos.de_wsl("\\\\wsl.localhost\\Ubuntu\\home\\yo\\app"), ("Ubuntu", "/home/yo/app"))
        self.assertEqual(repos.de_wsl("//wsl$/Debian/srv"), ("Debian", "/srv"))
        self.assertIsNone(repos.de_wsl("A:\\waveapp"))
        self.assertTrue(repos.IGNORAR.search("C:\\Users\\yo\\AppData\\Local\\Temp\\claude\\x"))
        self.assertFalse(repos.IGNORAR.search("A:\\waveapp"))


class Rama(unittest.TestCase):
    def test_estados(self):
        local = repos.Rama("nueva", adelante=2)
        self.assertEqual(local.estado, "local")
        self.assertEqual(local.pendientes, 2)
        self.assertFalse(local.mergeada)
        vacia = repos.Rama("vacia")
        self.assertTrue(vacia.mergeada)
        self.assertFalse(vacia.en_uso)  # sin carpeta y sin nada propio: va con las viejas
        subida = repos.Rama("x", en_remoto=True, arriba="origin/x", sin_subir=3, adelante=5)
        self.assertEqual((subida.estado, subida.pendientes), ("sin_subir", 3))
        self.assertEqual(repos.Rama("y", en_remoto=True, arriba="origin/y", sin_bajar=1).estado, "sin_bajar")
        self.assertEqual(repos.Rama("z", borrada=True).estado, "borrada")
        self.assertFalse(repos.Rama("main", base=True).mergeada)


@unittest.skipIf(not shutil.which("git"), "sin git")
class RepoDeVerdad(unittest.TestCase):
    """Un repo de prueba con un remoto local: main, una rama sin subir, una nueva desde origin/main, un
    worktree con un archivo sin commitear y una rama ya mergeada."""

    def setUp(self):
        self.registrado = []
        self.registrar = repos.registrar
        repos.registrar = self.registrado.append  # nunca al log de la app de verdad

    def tearDown(self):
        repos.registrar = self.registrar

    def git(self, *args, donde=None):
        subprocess.run(["git", "-C", str(donde or self.repo), *args], check=True, capture_output=True,
                       env=dict(os.environ, GIT_AUTHOR_NAME="a", GIT_AUTHOR_EMAIL="a@a", GIT_COMMITTER_NAME="a",
                                GIT_COMMITTER_EMAIL="a@a"))

    def commit(self, nombre, donde=None):
        (Path(donde or self.repo) / nombre).write_text(nombre)
        self.git("add", nombre, donde=donde)
        self.git("commit", "-qm", nombre, donde=donde)

    def test_lee_un_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            remoto, self.repo = tmp / "remoto.git", tmp / "app"
            self.git("init", "-q", "--bare", "-b", "main", str(remoto), donde=tmp)
            self.git("init", "-q", "-b", "main", str(self.repo), donde=tmp)
            self.commit("uno")
            self.git("remote", "add", "origin", str(remoto))
            self.git("push", "-q", "-u", "origin", "main")
            self.git("branch", "mergeada")
            self.git("switch", "-qc", "local")
            self.commit("dos")
            self.git("switch", "-q", "main")
            self.git("worktree", "add", "-q", "-b", "nueva", str(tmp / "app-nueva"), "origin/main")
            (tmp / "app-nueva" / "suelto.txt").write_text("x")
            proyectos = repos.Proyectos(tmp / "sin-transcripts")
            comun = proyectos.comun_de(str(self.repo))
            repo = proyectos.leer_repo(comun, str(self.repo), 0.0)
            self.assertEqual(repo.error, "")
            self.assertEqual(repo.base, "origin/main")
            ramas = {r.nombre: r for r in repo.ramas}
            self.assertTrue(ramas["main"].base)
            self.assertEqual(ramas["main"].estado, "subida")
            self.assertEqual((ramas["local"].estado, ramas["local"].pendientes), ("local", 1))
            # hecha desde origin/main: lo sigue, pero ella no está en GitHub
            self.assertEqual(ramas["nueva"].estado, "local")
            self.assertEqual(ramas["nueva"].carpeta.cambios, 1)
            self.assertTrue(ramas["mergeada"].mergeada)
            self.assertEqual(repo.para_limpiar, 1)
            self.assertEqual(repo.sin_subir, 1)
            self.assertEqual(repo.cambios, 1)
            self.assertEqual(len(repo.carpetas), 2)
            self.assertEqual(comun, proyectos.comun_de(str(tmp / "app-nueva")))  # los worktrees se juntan

    def armar(self, tmp: Path) -> Path:
        """app (main subido) con su remoto; devuelve el remoto."""
        remoto, self.repo = tmp / "remoto.git", tmp / "app"
        self.git("init", "-q", "--bare", "-b", "main", str(remoto), donde=tmp)
        self.git("init", "-q", "-b", "main", str(self.repo), donde=tmp)
        self.commit("uno")
        self.git("remote", "add", "origin", str(remoto))
        self.git("push", "-q", "-u", "origin", "main")
        return remoto

    def test_el_fetch_nunca_borra(self):
        """Aunque el repo tenga remote.origin.prune, la rama borrada en GitHub sigue en refs/remotes."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self.armar(tmp)
            self.git("switch", "-qc", "x")
            self.commit("dos")
            self.git("push", "-q", "-u", "origin", "x")
            self.git("config", "remote.origin.prune", "true")
            self.git("config", "fetch.prune", "true")
            self.git("push", "-q", "origin", "--delete", "x")
            self.git("update-ref", "refs/remotes/origin/x", "refs/heads/x")  # como si nadie hubiera podado
            proyectos = repos.Proyectos(tmp / "nada")
            repo = proyectos.leer_repo(proyectos.comun_de(str(self.repo)), str(self.repo), 0.0, True, True)
            self.assertEqual(repo.aviso, "")
            salida = subprocess.run(["git", "-C", str(self.repo), "for-each-ref", "refs/remotes/origin/x"],
                                    capture_output=True, text=True).stdout
            self.assertIn("refs/remotes/origin/x", salida)
            self.assertIsNotNone(repo.revisado)

    def test_fetch_head_de_un_worktree(self):
        """El fetch desde un worktree escribe su propio FETCH_HEAD: igual cuenta como revisado."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self.armar(tmp)
            self.git("worktree", "add", "-q", "-b", "otra", str(tmp / "app-wt"))
            proyectos = repos.Proyectos(tmp / "nada")
            comun = proyectos.comun_de(str(tmp / "app-wt"))
            repo = proyectos.leer_repo(comun, str(tmp / "app-wt"), 0.0, True, True)
            self.assertIsNotNone(repo.revisado)

    def test_un_fetch_que_falla_no_esconde_las_ramas(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self.armar(tmp)
            self.git("remote", "set-url", "origin", str(tmp / "no-existe.git"))
            proyectos = repos.Proyectos(tmp / "nada")
            comun = proyectos.comun_de(str(self.repo))
            repo = proyectos.leer_repo(comun, str(self.repo), 0.0, True, True)
            self.assertEqual((repo.error, repo.aviso), ("", "fetch"))
            self.assertEqual([r.nombre for r in repo.ramas], ["main"])
            # en la vuelta siguiente no se vuelve a intentar (espera 5 min), pero la nota sigue
            self.assertEqual(proyectos.leer_repo(comun, str(self.repo), 0.0, True, False).aviso, "fetch")
            self.assertTrue(self.registrado)  # fue al log (de mentira)
            self.git("remote", "remove", "origin")  # sin remoto ya no hay nota
            self.assertEqual(proyectos.leer_repo(comun, str(self.repo), 0.0, True, False).aviso, "")

    def test_errores_de_git_legibles_y_opcion_desconocida(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self.armar(tmp)
            with self.assertRaises(repos.ErrorGit) as error:
                repos.Git(str(self.repo)).correr("fetch", "--opcion-que-no-existe", "origin")
            self.assertTrue(str(error.exception).startswith(("error:", "fatal:")), str(error.exception))
            self.assertIn("usage:", error.exception.detalle)
            self.assertEqual(repos.linea_importante("remote: x\nfatal: no anda\nhint: probá"), "fatal: no anda")
            # un git viejo que no conoce --no-auto-maintenance: se repite sin esas opciones
            original = repos.Git.correr

            def viejo(git, *args, **kw):
                if "--no-auto-maintenance" in args:
                    raise repos.ErrorGit("error: unknown option `no-auto-maintenance'", "usage: git fetch ...")
                return original(git, *args, **kw)

            repos.Git.correr = viejo
            try:
                repos.Proyectos.fetch(repos.Git(str(self.repo)), "origin")
            finally:
                repos.Git.correr = original

    def test_git_viejo_y_errores_pasajeros(self):
        """Antes de 2.31 rev-parse no conoce --path-format (lo devuelve como texto): sin él, cada repo tiene
        su clave. Y un error pasajero (no "no es un repo") se vuelve a probar."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for nombre in ("uno", "dos"):
                self.git("init", "-q", str(tmp / nombre), donde=tmp)
            proyectos = repos.Proyectos(tmp / "nada")
            claves = {proyectos.comun_de(str(tmp / n)) for n in ("uno", "dos")}
            real = (lambda r: str(r)) if os.name == "nt" else os.path.realpath  # macOS: /var -> /private/var
            self.assertEqual(claves, {real(tmp / "uno" / ".git"), real(tmp / "dos" / ".git")})
            original, llamadas = repos.Git.correr, []

            def lento(git, *args, **kw):
                llamadas.append(args)
                if len(llamadas) == 1:
                    raise repos.ErrorGit("git rev-parse tardó más de 20 s")
                return original(git, *args, **kw)

            repos.Git.correr = lento
            try:
                otra = repos.Proyectos(tmp / "nada")
                self.assertEqual(otra.comun_de(str(tmp / "uno")), "")
                self.assertEqual(otra.comun_de(str(tmp / "uno")), real(tmp / "uno" / ".git"))
            finally:
                repos.Git.correr = original
            self.assertEqual(proyectos.comun_de(str(tmp)), "")  # no es un repo: eso sí se recuerda
            self.assertEqual(proyectos.comunes[str(tmp)], "")

    def test_casos_raros(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self.armar(tmp)
            # sigue a origin/user/fix: no es "su" rama de GitHub
            self.git("push", "-q", "origin", "main:user/fix")
            self.git("fetch", "-q")
            self.git("branch", "-q", "--track", "fix", "origin/user/fix")
            # un worktree cuya carpeta se borró
            self.git("worktree", "add", "-q", "-b", "gone/wt", str(tmp / "borrada"))
            shutil.rmtree(tmp / "borrada")
            proyectos = repos.Proyectos(tmp / "nada")
            repo = proyectos.leer_repo(proyectos.comun_de(str(self.repo)), str(self.repo), 0.0)
            ramas = {r.nombre: r for r in repo.ramas}
            self.assertEqual(ramas["fix"].estado, "local")
            self.assertIsNone(ramas["gone/wt"].carpeta)
            self.assertFalse(ramas["gone/wt"].en_uso)
            self.assertTrue([c for c in repo.carpetas if c.perdida])

    def test_si_no_se_puede_comparar_no_se_da_por_mergeada(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self.armar(tmp)
            self.git("switch", "-qc", "trabajo")
            self.commit("dos")
            self.commit("tres")
            proyectos = repos.Proyectos(tmp / "nada")
            original = repos.Git.correr

            def rota(git, *args, **kw):
                if any("ahead-behind" in a for a in args) or args[0] == "rev-list":
                    raise repos.ErrorGit("tardó demasiado")
                return original(git, *args, **kw)

            repos.Git.correr = rota
            try:
                repo = proyectos.leer_repo(proyectos.comun_de(str(self.repo)), str(self.repo), 0.0)
            finally:
                repos.Git.correr = original
            trabajo = next(r for r in repo.ramas if r.nombre == "trabajo")
            self.assertTrue(trabajo.incierta)
            self.assertFalse(trabajo.mergeada)
            self.assertTrue(trabajo.en_uso)
            self.assertEqual(repo.para_limpiar, 0)

    def test_sin_remoto_no_hay_nada_sin_subir(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self.repo = tmp / "solo"
            self.git("init", "-q", "-b", "master", str(self.repo), donde=tmp)
            self.commit("uno")
            self.git("switch", "-qc", "feat/x/y")
            self.commit("dos")
            proyectos = repos.Proyectos(tmp / "nada")
            repo = proyectos.leer_repo(proyectos.comun_de(str(self.repo)), str(self.repo), 0.0)
            self.assertEqual(repo.base, "master")
            self.assertEqual(repo.sin_subir, 0)
            self.assertEqual(next(r for r in repo.ramas if r.nombre == "feat/x/y").adelante, 1)

    def test_principal_con_barra(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self.armar(tmp)
            self.git("switch", "-qc", "release/v2")
            self.git("push", "-q", "-u", "origin", "release/v2")
            self.git("branch", "-q", "v2")
            self.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/release/v2")
            proyectos = repos.Proyectos(tmp / "nada")
            repo = proyectos.leer_repo(proyectos.comun_de(str(self.repo)), str(self.repo), 0.0)
            ramas = {r.nombre: r for r in repo.ramas}
            self.assertTrue(ramas["release/v2"].base)
            self.assertFalse(ramas["v2"].base)

    def test_transcript_vacio_se_vuelve_a_leer(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            carpeta = tmp / "projects" / "x"
            carpeta.mkdir(parents=True)
            (carpeta / "a.jsonl").write_text("")
            proyectos = repos.Proyectos(tmp / "projects")
            self.assertEqual(proyectos.carpetas_usadas(), {})
            (carpeta / "a.jsonl").write_text('{"cwd":"A:\\\\proyecto"}\n')
            self.assertEqual(list(proyectos.carpetas_usadas()), ["A:\\proyecto"])

    def test_wsl_apagado_no_se_toca(self):
        """Una carpeta de WSL con la distribución apagada: ni un acceso al disco (la prendería)."""
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp) / "projects" / "x"
            carpeta.mkdir(parents=True)
            cwd = "\\\\wsl.localhost\\Ubuntu\\home\\yo\\app"
            (carpeta / "a.jsonl").write_text(json.dumps({"cwd": cwd}) + "\n")
            proyectos = repos.Proyectos(Path(tmp) / "projects")
            tocadas = []
            originales = (repos.sys.platform, repos.wsl_prendidas, repos.os.path.isdir)
            repos.sys.platform = "win32"
            repos.wsl_prendidas = lambda: set()
            repos.os.path.isdir = lambda r: tocadas.append(r) or False
            proyectos.raiz_de = lambda r: tocadas.append(r) or ""
            proyectos.subcarpetas_repo = lambda r: tocadas.append(r) or []
            try:
                lista = proyectos.leer()
            finally:
                repos.sys.platform, repos.wsl_prendidas, repos.os.path.isdir = originales
            self.assertEqual(tocadas, [])
            self.assertEqual([(r.nombre, r.error) for r in lista], [("app", "wsl")])

    @unittest.skipUnless(os.name == "nt" and Path(r"C:\Program Files\Git\cmd\git.exe").exists(), "solo Windows")
    def test_el_tiempo_limite_corta_todo(self):
        """Con el git.exe de Git\\cmd (un lanzador), cortar solo a git dejaba a ssh colgado de las tuberías."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self.repo = tmp / "app"
            self.git("init", "-q", str(self.repo), donde=tmp)
            self.git("remote", "add", "origin", "ssh://git@example.invalid/x.git")
            self.git("config", "core.sshCommand", "sh -c 'sleep 25' x")
            camino = os.environ["PATH"]
            os.environ["PATH"] = r"C:\Program Files\Git\cmd;" + camino
            try:
                inicio = time.monotonic()
                with self.assertRaises(repos.ErrorGit):
                    repos.Git(str(self.repo)).correr("fetch", "--quiet", "origin", tiempo=3)
                self.assertLess(time.monotonic() - inicio, 10)
            finally:
                os.environ["PATH"] = camino


if __name__ == "__main__":
    unittest.main()
