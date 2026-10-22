"""Cada texto visible tiene su traducción al inglés y al portugués: python -m unittest discover tests

Recorre el código con ast (sin importar PyQt6): junta los textos que pasan por t(), por los ayudantes
de la interfaz que traducen solos (seccion, ayuda, opcion, segmentado) y por las tablas de nombres.
"""

from __future__ import annotations

import ast
import re
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
import idiomas  # noqa: E402

ARCHIVOS = ("mascota.py", "ajustes.py", "bandeja.py", "instalador.py", "celular.py")
TRADUCEN = {"t", "seccion", "ayuda", "opcion"}  # su primer argumento se traduce
# Tablas cuyos valores se traducen donde se usan: (archivo, nombre, cómo sacar el texto de cada valor)
TABLAS = [
    ("ajustes.py", "NOMBRES_ESTADO", None), ("ajustes.py", "NOMBRES_EVENTO", None),
    ("ajustes.py", "NOMBRES_CELULAR", None),
    ("ajustes.py", "NOMBRES_CONTENIDO", None), ("ajustes.py", "NOMBRES_ESQUINA", None),
    ("ajustes.py", "NOMBRES_TAMANO", None), ("ajustes.py", "AUTOMATICO", None), ("ajustes.py", "EJEMPLO", None),
    ("ajustes.py", "RESUMEN_EJEMPLO", None), ("mascota.py", "ESTADOS", "mensaje"), ("mascota.py", "BOTONES", None),
    ("sprites.py", "COLORES", 0), ("sprites.py", "CABEZAS", None), ("sprites.py", "ROPAS", None),
    ("sprites.py", "ACCESORIOS", None), ("sprites.py", "SONIDOS", 0),
]
CAMPOS = re.compile(r"\{(\w*)\}")


def nombre_funcion(nodo: ast.Call) -> str:
    f = nodo.func
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""


def constantes(nodo) -> list[str]:
    """El texto de un literal, o los dos de un "texto de macOS if MAC else texto de Windows"."""
    if isinstance(nodo, ast.IfExp):
        return constantes(nodo.body) + constantes(nodo.orelse)
    return [nodo.value] if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) else []


def usados() -> tuple[set[str], list[str]]:
    """(textos que se traducen, problemas: f-strings pasados a t())."""
    textos, problemas = set(), []
    for archivo in ARCHIVOS:
        arbol = ast.parse((RAIZ / archivo).read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Call) and nodo.args and nombre_funcion(nodo) in TRADUCEN:
                arg = nodo.args[0]
                if constantes(arg):
                    textos.update(constantes(arg))
                elif isinstance(arg, ast.JoinedStr):
                    problemas.append(f"{archivo}:{nodo.lineno}: f-string en {nombre_funcion(nodo)}(); usá campos {{}}")
            if isinstance(nodo, ast.Call) and nombre_funcion(nodo) == "segmentado" and isinstance(nodo.args[0], ast.Dict):
                textos.update(v.value for v in nodo.args[0].values if isinstance(v, ast.Constant))
            if isinstance(nodo, ast.For):  # for clave, texto in (("x", "Texto"), ...): ...t(texto)...
                textos.update(textos_de_bucle(nodo))
    for archivo, nombre, campo in TABLAS:
        textos.update(textos_de_tabla(archivo, nombre, campo))
    textos.discard("")
    return textos, problemas


def textos_de_bucle(nodo: ast.For) -> set[str]:
    destino, iterable = nodo.target, nodo.iter
    if isinstance(iterable, ast.Call) and nombre_funcion(iterable) == "enumerate" and isinstance(destino, ast.Tuple):
        destino, iterable = destino.elts[1], iterable.args[0]  # for numero, (clave, texto) in enumerate(...)
    if not (isinstance(destino, ast.Tuple) and isinstance(iterable, ast.Tuple)):
        return set()
    variables = [v.id if isinstance(v, ast.Name) else None for v in destino.elts]
    traducidas = {arg.id for n in ast.walk(nodo) if isinstance(n, ast.Call) and nombre_funcion(n) in TRADUCEN | {"QLabel"}
                  for arg in n.args[:1] if isinstance(arg, ast.Name)}
    textos = set()
    for elemento in iterable.elts:
        if isinstance(elemento, ast.Tuple) and len(elemento.elts) == len(variables):
            for variable, valor in zip(variables, elemento.elts):
                if variable in traducidas:
                    textos.update(constantes(valor))
    return textos


def textos_de_tabla(archivo: str, nombre: str, campo) -> set[str]:
    arbol = ast.parse((RAIZ / archivo).read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Assign) and any(isinstance(x, ast.Name) and x.id == nombre for x in nodo.targets):
            tabla = nodo.value
            break
    else:
        raise AssertionError(f"no encontré {nombre} en {archivo}")
    textos = set()
    for valor in tabla.values:
        if campo is None:
            elegido = valor
        elif isinstance(campo, int):
            elegido = valor.elts[campo]
        else:
            elegido = next(v for k, v in zip(valor.keys, valor.values) if k.value == campo)
        if isinstance(elegido, ast.Constant) and isinstance(elegido.value, str):
            textos.add(elegido.value)
    return textos


class Traducciones(unittest.TestCase):
    def test_todo_texto_visible_esta_traducido(self):
        textos, problemas = usados()
        self.assertEqual(problemas, [])
        faltan = sorted(x for x in textos if any(i not in idiomas.TEXTOS.get(x, {}) for i in ("en", "pt")))
        self.assertEqual(faltan, [], "textos sin traducción")

    def test_mismos_campos_en_cada_idioma(self):
        for clave, traducciones in idiomas.TEXTOS.items():
            for idioma, texto in traducciones.items():
                with self.subTest(clave=clave, idioma=idioma):
                    self.assertEqual(set(CAMPOS.findall(texto)), set(CAMPOS.findall(clave)))

    def test_no_sobran_traducciones(self):
        textos, _ = usados()
        self.assertEqual(sorted(set(idiomas.TEXTOS) - textos), [], "traducciones que ya no se usan")

    def test_t(self):
        try:
            idiomas.usar("pt")
            self.assertEqual(idiomas.t("Abrir ajustes"), idiomas.TEXTOS["Abrir ajustes"]["pt"])
            idiomas.usar("es")
            self.assertEqual(idiomas.t("Necesito permiso para usar {herramienta}", herramienta="Bash"),
                             "Necesito permiso para usar Bash")
            idiomas.usar("xx")  # desconocido: el de por defecto
            self.assertEqual(idiomas.actual(), "en")
            self.assertEqual(idiomas.t("texto que no está"), "texto que no está")
        finally:
            idiomas.usar(idiomas.POR_DEFECTO)


if __name__ == "__main__":
    unittest.main()
