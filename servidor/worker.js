// Servidor del bot oficial de WaveMascot (Cloudflare Worker).
//
// La clave del bot vive solo acá (secreto BOT_TOKEN). Cada instalación de WaveMascot se registra y
// recibe una llave propia: con ella solo puede mandarle avisos al chat que vinculó, nunca a otros.
//
// Vincular: la app muestra un código de 6 letras; la persona se lo manda al bot (o toca el botón que
// abre t.me/<bot>?start=<código>) y el chat queda unido a esa instalación.
//
// Los mensajes no se guardan: se reenvían a Telegram y listo. En KV queda solo:
//   inst:<sha256(llave)>  -> {"chat": id o null, "nombre": "...", "creado": fecha}
//   cod:<CÓDIGO>          -> sha256(llave)              (vence en 15 minutos)
//   chat:<id>             -> ["sha256(llave)", ...]     (para /stop desde Telegram)
//   gif:<clave>           -> file_id de Telegram         (cada GIF se sube una sola vez para todos)

const API = "https://api.telegram.org/bot";
const LETRAS = "ACDEFHJKMNPQRTUVWXY34679"; // sin las que se confunden (0/O, 1/I/L, 5/S, 8/B, 2/Z)
const VIDA_CODIGO = 15 * 60;
const MAX_TEXTO = 1024;

const DESCARGA = "https://github.com/Marescaa/wavemascot/releases/latest";
const FOTO_VERSION = "1"; // subirla para que /setup vuelva a subir la foto de perfil

