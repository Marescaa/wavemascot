"""Transcripts de Claude Code inventados, para las capturas del README.

La isla, el Dashboard y Uso leen los transcripts de ~/.claude/projects. Para las capturas no se leen los tuyos:
se escribe medio año de sesiones de mentira (proyectos, turnos, tokens, herramientas y listas de tareas) en la
carpeta de usuario temporal, más tres sesiones "de ahora" (dos trabajando y una en espera) para la isla.
Todo sale de una semilla fija: las capturas no cambian entre una corrida y otra salvo por la hora.
"""

from __future__ import annotations

import json
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path

DIAS = 182
# (nombre del proyecto, peso: cuánto se usa)
PROYECTOS = [("shop-frontend", 5), ("payments-api", 4), ("recipes-app", 3), ("data-pipeline", 2), ("blog", 1)]
MODELOS = [("claude-opus-5-5", 6), ("claude-sonnet-5-5", 3), ("claude-haiku-5-5", 1)]
HERRAMIENTAS = [("Read", 8), ("Edit", 6), ("Bash", 5), ("Grep", 4), ("Write", 2), ("Glob", 2), ("WebSearch", 1)]

# Las sesiones de ahora, por idioma: (proyecto, título, estado)
AHORA = {
    "en": [("shop-frontend", "Add checkout with saved cards"), ("payments-api", "Fix the flaky webhook tests"),
           ("recipes-app", "Translate onboarding to Portuguese")],
    "es": [("shop-frontend", "Agregar el pago con tarjetas guardadas"),
           ("payments-api", "Arreglar los tests del webhook que fallan"),
           ("recipes-app", "Traducir el onboarding al portugués")],
    "pt": [("shop-frontend", "Adicionar pagamento com cartões salvos"),
           ("payments-api", "Corrigir os testes instáveis do webhook"),
           ("recipes-app", "Traduzir o onboarding para português")],
}


