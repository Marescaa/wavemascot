"""Las cuentas de las secciones Dashboard y Uso de los ajustes: cuánto usaste Claude Code y cómo.

Todo sale de los transcripts de ~/.claude/projects (los mismos que lee la barra de sesiones); nada se
manda a ningún lado. De cada transcript se guarda un resumen chico (tokens por tramo de 5 minutos y por
modelo, turnos, herramientas) en ~/.wavemascot/cache/uso.json, así la próxima vez solo se leen los que
cambiaron; los que están abiertos se siguen leyendo de a pedazos, como en la barra.

Los tokens se cuentan igual que en la barra: entrada (lo que se mandó, con lo que se guardó en caché) +
salida (lo que respondió Claude). Las lecturas de la caché van aparte.
"""

from __future__ import annotations

import json
import os
import statistics
import threading
import time
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

import seguimiento

TRAMO = 300            # segundos de cada tramo en el que se agrupan los tokens
VERSION = 1
# Los lapsos de la sección Uso: cuánto abarcan, cada cuánto va una barra del gráfico y cuántas barras son.
# Todos terminan ahora (las últimas 5 horas, los últimos 7 días...), así se ven moverse en vivo.
LAPSOS = {"5h": (5 * 3600, 300, 60), "1d": (86400, 3600, 24), "7d": (7 * 86400, 6 * 3600, 28),
          "30d": (30 * 86400, 86400, 30), "180d": (182 * 86400, 7 * 86400, 26)}


