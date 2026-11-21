"""Las cuentas de Uso: python -m unittest discover tests"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
import estadisticas as e  # noqa: E402


def iso(cuando: float) -> str:
    return datetime.fromtimestamp(cuando, timezone.utc).isoformat()


def usuario(cuando: float, texto: str = "hola") -> dict:
    return {"type": "user", "timestamp": iso(cuando), "cwd": "C:/proyectos/demo", "message": {"content": texto}}


def respuesta(cuando: float, ident: str, entrada=100, cache=1000, salida=50, modelo="claude-opus-5-5", fin=False,
              herramienta=None) -> dict:
    contenido = [{"type": "tool_use", "id": "u" + ident, "name": herramienta, "input": {}}] if herramienta else []
    return {"type": "assistant", "timestamp": iso(cuando),
            "message": {"id": ident, "model": modelo, "content": contenido, "stop_reason": "end_turn" if fin else None,
                        "usage": {"input_tokens": entrada, "cache_read_input_tokens": cache, "output_tokens": salida}}}


def escribir(ruta: Path, lineas: list[dict]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "a", encoding="utf-8") as f:
        for linea in lineas:
            f.write(json.dumps(linea) + "\n")


class Informe(unittest.TestCase):
    def setUp(self):
        self.raiz = Path(tempfile.mkdtemp())
        self.cache = self.raiz / "cache" / "uso.json"
        # El mediodía de hoy: así nada de lo que se escribe "hace 10 minutos" cae en el día anterior.
        self.ahora = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0).timestamp()

    def analisis(self) -> e.Analisis:
        return e.Analisis(self.raiz / "projects", self.cache)

    def test_cuenta_tokens_turnos_y_modelos(self):
        t0 = self.ahora - 600
        sesion = self.raiz / "projects" / "p" / "s1.jsonl"
        escribir(sesion, [usuario(t0), respuesta(t0 + 5, "a", herramienta="Bash"),
                          respuesta(t0 + 5, "a", herramienta="Bash"),  # la misma respuesta repetida: una sola vez
                          respuesta(t0 + 60, "b", salida=70, fin=True)])
        escribir(sesion.with_suffix("") / "subagents" / "agent-x.jsonl",
                 [dict(respuesta(t0 + 20, "c", entrada=10, salida=5, modelo="claude-haiku-5-5-20260101"), isSidechain=True)])
        analisis = self.analisis()
        analisis.actualizar(self.ahora)
        analisis.actualizar(self.ahora)  # repetirlo no vuelve a sumar los subagentes
        informe = analisis.actualizar(self.ahora)
        hoy = informe["hoy"]
        self.assertEqual((hoy["entrada"], hoy["salida"], hoy["cache"]), (210, 125, 3000))
        self.assertEqual(hoy["tokens"], 335)
        self.assertEqual((hoy["sesiones"], hoy["turnos"]), (1, 1))
        self.assertAlmostEqual(hoy["trabajo"], 60, delta=1)
        self.assertEqual(informe["proyectos"], [("demo", 335, 1)])
        for clave, (_, _, cuantos) in e.LAPSOS.items():  # hace 10 minutos: entra en todos los lapsos
            lapso = informe["lapsos"][clave]
            self.assertEqual((lapso["tokens"], lapso["respuestas"], lapso["sesiones"]), (335, 3, 1), clave)
            self.assertEqual((sum(lapso["serie"]), len(lapso["serie"])), (335, cuantos), clave)
            self.assertEqual(lapso["serie"][-1] + lapso["serie"][-2] + lapso["serie"][-3], 335, clave)
            self.assertEqual(dict(lapso["modelos"]), {"Opus 5.5": 320, "Haiku 5.5": 15})
            self.assertEqual(lapso["proyectos"], [("demo", 335)])
            self.assertAlmostEqual(lapso["acierto_cache"], 3000 / 3210)
            self.assertEqual(lapso["anterior"], 0)
        self.assertGreater(informe["ritmo"], 0)
        self.assertEqual(len(informe["dias"]), 14)

    def test_lapso_anterior(self):
        hace = self.ahora - 7 * 3600  # hace 7 horas: fuera de las últimas 5, dentro de las 5 anteriores
        escribir(self.raiz / "projects" / "p" / "s.jsonl", [usuario(hace), respuesta(hace + 5, "a", fin=True)])
        lapsos = self.analisis().actualizar(self.ahora)["lapsos"]
        self.assertEqual((lapsos["5h"]["tokens"], lapsos["5h"]["anterior"]), (0, 150))
        self.assertEqual((lapsos["7d"]["tokens"], lapsos["7d"]["anterior"]), (150, 0))

    def test_hoy_contra_ayer_a_esta_misma_hora(self):
        sesion = self.raiz / "projects" / "p" / "s1.jsonl"
        dia = 86400
        escribir(sesion, [usuario(self.ahora - 600),
                          respuesta(self.ahora - 590, "hoy", entrada=100, salida=50, fin=True),    # hoy: 150, 11:50
                          usuario(self.ahora - dia - 3600),
                          respuesta(self.ahora - dia - 3590, "ayer1", entrada=20, salida=10),      # ayer antes: entra
                          respuesta(self.ahora - dia + 3600, "ayer2", entrada=500, salida=500)])   # ayer después: no
        hoy = self.analisis().actualizar(self.ahora)["lapsos"]["hoy"]
        self.assertEqual((hoy["tokens"], hoy["anterior"]), (150, 30))
        self.assertEqual(len(hoy["serie"]), 24)
        self.assertEqual(hoy["serie"][11], 150)

    def test_tiempo_trabajado_por_lapso(self):
        sesion = self.raiz / "projects" / "p" / "s1.jsonl"
        hace_dos_dias = self.ahora - 2 * 86400
        escribir(sesion, [usuario(hace_dos_dias), respuesta(hace_dos_dias + 40, "a", fin=True),
                          usuario(self.ahora - 100), respuesta(self.ahora - 70, "b", fin=True)])
        lapsos = self.analisis().actualizar(self.ahora)["lapsos"]
        self.assertAlmostEqual(lapsos["hoy"]["trabajo"], 30, delta=1)
        self.assertAlmostEqual(lapsos["5h"]["trabajo"], 30, delta=1)
        self.assertAlmostEqual(lapsos["7d"]["trabajo"], 70, delta=1)

    def test_un_turno_largo_no_se_pasa_del_lapso(self):
        inicio = self.ahora - 8 * 3600
        sesion = self.raiz / "projects" / "p" / "s1.jsonl"
        escribir(sesion, [usuario(inicio), respuesta(self.ahora - 60, "a", fin=True)])
        lapsos = self.analisis().actualizar(self.ahora)["lapsos"]
        self.assertAlmostEqual(lapsos["5h"]["trabajo"], 5 * 3600 - 60, delta=1)
        self.assertAlmostEqual(lapsos["7d"]["trabajo"], 8 * 3600 - 60, delta=1)

    def test_cache_y_lectura_de_lo_nuevo(self):
        t0 = self.ahora - 3 * 86400  # una sesión vieja: queda en el caché y no se vuelve a leer
        escribir(self.raiz / "projects" / "p" / "vieja.jsonl", [usuario(t0), respuesta(t0 + 5, "a", fin=True)])
        viva = self.raiz / "projects" / "p" / "viva.jsonl"
        escribir(viva, [usuario(self.ahora - 50), respuesta(self.ahora - 40, "b")])
        a = self.analisis()
        primero = a.actualizar(self.ahora)
        self.assertGreater(primero["analisis"]["bytes"], 0)
        self.assertEqual(a.actualizar(self.ahora)["analisis"]["bytes"], 0)  # nada nuevo: no lee nada
        escribir(viva, [respuesta(self.ahora - 10, "c", salida=7, fin=True)])
        tercero = a.actualizar(self.ahora)
        self.assertEqual(tercero["hoy"]["salida"], 50 + 7)                  # solo se leyó el pedazo nuevo
        self.assertLess(tercero["analisis"]["bytes"], primero["analisis"]["bytes"])
        otro = self.analisis()  # otro proceso: arranca del caché, sin releer la vieja
        cuarto = otro.actualizar(self.ahora)
        self.assertEqual(cuarto["semana"], tercero["semana"])
        self.assertNotIn(self.raiz / "projects" / "p" / "vieja.jsonl", otro.abiertos)

    def test_cache_roto_y_carpeta_vacia(self):
        self.cache.parent.mkdir(parents=True)
        for contenido in ("{roto", "[]", '{"version": 1, "archivos": {"x": 5}}', '{"version": 99, "archivos": {}}'):
            self.cache.write_text(contenido, encoding="utf-8")
            informe = self.analisis().actualizar(self.ahora)
            self.assertEqual(informe["hoy"]["tokens"], 0, contenido)
            self.assertEqual(informe["ritmo"], 0)
        cancelado = self.analisis()
        escribir(self.raiz / "projects" / "p" / "s.jsonl", [usuario(self.ahora - 5)])
        cancelado.cancelado = lambda: True
        self.assertIsNone(cancelado.actualizar(self.ahora))

    def test_reloj_corrido_y_cache_raro(self):
        futuro = self.ahora + 3600  # una respuesta con hora futura no se cuenta ni en hoy ni en los lapsos
        escribir(self.raiz / "projects" / "p" / "s.jsonl", [usuario(futuro), respuesta(futuro + 5, "a", fin=True)])
        informe = self.analisis().actualizar(self.ahora)
        self.assertEqual((informe["hoy"]["tokens"], informe["lapsos"]["5h"]["tokens"]), (0, 0))
        self.assertFalse(e.resumen_sano({"tramos": {"1": {"m": [1, 2, 3]}}, "turnos": []}))
        self.assertFalse(e.resumen_sano({"tramos": {}, "turnos": [[1]]}))
        self.assertTrue(e.resumen_sano({"tramos": {"1": {"m": [1, 2, 3, 4]}}, "turnos": [[1.0, 2.0]]}))

    def test_seis_meses_contra_los_seis_anteriores(self):
        self.assertGreaterEqual(self.analisis().dias * 86400, 2 * e.LAPSOS["180d"][0])

    def test_curva_no_inventa_picos(self):
        valores = [0, 0, 5, 100, 3, 0, 0, 40, 40, 0]
        puntos = e.curva(valores, 181)  # 181: cada valor original cae justo en un punto
        self.assertEqual(len(puntos), 181)
        self.assertGreaterEqual(min(puntos), 0)
        self.assertLessEqual(max(puntos), 100)
        for i, valor in enumerate(valores):
            self.assertAlmostEqual(puntos[i * 20], valor)
        self.assertTrue(all(x == 0 for x in puntos[:21]))        # lo plano queda plano
        self.assertTrue(all(x == 40 for x in puntos[140:161]))

    def test_curva_de_casos_chicos(self):
        self.assertEqual(e.curva([], 5), [0.0] * 5)
        self.assertEqual(e.curva([7], 3), [7.0] * 3)
        self.assertEqual(e.curva([0, 0, 0], 4), [0.0] * 4)

    def test_suavizar_no_sale_del_rango(self):
        valores = [0.0] * 20 + [100.0] + [0.0] * 20
        puntos = e.suavizar(valores)
        self.assertEqual(len(puntos), len(valores))
        self.assertGreaterEqual(min(puntos), 0)
        self.assertLess(max(puntos), 100)
        self.assertEqual(puntos[0], 0)
        for a, b in zip(e.suavizar([5.0] * 9), [5.0] * 9):
            self.assertAlmostEqual(a, b)
        self.assertEqual(e.suavizar([]), [])

    def test_agrupar(self):
        self.assertEqual(e.agrupar([1, 2, 3, 4, 5, 6], 3), [6, 15])
        self.assertEqual(e.agrupar([1, 2, 3], 2), [3, 3])

    def test_nombre_de_modelo(self):
        self.assertEqual(e.nombre_modelo("claude-opus-4-5-20251101"), "Opus 4.5")
        self.assertEqual(e.nombre_modelo("claude-fable-5-2"), "Fable 5.2")
        self.assertEqual(e.nombre_modelo("<synthetic>"), "—")


if __name__ == "__main__":
    unittest.main()