// Lo que dice el bot, en el idioma de cada persona (el de su Telegram; si no es es/pt, inglés).
const TEXTOS = {
  es: {
    saludo: "<b>¡Hola{coma_nombre}! Soy Wave 👋</b>\n\n" +
      "Soy la mascota de <b>WaveMascot</b>. Te escribo por acá cuando Claude Code termina una tarea o necesita tu " +
      "permiso, así no tenés que quedarte mirando la compu.\n\n" +
      "<b>Para conectarme:</b>\n" +
      "1️⃣ Abrí WaveMascot → <b>Ajustes</b> → <b>Celular</b>\n" +
      "2️⃣ Tocá <b>Conectar con Telegram</b>\n" +
      "3️⃣ Se abre este chat: tocá <b>Iniciar</b> (o mandame el código de 6 letras)\n\n" +
      "¿Todavía no tenés WaveMascot? Es gratis 👇",
    descargar: "⬇️ Descargar WaveMascot",
    listo: "<b>¡Conectados{coma_nombre}! 🎉</b>\n\n" +
      "Desde ahora te aviso por acá cuando Claude Code:\n" +
      "✅ termine una tarea\n" +
      "✋ necesite tu permiso o te haga una pregunta\n" +
      "⚠️ llegue al límite de uso o tenga un error\n\n" +
      "Mientras estés en la compu te avisa la mascota en pantalla; acá te llegan cuando estás lejos. Eso y qué " +
      "avisos querés lo cambiás en <b>Ajustes → Celular</b>.\n\n" +
      "/help ayuda · /stop dejar de recibir avisos",
    vencido: "😕 Ese código no existe o ya venció (duran 15 minutos).\n\n" +
      "Sacá uno nuevo en WaveMascot → Ajustes → Celular → <b>Conectar con Telegram</b>.",
    ayuda: "<b>Cómo funciono</b> 🤖\n\n" +
      "WaveMascot vive en tu compu y me avisa cada vez que Claude Code termina o necesita algo; yo te lo paso por " +
      "acá, con un resumen y el nombre del proyecto.\n\n{estado}\n\n" +
      "<b>Comandos</b>\n/help — esta ayuda\n/stop — dejar de recibir avisos\n\n" +
      "Para sumar otra compu, tocá <b>Conectar con Telegram</b> en WaveMascot desde esa compu.",
    compus: (n) => n === 0 ? "📭 Todavía no tenés ninguna compu conectada."
      : n === 1 ? "📱 Tenés <b>1 compu</b> conectada." : `📱 Tenés <b>${n} compus</b> conectadas.`,
    stop: "👋 Listo, no te mando más avisos.\n\nCuando quieras volver, tocá <b>Conectar con Telegram</b> en WaveMascot.",
    nada: "No tenías ninguna compu conectada. 🤷",
    descripcion: "👋 Soy Wave, la mascota de WaveMascot.\n\n" +
      "Te aviso por acá cuando Claude Code termina una tarea o necesita tu permiso, con un resumen de lo que hizo. " +
      "Así podés levantarte de la compu tranquilo.\n\n" +
      "Para conectarme: WaveMascot → Ajustes → Celular → Conectar con Telegram.",
    corta: "Avisos de Claude Code en tu celular, con Wave animada 👋",
    comandos: { help: "Cómo funciono y qué compus tenés conectadas", stop: "Dejar de recibir avisos" },
  },
  en: {
    saludo: "<b>Hi{coma_nombre}! I'm Wave 👋</b>\n\n" +
      "I'm the <b>WaveMascot</b> mascot. I message you here when Claude Code finishes a task or needs your " +
      "permission, so you don't have to keep staring at the computer.\n\n" +
      "<b>To connect me:</b>\n" +
      "1️⃣ Open WaveMascot → <b>Settings</b> → <b>Phone</b>\n" +
      "2️⃣ Tap <b>Connect Telegram</b>\n" +
      "3️⃣ This chat opens: tap <b>Start</b> (or send me the 6-letter code)\n\n" +
      "Don't have WaveMascot yet? It's free 👇",
    descargar: "⬇️ Download WaveMascot",
    listo: "<b>We're connected{coma_nombre}! 🎉</b>\n\n" +
      "From now on I'll let you know here when Claude Code:\n" +
      "✅ finishes a task\n" +
      "✋ needs your permission or asks you something\n" +
      "⚠️ hits the usage limit or runs into an error\n\n" +
      "While you're at the computer the on-screen mascot tells you; here you get them when you're away. You can " +
      "change that, and which notifications you want, in <b>Settings → Phone</b>.\n\n" +
      "/help help · /stop stop notifications",
    vencido: "😕 That code doesn't exist or has expired (they last 15 minutes).\n\n" +
      "Get a new one in WaveMascot → Settings → Phone → <b>Connect Telegram</b>.",
    ayuda: "<b>How I work</b> 🤖\n\n" +
      "WaveMascot lives on your computer and tells me whenever Claude Code finishes or needs something; I pass it " +
      "on to you here, with a summary and the project name.\n\n{estado}\n\n" +
      "<b>Commands</b>\n/help — this help\n/stop — stop notifications\n\n" +
      "To add another computer, tap <b>Connect Telegram</b> in WaveMascot on that computer.",
    compus: (n) => n === 0 ? "📭 You don't have any computer connected yet."
      : n === 1 ? "📱 You have <b>1 computer</b> connected." : `📱 You have <b>${n} computers</b> connected.`,
    stop: "👋 Done, no more notifications.\n\nWhenever you want to come back, tap <b>Connect Telegram</b> in WaveMascot.",
    nada: "You didn't have any computer connected. 🤷",
    descripcion: "👋 I'm Wave, the WaveMascot mascot.\n\n" +
      "I let you know here when Claude Code finishes a task or needs your permission, with a summary of what it " +
      "did. So you can step away from the computer without worrying.\n\n" +
      "To connect me: WaveMascot → Settings → Phone → Connect Telegram.",
    corta: "Claude Code notifications on your phone, with Wave animated 👋",
    comandos: { help: "How I work and which computers are connected", stop: "Stop notifications" },
  },
  pt: {
    saludo: "<b>Oi{coma_nombre}! Eu sou o Wave 👋</b>\n\n" +
      "Sou o mascote do <b>WaveMascot</b>. Eu te escrevo aqui quando o Claude Code termina uma tarefa ou precisa da " +
      "sua permissão, assim você não precisa ficar olhando o computador.\n\n" +
      "<b>Para me conectar:</b>\n" +
      "1️⃣ Abra o WaveMascot → <b>Ajustes</b> → <b>Celular</b>\n" +
      "2️⃣ Toque em <b>Conectar com o Telegram</b>\n" +
      "3️⃣ Este chat abre: toque em <b>Iniciar</b> (ou me mande o código de 6 letras)\n\n" +
      "Ainda não tem o WaveMascot? É grátis 👇",
    descargar: "⬇️ Baixar o WaveMascot",
    listo: "<b>Conectados{coma_nombre}! 🎉</b>\n\n" +
      "A partir de agora eu aviso aqui quando o Claude Code:\n" +
      "✅ terminar uma tarefa\n" +
      "✋ precisar da sua permissão ou te fizer uma pergunta\n" +
      "⚠️ chegar ao limite de uso ou tiver um erro\n\n" +
      "Enquanto você estiver no computador, o mascote avisa na tela; aqui os avisos chegam quando você está longe. " +
      "Isso e quais avisos você quer dá para mudar em <b>Ajustes → Celular</b>.\n\n" +
      "/help ajuda · /stop parar os avisos",
    vencido: "😕 Esse código não existe ou já venceu (duram 15 minutos).\n\n" +
      "Gere um novo em WaveMascot → Ajustes → Celular → <b>Conectar com o Telegram</b>.",
    ayuda: "<b>Como eu funciono</b> 🤖\n\n" +
      "O WaveMascot vive no seu computador e me avisa sempre que o Claude Code termina ou precisa de algo; eu te " +
      "passo aqui, com um resumo e o nome do projeto.\n\n{estado}\n\n" +
      "<b>Comandos</b>\n/help — esta ajuda\n/stop — parar os avisos\n\n" +
      "Para adicionar outro computador, toque em <b>Conectar com o Telegram</b> no WaveMascot desse computador.",
    compus: (n) => n === 0 ? "📭 Você ainda não tem nenhum computador conectado."
      : n === 1 ? "📱 Você tem <b>1 computador</b> conectado." : `📱 Você tem <b>${n} computadores</b> conectados.`,
    stop: "👋 Pronto, não mando mais avisos.\n\nQuando quiser voltar, toque em <b>Conectar com o Telegram</b> no WaveMascot.",
    nada: "Você não tinha nenhum computador conectado. 🤷",
    descripcion: "👋 Eu sou o Wave, o mascote do WaveMascot.\n\n" +
      "Eu aviso aqui quando o Claude Code termina uma tarefa ou precisa da sua permissão, com um resumo do que ele " +
      "fez. Assim você pode sair do computador tranquilo.\n\n" +
      "Para me conectar: WaveMascot → Ajustes → Celular → Conectar com o Telegram.",
    corta: "Avisos do Claude Code no seu celular, com o Wave animado 👋",
    comandos: { help: "Como eu funciono e quais computadores estão conectados", stop: "Parar os avisos" },
  },
};

