"""Lo que muestra la barra de sesiones: qué sesiones de Claude Code están vivas y qué hacen.

Todo sale de los transcripts que Claude Code escribe en ~/.claude/projects (o en CLAUDE_CONFIG_DIR): no
hace falta que los hooks hayan corrido. Se leen de a pedazos (solo lo nuevo desde la última vez), así un
transcript de 20 MB se lee entero una sola vez.

- Sesión activa: su transcript tiene alguna línea con hora de los últimos 30 minutos.
- Trabajando: después de tu último mensaje todavía no llegó el final del turno (la respuesta con
  "end_turn", el resumen de los hooks de Stop o "Request interrupted").
- Tokens: la suma de lo que se mandó (entrada + lo que se guardó en caché) y lo que respondió Claude,
  contando cada respuesta una vez (Claude Code repite el mismo mensaje en varias líneas). Las lecturas de
  la caché van aparte: se repiten en cada llamada y no son tokens nuevos. Los subagentes suman.
- Agentes activos: subagentes de la sesión sin "finished" en su .meta.json y que escribieron hace poco.
- Tiempo que falta: una estimación con lo que duraron tus turnos anteriores (ver Estimador).
"""

from __future__ import annotations

import bisect
import json
import math
import os
import re
import statistics
import threading
import time
from datetime import datetime
from pathlib import Path

ACTIVA = 30 * 60          # una sesión sin cambios en su transcript por más de esto ya no se muestra
COLGADA = 15 * 60         # "trabajando" pero sin escribir nada en este tiempo: se cortó (se cerró la terminal)
HERRAMIENTA_LARGA = 2 * 3600  # una herramienta sin terminar puede tardar esto sin que el turno se dé por cortado
AGENTE_VIVO = 10 * 60    # un subagente sin escribir en este tiempo ya no cuenta como activo
MAX_HISTORIAL = 800
MAX_PASOS = 400           # herramientas de un turno que se anotan (para estimar cuánto falta)


def carpeta_claude() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def hora(texto) -> float | None:
    try:
        return datetime.fromisoformat(str(texto).replace("Z", "+00:00")).timestamp()
    except (ValueError, OSError, OverflowError):  # fechas imposibles (Windows no acepta antes de 1970)
        return None


def es_mensaje_tuyo(d: dict) -> bool:
    """Un mensaje que escribiste (o un aviso que reanuda el turno), no el resultado de una herramienta."""
    if d.get("isMeta") or d.get("isCompactSummary") or d.get("isSidechain"):
        return False
    contenido = (d.get("message") or {}).get("content")
    if isinstance(contenido, str):
        # Los comandos locales (/model, /cost...) quedan escritos como mensajes pero no esperan respuesta;
        # si Claude igual contesta (un comando que es un prompt), el turno arranca con su respuesta.
        # Igual los avisos de tareas en segundo plano: si Claude los contesta, el turno arranca con su respuesta.
        return bool(contenido.strip()) and not contenido.lstrip().startswith(
            ("<local-command", "<command-", "<task-notification"))
    if isinstance(contenido, list):
        return bool(contenido) and not any(isinstance(c, dict) and c.get("type") == "tool_result" for c in contenido)
    return False


def largo_del_mensaje(d: dict) -> int:
    contenido = (d.get("message") or {}).get("content")
    if isinstance(contenido, str):
        return len(contenido)
    if isinstance(contenido, list):
        return sum(len(c.get("text") or "") for c in contenido if isinstance(c, dict))
    return 0


def es_interrupcion(d: dict) -> bool:
    contenido = (d.get("message") or {}).get("content")
    if isinstance(contenido, str):
        textos = [contenido]
    elif isinstance(contenido, list):
        textos = [c.get("text", "") for c in contenido if isinstance(c, dict)]
    else:
        textos = []
    return any(isinstance(x, str) and x.startswith("[Request interrupted") for x in textos)