class Registro(seguimiento.Transcript):
    """Un transcript que además anota cuándo se gastó cada token, con qué modelo y qué herramientas se usaron."""

    def __init__(self, ruta: Path):
        super().__init__(ruta)
        self.tramos: dict[int, dict[str, list[int]]] = {}  # tramo -> modelo -> [entrada, caché, salida, respuestas]
        self.herramientas: Counter = Counter()
        self.usos: set[str] = set()
        self.historia: list[tuple[float, float]] = []     # todos los turnos (el de la barra los va vaciando)

    def contar(self, d: dict) -> None:
        antes = (self.entrada, self.cache, self.salida)
        super().contar(d)
        mensaje = d.get("message") or {}
        for c in mensaje.get("content") or ():
            if isinstance(c, dict) and c.get("type") == "tool_use" and c.get("name") and c.get("id") not in self.usos:
                self.usos.add(c.get("id"))
                self.herramientas[str(c["name"]).rsplit("__", 1)[-1]] += 1
        delta = (self.entrada - antes[0], self.cache - antes[1], self.salida - antes[2])
        momento = seguimiento.hora(d.get("timestamp")) if d.get("timestamp") else None
        if any(delta) and momento is not None:
            modelo = str(mensaje.get("model") or "?")
            cuenta = self.tramos.setdefault(int(momento // TRAMO), {}).setdefault(modelo, [0, 0, 0, 0])
            for i, valor in enumerate(delta):
                cuenta[i] += valor
            cuenta[3] += 1

    def terminar_turno(self, momento: float | None) -> None:
        cuantos = len(self.turnos)
        super().terminar_turno(momento)
        if len(self.turnos) > cuantos:
            self.historia.append(self.turnos[-1])

    def resumen(self) -> dict:
        return {"sesion": self.sesion, "titulo": self.titulo,
                "proy": Path(self.cwd).name if self.cwd else self.ruta.parent.name,
                "inicio": self.inicio, "ultima": self.ultima, "contexto": self.contexto,
                # copias: al resumen se le suman los subagentes, y eso no puede volver a este registro
                "tramos": {str(k): {modelo: list(c) for modelo, c in v.items()} for k, v in self.tramos.items()},
                "turnos": [[round(fin, 1), round(dur, 1)] for fin, dur in self.historia],
                "herramientas": dict(self.herramientas)}


def nombre_modelo(modelo: str) -> str:
    """claude-opus-4-5-20251101 -> Opus 4.5 (lo que entra en una etiqueta)."""
    partes = [p for p in modelo.replace("claude-", "").split("-") if not (p.isdigit() and len(p) >= 6)]
    if not partes or modelo in ("?", "<synthetic>"):
        return "—"
    familia = next((p for p in partes if p.isalpha()), partes[0])
    numeros = [p for p in partes if p.isdigit()]
    return (familia.capitalize() + " " + ".".join(numeros)).strip()


def resumen_sano(resumen) -> bool:
    """Un resumen del caché con la forma esperada (uno roto o tocado a mano se descarta y se vuelve a leer)."""
    if not isinstance(resumen, dict) or not isinstance(resumen.get("tramos"), dict):
        return False
    for por_modelo in resumen["tramos"].values():
        if not isinstance(por_modelo, dict) or not all(
                isinstance(c, list) and len(c) == 4 and all(isinstance(x, (int, float)) for x in c)
                for c in por_modelo.values()):
            return False
    turnos = resumen.get("turnos")
    return isinstance(turnos, list) and all(isinstance(x, list) and len(x) == 2 for x in turnos)


class Analisis:
    """Lee los transcripts de los últimos días y arma el informe. actualizar() va en un hilo aparte."""

    def __init__(self, carpeta: Path | None = None, cache: Path | None = None, dias: int = 370):  # 6 meses y los 6 anteriores
        self.carpeta = carpeta or seguimiento.carpeta_claude() / "projects"
        self.cache = cache
        self.dias = dias
        self.abiertos: dict[Path, tuple[Registro, list[Registro]]] = {}
        self.guardados: dict[str, dict] = {}   # ruta -> {"firma": [...], "resumen": {...}}
        self.cancelado = lambda: False
        self.cargado = False

    # --- lectura ----------------------------------------------------------------

    def cargar_cache(self) -> None:
        self.cargado = True
        if not self.cache:
            return
        try:
            datos = json.loads(self.cache.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if isinstance(datos, dict) and datos.get("version") == VERSION and isinstance(datos.get("archivos"), dict):
            self.guardados = {k: v for k, v in datos["archivos"].items()
                              if isinstance(v, dict) and resumen_sano(v.get("resumen"))}

    def guardar_cache(self) -> None:
        if not self.cache:
            return
        try:
            self.cache.parent.mkdir(parents=True, exist_ok=True)
            temporal = self.cache.with_name(f"{self.cache.stem}.{os.getpid()}-{threading.get_ident()}.tmp")
            temporal.write_text(json.dumps({"version": VERSION, "archivos": self.guardados}), encoding="utf-8")
            os.replace(temporal, self.cache)
        except OSError:  # otro proceso lo estaba leyendo (la barra o los ajustes): se guarda en la próxima
            try:
                temporal.unlink(missing_ok=True)
            except (OSError, UnboundLocalError):
                pass

    @staticmethod
    def firma(archivo: Path, agentes: list[Path]) -> list:
        total, ultimo = 0, 0
        for a in (archivo, *agentes):
            try:
                dato = a.stat()
            except OSError:
                continue
            total += dato.st_size
            ultimo = max(ultimo, dato.st_mtime_ns)
        return [total, ultimo, len(agentes)]

    def resumen_de(self, archivo: Path, ahora: float, leido: list[int]) -> dict | None:
        try:
            agentes = sorted((archivo.with_suffix("") / "subagents").glob("agent-*.jsonl"))
        except OSError:
            agentes = []
        firma = self.firma(archivo, agentes)
        clave = str(archivo)
        guardado = self.guardados.get(clave)
        if guardado and guardado.get("firma") == firma and archivo not in self.abiertos:
            return guardado["resumen"]
        if archivo not in self.abiertos:
            self.abiertos[archivo] = (Registro(archivo), [])
        principal, de_agentes = self.abiertos[archivo]
        conocidos = {r.ruta for r in de_agentes}
        de_agentes.extend(Registro(a) for a in agentes if a not in conocidos)
        for registro in (principal, *de_agentes):
            antes = registro.offset
            registro.leer()
            leido[0] += registro.offset - antes
        resumen = principal.resumen()
        tokens_agentes = 0
        for registro in de_agentes:  # los subagentes suman a la sesión que los lanzó
            tokens_agentes += registro.tokens
            for tramo, modelos in registro.tramos.items():
                destino = resumen["tramos"].setdefault(str(tramo), {})
                for modelo, cuenta in modelos.items():
                    suma = destino.setdefault(modelo, [0, 0, 0, 0])
                    destino[modelo] = [a + b for a, b in zip(suma, cuenta)]
            for nombre, veces in registro.herramientas.items():
                resumen["herramientas"][nombre] = resumen["herramientas"].get(nombre, 0) + veces
        resumen["agentes"] = tokens_agentes
        resumen["trabajando"] = principal.trabajando(ahora)
        self.guardados[clave] = {"firma": firma, "resumen": resumen}
        # Una sesión que ya no cambia no hace falta tenerla abierta: queda su resumen.
        if principal.ultima is None or ahora - principal.ultima > seguimiento.ACTIVA:
            self.abiertos.pop(archivo, None)
            resumen["trabajando"] = False
        return resumen

    def actualizar(self, ahora: float | None = None) -> dict | None:
        """Lee lo nuevo y devuelve el informe (None si se canceló a mitad de camino)."""
        ahora = ahora or time.time()
        empezo = time.perf_counter()
        if not self.cargado:
            self.cargar_cache()
        leido, resumenes, vivos = [0], [], set()
        try:
            proyectos = [p for p in self.carpeta.iterdir() if p.is_dir()]
        except OSError:
            proyectos = []
        for proyecto in proyectos:
            try:
                archivos = list(proyecto.glob("*.jsonl"))
            except OSError:
                continue
            for archivo in archivos:
                if self.cancelado():
                    return None
                try:
                    if ahora - archivo.stat().st_mtime > self.dias * 86400:
                        continue
                except OSError:
                    continue
                vivos.add(str(archivo))
                resumen = self.resumen_de(archivo, ahora, leido)
                if resumen:
                    resumenes.append(resumen)
        for viejo in set(self.guardados) - vivos:
            self.guardados.pop(viejo, None)
        for viejo in [a for a in self.abiertos if str(a) not in vivos]:  # se borró o ya es demasiado viejo
            self.abiertos.pop(viejo, None)
        if leido[0]:
            self.guardar_cache()
        informe = armar_informe(resumenes, ahora)
        informe["analisis"] = {"archivos": len(resumenes), "bytes": leido[0], "hora": ahora,
                               "segundos": time.perf_counter() - empezo}
        return informe


# --- el informe -------------------------------------------------------------------

def _suma(cuentas) -> list[int]:
    total = [0, 0, 0, 0]
    for cuenta in cuentas:
        for i in range(4):
            total[i] += int(cuenta[i])
    return total


def armar_informe(resumenes: list[dict], ahora: float, dias: int = 14) -> dict:
    hoy = datetime.fromtimestamp(ahora).date()
    por_dia: dict[date, dict] = {hoy - timedelta(days=i): {"entrada": 0, "cache": 0, "salida": 0, "sesiones": set(),
                                                           "turnos": 0, "trabajo": 0.0} for i in range(dias)}
    por_hora = [0] * 24
    proyectos: dict[str, list] = {}
    duraciones: list[float] = []
    semana, semana_anterior = 0, 0
    lapsos = {clave: {"entrada": 0, "cache": 0, "salida": 0, "respuestas": 0, "anterior": 0, "modelos": Counter(),
                      "proyectos": Counter(), "sesiones": set(), "serie": [0] * cuantos}
              for clave, (_, _, cuantos) in LAPSOS.items()}
    reciente, primero_reciente = 0, None   # tokens de los últimos 15 minutos
    for r in resumenes:
        tokens_semana = 0
        for clave, por_modelo in (r.get("tramos") or {}).items():
            try:
                tramo = int(clave)
            except ValueError:
                continue
            momento = tramo * TRAMO
            hace = ahora - momento
            if hace < 0:  # con hora futura (el reloj se corrió): no se cuenta en ningún lado
                continue
            dia = datetime.fromtimestamp(momento).date()
            entrada, cache, salida, respuestas = _suma(por_modelo.values())
            tokens = entrada + salida
            antiguedad = (hoy - dia).days
            if dia in por_dia:
                d = por_dia[dia]
                d["entrada"] += entrada
                d["cache"] += cache
                d["salida"] += salida
                d["sesiones"].add(r.get("sesion"))
                por_hora[datetime.fromtimestamp(momento).hour] += tokens
            if 0 <= antiguedad < 7:
                semana += tokens
                tokens_semana += tokens
            elif 7 <= antiguedad < 14:
                semana_anterior += tokens
            if hace < 900:
                reciente += tokens
                primero_reciente = min(primero_reciente or momento, momento)
            for nombre, (largo, paso, cuantos) in LAPSOS.items():
                if hace < largo:
                    lapso = lapsos[nombre]
                    lapso["entrada"] += entrada
                    lapso["cache"] += cache
                    lapso["salida"] += salida
                    lapso["respuestas"] += respuestas
                    lapso["serie"][cuantos - 1 - min(cuantos - 1, int(hace // paso))] += tokens
                    lapso["sesiones"].add(r.get("sesion"))
                    lapso["proyectos"][r.get("proy") or "?"] += tokens
                    for modelo, cuenta in por_modelo.items():
                        lapso["modelos"][nombre_modelo(modelo)] += int(cuenta[0]) + int(cuenta[2])
                elif hace < 2 * largo:
                    lapsos[nombre]["anterior"] += tokens
        for fin, duracion in r.get("turnos") or ():
            dia = datetime.fromtimestamp(fin).date()
            if dia in por_dia:
                por_dia[dia]["turnos"] += 1
                por_dia[dia]["trabajo"] += duracion
            if (hoy - dia).days < 7:
                duraciones.append(duracion)
        if tokens_semana:
            p = proyectos.setdefault(r.get("proy") or "?", [0, set()])
            p[0] += tokens_semana
            p[1].add(r.get("sesion"))
    lista_dias = [{"dia": dia, "entrada": d["entrada"], "cache": d["cache"], "salida": d["salida"],
                   "tokens": d["entrada"] + d["salida"], "sesiones": len(d["sesiones"]), "turnos": d["turnos"],
                   "trabajo": d["trabajo"]} for dia, d in sorted(por_dia.items())]
    duraciones.sort()
    for lapso in lapsos.values():
        lapso["tokens"] = lapso["entrada"] + lapso["salida"]
        lapso["acierto_cache"] = lapso["cache"] / max(1, lapso["cache"] + lapso["entrada"])
        lapso["modelos"] = lapso["modelos"].most_common(3)
        lapso["proyectos"] = lapso["proyectos"].most_common(3)
        lapso["sesiones"] = len(lapso["sesiones"])
    minutos = max(1.0, min(15.0, (ahora - primero_reciente) / 60)) if primero_reciente else 15.0
    return {
        "dias": lista_dias, "hoy": lista_dias[-1], "ayer": lista_dias[-2] if len(lista_dias) > 1 else None,
        "semana": semana, "semana_anterior": semana_anterior, "por_hora": por_hora,
        "proyectos": sorted(((n, v[0], len(v[1])) for n, v in proyectos.items()), key=lambda x: -x[1])[:6],
        "turnos": {"cuantos": len(duraciones),
                   "mediana": statistics.median(duraciones) if duraciones else 0.0,
                   "p90": duraciones[int(len(duraciones) * 0.9)] if duraciones else 0.0},
        "lapsos": lapsos, "ritmo": reciente / minutos,  # tokens por minuto, ahora
    }