export default {
  async fetch(pedido, env) {
    const url = new URL(pedido.url);
    try {
      if (url.pathname === "/telegram" && pedido.method === "POST") return await webhook(pedido, env);
      if (url.pathname === "/setup") return await setup(url, env);
      if (url.pathname === "/v1/registro" && pedido.method === "POST") return await registrar(env);
      if (url.pathname === "/v1/registro" && pedido.method === "DELETE") return await conLlave(pedido, env, desconectar);
      if (url.pathname === "/v1/codigo" && pedido.method === "POST") return await conLlave(pedido, env, nuevoCodigo);
      if (url.pathname === "/v1/estado" && pedido.method === "GET") return await conLlave(pedido, env, estado);
      if (url.pathname === "/v1/aviso" && pedido.method === "POST") return await conLlave(pedido, env, aviso);
      if (url.pathname === "/") return json({ ok: true, servicio: "WaveMascot" });
      return json({ ok: false, error: "no existe" }, 404);
    } catch (e) {
      console.log("error", e && e.stack || e);
      return json({ ok: false, error: "error del servidor" }, 500);
    }
  },
};

// --- utilidades -------------------------------------------------------------------------

function json(datos, estado = 200) {
  return new Response(JSON.stringify(datos), { status: estado, headers: { "content-type": "application/json" } });
}