class Plan:
    """La lista de tareas que Claude lleva durante un turno (TodoWrite, las tareas de Claude Code o el plan
    de la app de escritorio): cuántas hay y cuántas terminó. Es la mejor pista de cuánto falta."""

    def __init__(self):
        self.estados: list[str] = []
        self.ids: list[str | None] = []  # el taskId de cada tarea, cuando se lo conoce (TaskUpdate)

    def lugar(self, ident) -> int | None:
        """Dónde está la tarea con ese taskId. TaskCreate no lo dice: la primera vez que aparece uno se
        lo toma como la tarea sin identificar más vieja."""
        ident = str(ident) if ident is not None else None
        if ident is not None and ident in self.ids:
            return self.ids.index(ident)
        libre = next((i for i, x in enumerate(self.ids) if x is None
                      and (ident is not None or self.estados[i] != "completed")), None)
        if libre is not None and ident is not None:
            self.ids[libre] = ident
        return libre

    @property
    def total(self) -> int:
        return len(self.estados)

    @property
    def hechas(self) -> int:
        return sum(1 for e in self.estados if e == "completed")

    def anotar(self, herramienta: str, entrada) -> bool:
        """True si esta herramienta era de la lista de tareas (y la cambió)."""
        if not isinstance(entrada, dict):
            return False
        nombre = herramienta.rsplit("__", 1)[-1]
        if nombre in ("TodoWrite", "update_plan"):
            items = entrada.get("todos") if nombre == "TodoWrite" else entrada.get("items")
            if isinstance(items, list):
                self.estados = [str(i.get("status", "pending")) if isinstance(i, dict) else "pending" for i in items]
                self.ids = [None] * len(self.estados)
            elif nombre == "update_plan":
                hechos = entrada.get("done")
                for n in hechos if isinstance(hechos, list) else []:
                    if isinstance(n, (int, float)) and 1 <= int(n) <= self.total:
                        self.estados[int(n) - 1] = "completed"
                if entrada.get("advance"):
                    actual = next((i for i, e in enumerate(self.estados) if e == "in_progress"), None)
                    if actual is None:
                        actual = next((i for i, e in enumerate(self.estados) if e != "completed"), None)
                    if actual is not None:
                        self.estados[actual] = "completed"
                        if actual + 1 < self.total and self.estados[actual + 1] == "pending":
                            self.estados[actual + 1] = "in_progress"
                empieza = entrada.get("start")
                if isinstance(empieza, (int, float)) and 1 <= int(empieza) <= self.total:
                    self.estados[int(empieza) - 1] = "in_progress"
            return True
        if nombre == "wrap_up":
            self.estados = ["completed"] * self.total
            return True
        if nombre == "TaskCreate":
            self.estados.append("pending")
            self.ids.append(None)
            return True
        if nombre == "TaskUpdate" and entrada.get("status") in ("completed", "deleted", "in_progress", "pending"):
            i = self.lugar(entrada.get("taskId"))
            if i is not None:
                if entrada["status"] == "deleted":
                    self.estados.pop(i)
                    self.ids.pop(i)
                else:
                    self.estados[i] = entrada["status"]
            return True
        return False