def iso(t: float) -> str:
    return datetime.fromtimestamp(t, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def elegir(azar: random.Random, opciones):
    return azar.choices([o for o, _ in opciones], weights=[p for _, p in opciones])[0]


class Escritor:
    """Arma las líneas de un transcript con el formato de Claude Code (lo justo que leen seguimiento y
    estadisticas)."""

    def __init__(self, azar: random.Random, sesion: str, proyecto: str):
        self.azar, self.sesion, self.proyecto = azar, sesion, proyecto
        self.cwd = f"/home/dev/code/{proyecto}"
        self.lineas: list[dict] = []
        self.n = 0
        self.contexto = azar.randint(12_000, 20_000)
        self.modelo = elegir(azar, MODELOS)

    def ident(self, prefijo: str) -> str:
        self.n += 1
        return f"{prefijo}_{self.sesion[:8]}{self.n:05d}"

    def base(self, tipo: str, t: float) -> dict:
        return {"type": tipo, "sessionId": self.sesion, "cwd": self.cwd, "timestamp": iso(t)}

    def titulo(self, texto: str) -> None:
        self.lineas.append({"type": "ai-title", "sessionId": self.sesion, "aiTitle": texto})

    def pedido(self, t: float, texto: str) -> None:
        d = self.base("user", t)
        d["message"] = {"role": "user", "content": texto}
        self.lineas.append(d)

    def respuesta(self, t: float, herramienta: str | None = None, entrada: dict | None = None,
                  fin: bool = False) -> str | None:
        az = self.azar
        nuevo = az.randint(800, 6_000)
        salida = az.randint(150, 1_400) if not fin else az.randint(300, 900)
        uso = {"input_tokens": az.randint(3, 40), "cache_creation_input_tokens": nuevo,
               "cache_read_input_tokens": self.contexto, "output_tokens": salida}
        self.contexto = min(180_000, self.contexto + nuevo + salida)
        contenido: list[dict] = [{"type": "text", "text": "…"}]
        uso_id = None
        if herramienta:
            uso_id = self.ident("toolu")
            contenido.append({"type": "tool_use", "id": uso_id, "name": herramienta, "input": entrada or {}})
        d = self.base("assistant", t)
        d["message"] = {"id": self.ident("msg"), "model": self.modelo, "role": "assistant", "content": contenido,
                        "usage": uso, "stop_reason": "end_turn" if fin else "tool_use"}
        self.lineas.append(d)
        return uso_id

    def resultado(self, t: float, uso_id: str) -> None:
        d = self.base("user", t)
        d["message"] = {"role": "user", "content": [{"type": "tool_result", "tool_use_id": uso_id, "content": "ok"}]}
        self.lineas.append(d)

    def turno(self, t: float, duracion: float, con_lista: bool = False, cortar_en: float | None = None) -> float:
        """Un turno entero (o cortado a los cortar_en segundos, para una sesión que sigue trabajando).
        Devuelve la hora de la última línea."""
        az = self.azar
        self.pedido(t, "x" * az.randint(40, 600))
        pasos = max(2, int(duracion / az.uniform(12, 30)))
        tareas = az.randint(4, 6) if con_lista else 0
        hechas = 0
        ultima = t
        for i in range(pasos):
            momento = t + duracion * (i + 1) / (pasos + 1)
            if cortar_en is not None and momento - t > cortar_en:
                return ultima
            if tareas and (i == 0 or (i % max(1, pasos // tareas) == 0 and hechas < tareas)):
                if i:
                    hechas += 1
                lista = [{"content": f"paso {k}", "status": "completed" if k < hechas else
                          "in_progress" if k == hechas else "pending"} for k in range(tareas)]
                uso_id = self.respuesta(momento, "TodoWrite", {"todos": lista})
            else:
                uso_id = self.respuesta(momento, elegir(az, HERRAMIENTAS))
            ultima = momento
            if cortar_en is not None and momento + 2 - t > cortar_en:
                return ultima  # la herramienta todavía está corriendo
            self.resultado(momento + az.uniform(0.5, 4), uso_id)
            ultima = momento + 2
        if cortar_en is not None:
            return ultima
        self.respuesta(t + duracion, fin=True)
        return t + duracion

    def guardar(self, carpeta: Path, mtime: float) -> Path:
        carpeta.mkdir(parents=True, exist_ok=True)
        ruta = carpeta / f"{self.sesion}.jsonl"
        with open(ruta, "w", encoding="utf-8") as f:
            for d in self.lineas:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        os.utime(ruta, (mtime, mtime))
        return ruta


def carpeta_de(raiz: Path, proyecto: str) -> Path:
    return raiz / f"-home-dev-code-{proyecto}"


def duracion_turno(azar: random.Random) -> float:
    return max(8.0, min(1500.0, azar.lognormvariate(4.4, 0.85)))  # mediana ~80 s, algunos de 10+ minutos


def historia(raiz: Path, ahora: float, semilla: int = 7) -> None:
    """Medio año de sesiones terminadas: más los días de semana, con rachas de proyectos."""
    az = random.Random(semilla)
    hoy = datetime.fromtimestamp(ahora).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    for dia in range(DIAS, -1, -1):
        inicio_dia = hoy - dia * 86400
        semana = datetime.fromtimestamp(inicio_dia).weekday()
        if az.random() > (0.82 if semana < 5 else 0.35):
            continue
        # el uso va creciendo de a poco con los meses
        sesiones = az.randint(1, 3) + (1 if dia < 60 else 0) + (1 if dia < 14 and az.random() < 0.5 else 0)
        for _ in range(sesiones):
            t = inicio_dia + az.uniform(9, 20) * 3600
            if t > ahora - 1.5 * 3600:  # lo último lo ponen las sesiones de ahora
                continue
            proyecto = elegir(az, PROYECTOS)
            e = Escritor(az, f"{az.getrandbits(64):016x}{az.getrandbits(64):016x}", proyecto)
            for _ in range(az.randint(3, 10)):
                # que ninguna quede "activa" (seguimiento.ACTIVA = 30 min, y un turno dura hasta 25 min):
                # en la isla van solo las tres de ahora
                if t > ahora - 60 * 60:
                    break
                fin = e.turno(t, duracion_turno(az), con_lista=az.random() < 0.4)
                t = fin + az.uniform(30, 900)
            if e.lineas:
                e.guardar(carpeta_de(raiz, proyecto), fin)


def sesiones_de_ahora(raiz: Path, ahora: float, idioma: str, semilla: int = 11) -> None:
    """Dos sesiones trabajando (una con lista de tareas, otra con un subagente) y una en espera."""
    az = random.Random(semilla)
    (p1, t1), (p2, t2), (p3, t3) = AHORA[idioma]

    # 1) Trabajando hace 2 min 40 s, con la lista de tareas por la mitad
    e = Escritor(az, "a1" * 16, p1)
    e.titulo(t1)
    t = ahora - 55 * 60
    for _ in range(4):
        t = e.turno(t, duracion_turno(az)) + az.uniform(60, 300)
    e.turno(ahora - 160, 230, cortar_en=150)
    for cuando, hechas in ((150, 0), (110, 1), (70, 2), (25, 3)):  # la lista de tareas: va por la 4 de 5
        lista = [{"content": f"paso {k}", "status": "completed" if k < hechas else
                  "in_progress" if k == hechas else "pending"} for k in range(5)]
        e.respuesta(ahora - cuando + 1, "TodoWrite", {"todos": lista})
    e.lineas.sort(key=lambda d: d.get("timestamp", ""))
    e.respuesta(ahora - 4, "Edit")  # lo que está haciendo justo ahora
    e.guardar(carpeta_de(raiz, p1), ahora - 3)

    # 2) Trabajando hace 48 s, con un subagente corriendo
    e = Escritor(az, "b2" * 16, p2)
    e.titulo(t2)
    t = ahora - 25 * 60
    for _ in range(3):
        t = e.turno(t, duracion_turno(az)) + az.uniform(60, 200)
    e.turno(ahora - 48, 300, cortar_en=40)
    e.respuesta(ahora - 3, "Bash")
    ruta = e.guardar(carpeta_de(raiz, p2), ahora - 2)
    agentes = ruta.with_suffix("") / "subagents"
    agentes.mkdir(parents=True, exist_ok=True)
    sub = Escritor(az, "c3" * 16, p2)
    for i in range(4):
        sub.respuesta(ahora - 40 + i * 9, "Grep")
    for d in sub.lineas:
        d["isSidechain"] = True
    sub.sesion = "agent-explore"
    sub.guardar(agentes, ahora - 4)
    (agentes / "agent-explore.meta.json").write_text(json.dumps({"finished": False}))

    # 3) En espera: terminó hace 6 minutos
    e = Escritor(az, "d4" * 16, p3)
    e.titulo(t3)
    t = ahora - 40 * 60
    for _ in range(3):
        t = e.turno(t, duracion_turno(az)) + az.uniform(60, 200)
    fin = e.turno(ahora - 6 * 60 - 240, 240)
    e.guardar(carpeta_de(raiz, p3), fin)


def escribir(raiz: Path, idioma: str = "en", ahora: float | None = None) -> None:
    ahora = ahora or time.time()
    historia(raiz, ahora)
    sesiones_de_ahora(raiz, ahora, idioma)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        sys.exit("uso: python tools/datos_ejemplo.py <carpeta de destino>")
    destino = Path(sys.argv[1])
    escribir(destino)
    archivos = list(destino.rglob("*.jsonl"))
    print(len(archivos), "transcripts,", sum(f.stat().st_size for f in archivos) // 1024, "KB")
