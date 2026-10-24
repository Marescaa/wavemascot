# Servidor del bot de Telegram

El bot oficial [@WaveNotificationBot](https://t.me/WaveNotificationBot) corre en un Cloudflare Worker
(`worker.js`). La app (`celular.py`) nunca ve el token del bot: cada instalación se registra, recibe una llave
propia y se vincula mandándole al bot un código de 6 letras. Los avisos se reenvían a Telegram y no se guardan.

## Publicar

```bash
npx wrangler login
npx wrangler kv namespace create DATOS     # poné el id en wrangler.toml (una sola vez)
npx wrangler secret put BOT_TOKEN          # el token de @BotFather (una sola vez, o al cambiarlo)
python generar_imagenes.py                 # GIF y foto de perfil de Wave (necesita ffmpeg)
npx wrangler deploy
curl https://wavemascot.wavemascot.workers.dev/setup   # webhook, descripción, comandos y foto
```

`/setup` se puede llamar las veces que haga falta; la foto de perfil solo se vuelve a subir si cambia
`FOTO_VERSION` en `worker.js`. La imagen que se ve en el chat vacío (`publico/img/descripcion.gif`) no se puede
cambiar por la API: va con `/setdescriptionpic` en @BotFather.

## WaveMascot Pro

La app es gratis y abierta; los avisos y los permisos por Telegram son de **Pro**. Lo decide este servidor (la app
solo lo muestra), según la **cuenta de Telegram**: un Pro sirve en todas las compus que esa persona vincule, y copiar
una llave no sirve de nada porque los avisos solo le llegan a su chat.

- **Prueba gratis** de `DIAS_PRUEBA` días desde que vincula su primera compu (una por cuenta de Telegram).
- **Planes** en Telegram Stars (`XTR`): mensual (suscripción de 30 días que Telegram renueva sola) y de por vida.
  Los enlaces de pago se crean con `createInvoiceLink` y se reusan; el pago llega por el webhook
  (`pre_checkout_query` y `successful_payment`), así que no hay firmas que verificar ni datos de tarjeta.
- Sin Pro, `/v1/aviso` y `/v1/permiso` contestan **402**; el bot le explica a la persona qué pasó una sola vez, y un
  día antes de que termine la prueba le avisa. La compu sigue sola: la mascota avisa en pantalla y el permiso se
  contesta en la terminal.
- `COBRAR = "no"` en `wrangler.toml` apaga el cobro: todo vuelve a ser gratis.

Comandos del bot: `/pro` (tu plan, pagar, cancelar o reactivar la renovación), `/paysupport`, `/terms`, `/id`.
Con el secreto `DUENO` (tu id de chat, mandale `/id` al bot) te llegan los pagos y los pedidos de soporte, y podés usar
`/cuenta CHAT`, `/regalar CHAT DÍAS|siempre`, `/quitar CHAT`, `/reembolsar CHAT ID_DEL_PAGO` y
`/responder CHAT texto`.

**Para lanzarlo**: `npx wrangler deploy` y después `/setup` (hace falta para que Telegram mande los pagos al
webhook). Las compus que ya estaban conectadas arrancan su prueba con el primer aviso después del deploy.

## Probar en local

Con un `.dev.vars` (no se sube al repo) que tenga `BOT_TOKEN="falso"`, `TELEGRAM_FALSO="1"` y `DUENO="999"`:

```bash
npx wrangler dev --local --port 8799
python prueba_local.py http://127.0.0.1:8799   # registro, prueba, freno de Pro, pagos y renovación
```

Con `TELEGRAM_FALSO` no sale nada a Telegram: lo que mandaría el bot queda en el log de wrangler.