class Transcript:
    """Lee un .jsonl de Claude Code de a pedazos y lleva las cuentas."""

    def __init__(self, ruta: Path):
        self.ruta = Path(ruta)
        self.offset = 0
        self.resto = b""
        self.ids: set[str] = set()
        self.inicio: float | None = None       # primera línea con hora: cuándo empezó la sesión
        self.ultima: float | None = None       # última línea con hora
        self.prompt: float | None = None       # tu último mensaje
        self.fin: float | None = None          # el último final de turno
        self.despertador: float | None = None  # mensaje interno después del final, por si Claude sigue
        self.actividad: float | None = None    # última línea tuya o de Claude (no de la cola ni adjuntos)
        self.herramienta_pendiente = False     # Claude pidió una herramienta y todavía no llegó el resultado
        self.entrada = self.salida = self.cache = 0
        self.contexto = 0                      # lo que ocupaba la conversación en la última llamada
        self.tokens_desde_prompt = 0
        self.herramienta = ""                  # la última herramienta que pidió en este turno
        self.titulo = ""
        self.cwd = ""
        self.turnos: list[tuple[float, float]] = []  # (hora de fin, duración) de cada turno terminado
        self.detalles: list[dict] = []         # de cada turno terminado: sus pasos y el largo del pedido
        self.pasos: list[float] = []           # segundos (desde tu mensaje) de cada herramienta que pidió
        self.largo = 0                         # letras de tu mensaje: uno corto suele pedir algo corto
        self.plan = Plan()                     # la lista de tareas que lleva Claude (hechas / total)
        self.ya_hechas = 0                     # las que ya estaban hechas cuando empezó este turno
        self.avances: list[tuple[float, int, int]] = []  # (segundos, hechas, total) cada vez que la tocó
        self.leido_hasta_mtime = 0.0

    @property
    def sesion(self) -> str:
        return self.ruta.stem

    def leer(self, pedazo: int = 8_000_000) -> bool:
        """Lee lo nuevo, de a pedazos (un transcript enorme no se carga entero). True si había algo."""
        try:
            tam = self.ruta.stat().st_size
            if tam < self.offset:  # se reescribió (raro): de cero
                self.__init__(self.ruta)
            if tam == self.offset:
                return False
            with open(self.ruta, "rb") as f:
                f.seek(self.offset)
                while datos := f.read(pedazo):
                    self.offset += len(datos)
                    lineas = (self.resto + datos).split(b"\n")
                    self.resto = lineas.pop()  # la última puede estar a medio escribir
                    for linea in lineas:
                        self.procesar(linea)
        except OSError:
            pass
        return True

    def procesar(self, linea: bytes) -> None:
        """Una línea rara (de otra versión de Claude Code, cortada, con tipos inesperados) se saltea sola."""
        if not linea.strip():
            return
        try:
            self._procesar(linea)
        except Exception:
            pass

    def _procesar(self, linea: bytes) -> None:
        tipo_user = b'"type":"user"' in linea
        if tipo_user and b'"tool_result"' in linea and b"[Request interrupted" not in linea:
            # Resultados de herramientas: solo importa la hora (son las líneas más pesadas).
            m = re.search(rb'"timestamp":"([^"]+)"', linea)
            if m:
                momento = hora(m.group(1).decode())
                self.marcar_hora(momento)
                self.actividad = max(self.actividad or 0, momento or 0) or None
            if b'"isSidechain":true' not in linea:
                self.herramienta_pendiente = False
            return
        try:
            d = json.loads(linea)
        except ValueError:
            return
        if not isinstance(d, dict):
            return
        momento = hora(d.get("timestamp")) if d.get("timestamp") else None
        # La última vez que Claude o vos escribieron algo (las líneas de cola, adjuntos, etc. no cuentan:
        # Claude Code las escribe justo antes de tu mensaje y taparían que el turno quedó colgado).
        previa = self.actividad
        self.marcar_hora(momento)
        tipo = d.get("type")
        if tipo in ("user", "assistant") and momento is not None and not d.get("isSidechain"):
            self.actividad = max(self.actividad or momento, momento)
        if d.get("customTitle") or d.get("aiTitle"):
            self.titulo = " ".join(str(d.get("customTitle") or d.get("aiTitle")).split())
        if d.get("cwd") and not d.get("isSidechain"):
            self.cwd = d["cwd"]
        if tipo == "user":
            if not d.get("isSidechain"):
                self.herramienta_pendiente = False  # llegó el resultado (o algo tuyo después del pedido)
            if not d.get("isSidechain") and momento is not None and not self.en_curso():
                # Un mensaje interno (el informe de un subagente, una tarea en segundo plano que terminó)
                # puede hacer que Claude vuelva a trabajar sin que escribas nada: se anota por si responde.
                self.despertador = momento  # el último: lo que hizo arrancar a Claude es lo más reciente
            if es_interrupcion(d):
                self.terminar_turno(momento)
            elif es_mensaje_tuyo(d):
                # Turno nuevo si el anterior terminó, o si quedó abierto (se cerró la terminal a mitad de
                # camino) y no se escribió nada en mucho tiempo. Si no, es un mensaje en cola.
                colgado = momento is not None and previa is not None and momento - previa > COLGADA
                if not self.en_curso() or colgado:
                    self.empezar_turno(momento)  # un turno nuevo (los mensajes en cola no lo reinician)
                    self.largo = largo_del_mensaje(d)
        elif tipo == "assistant":
            self.contar(d)
        elif tipo == "system" and d.get("subtype") == "stop_hook_summary":
            self.terminar_turno(momento)

    def marcar_hora(self, momento: float | None) -> None:
        if momento is None:
            return
        if self.inicio is None:
            self.inicio = momento
        self.ultima = max(self.ultima or momento, momento)

    def en_curso(self) -> bool:
        return self.prompt is not None and (self.fin is None or self.fin < self.prompt)

    def empezar_turno(self, momento: float | None) -> None:
        self.prompt = momento
        self.tokens_desde_prompt = 0
        self.herramienta = ""
        self.despertador = None
        self.pasos = []
        self.largo = 0
        self.avances = []
        self.ya_hechas = self.plan.hechas

    def avance(self) -> tuple[int, int]:
        """(hechas, total) de la lista de tareas contando solo lo de este turno: lo que ya estaba hecho de
        turnos anteriores no es avance de este."""
        antes = min(self.ya_hechas, self.plan.hechas)
        return self.plan.hechas - antes, self.plan.total - antes

    def contar(self, d: dict) -> None:
        mensaje = d.get("message") or {}
        principal = not d.get("isSidechain")
        if d.get("isApiErrorMessage"):
            # El aviso de error que escribe Claude Code (límite de uso, sin conexión): el turno se cortó.
            if principal:
                self.terminar_turno(hora(d.get("timestamp")))
            return
        ident = mensaje.get("id")
        if principal and not self.en_curso() and ident and ident not in self.ids:
            # Claude volvió a trabajar sin que escribas: después de un mensaje interno (el informe de un
            # subagente) o porque un hook de Stop le pidió seguir. El turno arranca ahí.
            self.empezar_turno(self.despertador or hora(d.get("timestamp")))
        for c in mensaje.get("content") or ():
            if isinstance(c, dict) and c.get("type") == "tool_use" and c.get("name"):
                self.herramienta = c["name"]
                if principal:
                    self.herramienta_pendiente = True
                    momento = hora(d.get("timestamp"))
                    if momento is not None and self.prompt is not None and len(self.pasos) < MAX_PASOS:
                        self.pasos.append(round(max(0.0, momento - self.prompt), 1))
                        if self.plan.anotar(c["name"], c.get("input")) and len(self.avances) < MAX_PASOS:
                            self.avances.append((self.pasos[-1], *self.avance()))
        uso = mensaje.get("usage") or {}
        if ident and ident not in self.ids and uso:
            self.ids.add(ident)
            entrada = int(uso.get("input_tokens") or 0) + int(uso.get("cache_creation_input_tokens") or 0)
            salida = int(uso.get("output_tokens") or 0)
            cache = int(uso.get("cache_read_input_tokens") or 0)
            self.entrada += entrada
            self.salida += salida
            self.cache += cache
            self.tokens_desde_prompt += entrada + salida
            if not d.get("isSidechain"):
                self.contexto = entrada + cache
        if mensaje.get("stop_reason") == "end_turn" and not d.get("isSidechain"):
            self.terminar_turno(hora(d.get("timestamp")))

    def terminar_turno(self, momento: float | None) -> None:
        if momento is None:
            return
        if self.en_curso() and momento >= self.prompt:
            self.turnos.append((momento, momento - self.prompt))
            self.detalles.append({"pasos": self.pasos, "largo": self.largo, "avances": self.avances})
        self.fin = max(self.fin or momento, momento)
        self.despertador = None

    @property
    def tokens(self) -> int:
        return self.entrada + self.salida

    def trabajando(self, ahora: float | None = None) -> bool:
        ahora = ahora or time.time()
        if not self.en_curso():
            return False
        # Una herramienta que tarda (un build, una prueba larga) no escribe nada hasta terminar: se le da más
        # margen que a un turno que simplemente dejó de escribir.
        margen = HERRAMIENTA_LARGA if self.herramienta_pendiente else COLGADA
        return ahora - (self.actividad or self.prompt) < margen