async function sha256(texto) {
  const datos = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(texto));
  return [...new Uint8Array(datos)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function azar(cantidad, letras) {
  const bytes = crypto.getRandomValues(new Uint8Array(cantidad));
  return [...bytes].map((b) => letras[b % letras.length]).join("");
}

async function telegram(env, metodo, datos) {
  const opciones = datos instanceof FormData
    ? { method: "POST", body: datos }
    : { method: "POST", body: JSON.stringify(datos || {}), headers: { "content-type": "application/json" } };
  const respuesta = await fetch(API + env.BOT_TOKEN + "/" + metodo, opciones);
  return respuesta.json();
}

async function nombreDelBot(env) {
  let bot = await env.DATOS.get("bot");
  if (!bot) {
    const r = await telegram(env, "getMe");
    bot = r.ok ? r.result.username : "";
    if (bot) await env.DATOS.put("bot", bot, { expirationTtl: 86400 });
  }
  return bot;
}

function normalizarCodigo(texto) {
  return (texto || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
}

async function crearCodigo(env, hash) {
  for (let intento = 0; intento < 5; intento++) {
    const codigo = azar(6, LETRAS);
    if (await env.DATOS.get("cod:" + codigo)) continue;
    await env.DATOS.put("cod:" + codigo, hash, { expirationTtl: VIDA_CODIGO });
    return codigo;
  }
  throw new Error("no se pudo crear un código");
}

// --- lo que pide la app ----------------------------------------------------------------------

async function registrar(env) {
  const llave = azar(40, "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789");
  const hash = await sha256(llave);
  await env.DATOS.put("inst:" + hash, JSON.stringify({ chat: null, nombre: "", creado: new Date().toISOString() }));
  return json({ ok: true, llave, codigo: await crearCodigo(env, hash), bot: await nombreDelBot(env) });
}

async function conLlave(pedido, env, accion) {
  const llave = (pedido.headers.get("authorization") || "").replace(/^Bearer\s+/i, "").trim();
  if (llave.length < 20) return json({ ok: false, error: "falta la llave" }, 401);
  const hash = await sha256(llave);
  const datos = await env.DATOS.get("inst:" + hash, "json");
  if (!datos) return json({ ok: false, error: "llave desconocida" }, 401);
  if (env.LIMITE) { // rate limiting de Cloudflare (opcional): frena a quien mande avisos sin parar
    const { success } = await env.LIMITE.limit({ key: hash });
    if (!success) return json({ ok: false, error: "demasiados avisos, esperá un minuto" }, 429);
  }
  return accion(pedido, env, hash, datos);
}

async function estado(pedido, env, hash, datos) {
  return json({ ok: true, conectado: !!datos.chat, nombre: datos.nombre || "", bot: await nombreDelBot(env) });
}

async function nuevoCodigo(pedido, env, hash) {
  return json({ ok: true, codigo: await crearCodigo(env, hash), bot: await nombreDelBot(env) });
}

async function desconectar(pedido, env, hash, datos) {
  if (datos.chat) await sacarDelChat(env, datos.chat, hash);
  await env.DATOS.delete("inst:" + hash);
  return json({ ok: true });
}

async function sacarDelChat(env, chat, hash) {
  const lista = (await env.DATOS.get("chat:" + chat, "json")) || [];
  const resto = lista.filter((h) => h !== hash);
  if (resto.length) await env.DATOS.put("chat:" + chat, JSON.stringify(resto));
  else await env.DATOS.delete("chat:" + chat);
}

async function aviso(pedido, env, hash, datos) {
  if (!datos.chat) return json({ ok: false, error: "no conectado", conectado: false }, 409);
  const multipart = (pedido.headers.get("content-type") || "").startsWith("multipart/");
  const entrada = multipart ? Object.fromEntries((await pedido.formData()).entries()) : await pedido.json();
  const texto = String(entrada.texto || "").slice(0, MAX_TEXTO);
  if (!texto.trim()) return json({ ok: false, error: "falta el texto" }, 400);
  const clave = String(entrada.gif || "").slice(0, 120);
  const tipo = entrada.tipo === "photo" ? "photo" : "animation";
  const metodo = tipo === "photo" ? "sendPhoto" : "sendAnimation";
  const base = { chat_id: datos.chat, parse_mode: "HTML" };

  let r;
  if (multipart && entrada.archivo instanceof File) {
    if (entrada.archivo.size > 10_000_000) return json({ ok: false, error: "imagen muy grande" }, 413);
    const forma = new FormData();
    forma.append("chat_id", String(datos.chat));
    forma.append("parse_mode", "HTML");
    forma.append("caption", texto);
    forma.append(tipo, entrada.archivo, entrada.archivo.name || "wave.gif");
    r = await telegram(env, metodo, forma);
    const archivo = r.ok && (r.result.animation || r.result.document || (r.result.photo || []).slice(-1)[0]);
    if (archivo && clave) await env.DATOS.put("gif:" + clave, archivo.file_id);
  } else if (clave) {
    const id = await env.DATOS.get("gif:" + clave);
    if (!id) return json({ ok: false, falta_gif: true }); // la app lo vuelve a mandar con el archivo
    r = await telegram(env, metodo, { ...base, [tipo]: id, caption: texto });
    if (!r.ok && r.error_code === 400) { // el id dejó de valer: que lo suba de nuevo
      await env.DATOS.delete("gif:" + clave);
      return json({ ok: false, falta_gif: true });
    }
  } else {
    r = await telegram(env, "sendMessage", { ...base, text: texto });
  }
  if (!r.ok && r.error_code === 403) { // bloqueó al bot o borró el chat: queda desconectado
    await sacarDelChat(env, datos.chat, hash);
    await env.DATOS.put("inst:" + hash, JSON.stringify({ ...datos, chat: null }));
    return json({ ok: false, error: "el chat bloqueó al bot", conectado: false }, 409);
  }
  return json(r.ok ? { ok: true } : { ok: false, error: r.description || "Telegram no lo aceptó" }, r.ok ? 200 : 502);
}

// --- lo que llega de Telegram ------------------------------------------------------------------

async function secretoWebhook(env) {
  return (await sha256("webhook:" + env.BOT_TOKEN)).slice(0, 48);
}

async function setup(url, env) {
  // Apunta el webhook a este servidor y deja el perfil del bot armado (descripción, comandos y foto, en
  // los tres idiomas). Se puede llamar las veces que sea: la foto solo se sube si cambió FOTO_VERSION.
  const r = await telegram(env, "setWebhook", {
    url: url.origin + "/telegram",
    secret_token: await secretoWebhook(env),
    allowed_updates: ["message"],
    drop_pending_updates: true,
  });
  const resultado = { ok: r.ok, webhook: r.description, bot: await nombreDelBot(env) };
  for (const [idioma, t] of Object.entries(TEXTOS)) {
    const codigo = idioma === "en" ? "" : idioma; // inglés es el de todos los demás idiomas
    const comandos = Object.entries(t.comandos).map(([command, description]) => ({ command, description }));
    const respuestas = await Promise.all([
      telegram(env, "setMyDescription", { description: t.descripcion, language_code: codigo }),
      telegram(env, "setMyShortDescription", { short_description: t.corta, language_code: codigo }),
      telegram(env, "setMyCommands", { commands: comandos, language_code: codigo }),
    ]);
    resultado["perfil_" + idioma] = respuestas.every((x) => x.ok) || respuestas.map((x) => x.description);
  }
  if (await env.DATOS.get("foto") !== FOTO_VERSION) {
    resultado.foto = await subirFoto(url, env);
    if (resultado.foto === true) await env.DATOS.put("foto", FOTO_VERSION);
  } else {
    resultado.foto = "ya estaba";
  }
  return json(resultado);
}

async function subirFoto(url, env) {
  // Foto de perfil animada (Wave saludando); si Telegram no la acepta, la quieta.
  for (const [archivo, foto] of [["perfil.mp4", { type: "animated", animation: "attach://perfil", main_frame_timestamp: 0.6 }],
                                 ["perfil.jpg", { type: "static", photo: "attach://perfil" }]]) {
    const imagen = await env.ASSETS.fetch(new Request(url.origin + "/img/" + archivo));
    if (!imagen.ok) continue;
    const forma = new FormData();
    forma.append("photo", JSON.stringify(foto));
    forma.append("perfil", await imagen.blob(), archivo);
    const r = await telegram(env, "setMyProfilePhoto", forma);
    if (r.ok) return true;
    console.log("foto", archivo, r.description);
  }
  return "Telegram no aceptó la foto";
}

async function mandarGif(env, origen, chat, nombre, caption, botones) {
  // Los GIF del bot se publican con el Worker (publico/img); Telegram los baja la primera vez y después
  // se reusan por su file_id.
  const clave = "gif:bot-" + nombre;
  const id = await env.DATOS.get(clave);
  const datos = { chat_id: chat, caption, parse_mode: "HTML", animation: id || `${origen}/img/${nombre}.gif` };
  if (botones) datos.reply_markup = { inline_keyboard: botones };
  let r = await telegram(env, "sendAnimation", datos);
  if (!r.ok && id) { // el id dejó de valer: de nuevo desde el archivo
    await env.DATOS.delete(clave);
    r = await telegram(env, "sendAnimation", { ...datos, animation: `${origen}/img/${nombre}.gif` });
  }
  if (r.ok && !id && r.result.animation) await env.DATOS.put(clave, r.result.animation.file_id);
  if (!r.ok) { // sin GIF, por lo menos el texto
    const texto = { chat_id: chat, text: caption, parse_mode: "HTML" };
    if (botones) texto.reply_markup = { inline_keyboard: botones };
    await telegram(env, "sendMessage", texto);
  }
}

async function webhook(pedido, env) {
  if (pedido.headers.get("x-telegram-bot-api-secret-token") !== await secretoWebhook(env)) {
    return new Response("no", { status: 401 });
  }
  const origen = new URL(pedido.url).origin;
  const novedad = await pedido.json();
  const mensaje = novedad.message;
  if (!mensaje || !mensaje.chat || mensaje.chat.type !== "private") return new Response("ok");
  const idioma = (mensaje.from && mensaje.from.language_code || "en").slice(0, 2);
  const t = TEXTOS[idioma] || TEXTOS.en;
  const chat = mensaje.chat.id;
  const nombre = escapar((mensaje.from && mensaje.from.first_name) || "");
  const conNombre = (texto) => texto.replace("{coma_nombre}", nombre ? ", " + nombre : "");
  const responder = (texto) => telegram(env, "sendMessage", { chat_id: chat, text: texto, parse_mode: "HTML" });
  const saludar = () => mandarGif(env, origen, chat, "saludo", conNombre(t.saludo), [[{ text: t.descargar, url: DESCARGA }]]);
  const texto = (mensaje.text || "").trim();

  if (/^\/(stop|desconectar)\b/i.test(texto)) {
    const lista = (await env.DATOS.get("chat:" + chat, "json")) || [];
    for (const hash of lista) {
      const datos = await env.DATOS.get("inst:" + hash, "json");
      if (datos) await env.DATOS.put("inst:" + hash, JSON.stringify({ ...datos, chat: null }));
    }
    await env.DATOS.delete("chat:" + chat);
    await responder(lista.length ? t.stop : t.nada);
    return new Response("ok");
  }
  if (/^\/(help|ayuda|ajuda)\b/i.test(texto)) {
    const lista = (await env.DATOS.get("chat:" + chat, "json")) || [];
    await responder(t.ayuda.replace("{estado}", t.compus(lista.length)));
    return new Response("ok");
  }

  const codigo = normalizarCodigo(texto.replace(/^\/start\b/i, ""));
  if (codigo.length !== 6) { // /start sin código, un saludo, un sticker...
    await saludar();
    return new Response("ok");
  }
  const hash = await env.DATOS.get("cod:" + codigo);
  const datos = hash && await env.DATOS.get("inst:" + hash, "json");
  if (!datos) {
    await responder(t.vencido);
    return new Response("ok");
  }
  await env.DATOS.put("inst:" + hash, JSON.stringify({ ...datos, chat, nombre: (mensaje.from && mensaje.from.first_name) || "" }));
  const lista = (await env.DATOS.get("chat:" + chat, "json")) || [];
  if (!lista.includes(hash)) await env.DATOS.put("chat:" + chat, JSON.stringify([...lista, hash]));
  await env.DATOS.delete("cod:" + codigo);
  await mandarGif(env, origen, chat, "festejo", conNombre(t.listo));
  return new Response("ok");
}

function escapar(texto) {
  return texto.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
