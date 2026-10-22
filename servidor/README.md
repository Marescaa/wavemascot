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

## Probar en local

Con un `.dev.vars` que tenga `BOT_TOKEN="..."` (no se sube al repo): `npx wrangler dev --local`.