class Agentes:
    """Los subagentes de una sesión: <sesión>/subagents/agent-*.jsonl y su .meta.json."""

    def __init__(self, carpeta: Path):
        self.carpeta = carpeta
        self.transcripts: dict[str, Transcript] = {}

    def actualizar(self, ahora: float) -> tuple[int, int]:
        """Lee lo nuevo; devuelve (activos, tokens de todos)."""
        activos = 0
        try:
            archivos = list(self.carpeta.glob("agent-*.jsonl"))
        except OSError:
            archivos = []
        for archivo in archivos:
            nombre = archivo.stem
            t = self.transcripts.get(nombre)
            if t is None:
                t = self.transcripts[nombre] = Transcript(archivo)
            t.leer()
            try:
                if ahora - archivo.stat().st_mtime >= AGENTE_VIVO:
                    continue
            except OSError:  # se borró recién
                continue
            try:
                meta = json.loads(archivo.with_suffix(".meta.json").read_text(encoding="utf-8"))
            except FileNotFoundError:
                meta = {}
            except (OSError, ValueError):
                continue
            if not (isinstance(meta, dict) and meta.get("finished")):
                activos += 1
        return activos, sum(t.tokens for t in self.transcripts.values())


def plan_a_los(avances, t: float) -> tuple[int, int] | None:
    """(hechas, total) de la lista de tareas a los t segundos del turno, o None si todavía no había."""
    ultimo = None
    for cuando, hechas, total in avances:
        if cuando > t:
            break
        ultimo = (hechas, total)
    return ultimo if ultimo and ultimo[1] > 0 else None


