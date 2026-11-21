"""Proyectos: las ramas, las carpetas (worktrees) y qué está subido de cada repo con el que trabajás.

Los proyectos salen de las carpetas donde usaste Claude Code (el "cwd" de cada transcript). Si una de esas
carpetas no es un repo, se miran sus subcarpetas directas (A:/proyectos/app-1, app-2...). Los worktrees de un
mismo repo se juntan en un solo proyecto (los agrupa su carpeta .git común).

Todo es de solo lectura, y con cuidado porque otras sesiones trabajan en esas carpetas al mismo tiempo:
- `--no-optional-locks` en cada llamada: `git status` no refresca el índice ni toma index.lock, así no le
  hace fallar un commit a nadie.
- `git fetch` (lo único que va a la red) solo cada tanto, sin pedir contraseñas y nunca con --prune.
- Los repos de WSL se leen con el git de adentro de WSL (leerlos desde Windows tarda 100 veces más), y solo
  si WSL ya está prendido: abrir los ajustes no lo arranca.

La parte de leer la salida de git son funciones puras (parsear_*), probadas en tests/test_repos.py.
"""

from __future__ import annotations

import json
import os
import posixpath
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

TIEMPO = 20           # segundos máximos por comando de git
TIEMPO_FETCH = 40
CADA_FETCH = 5 * 60   # cada cuánto se pregunta a GitHub (mientras se mira la sección)
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # sin esto pythonw abre una consola por llamada
# En inglés (para leer "[ahead 2, behind 1]"), sin pedir nada por consola ni por ventana, sin locks opcionales.
ENTORNO = {"LC_ALL": "C", "LANGUAGE": "C", "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never",
           "GIT_OPTIONAL_LOCKS": "0", "SSH_ASKPASS_REQUIRE": "never"}
