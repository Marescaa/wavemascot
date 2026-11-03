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

## Todo gratis

Los avisos y los permisos por Telegram son gratis para todos. La 1.3.0 tenía un plan **Pro** pago (Telegram Stars) que
se sacó en la 1.4.0. Para que las instalaciones 1.3.0 no muestren candados, `/v1/estado` y `/v1/planes` siguen
contestando `cobrando: false` y un plan `libre`, y los comandos viejos `/pro`, `/paysupport` y `/terms` responden que
ya no hace falta ningún plan. Después de deployar, abrir `/setup` para que el menú del bot quede con `/help` y `/stop`.

## Probar en local

Con un `.dev.vars` (no se sube al repo) que tenga `BOT_TOKEN="falso"` y `TELEGRAM_FALSO="1"`:
`npx wrangler dev --local --port 8799`. Con `TELEGRAM_FALSO` no sale nada a Telegram: lo que mandaría el bot queda en
el log de wrangler.
