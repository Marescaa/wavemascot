"""La barra de sesiones lee bien los transcripts de Claude Code: python -m unittest discover tests"""

from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import seguimiento as s  # noqa: E402


def iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")


def usuario(epoch, texto="hola", **extra):
    return {"type": "user", "timestamp": iso(epoch), "message": {"role": "user", "content": texto}, **extra}


def resultado(epoch):
    return {"type": "user", "timestamp": iso(epoch),
            "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "x", "content": "ok"}]}}


def respuesta(epoch, ident, salida=100, entrada=10, cache=1000, fin="tool_use", herramienta="Bash", **extra):
    contenido = [{"type": "tool_use", "id": "t" + ident, "name": herramienta, "input": {}}] if herramienta else []
    return {"type": "assistant", "timestamp": iso(epoch), "cwd": "/a/proyecto",
            "message": {"id": ident, "stop_reason": fin, "content": contenido,
                        "usage": {"input_tokens": entrada, "cache_creation_input_tokens": 5,
                                  "cache_read_input_tokens": cache, "output_tokens": salida}}, **extra}


def escribir(ruta: Path, lineas: list[dict], modo="w") -> None:
    with open(ruta, modo, encoding="utf-8") as f:
        for linea in lineas:
            f.write(json.dumps(linea) + "\n")


class Transcripts(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.ruta = self.dir / "sesion1.jsonl"
        self.t0 = time.time() - 600

    def leido(self) -> s.Transcript:
        t = s.Transcript(self.ruta)
        t.leer()
        return t

    def test_cuenta_cada_respuesta_una_vez(self):
        # Claude Code repite el mismo mensaje (mismo id y mismo uso) en una línea por bloque.
        escribir(self.ruta, [usuario(self.t0), respuesta(self.t0 + 1, "m1"), respuesta(self.t0 + 1, "m1"),
                             resultado(self.t0 + 2), respuesta(self.t0 + 3, "m2")])
        t = self.leido()
        self.assertEqual(t.salida, 200)
        self.assertEqual(t.tokens, 2 * (100 + 10 + 5))
        self.assertEqual(t.cache, 2000)  # las lecturas de caché van aparte
        self.assertEqual(t.contexto, 10 + 5 + 1000)

    def test_trabajando_hasta_el_final_del_turno(self):
        escribir(self.ruta, [usuario(self.t0), respuesta(self.t0 + 5, "m1"), resultado(self.t0 + 6)])
        t = self.leido()
        self.assertTrue(t.trabajando(self.t0 + 10))
        self.assertEqual(t.herramienta, "Bash")
        self.assertFalse(t.trabajando(self.t0 + 6 + s.COLGADA + 1))  # nada escrito hace mucho: se cortó
        escribir(self.ruta, [respuesta(self.t0 + 40, "m2", fin="end_turn", herramienta=None),
                             {"type": "system", "subtype": "stop_hook_summary", "timestamp": iso(self.t0 + 41)}], "a")
        t.leer()
        self.assertFalse(t.trabajando(self.t0 + 42))
        self.assertEqual([round(d) for _, d in t.turnos], [40])  # un solo turno, aunque haya dos finales

    def test_resultados_y_mensajes_internos_no_son_tuyos(self):
        escribir(self.ruta, [usuario(self.t0), respuesta(self.t0 + 1, "m1", fin="end_turn"),
                             resultado(self.t0 + 2), usuario(self.t0 + 3, isMeta=True),
                             usuario(self.t0 + 4, isCompactSummary=True)])
        self.assertFalse(self.leido().trabajando(self.t0 + 5))

    def test_interrupcion_termina_el_turno(self):
        interrumpido = {"type": "user", "timestamp": iso(self.t0 + 9), "message": {
            "role": "user", "content": [{"type": "text", "text": "[Request interrupted by user]"}]}}
        escribir(self.ruta, [usuario(self.t0), respuesta(self.t0 + 2, "m1"), interrumpido])
        self.assertFalse(self.leido().trabajando(self.t0 + 10))

    def test_mensaje_en_cola_no_reinicia_el_turno(self):
        escribir(self.ruta, [usuario(self.t0), respuesta(self.t0 + 2, "m1"), usuario(self.t0 + 30, "y además")])
        self.assertAlmostEqual(self.leido().prompt, self.t0, places=2)

    def test_lee_de_a_pedazos_y_espera_la_linea_entera(self):
        linea = json.dumps(respuesta(self.t0 + 1, "m1")) + "\n"
        escribir(self.ruta, [usuario(self.t0)])
        with open(self.ruta, "a", encoding="utf-8") as f:
            f.write(linea[:40])
        t = self.leido()
        self.assertEqual(t.salida, 0)
        with open(self.ruta, "a", encoding="utf-8") as f:
            f.write(linea[40:])
        self.assertTrue(t.leer())
        self.assertEqual(t.salida, 100)
        self.assertFalse(t.leer())  # nada nuevo


class Monitor(unittest.TestCase):
    def test_sesiones_agentes_y_viejas(self):
        raiz = Path(tempfile.mkdtemp())
        proyecto = raiz / "A--proyecto"
        proyecto.mkdir()
        ahora = time.time()
        escribir(proyecto / "viva.jsonl", [usuario(ahora - 60), respuesta(ahora - 30, "m1")])
        # Vieja, pero con el archivo recién tocado (Claude Code agrega líneas sin hora al abrir).
        escribir(proyecto / "vieja.jsonl", [usuario(ahora - 86400), {"type": "cost-state", "totalCostUSD": 1}])
        agentes = proyecto / "viva" / "subagents"
        agentes.mkdir(parents=True)
        escribir(agentes / "agent-a1.jsonl", [respuesta(ahora - 5, "s1", salida=50, isSidechain=True)])
        (agentes / "agent-a1.meta.json").write_text('{"agentType": "Explore"}', encoding="utf-8")
        escribir(agentes / "agent-a2.jsonl", [respuesta(ahora - 5, "s2", salida=50, isSidechain=True)])
        (agentes / "agent-a2.meta.json").write_text('{"finished": true}', encoding="utf-8")
        sesiones = s.Monitor(carpeta=raiz).actualizar(ahora)
        self.assertEqual([x["id"] for x in sesiones], ["viva"])
        viva = sesiones[0]
        self.assertTrue(viva["trabajando"])
        self.assertEqual(viva["agentes"], 1)
        self.assertEqual(viva["tokens"], 115 + 2 * 65)  # los subagentes suman
        self.assertEqual(viva["proyecto"], "proyecto")


class Estimador(unittest.TestCase):
    def test_estima_con_los_turnos_mas_largos(self):
        e = s.Estimador()
        for i, d in enumerate((10, 20, 30, 60, 120, 300)):
            e.agregar("x", "p", 1000 + i, d)
        self.assertEqual(e.estimar(0, "p"), 60)          # mediana de los 6 (los más nuevos pesan apenas más)
        self.assertEqual(e.estimar(50, "p"), 120 - 50)   # solo 60, 120 y 300
        self.assertIsNone(e.estimar(200, "p"))           # más largo que casi todos: no se inventa un número
        for i in range(3):
            e.agregar("y", "q", 2000 + i, 100.2)
        self.assertEqual(e.estimar(100.1, "q"), 1.0)     # nunca 0 ni negativo

    def test_se_guarda_y_no_repite(self):
        archivo = Path(tempfile.mkdtemp()) / "duraciones.json"
        e = s.Estimador(archivo)
        e.agregar("x", "p", 1000, 30)
        e.agregar("x", "p", 1000, 30)
        e.agregar("x", "p", 1001, 0.2)  # los turnos instantáneos no cuentan
        e.guardar()
        self.assertEqual(len(s.Estimador(archivo).turnos), 1)

    def test_historial_lleno_no_se_reescribe_en_cada_vuelta(self):
        raiz = Path(tempfile.mkdtemp())
        (raiz / "p").mkdir()
        ahora = time.time()
        archivo = raiz / "duraciones.json"
        e = s.Estimador(archivo)
        for i in range(s.MAX_HISTORIAL + 20):  # historial lleno con turnos más nuevos que el de la sesión
            e.agregar("otra", "p", ahora + i, 30)
        e.guardar()
        escribir(raiz / "p" / "viva.jsonl", [usuario(ahora - 100), respuesta(ahora - 50, "m1", fin="end_turn")])
        mon = s.Monitor(archivo, carpeta=raiz)
        mon.actualizar(ahora)
        mtime = archivo.stat().st_mtime_ns
        mon.actualizar(ahora + 1)
        mon.actualizar(ahora + 2)
        self.assertEqual(archivo.stat().st_mtime_ns, mtime)
        self.assertFalse(mon.estimador.cambios)


class Parecidos(unittest.TestCase):
    """La estimación pesa más a los turnos que se parecen al que está corriendo."""

    def historial(self) -> s.Estimador:
        e = s.Estimador()
        for i in range(12):  # cortos sin lista de tareas y largos con lista, mezclados
            e.agregar("a", "p", 1000 + 2 * i, 40, {"largo": 20})
            e.agregar("a", "p", 1001 + 2 * i, 600, {"largo": 900, "pasos": [5, 10, 15, 20, 200, 400],
                                                    "avances": [[10, 0, 4], [200, 2, 4], [550, 4, 4]]})
        return e

    def test_pedido_largo_con_herramientas_espera_mas(self):
        e = self.historial()
        self.assertEqual(e.estimar(20, "p", "b", [], 20), 20)
        self.assertEqual(e.estimar(20, "p", "b", [5, 10, 15, 20], 900), 580)

    def test_lista_de_tareas(self):
        e = self.historial()
        # A los 300 s solo quedan los largos: faltan 300.
        self.assertEqual(e.estimar(300, "p", "b", [5, 10, 15, 20, 200], 900, [(10, 0, 4), (200, 2, 4)]), 300)
        self.assertEqual(s.plan_a_los([(10, 0, 4), (200, 2, 4)], 100), (0, 4))
        self.assertIsNone(s.plan_a_los([(10, 0, 4)], 5))
        plan = s.Plan()
        self.assertTrue(plan.anotar("TodoWrite", {"todos": [{"status": "completed"}, {"status": "pending"}]}))
        self.assertEqual((plan.hechas, plan.total), (1, 2))
        plan.anotar("mcp__ccd_turn__update_plan", {"items": [{"status": "in_progress"}, {"status": "pending"},
                                                              {"status": "pending"}]})
        plan.anotar("mcp__ccd_turn__update_plan", {"advance": True})
        self.assertEqual((plan.hechas, plan.total), (1, 3))
        plan.anotar("mcp__ccd_turn__update_plan", {"done": [2, 99], "start": 3})
        self.assertEqual((plan.hechas, plan.total), (2, 3))
        plan.anotar("mcp__ccd_turn__wrap_up", {"recap": "listo"})
        self.assertEqual((plan.hechas, plan.total), (3, 3))
        self.assertFalse(plan.anotar("Bash", {"command": "ls"}))
        self.assertFalse(plan.anotar("TodoWrite", "roto"))
        plan.anotar("TodoWrite", {"todos": []})  # la lista vacía la vacía
        self.assertEqual((plan.hechas, plan.total), (0, 0))
        for _ in range(3):
            plan.anotar("TaskCreate", {"subject": "x"})
        plan.anotar("TaskUpdate", {"taskId": "7", "status": "completed"})
        plan.anotar("TaskUpdate", {"taskId": "7", "status": "completed"})  # la misma dos veces: una hecha
        self.assertEqual((plan.hechas, plan.total), (1, 3))
        plan.anotar("TaskUpdate", {"taskId": "7", "status": "deleted"})    # se borra la hecha, no una pendiente
        self.assertEqual((plan.hechas, plan.total), (0, 2))
        e = s.Estimador()
        for i in range(8):  # un historial con más hechas que tareas (archivo tocado a mano) no rompe nada
            e.agregar("a", "p", 100 + i, 500, {"avances": [[1, 5, 2], [2, -3, -1]]})
        self.assertEqual(e.turnos[0]["avances"], [(1.0, 2, 2), (2.0, 0, 0)])
        self.assertEqual(e.estimar(100, "p", "b", [], 0, [(1, 0, 3)]), 400)

    def test_lista_de_un_turno_a_otro(self):
        t = s.Transcript(Path(tempfile.mkdtemp()) / "x.jsonl")
        t.prompt = 100.0
        for _ in range(2):
            t.plan.anotar("TaskCreate", {})
        t.plan.anotar("TaskUpdate", {"taskId": "1", "status": "completed"})
        t.plan.anotar("TaskUpdate", {"taskId": "2", "status": "completed"})
        self.assertEqual(t.avance(), (2, 2))
        t.empezar_turno(200.0)  # lo hecho en el turno anterior no cuenta como avance del nuevo
        t.plan.anotar("TaskCreate", {})
        t.plan.anotar("TaskCreate", {})
        self.assertEqual(t.avance(), (0, 2))
        t.plan.anotar("TaskUpdate", {"taskId": "3", "status": "completed"})
        self.assertEqual(t.avance(), (1, 2))

    def test_precision_y_archivo_viejo(self):
        e = self.historial()
        for i in range(40):
            e.agregar("c", "p", 5000 + i, 40 if i % 2 else 600, {"largo": 20 if i % 2 else 900})
        medida = e.precision()
        self.assertGreater(medida["muestras"], 100)
        self.assertGreater(medida["dentro_del_doble"], 0.5)
        archivo = Path(tempfile.mkdtemp()) / "duraciones.json"
        archivo.write_text('{"turnos": [{"dur": 40, "fin": 1000, "proy": "p", "sesion": "x"}]}', encoding="utf-8")
        self.assertTrue(s.Estimador(archivo).vacio)  # sin los pasos de cada turno: se aprende de nuevo
        e.archivo = archivo
        e.guardar()
        otro = s.Estimador(archivo)
        self.assertEqual(len(otro.turnos), len(e.turnos))
        self.assertEqual(otro.turnos[1]["avances"], [(10.0, 0, 4), (200.0, 2, 4), (550.0, 4, 4)])


class Robustez(unittest.TestCase):
    """Lo que encontró la revisión: nada raro en disco puede trabar la barra ni el ícono."""

    def test_historial_roto_se_ignora(self):
        carpeta = Path(tempfile.mkdtemp())
        for contenido in ("null", "[]", '"x"', "{roto", '{"turnos": 5}',
                          '{"turnos": [{"dur": 5}, {"dur": 30, "fin": "x"}, {"dur": null, "fin": 1},'
                          ' {"dur": "30", "fin": 1e400}, 7, {"dur": 40, "fin": 1000}]}'):
            archivo = carpeta / "duraciones.json"
            archivo.write_text(contenido, encoding="utf-8")
            e = s.Estimador(archivo)
            e.estimar(10, "p")
            e.agregar("x", "p", 2000, 20)
            e.guardar()  # no explota al ordenar
            self.assertTrue(all(isinstance(t["dur"], float) for t in e.turnos), contenido)

    def test_linea_rara_no_se_lleva_las_siguientes(self):
        ruta = Path(tempfile.mkdtemp()) / "x.jsonl"
        t0 = time.time() - 100
        raras = [{"type": "assistant", "message": "texto"}, {"type": "assistant", "message": {"usage": []}},
                 {"type": "assistant", "message": {"id": "z", "usage": {"output_tokens": "abc"}}},
                 {"type": "user", "message": {"content": 5}}, {"type": "user", "timestamp": "0001-01-01T00:00:00"}]
        escribir(ruta, [usuario(t0), *raras, respuesta(t0 + 5, "m1", fin="end_turn", herramienta=None)])
        t = s.Transcript(ruta)
        t.leer()
        self.assertEqual(t.salida, 100)
        self.assertFalse(t.trabajando(t0 + 10))

    def test_turno_que_quedo_abierto_no_se_traga_el_siguiente(self):
        ruta = Path(tempfile.mkdtemp()) / "x.jsonl"
        ahora = time.time()
        hace_dias = ahora - 3 * 86400
        escribir(ruta, [usuario(hace_dias), respuesta(hace_dias + 5, "m1"),  # se cerró la terminal acá
                        usuario(ahora - 20, "hola de nuevo"), respuesta(ahora - 10, "m2")])
        t = s.Transcript(ruta)
        t.leer()
        self.assertTrue(t.trabajando(ahora))
        self.assertAlmostEqual(t.prompt, ahora - 20, places=2)

    def test_mensaje_interno_que_hace_volver_a_trabajar(self):
        # El informe de un subagente llega como mensaje interno (isMeta) y Claude sigue sin que escribas.
        ruta = Path(tempfile.mkdtemp()) / "x.jsonl"
        t0 = time.time() - 300
        escribir(ruta, [usuario(t0), respuesta(t0 + 5, "m1", fin="end_turn", herramienta=None),
                        {"type": "system", "subtype": "stop_hook_summary", "timestamp": iso(t0 + 6)},
                        usuario(t0 + 100, "informe del subagente", isMeta=True), respuesta(t0 + 104, "m2")])
        t = s.Transcript(ruta)
        t.leer()
        self.assertTrue(t.trabajando(t0 + 110))
        self.assertAlmostEqual(t.prompt, t0 + 100, places=2)
        escribir(ruta, [respuesta(t0 + 130, "m3", fin="end_turn", herramienta=None)], "a")
        t.leer()
        self.assertEqual([round(d) for _, d in t.turnos], [5, 30])

    def test_limite_de_uso_corta_el_turno(self):
        # Al llegar al límite, Claude Code escribe un aviso de error "sintético"; horas después seguís.
        ruta = Path(tempfile.mkdtemp()) / "x.jsonl"
        t0 = time.time() - 4 * 3600
        error = {"type": "assistant", "isApiErrorMessage": True, "timestamp": iso(t0 + 600),
                 "message": {"id": "e1", "model": "<synthetic>", "stop_reason": "stop_sequence",
                             "content": [{"type": "text", "text": "You've hit your limit"}]}}
        cola = {"type": "queue-operation", "timestamp": iso(t0 + 3 * 3600)}
        escribir(ruta, [usuario(t0), respuesta(t0 + 300, "m1"), error])
        t = s.Transcript(ruta)
        t.leer()
        self.assertFalse(t.trabajando(t0 + 700))
        escribir(ruta, [cola, usuario(t0 + 3 * 3600, "seguí"), respuesta(t0 + 3 * 3600 + 30, "m2", fin="end_turn",
                                                                       herramienta=None)], "a")
        t.leer()
        self.assertEqual([round(d) for _, d in t.turnos], [600, 30])

    def test_hook_de_stop_que_hace_seguir(self):
        ruta = Path(tempfile.mkdtemp()) / "x.jsonl"
        t0 = time.time() - 100
        escribir(ruta, [usuario(t0), respuesta(t0 + 10, "m1", fin="end_turn", herramienta=None),
                        {"type": "system", "subtype": "stop_hook_summary", "timestamp": iso(t0 + 11)},
                        respuesta(t0 + 13, "m2")])
        t = s.Transcript(ruta)
        t.leer()
        self.assertTrue(t.trabajando(t0 + 20))
        self.assertAlmostEqual(t.prompt, t0 + 13, places=2)

    def test_herramienta_larga_sigue_trabajando(self):
        ruta = Path(tempfile.mkdtemp()) / "x.jsonl"
        t0 = time.time() - 4000
        escribir(ruta, [usuario(t0), respuesta(t0 + 5, "m1")])  # pide un Bash que tarda una hora
        t = s.Transcript(ruta)
        t.leer()
        self.assertTrue(t.trabajando(t0 + 3600))
        escribir(ruta, [resultado(t0 + 3700)], "a")
        t.leer()
        self.assertTrue(t.trabajando(t0 + 3800))
        self.assertFalse(t.trabajando(t0 + 3700 + s.COLGADA + 1))  # con el resultado, vuelve el margen corto

    def test_aviso_de_tarea_sin_respuesta_no_queda_trabajando(self):
        ruta = Path(tempfile.mkdtemp()) / "x.jsonl"
        t0 = time.time() - 120
        escribir(ruta, [usuario(t0), respuesta(t0 + 5, "m1", fin="end_turn", herramienta=None),
                        usuario(t0 + 60, "<task-notification>listo</task-notification>")])
        t = s.Transcript(ruta)
        t.leer()
        self.assertFalse(t.trabajando(t0 + 70))

    def test_comando_local_no_queda_trabajando(self):
        ruta = Path(tempfile.mkdtemp()) / "x.jsonl"
        t0 = time.time() - 60
        escribir(ruta, [usuario(t0), respuesta(t0 + 5, "m1", fin="end_turn", herramienta=None),
                        usuario(t0 + 20, "<command-name>/model</command-name>"),
                        usuario(t0 + 21, "<local-command-stdout>Set model</local-command-stdout>")])
        t = s.Transcript(ruta)
        t.leer()
        self.assertFalse(t.trabajando(t0 + 30))
        # Más tarde, un comando que sí es un prompt (un skill): el turno arranca ahí, no con /model.
        escribir(ruta, [usuario(t0 + 50, "<command-name>/skill</command-name>"), respuesta(t0 + 55, "m2")], "a")
        t.leer()
        self.assertTrue(t.trabajando(t0 + 56))
        self.assertAlmostEqual(t.prompt, t0 + 50, places=2)

    def test_meta_de_agente_rara_o_borrada(self):
        carpeta = Path(tempfile.mkdtemp())
        ahora = time.time()
        escribir(carpeta / "agent-a.jsonl", [respuesta(ahora, "s1", isSidechain=True)])
        (carpeta / "agent-a.meta.json").write_text("null", encoding="utf-8")
        agentes = s.Agentes(carpeta)
        self.assertEqual(agentes.actualizar(ahora)[0], 1)
        (carpeta / "agent-a.jsonl").unlink()
        self.assertEqual(agentes.actualizar(ahora)[0], 0)

    def test_formato_tokens(self):
        self.assertEqual(s.formato_tokens(999), "999")
        self.assertEqual(s.formato_tokens(1500), "1.5 k")
        self.assertEqual(s.formato_tokens(999_950), "1.00 M")


class SinChats(unittest.TestCase):
    """La isla se va si ningún chat se movió en un rato y vuelve con el próximo."""

    AHORA = 1_000_000.0

    def sesion(self, hace, trabajando=False, agentes=0):
        return {"ultima": self.AHORA - hace, "trabajando": trabajando, "agentes": agentes}

    def test_sin_sesiones_cuenta_desde_antes(self):
        antes = self.AHORA - 700
        self.assertEqual(s.ultima_actividad([], antes, self.AHORA), antes)
        self.assertTrue(s.sin_chats(antes, self.AHORA, 10))
        self.assertFalse(s.sin_chats(antes, self.AHORA, 15))

    def test_sesion_quieta_dentro_y_fuera_del_rato(self):
        ultima = s.ultima_actividad([self.sesion(120)], 0.0, self.AHORA)
        self.assertEqual(ultima, self.AHORA - 120)
        self.assertFalse(s.sin_chats(ultima, self.AHORA, 5))
        ultima = s.ultima_actividad([self.sesion(20 * 60)], 0.0, self.AHORA)
        self.assertTrue(s.sin_chats(ultima, self.AHORA, 10))

    def test_trabajando_o_con_agentes_es_actividad_aunque_no_escriba(self):
        for sesion in (self.sesion(25 * 60, trabajando=True), self.sesion(25 * 60, agentes=1)):
            self.assertEqual(s.ultima_actividad([self.sesion(29 * 60), sesion], 0.0, self.AHORA), self.AHORA)

    def test_no_va_para_atras_cuando_la_lista_se_vacia(self):
        # Con 60 minutos elegidos la sesión se cae de la lista a los 30: la cuenta sigue desde su última línea.
        ultima = s.ultima_actividad([self.sesion(29 * 60)], 0.0, self.AHORA)
        ultima = s.ultima_actividad([], ultima, self.AHORA + 120)
        self.assertEqual(ultima, self.AHORA - 29 * 60)
        self.assertFalse(s.sin_chats(ultima, self.AHORA + 120, 60))
        self.assertTrue(s.sin_chats(ultima, self.AHORA + 32 * 60, 60))

    def test_un_chat_nuevo_la_trae_de_vuelta(self):
        ultima = self.AHORA - 3600
        self.assertTrue(s.sin_chats(ultima, self.AHORA, 10))
        ultima = s.ultima_actividad([self.sesion(1)], ultima, self.AHORA)
        self.assertFalse(s.sin_chats(ultima, self.AHORA, 10))

    def test_hora_del_futuro_no_la_deja_para_siempre(self):
        antes = self.AHORA - 3600
        for ahora in (self.AHORA, self.AHORA + 3600):  # en cada vuelta, no solo en la primera
            antes = s.ultima_actividad([self.sesion(-86400)], antes, ahora)
            self.assertEqual(antes, self.AHORA - 3600)
        self.assertEqual(s.ultima_actividad([self.sesion(-30)], 0.0, self.AHORA), self.AHORA)  # un poco: vale

    def test_sesion_sin_hora_no_cuenta(self):
        antes = self.AHORA - 3600
        self.assertEqual(s.ultima_actividad([{"ultima": None, "trabajando": False, "agentes": 0}], antes,
                                            self.AHORA), antes)


if __name__ == "__main__":
    unittest.main()