WSL = re.compile(r"^[\\/]{2}wsl(?:\.localhost|\$)[\\/]([^\\/]+)(.*)$", re.IGNORECASE)
GITHUB = re.compile(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?/?$", re.IGNORECASE)
CWD = re.compile(r'"cwd"\s*:\s*"((?:[^"\\]|\\.)*)"')
# Carpetas que no son proyectos: las temporales de Claude y de Windows.
IGNORAR = re.compile(r"[\\/](?:AppData[\\/]Local[\\/]Temp|scratch-workspaces|scratchpad)(?:[\\/]|$)", re.IGNORECASE)


class ErrorGit(Exception):
    """El mensaje es la línea que importa ("fatal: ..."); detalle, todo lo que git escribió en stderr."""

    def __init__(self, mensaje: str, detalle: str = ""):
        super().__init__(mensaje)
        self.detalle = detalle or mensaje


def registrar(texto: str) -> None:
    """Al log de la app (los tests lo reemplazan para no escribir en el log de verdad)."""
    import mascota
    mascota.log(texto)


def linea_importante(errores: str) -> str:
    """De todo lo que git escribió en stderr, la línea que explica el problema: la primera "fatal:" o
    "error:" (al final suele venir la ayuda de uso o una pista, que no dicen nada)."""
    lineas = [linea.strip() for linea in errores.strip().splitlines() if linea.strip()]
    return next((linea for linea in lineas if linea.startswith(("fatal:", "error:"))), lineas[0] if lineas else "")


class SinGit(ErrorGit):
    """git no está instalado (o no está en el PATH)."""


# ---------------------------------------------------------------------------------------------- datos

@dataclass
class Carpeta:
    """Un worktree: una carpeta con una rama puesta."""
    ruta: str              # como se abre en esta compu
    rama: str = ""         # "" si está en un commit suelto (detached)
    cambios: int = 0       # archivos modificados o nuevos sin commitear
    principal: bool = False
    perdida: bool = False  # git la recuerda pero la carpeta ya no está ("prunable")

    @property
    def nombre(self) -> str:
        return re.split(r"[\\/]", self.ruta.rstrip("\\/"))[-1] or self.ruta


@dataclass
class Rama:
    nombre: str
    fecha: float = 0.0     # último commit (unix)
    arriba: str = ""       # la rama de GitHub que sigue (origin/x), si sigue alguna
    sin_subir: int = 0     # commits que están acá y no en GitHub
    sin_bajar: int = 0     # commits que están en GitHub y no acá
    borrada: bool = False  # seguía una rama de GitHub que ya no existe
    en_remoto: bool = False
    adelante: int = 0      # contra la rama principal (origin/main)
    atras: int = 0
    base: bool = False     # es la rama principal
    carpeta: Carpeta | None = None
    incierta: bool = False  # no se pudo comparar (git falló o tardó): nunca se da por mergeada

    @property
    def mergeada(self) -> bool:
        """Todo lo suyo ya está en la principal."""
        return not self.base and not self.incierta and self.adelante == 0

    @property
    def estado(self) -> str:
        """Una palabra para la pastilla: local, borrada, sin_subir, sin_bajar o subida."""
        if self.borrada:
            return "borrada"
        if not self.en_remoto:
            return "local"
        if self.sin_subir:
            return "sin_subir"
        if self.sin_bajar:
            return "sin_bajar"
        return "subida"

    @property
    def pendientes(self) -> int:
        """Commits que se perderían si se borrara esta compu: los sin subir (o todos los suyos si es local)."""
        if self.estado in ("local", "borrada"):
            return 0 if self.mergeada else self.adelante
        return self.sin_subir

    @property
    def en_uso(self) -> bool:
        """Se muestra arriba: la principal, las que tienen carpeta y las que tienen algo propio."""
        return self.base or self.carpeta is not None or not self.mergeada or self.pendientes > 0


@dataclass
class Repo:
    clave: str                 # la carpeta .git común, normalizada
    nombre: str
    remoto: str = ""           # "usuario/repo" (o el servidor, si no es GitHub)
    web: str = ""              # la página en GitHub
    base: str = ""             # contra qué se mide (origin/main)
    base_rama: str = ""        # el nombre de esa rama, sin el remoto (main)
    ramas: list[Rama] = field(default_factory=list)
    carpetas: list[Carpeta] = field(default_factory=list)
    revisado: float | None = None   # cuándo se preguntó a GitHub por última vez (FETCH_HEAD)
    actividad: float = 0.0     # cuándo se usó Claude Code ahí por última vez
    ruta: str = ""             # la carpeta por la que se entró (se muestra si no se pudo leer más)
    error: str = ""            # no se pudo leer ("wsl": la distribución está apagada)
    aviso: str = ""            # se leyó, pero algo menor falló ("fetch": no se pudo preguntar a GitHub)

    @property
    def sin_subir(self) -> int:
        """Commits que no están en GitHub. Un repo sin remoto no tiene adónde subir: 0."""
        return sum(r.pendientes for r in self.ramas) if self.remoto else 0

    @property
    def cambios(self) -> int:
        return sum(c.cambios for c in self.carpetas)

    @property
    def para_limpiar(self) -> int:
        """Ramas que ya están enteras en la principal y no tienen carpeta: se podrían borrar."""
        return sum(1 for r in self.ramas if r.mergeada and r.carpeta is None and not r.pendientes)


# ------------------------------------------------------------------------------- lectura (puras)

def parsear_worktrees(texto: str) -> list[dict]:
    """La salida de `git worktree list --porcelain`: [{ruta, rama, detached, prunable, bare}]."""
    lista, actual = [], None
    for linea in texto.splitlines():
        if linea.startswith("worktree "):
            actual = {"ruta": linea[9:], "rama": "", "detached": False, "prunable": False, "bare": False}
            lista.append(actual)
        elif actual is None:
            continue
        elif linea.startswith("branch "):
            actual["rama"] = linea[7:].removeprefix("refs/heads/")
        elif linea == "detached":
            actual["detached"] = True
        elif linea == "bare":
            actual["bare"] = True
        elif linea.startswith("prunable"):
            actual["prunable"] = True
    return lista


def parsear_track(texto: str) -> tuple[int, int, bool]:
    """"[ahead 2, behind 1]" -> (2, 1, False); "[gone]" -> (0, 0, True)."""
    adelante = re.search(r"ahead (\d+)", texto)
    atras = re.search(r"behind (\d+)", texto)
    return (int(adelante.group(1)) if adelante else 0, int(atras.group(1)) if atras else 0, "gone" in texto)


FORMATO_REFS = "%(refname)%00%(upstream)%00%(upstream:track)%00%(committerdate:unix)%00%(symref)"


def parsear_refs(texto: str) -> tuple[list[dict], dict[str, str]]:
    """La salida de for-each-ref con FORMATO_REFS: (ramas locales, {ref remota: a qué apunta})."""
    locales, remotas = [], {}
    for linea in texto.splitlines():
        partes = linea.split("\x00")
        if len(partes) < 5:
            continue
        ref, arriba, track, fecha, symref = partes[:5]
        if ref.startswith("refs/heads/"):
            sube, baja, borrada = parsear_track(track)
            locales.append({"nombre": ref[11:], "arriba": arriba, "sin_subir": sube, "sin_bajar": baja,
                            "borrada": borrada, "fecha": float(fecha or 0)})
        elif ref.startswith("refs/remotes/"):
            remotas[ref] = symref
    return locales, remotas


def elegir_base(remotas: dict[str, str], locales: list[str], remoto: str = "origin") -> str:
    """Contra qué rama se mide todo: la que GitHub marca como principal, o main / master."""
    cabeza = remotas.get(f"refs/remotes/{remoto}/HEAD")
    if cabeza:
        return cabeza
    for nombre in ("main", "master"):
        if f"refs/remotes/{remoto}/{nombre}" in remotas:
            return f"refs/remotes/{remoto}/{nombre}"
    for nombre in ("main", "master"):
        if nombre in locales:
            return f"refs/heads/{nombre}"
    return f"refs/heads/{locales[0]}" if locales else ""


def parsear_divergencia(texto: str) -> dict[str, tuple[int, int]]:
    """for-each-ref con %(refname)%00%(ahead-behind:base): {rama: (adelante, atrás)}."""
    res = {}
    for linea in texto.splitlines():
        ref, _, cuentas = linea.partition("\x00")
        numeros = cuentas.split()
        if ref.startswith("refs/heads/") and len(numeros) == 2:
            res[ref[11:]] = (int(numeros[0]), int(numeros[1]))
    return res


def nombre_remoto(url: str) -> tuple[str, str]:
    """La URL del remoto -> ("usuario/repo", página web). Si no es GitHub: (servidor/ruta, "")."""
    url = url.strip()
    encontrado = GITHUB.search(url)
    if encontrado:
        usuario, repo = encontrado.groups()
        return f"{usuario}/{repo}", f"https://github.com/{usuario}/{repo}"
    if re.match(r"^(?:[A-Za-z]:[\\/]|[\\/]|\.{1,2}[\\/]|file://)", url):  # un remoto en otra carpeta
        return re.split(r"[\\/]", url.rstrip("\\/"))[-1].removesuffix(".git"), ""
    limpio = re.sub(r"^\w+://(?:[^@/]+@)?|^[^@/]+@", "", url).removesuffix(".git").replace(":", "/", 1)
    return limpio, (url.removesuffix(".git") if url.startswith("https://") else "")


def cwd_de(texto: str) -> str:
    """El primer "cwd" del comienzo de un transcript."""
    encontrado = CWD.search(texto)
    if not encontrado:
        return ""
    try:
        return json.loads(f'"{encontrado.group(1)}"')
    except ValueError:
        return ""


def de_wsl(ruta: str) -> tuple[str, str] | None:
    """\\\\wsl.localhost\\Ubuntu\\home\\x -> ("Ubuntu", "/home/x")."""
    encontrado = WSL.match(ruta)
    if not encontrado:
        return None
    return encontrado.group(1), (encontrado.group(2).replace("\\", "/") or "/")


def contar_cambios(texto: str) -> int:
    return sum(1 for linea in texto.splitlines() if linea.strip())


# ------------------------------------------------------------------------------------ git de verdad

class Git:
    """Corre git en un repo: el de Windows (o el del sistema) o, si el repo vive en WSL, el de adentro."""

    def __init__(self, ruta: str):
        self.ruta = ruta
        wsl = de_wsl(ruta) if sys.platform == "win32" else None
        self.distro, self.linux = wsl if wsl else ("", "")

    def comando(self, args: list[str], donde: str | None = None, tiempo: float = TIEMPO) -> list[str]:
        donde = donde or (self.linux if self.distro else self.ruta)
        if self.distro:
            variables = [f"{k}={v}" for k, v in ENTORNO.items()]
            # --exec: sin pasar por bash (que se traba con los paréntesis de --format=%(...)). `timeout` corta
            # a git adentro de Linux: matar wsl.exe desde Windows no lo frena y seguiría corriendo allá.
            return ["wsl.exe", "-d", self.distro, "--exec", "timeout", "-k", "2", f"{max(1, int(tiempo))}",
                    "env", *variables, "git", "--no-optional-locks", "-C", donde, *args]
        return ["git", "--no-optional-locks", "-C", donde, *args]

    def correr(self, *args: str, donde: str | None = None, tiempo: float = TIEMPO) -> str:
        """Corre git y devuelve lo que imprimió. Al pasar `tiempo` corta el árbol entero (git, ssh, el gestor
        de credenciales...): si solo se cortara git, sus hijos dejan las tuberías abiertas y la espera no
        termina nunca (pasa con el git.exe de Git\\cmd, que es el que encuentra el programa instalado)."""
        entorno = dict(os.environ, **ENTORNO)
        try:
            proceso = subprocess.Popen(self.comando(list(args), donde, tiempo), stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=entorno,
                                       creationflags=SIN_VENTANA, start_new_session=os.name != "nt")
        except FileNotFoundError as e:
            raise SinGit(str(e)) from e
        try:
            salida, errores = proceso.communicate(timeout=tiempo + (3 if self.distro else 0))
        except subprocess.TimeoutExpired:
            matar_arbol(proceso)
            raise ErrorGit(f"git {args[0]} tardó más de {tiempo:.0f} s") from None
        if self.distro and proceso.returncode in (124, 137):  # el `timeout` de adentro de WSL lo cortó
            raise ErrorGit(f"git {args[0]} tardó más de {tiempo:.0f} s")
        if proceso.returncode != 0:
            texto = errores.decode("utf-8", "replace")
            raise ErrorGit(linea_importante(texto) or f"git {args[0]} falló ({proceso.returncode})", texto)
        return salida.decode("utf-8", "replace")

    def a_local(self, ruta: str) -> str:
        """Una ruta que devolvió git -> como se abre en esta compu."""
        if self.distro and ruta.startswith("/"):
            return f"\\\\wsl.localhost\\{self.distro}" + ruta.replace("/", "\\")
        return os.path.normpath(ruta) if ruta else ruta

    def de_local(self, ruta: str) -> str:
        """Al revés: una carpeta de esta compu -> como la entiende el git que corre."""
        if self.distro:
            wsl = de_wsl(ruta)
            return wsl[1] if wsl else ruta
        return ruta


def matar_arbol(proceso: subprocess.Popen) -> None:
    """Corta un proceso y todos sus hijos, y no espera más de un par de segundos a que suelten las tuberías."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proceso.pid)], capture_output=True, timeout=10,
                           stdin=subprocess.DEVNULL, creationflags=SIN_VENTANA)
        else:
            os.killpg(proceso.pid, 9)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        proceso.kill()
        proceso.communicate(timeout=2)
    except (OSError, subprocess.SubprocessError, ValueError):
        for tubo in (proceso.stdout, proceso.stderr):
            try:
                tubo and tubo.close()
            except OSError:
                pass


_wsl_prendidas: tuple[float, set[str]] = (0.0, set())


def wsl_prendidas() -> set[str]:
    """Las distribuciones de WSL que están corriendo (en minúsculas). Preguntar no prende ninguna."""
    global _wsl_prendidas
    # Menos que una vuelta de la sección (VIVO = 6 s): si apagaron WSL hace un momento, no hay que
    # mandarle un git que lo vuelva a prender. Preguntar cuesta unos 60 ms.
    if time.monotonic() - _wsl_prendidas[0] < 4:
        return _wsl_prendidas[1]
    nombres: set[str] = set()
    try:
        proceso = subprocess.Popen(["wsl.exe", "-l", "--running", "-q"], stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=SIN_VENTANA)
        try:
            crudo, _ = proceso.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            matar_arbol(proceso)
            crudo = b""
        salida = crudo.decode("utf-16-le", "ignore") if b"\x00" in crudo else crudo.decode("utf-8", "ignore")
        nombres = {n.strip().strip("\x00").lower() for n in salida.splitlines() if n.strip().strip("\x00")}
    except (OSError, subprocess.SubprocessError):
        pass
    _wsl_prendidas = (time.monotonic(), nombres)
    return nombres


def normalizar(ruta: str) -> str:
    """La clave de una carpeta (para comparar). Solo para comparar: para abrir archivos se usa la ruta tal
    cual, porque en WSL las mayúsculas importan."""
    return os.path.normcase(os.path.normpath(ruta.replace("/", os.sep) if os.sep == "\\" else ruta))


def apagada(ruta: str) -> bool:
    """La carpeta vive en una distribución de WSL que no está corriendo. Ni siquiera hay que mirarla: abrir
    \\\\wsl.localhost\\<distro> hace que Windows la prenda."""
    wsl = de_wsl(ruta) if sys.platform == "win32" else None
    return bool(wsl) and wsl[0].lower() not in wsl_prendidas()


# ------------------------------------------------------------------------------------- los proyectos

class Proyectos:
    """Arma la lista de repos. Guarda entre una vuelta y la otra lo que no cambia (el cwd de cada transcript,
    la carpeta .git de cada carpeta) para que cada actualización sea barata."""

    def __init__(self, transcripts: Path | None = None):
        if transcripts is None:
            import seguimiento
            transcripts = seguimiento.carpeta_claude() / "projects"
        self.transcripts = transcripts
        self.cwds: dict[str, tuple[int, str]] = {}   # transcript -> (tamaño cuando se leyó, cwd)
        self.comunes: dict[str, str] = {}             # carpeta del repo -> su .git común ("" si no es repo)
        self.por_cwd: dict[str, list[str]] = {}       # cwd -> las carpetas de repo que se encontraron ahí
        self.ultima_busqueda = 0.0
        # clave del .git común -> (una carpeta para entrar, actividad, el .git común tal cual)
        self.raices: dict[str, tuple[str, float, str]] = {}
        self.ultimo_fetch: dict[str, float] = {}
        self.fallo_fetch: set[str] = set()  # repos cuyo último fetch falló
        self.sin_git = False  # el git de Windows (o del sistema) no está instalado
        self.cancelado = lambda: False
        self.al_preguntar = lambda: None  # justo antes de cada git fetch

    # dónde trabajás

    def carpetas_usadas(self) -> dict[str, float]:
        """Cada carpeta donde se usó Claude Code y la última vez (lo nuevo de cada transcript)."""
        usadas: dict[str, float] = {}
        try:
            archivos = list(self.transcripts.glob("*/*.jsonl"))
        except OSError:
            return usadas
        for archivo in archivos:
            try:
                datos = archivo.stat()
            except OSError:
                continue
            clave = str(archivo)
            tamano, cwd = self.cwds.get(clave, (-1, ""))
            # Un transcript recién creado puede no tener el cwd todavía: se vuelve a leer cuando crece.
            if not cwd and tamano != datos.st_size:
                try:
                    with open(archivo, "rb") as f:
                        cwd = cwd_de(f.read(256 * 1024).decode("utf-8", "ignore"))
                except OSError:
                    continue
                self.cwds[clave] = (datos.st_size, cwd)
            if cwd and not IGNORAR.search(cwd):
                usadas[cwd] = max(usadas.get(cwd, 0.0), datos.st_mtime)
        return usadas

    @staticmethod
    def raiz_de(carpeta: str) -> str:
        """La carpeta (o una de arriba) que tiene .git, sin llamar a git."""
        ruta = Path(carpeta)
        for candidata in (ruta, *ruta.parents):
            try:
                if (candidata / ".git").exists():
                    return str(candidata)
            except OSError:
                return ""
        return ""

    def comun_de(self, raiz: str) -> str:
        """El .git común de un repo (tal cual lo da git), o "" si no es un repo."""
        if raiz not in self.comunes:
            if apagada(raiz):
                return ""  # se vuelve a probar la próxima vez (puede que se prenda)
            git = Git(raiz)
            try:
                # Sin --path-format=absolute: antes de git 2.31 rev-parse no lo conoce y lo devuelve como texto
                # (sin fallar). La ruta relativa se completa a mano desde la carpeta del repo.
                salida = git.correr("rev-parse", "--git-common-dir").strip()
            except SinGit:
                self.sin_git = True
                return ""  # sin cachear: puede que lo instalen
            except ErrorGit as e:
                if "not a git repository" in e.detalle:
                    self.comunes[raiz] = ""  # solo esto se recuerda; un error pasajero se vuelve a probar
                return ""
            if not salida or len(salida.splitlines()) > 1 or salida.startswith("-"):
                return ""
            if git.distro:
                linux = salida if salida.startswith("/") else posixpath.normpath(posixpath.join(git.linux, salida))
                self.comunes[raiz] = git.a_local(linux)
            else:
                self.comunes[raiz] = os.path.normpath(os.path.join(raiz, salida))  # join ignora raiz si es absoluta
        return self.comunes[raiz]

    def repos_en(self, cwd: str) -> list[str]:
        """Las carpetas de repo de un cwd: él mismo (o el de arriba con .git) o sus subcarpetas con .git."""
        if apagada(cwd):  # sin tocar el disco: lo que se encontró cuando estaba prendida
            return self.por_cwd.get(cwd, [])
        if not os.path.isdir(cwd):
            return []
        raiz = self.raiz_de(cwd)
        self.por_cwd[cwd] = [raiz] if raiz else self.subcarpetas_repo(cwd)
        return self.por_cwd[cwd]

    def buscar(self) -> None:
        """Los repos (agrupados por su .git común) de las carpetas donde trabajaste. Cada medio minuto."""
        if self.raices and time.monotonic() - self.ultima_busqueda < 30:
            return
        self.ultima_busqueda = time.monotonic()
        self.sin_git = False
        raices: dict[str, tuple[str, float, str]] = {}
        for cwd, cuando in sorted(self.carpetas_usadas().items(), key=lambda par: -par[1]):
            if self.cancelado():
                return
            if apagada(cwd) and cwd not in self.por_cwd:
                # Nunca se la vio prendida: no se sabe si es un repo, pero tampoco se la puede mirar sin
                # prenderla. Queda una tarjeta "WSL apagado" con el nombre de la carpeta.
                clave = "wsl:" + normalizar(cwd)
                raices[clave] = (cwd, max(raices.get(clave, ("", 0.0, ""))[1], cuando), cwd)
                continue
            for candidata in self.repos_en(cwd):
                comun = self.comun_de(candidata)  # si la distro está apagada, el que se guardó antes
                if comun:
                    clave = normalizar(comun)
                    entrada, antes, _ = raices.get(clave, (candidata, 0.0, comun))
                    raices[clave] = (entrada, max(antes, cuando), comun)
        self.raices = raices

    @staticmethod
    def subcarpetas_repo(carpeta: str) -> list[str]:
        try:
            with os.scandir(carpeta) as entradas:
                return sorted(e.path for e in entradas
                              if e.is_dir() and not e.name.startswith(".") and os.path.exists(os.path.join(e.path, ".git")))
        except OSError:
            return []

    # cada repo

    def leer(self, buscar_en_github: bool = False, forzar: bool = False, al_avanzar=None) -> list[Repo]:
        """Todos los repos, el que se usó último primero. buscar_en_github: hace git fetch en los que hace
        más de CADA_FETCH que no se revisan (o en todos, con forzar). al_avanzar(lista): se llama con lo
        que va habiendo, así un repo lento (WSL arrancando, un disco de red) no demora a los demás."""
        self.buscar()
        repos = []
        for clave, (entrada, actividad, comun) in sorted(self.raices.items(), key=lambda par: -par[1][1]):
            if self.cancelado():
                break
            try:
                repos.append(self.leer_repo(comun, entrada, actividad, buscar_en_github, forzar))
            except SinGit:
                self.sin_git = True  # los de WSL usan el git de adentro: siguen andando
            if al_avanzar and repos:  # una lista vacía haría mostrar "no hay proyectos" por un momento
                al_avanzar(list(repos))
        return repos

    def leer_repo(self, comun: str, entrada: str, actividad: float, buscar_en_github: bool = False,
                  forzar: bool = False) -> Repo:
        git = Git(entrada)
        repo = Repo(clave=normalizar(comun), nombre=re.split(r"[\\/]", entrada.rstrip("\\/"))[-1],
                    actividad=actividad, ruta=entrada)
        if apagada(entrada):
            repo.error = "wsl"
            return repo
        try:
            remotos = git.correr("remote").split()
            remoto = "origin" if "origin" in remotos else (remotos[0] if remotos else "")
            if remoto:
                try:
                    repo.remoto, repo.web = nombre_remoto(git.correr("config", "--get", f"remote.{remoto}.url"))
                except ErrorGit:
                    pass
            revisado = self.fecha_fetch(comun)
            if remoto and buscar_en_github and (forzar or not revisado or time.time() - revisado > CADA_FETCH):
                if forzar or time.time() - self.ultimo_fetch.get(repo.clave, 0) > CADA_FETCH:
                    self.ultimo_fetch[repo.clave] = time.time()
                    self.al_preguntar()
                    try:
                        self.fetch(git, remoto)
                        self.fallo_fetch.discard(repo.clave)
                    except ErrorGit as e:
                        self.fallo_fetch.add(repo.clave)
                        registrar(f"[repos] no se pudo revisar {repo.nombre} en GitHub: {e}")
                    revisado = self.fecha_fetch(comun)
            if not remoto:  # sin remoto no hay a quién preguntar: tampoco hay nota
                self.fallo_fetch.discard(repo.clave)
            elif repo.clave in self.fallo_fetch:  # la nota queda hasta que un fetch salga bien
                repo.aviso = "fetch"
            repo.revisado = revisado
            carpetas = parsear_worktrees(git.correr("worktree", "list", "--porcelain"))
            locales, remotas = parsear_refs(git.correr("for-each-ref", f"--format={FORMATO_REFS}",
                                                       "refs/heads", "refs/remotes"))
            base = elegir_base(remotas, [r["nombre"] for r in locales], remoto or "origin")
            repo.base = re.sub(r"^refs/(heads|remotes)/", "", base)
            divergencia = self.divergencia(git, base, [r["nombre"] for r in locales])
        except SinGit:
            raise
        except ErrorGit as e:
            repo.error = str(e)
            return repo
        if base.startswith("refs/heads/"):
            nombre_base_local = base[11:]
        else:  # refs/remotes/origin/release/v2 -> release/v2
            nombre_base_local = next((base[len(f"refs/remotes/{r}/"):] for r in remotos
                                      if base.startswith(f"refs/remotes/{r}/")), base.rsplit("/", 1)[-1])
        repo.base_rama = nombre_base_local
        if carpetas and not carpetas[0]["bare"]:
            repo.nombre = Carpeta(git.a_local(carpetas[0]["ruta"])).nombre
        if repo.web:  # el nombre en GitHub (la carpeta puede llamarse distinto)
            repo.nombre = repo.remoto.rsplit("/", 1)[-1]
        por_rama: dict[str, Carpeta] = {}
        for i, c in enumerate(carpetas):
            if c["bare"]:
                continue
            carpeta = Carpeta(git.a_local(c["ruta"]), "" if c["detached"] else c["rama"], principal=i == 0,
                              perdida=c["prunable"])
            if not carpeta.perdida:
                try:
                    carpeta.cambios = contar_cambios(git.correr("status", "--porcelain", "--untracked-files=normal",
                                                                donde=c["ruta"]))
                except ErrorGit:
                    carpeta.perdida = not os.path.isdir(carpeta.ruta)
            repo.carpetas.append(carpeta)
            if carpeta.rama and not carpeta.perdida:  # una carpeta borrada ya no "usa" su rama
                por_rama[carpeta.rama] = carpeta
        for datos in locales:
            nombre = datos["nombre"]
            # Solo cuenta como "subida" si sigue a una rama de GitHub con su mismo nombre: una rama nueva
            # hecha desde origin/main la sigue a esa, pero ella todavía no está en GitHub.
            propia = any(datos["arriba"] == f"refs/remotes/{r}/{nombre}" for r in remotos)
            rama = Rama(nombre, datos["fecha"], carpeta=por_rama.get(nombre), borrada=propia and datos["borrada"])
            if propia and not datos["borrada"]:
                rama.arriba = datos["arriba"].removeprefix("refs/remotes/")
                rama.sin_subir, rama.sin_bajar = datos["sin_subir"], datos["sin_bajar"]
            rama.en_remoto = bool(rama.arriba) or f"refs/remotes/{remoto}/{nombre}" in remotas
            rama.base = nombre == nombre_base_local
            if rama.base or nombre in divergencia:
                rama.adelante, rama.atras = divergencia.get(nombre, (0, 0))
            else:  # no se pudo medir: mejor "no sé" que "ya está en main" (la mandaría a limpiar)
                rama.incierta = True
            if rama.en_remoto and not rama.arriba:  # está en GitHub pero no la sigue: se compara a mano
                try:
                    atras, adelante = git.correr("rev-list", "--left-right", "--count",
                                                 f"refs/remotes/{remoto}/{nombre}...refs/heads/{nombre}").split()
                    rama.sin_subir, rama.sin_bajar = int(adelante), int(atras)
                    rama.arriba = f"{remoto}/{nombre}"
                except (ErrorGit, ValueError):
                    rama.incierta = True
            repo.ramas.append(rama)
        repo.ramas.sort(key=lambda r: (not r.base, -r.fecha))
        return repo

    @staticmethod
    def fetch(git: Git, remoto: str) -> None:
        """git fetch que solo agrega: nunca borra refs (aunque el repo tenga fetch.prune), no arranca el
        mantenimiento automático de git (que sigue corriendo suelto y puede podar objetos y worktrees) y no
        entra a los submódulos."""
        config = ["-c", "gc.auto=0", "-c", "maintenance.auto=false", "-c", "fetch.writeCommitGraph=false",
                  "-c", "fetch.prune=false", "-c", "fetch.pruneTags=false", "-c", f"remote.{remoto}.prune=false",
                  "-c", f"remote.{remoto}.pruneTags=false"]
        try:
            git.correr(*config, "fetch", "--quiet", "--no-prune", "--no-prune-tags", "--no-auto-maintenance",
                       "--no-recurse-submodules", remoto, tiempo=TIEMPO_FETCH)
        except ErrorGit as e:
            if "unknown option" not in e.detalle and "usage:" not in e.detalle:
                raise
            # un git viejo (antes de 2.29) no conoce algunas opciones: lo mismo con la configuración sola
            git.correr(*config, "fetch", "--quiet", "--no-prune", "--no-recurse-submodules", remoto,
                       tiempo=TIEMPO_FETCH)

    @staticmethod
    def divergencia(git: Git, base: str, ramas: list[str]) -> dict[str, tuple[int, int]]:
        """Cuánto adelante y atrás de la principal está cada rama. Una sola llamada en git 2.41 o más nuevo.
        Las que no se pudieron medir no aparecen."""
        if not base or not ramas:
            return {}
        try:
            return parsear_divergencia(git.correr("for-each-ref", f"--format=%(refname)%00%(ahead-behind:{base})",
                                                  "refs/heads"))
        except SinGit:
            raise
        except ErrorGit:
            pass
        res = {}
        for nombre in ramas:
            try:
                atras, adelante = git.correr("rev-list", "--left-right", "--count",
                                             f"{base}...refs/heads/{nombre}").split()
                res[nombre] = (int(adelante), int(atras))
            except (ErrorGit, ValueError):
                pass
        return res

    @staticmethod
    def fecha_fetch(comun: str) -> float | None:
        """La última vez que se preguntó a GitHub: el FETCH_HEAD más nuevo (cada worktree tiene el suyo)."""
        fechas = []
        for archivo in [os.path.join(comun, "FETCH_HEAD"), *Path(comun).glob("worktrees/*/FETCH_HEAD")]:
            try:
                fechas.append(os.stat(archivo).st_mtime)
            except OSError:
                pass
        return max(fechas) if fechas else None