def mediana_pesada(pares: list[tuple[float, float]]) -> float:
    pares.sort()
    mitad, suma = sum(peso for _, peso in pares) / 2, 0.0
    for valor, peso in pares:
        suma += peso
        if suma >= mitad:
            return valor
    return pares[-1][0]


class Estimador:
    """Cuánto falta para que Claude termine de responder, según cómo fueron tus turnos anteriores.

    No hay forma de saberlo de verdad: es una estimación. Con lo que ya lleva el turno (t), se miran los
    turnos del historial que duraron más que t y se toma la mediana de lo que les faltaba, pero pesando
    más a los que se parecen a este:

    - los del mismo proyecto y la misma sesión, y los más recientes;
    - los que a esta altura habían usado una cantidad parecida de herramientas;
    - los que arrancaron con un pedido de largo parecido (uno corto suele pedir algo corto);
    - y, si Claude lleva una lista de tareas, los que iban por la misma parte de la suya (es la mejor
      pista: con 4 de 5 hechas falta poco).

    A medida que el turno se alarga la estimación se corrige sola. Cuando ya duró más que casi todos los
    anteriores no se inventa un número: devuelve None. Los pesos salieron de probar contra turnos reales
    (precision() repite esa prueba con tu historial).
    """

    MINIMO = 3        # turnos más largos que t que hacen falta para estimar
    VERSION = 2       # el historial guarda los pasos de cada turno; uno más viejo se vuelve a aprender
    VIDA = 100        # cada tantos turnos para atrás, la mitad de peso
    PROYECTO, SESION = 8.0, 2.0
    PASOS, LARGO = 1.0, 1.0
    FRACCION, FALTAN, SIN_LISTA, MINIMO_LISTA = 4.0, 0.5, 0.5, 5

    def __init__(self, archivo: Path | None = None):
        self.archivo = archivo
        self.turnos: list[dict] = []  # {"fin", "dur", "proy", "sesion", "pasos", "largo", "avances"}
        self.vistos: set[tuple[str, int]] = set()
        self.cambios = False
        if archivo:
            try:
                datos = json.loads(archivo.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                datos = None
            # Un archivo roto o tocado a mano no puede trabar la barra: quedan solo los turnos sanos.
            al_dia = isinstance(datos, dict) and datos.get("version") == self.VERSION
            turnos = datos.get("turnos") if al_dia else None
            for t in turnos if isinstance(turnos, list) else []:
                try:
                    self.agregar(str(t.get("sesion", "")), str(t.get("proy", "")), float(t["fin"]), float(t["dur"]), t)
                except (AttributeError, TypeError, KeyError, ValueError, OverflowError):
                    continue
            self.turnos.sort(key=lambda t: t["fin"])
            self.cambios = False

    @property
    def vacio(self) -> bool:
        return not self.turnos

    @property
    def suficiente(self) -> bool:
        """¿Hay historial para estimar? Si no, la barra dice "aprendiendo" en vez de "más de lo normal"."""
        return len(self.turnos) >= self.MINIMO

    @staticmethod
    def detalle_sano(detalle) -> dict:
        """Los pasos, el largo y los avances de un turno, descartando lo que no tenga la forma esperada."""
        detalle = detalle if isinstance(detalle, dict) else {}
        pasos = detalle.get("pasos")
        if isinstance(pasos, list):
            pasos = sorted(float(x) for x in pasos if isinstance(x, (int, float)) and math.isfinite(x))
        else:
            pasos = []
        avances = []
        for a in detalle.get("avances") if isinstance(detalle.get("avances"), (list, tuple)) else []:
            if (isinstance(a, (list, tuple)) and len(a) == 3
                    and all(isinstance(x, (int, float)) and math.isfinite(x) for x in a)):
                total = max(0, int(a[2]))  # nunca más hechas que tareas, ni negativas
                avances.append((float(a[0]), min(max(0, int(a[1])), total), total))
        largo = detalle.get("largo")
        return {"pasos": pasos[:MAX_PASOS], "avances": sorted(avances)[:MAX_PASOS],
                "largo": int(largo) if isinstance(largo, (int, float)) and math.isfinite(largo) and largo > 0 else 0}

    def agregar(self, sesion: str, proyecto: str, fin: float, duracion: float, detalle: dict | None = None) -> None:
        if not (math.isfinite(fin) and abs(fin) < 1e11 and math.isfinite(duracion)):
            return
        clave = (sesion, int(fin))
        if clave in self.vistos or not 1 <= duracion <= 3 * 3600:
            return
        self.vistos.add(clave)
        self.turnos.append({"fin": float(fin), "dur": round(float(duracion), 1), "proy": proyecto, "sesion": sesion,
                            **self.detalle_sano(detalle)})
        self.cambios = True

    def guardar(self) -> None:
        if not (self.archivo and self.cambios):
            return
        self.turnos.sort(key=lambda t: t["fin"])
        self.turnos = self.turnos[-MAX_HISTORIAL:]  # vistos no se achica: lo que se recortó no vuelve a entrar
        try:
            self.archivo.parent.mkdir(parents=True, exist_ok=True)
            temporal = self.archivo.with_name(f"{self.archivo.stem}.{os.getpid()}-{threading.get_ident()}.tmp")
            temporal.write_text(json.dumps({"version": self.VERSION, "turnos": self.turnos}), encoding="utf-8")
            os.replace(temporal, self.archivo)
            self.cambios = False
        except OSError:
            pass

    def estimar(self, transcurrido: float, proyecto: str = "", sesion: str = "", pasos=(), largo: int = 0,
                avances=()) -> float | None:
        """Segundos que faltan (siempre > 0), o None si no hay con qué estimar."""
        return self.estimar_con(self.turnos, transcurrido, proyecto, sesion, pasos, largo, avances)

    def estimar_con(self, historial: list[dict], t: float, proyecto: str, sesion: str, pasos, largo: int,
                    avances) -> float | None:
        n = bisect.bisect_right(pasos, t)
        plan = plan_a_los(avances, t)
        todos: list[tuple[float, float]] = []
        con_lista: list[tuple[float, float]] = []
        cuantos = len(historial)
        for i, q in enumerate(historial):
            if q["dur"] <= t:
                continue
            peso = 0.5 ** ((cuantos - i) / self.VIDA)
            if q["proy"] == proyecto:
                peso *= self.PROYECTO
            if sesion and q["sesion"] == sesion:
                peso *= self.SESION
            peso *= math.exp(-self.PASOS * abs(math.log1p(n) - math.log1p(bisect.bisect_right(q["pasos"], t)))
                             - self.LARGO * abs(math.log1p(largo) - math.log1p(q["largo"])))
            falta = q["dur"] - t
            su_plan = plan_a_los(q["avances"], t)
            if plan and su_plan:
                parecido = (self.FRACCION * abs(plan[0] / plan[1] - su_plan[0] / su_plan[1])
                            + self.FALTAN * abs(math.log1p(plan[1] - plan[0]) - math.log1p(su_plan[1] - su_plan[0])))
                con_lista.append((falta, peso * math.exp(-parecido)))
            if bool(plan) != bool(su_plan):
                peso *= self.SIN_LISTA
            todos.append((falta, peso))
        if len(con_lista) >= self.MINIMO_LISTA:
            return max(1.0, mediana_pesada(con_lista))
        if len(todos) >= self.MINIMO:
            return max(1.0, mediana_pesada(todos))
        return None

    def precision(self, ultimos: int = 250, cancelado=lambda: False) -> dict | None:
        """Qué tan bien viene estimando: repasa tus últimos turnos como si fueran en vivo (cada uno solo con
        lo que se sabía antes de él) y compara lo que hubiera dicho con lo que faltaba de verdad."""
        turnos = sorted(self.turnos, key=lambda t: t["fin"])
        desde = max(30, len(turnos) - ultimos)
        errores, dentro, muestras, sin_numero = [], 0, 0, 0
        for i in range(desde, len(turnos)):
            if cancelado():
                return None
            x, historial = turnos[i], turnos[:i]
            t = 2.0
            while t < x["dur"]:
                dicho = self.estimar_con(historial, t, x["proy"], x["sesion"], x["pasos"], x["largo"], x["avances"])
                real = x["dur"] - t
                muestras += 1
                if dicho is None:
                    sin_numero += 1
                else:
                    errores.append(abs(dicho - real))
                    dentro += 0.5 <= dicho / real <= 2
                t += max(5.0, t * 0.08)  # cada 5 s al principio; en los turnos largos, más espaciado
        if not errores:
            return None
        return {"muestras": muestras, "turnos": len(turnos) - desde, "dentro_del_doble": dentro / len(errores),
                "error_mediano": statistics.median(errores), "sin_numero": sin_numero / muestras}


class Monitor:
    """Junta todo: qué sesiones hay y cómo van. actualizar() se llama desde un hilo aparte."""

    def __init__(self, historial: Path | None = None, carpeta: Path | None = None):
        self.carpeta = carpeta or carpeta_claude() / "projects"
        self.transcripts: dict[Path, Transcript] = {}
        self.agentes: dict[Path, Agentes] = {}
        self.estimador = Estimador(historial)
        self.lock = threading.Lock()
        self.sesiones: list[dict] = []
        self.cancelado = lambda: False  # el Lector lo cambia: apagar la barra corta el aprendizaje

    def archivos_recientes(self, ahora: float, ventana: float) -> list[tuple[float, Path]]:
        recientes = []
        try:
            proyectos = [p for p in self.carpeta.iterdir() if p.is_dir()]
        except OSError:
            return []
        for proyecto in proyectos:
            try:
                for archivo in proyecto.glob("*.jsonl"):
                    mtime = archivo.stat().st_mtime
                    if ahora - mtime < ventana:
                        recientes.append((mtime, archivo))
            except OSError:
                continue
        return sorted(recientes, reverse=True)

    def aprender_del_pasado(self, dias: int = 45, maximo_archivos: int = 150,
                            maximo_bytes: int = 800_000_000) -> None:
        """La primera vez, el historial de duraciones se arma con los transcripts de las últimas semanas."""
        if not self.estimador.vacio:
            return
        leidos = 0
        for _, archivo in self.archivos_recientes(time.time(), dias * 86400)[:maximo_archivos]:
            if self.cancelado():
                return
            try:
                tam = archivo.stat().st_size
            except OSError:
                continue
            if leidos + tam > maximo_bytes:
                continue
            leidos += tam
            t = Transcript(archivo)
            t.leer()
            proy = Path(t.cwd).name if t.cwd else archivo.parent.name
            for (fin, duracion), detalle in zip(t.turnos, t.detalles):
                self.estimador.agregar(t.sesion, proy, fin, duracion, detalle)
        self.estimador.guardar()

    def actualizar(self, ahora: float | None = None) -> list[dict]:
        ahora = ahora or time.time()
        sesiones = []
        vivos = set()
        for _, archivo in self.archivos_recientes(ahora, ACTIVA):
            vivos.add(archivo)
            t = self.transcripts.get(archivo)
            if t is None:
                t = self.transcripts[archivo] = Transcript(archivo)
            t.leer()
            proy = Path(t.cwd).name if t.cwd else archivo.parent.name
            for (fin, duracion), detalle in zip(t.turnos, t.detalles):
                self.estimador.agregar(t.sesion, proy, fin, duracion, detalle)
            t.turnos.clear()  # ya pasaron al historial: no se ofrecen de nuevo en cada vuelta
            t.detalles.clear()
            # Claude Code toca transcripts viejos al abrir la app (costo, último mensaje) con líneas sin hora:
            # lo que cuenta es la última línea con hora, no la fecha del archivo.
            if t.ultima is None or ahora - t.ultima > ACTIVA:
                continue
            agentes = self.agentes.get(archivo)
            if agentes is None:
                agentes = self.agentes[archivo] = Agentes(archivo.with_suffix("") / "subagents")
            activos, tokens_agentes = agentes.actualizar(ahora)
            trabajando = t.trabajando(ahora)
            transcurrido = max(0.0, ahora - t.prompt) if trabajando and t.prompt else 0.0
            sesiones.append({
                "id": t.sesion, "proyecto": proy, "titulo": t.titulo,
                "inicio": t.inicio or ahora, "ultima": t.ultima or ahora,
                "trabajando": trabajando, "transcurrido": transcurrido,
                "falta": (self.estimador.estimar(transcurrido, proy, t.sesion, t.pasos, t.largo, t.avances)
                          if trabajando else None),
                "plan": t.avance() if trabajando and t.avances else None,
                "historial": self.estimador.suficiente,
                "tokens": t.tokens + tokens_agentes, "turno": t.tokens_desde_prompt if trabajando else 0,
                "salida": t.salida, "cache": t.cache, "contexto": t.contexto,
                "agentes": activos, "herramienta": t.herramienta if trabajando else "",
            })
        for viejo in set(self.transcripts) - vivos:  # las que ya no están activas se olvidan
            self.transcripts.pop(viejo, None)
            self.agentes.pop(viejo, None)
        self.estimador.guardar()
        sesiones.sort(key=lambda s: (not s["trabajando"], -s["ultima"]))
        with self.lock:
            self.sesiones = sesiones
        return sesiones

    def leer(self) -> list[dict]:
        with self.lock:
            return list(self.sesiones)


def formato_tokens(n: int) -> str:
    if n < 1000:
        return str(n)
    if n < 999_950:  # 999 950 ya se redondea a 1000 k: mejor "1.00 M"
        return f"{n / 1000:.1f} k".replace(".0 k", " k")
    return f"{n / 1_000_000:.2f} M"
