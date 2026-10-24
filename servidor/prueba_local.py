#!/usr/bin/env python3
"""Prueba de punta a punta del servidor con Telegram falso: registro, vínculo, prueba gratis, freno de Pro,
pagos con Stars y renovación. No sale nada a Telegram de verdad.

    # .dev.vars (no se sube):  BOT_TOKEN="falso"  TELEGRAM_FALSO="1"  DUENO="999"
    npx wrangler dev --local --port 8799
    python prueba_local.py http://127.0.0.1:8799

Cada corrida usa chats nuevos, así que se puede repetir sin borrar nada.
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
import time
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8799").rstrip("/")
TOKEN = "falso"
DUENO = 999
SECRETO = hashlib.sha256(f"webhook:{TOKEN}".encode()).hexdigest()[:48]
fallas = []


def pedir(metodo: str, ruta: str, llave: str = "", datos: dict | None = None, cabeceras: dict | None = None):
    cab = {"content-type": "application/json", **(cabeceras or {})}
    if llave:
        cab["authorization"] = "Bearer " + llave
    cuerpo = json.dumps(datos).encode() if datos is not None else None
    pedido = urllib.request.Request(BASE + ruta, data=cuerpo, headers=cab, method=metodo)
    try:
        with urllib.request.urlopen(pedido, timeout=30) as r:
            texto = r.read().decode()
            return r.status, (json.loads(texto) if texto.startswith("{") else texto)
    except urllib.error.HTTPError as e:
        texto = e.read().decode()
        return e.code, (json.loads(texto) if texto.startswith("{") else texto)


def telegram(novedad: dict):
    return pedir("POST", "/telegram", datos=novedad, cabeceras={"x-telegram-bot-api-secret-token": SECRETO})


def mensaje(chat: int, texto: str = "", **extra) -> dict:
    return {"message": {"chat": {"id": chat, "type": "private"}, "from": {"id": chat, "first_name": "Prueba",
                                                                            "language_code": "es"},
                        "text": texto, **extra}}


def pago(chat: int, plan: str, cargo: str, **extra) -> dict:
    return mensaje(chat, successful_payment={"currency": "XTR", "total_amount": 100 if plan == "mensual" else 1500,
                                             "invoice_payload": "pro:" + plan,
                                             "telegram_payment_charge_id": cargo, **extra})


def ver(nombre: str, condicion: bool, detalle=""):
    print(("  ok   " if condicion else "  FALLA ") + nombre + ("" if condicion else f"  -> {detalle}"))
    if not condicion:
        fallas.append(nombre)


def nueva_compu(chat: int) -> str:
    estado, r = pedir("POST", "/v1/registro", datos={})
    llave, codigo = r["llave"], r["codigo"]
    telegram(mensaje(chat, "/start " + codigo))
    return llave


def main() -> int:
    print("Servidor:", BASE)
    chat_a, chat_b = random.randint(10**8, 10**9), random.randint(10**8, 10**9)

    estado, r = pedir("GET", "/v1/planes")
    ver("planes públicos", estado == 200 and r["cobrando"] and r["precios"]["mensual"] > 0, r)

    estado, r = pedir("POST", "/v1/registro", datos={})
    llave = r["llave"]
    estado, r = pedir("GET", "/v1/estado", llave)
    ver("sin vincular no hay plan", r["conectado"] is False and r["plan"] is None, r)

    estado, r = telegram({"message": {"chat": {"id": 1, "type": "private"}, "text": "/pro"}})
    ver("webhook sin secreto no entra", pedir("POST", "/telegram", datos={})[0] == 401)

    # --- A: recién vinculado, en la prueba gratis --------------------------------------------------
    llave_a = nueva_compu(chat_a)
    estado, r = pedir("GET", "/v1/estado", llave_a)
    ver("vincular arranca la prueba", r["conectado"] and r["plan"]["tipo"] == "prueba" and r["plan"]["pro"], r)
    ver("la prueba dura 7 días", r["plan"]["dias"] == 7, r["plan"])
    estado, r = pedir("POST", "/v1/aviso", llave_a, {"texto": "hola"})
    ver("en la prueba el aviso sale", estado == 200 and r.get("ok"), (estado, r))
    estado, r = pedir("POST", "/v1/permiso", llave_a, {"texto": "¿Permitir?", "idioma": "es", "espera": 60})
    ver("en la prueba el permiso sale", estado == 200 and r.get("id"), (estado, r))

    llave_a2 = nueva_compu(chat_a)  # otra compu del mismo Telegram: comparte el plan
    estado, r = pedir("GET", "/v1/estado", llave_a2)
    ver("segunda compu, mismo plan", r["plan"]["tipo"] == "prueba", r)

    # --- se termina la prueba (DUENO la corta) ----------------------------------------------------
    telegram(mensaje(DUENO, f"/quitar {chat_a}"))
    estado, r = pedir("GET", "/v1/estado", llave_a)
    ver("sin prueba: vencido", r["plan"]["tipo"] == "vencido" and not r["plan"]["pro"], r)
    estado, r = pedir("POST", "/v1/aviso", llave_a, {"texto": "hola"})
    ver("vencido: el aviso se frena con 402", estado == 402 and r.get("pro") is False, (estado, r))
    estado, r = pedir("POST", "/v1/aviso", llave_a2, {"texto": "hola"})
    ver("vencido: también desde la otra compu", estado == 402, (estado, r))
    estado, r = pedir("POST", "/v1/permiso", llave_a, {"texto": "¿Permitir?", "idioma": "es", "espera": 60})
    ver("vencido: el permiso se frena con 402", estado == 402, (estado, r))
    estado, r = pedir("GET", "/v1/estado", llave_a)
    ver("estado sigue andando sin Pro", estado == 200 and r["conectado"], r)

    # --- paga el mensual ---------------------------------------------------------------------------
    vence = int(time.time()) + 30 * 86400
    telegram({"pre_checkout_query": {"id": "q1", "from": {"id": chat_a, "language_code": "es"}, "currency": "XTR",
                                     "total_amount": 100, "invoice_payload": "pro:mensual"}})
    telegram(pago(chat_a, "mensual", "cargo-1", subscription_expiration_date=vence, is_recurring=True,
                  is_first_recurring=True))
    estado, r = pedir("GET", "/v1/estado", llave_a2)
    ver("pagó: mensual que se renueva", r["plan"]["tipo"] == "mensual" and r["plan"]["renueva"] is True, r)
    ver("vence en 30 días", r["plan"]["dias"] == 30, r["plan"])
    estado, r = pedir("POST", "/v1/aviso", llave_a, {"texto": "hola"})
    ver("con Pro el aviso vuelve a salir", estado == 200, (estado, r))

    telegram(pago(chat_a, "mensual", "cargo-1", subscription_expiration_date=vence))  # Telegram repite
    estado, r = telegram(mensaje(DUENO, f"/cuenta {chat_a}"))
    estado, r = pedir("GET", "/v1/estado", llave_a)
    ver("un pago repetido no suma", r["plan"]["dias"] == 30, r["plan"])

    telegram({"callback_query": {"id": "c1", "data": "s:cancelar", "from": {"id": chat_a, "language_code": "es"},
                                 "message": {"message_id": 5, "chat": {"id": chat_a, "type": "private"}}}})
    estado, r = pedir("GET", "/v1/estado", llave_a)
    ver("cancelar la renovación", r["plan"]["tipo"] == "mensual" and r["plan"]["renueva"] is False, r)

    telegram(pago(chat_a, "mensual", "cargo-2", subscription_expiration_date=vence + 30 * 86400, is_recurring=True))
    estado, r = pedir("GET", "/v1/estado", llave_a)
    ver("la renovación extiende el mes", r["plan"]["dias"] == 60, r["plan"])

    # --- B: de por vida, y lo que no se puede ------------------------------------------------------
    llave_b = nueva_compu(chat_b)
    telegram(pago(chat_b, "vitalicio", "cargo-3"))
    estado, r = pedir("GET", "/v1/estado", llave_b)
    ver("de por vida", r["plan"]["tipo"] == "vitalicio" and r["plan"]["pro"], r)
    telegram(mensaje(DUENO, f"/reembolsar {chat_b} cargo-3"))
    estado, r = pedir("GET", "/v1/estado", llave_b)
    ver("reembolso: vuelve a la prueba", r["plan"]["tipo"] == "prueba", r)
    telegram(mensaje(DUENO, f"/regalar {chat_b} siempre"))
    estado, r = pedir("GET", "/v1/estado", llave_b)
    ver("regalo de por vida", r["plan"]["tipo"] == "vitalicio", r)

    telegram(mensaje(chat_b, f"/regalar {chat_b} siempre"))  # alguien que no es DUENO: no hace nada
    telegram(mensaje(chat_a, f"/regalar {chat_a} siempre"))
    estado, r = pedir("GET", "/v1/estado", llave_a)
    ver("solo DUENO regala", r["plan"]["tipo"] == "mensual", r)

    for texto in ("/pro", "/start pro_vitalicio", "/help", "/terms", "/paysupport", "pagué y no anda", "/id"):
        estado, r = telegram(mensaje(chat_a, texto))
        ver(f"bot responde a «{texto}»", estado == 200, (estado, r))

    print("\n" + ("TODO BIEN" if not fallas else f"{len(fallas)} FALLAS: " + ", ".join(fallas)))
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
