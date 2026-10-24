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
//
// Permisos: cuando Claude Code pide permiso y no estás en la compu, la app manda un mensaje con los
// botones Permitir / Denegar. Cada pedido vive en un Durable Object (Permisos): guarda la respuesta con
// consistencia fuerte y despierta al instante a la compu, que la espera con long polling.
//
// WaveMascot Pro: la app es gratis y abierta; los avisos y los permisos por Telegram son de Pro (con unos
// días de prueba). Pro es de la cuenta de Telegram, no de la compu: sirve en todas las compus que vincule
// y no se puede pasar copiando una llave, porque los avisos solo le llegan a ese chat. Se paga con
// Telegram Stars (moneda XTR): cobra Telegram, sin pasarelas ni datos de tarjeta. La decisión es siempre
// de este servidor; lo que diga la app no cuenta.
//   cuenta:<chat>   -> {prueba, hasta, vitalicio, renueva, cargo, regalo, idioma, pagos, avisado_fin, recordado}
//   factura:<...>   -> enlace de pago de Telegram (uno por plan, precio e idioma; se reusa)
//   soporte:<chat>  -> "1" mientras se espera el mensaje para /paysupport (1 hora)

const API = "https://api.telegram.org/bot";
const LETRAS = "ACDEFHJKMNPQRTUVWXY34679"; // sin las que se confunden (0/O, 1/I/L, 5/S, 8/B, 2/Z)
const VIDA_CODIGO = 15 * 60;
const MAX_TEXTO = 1024;

const DESCARGA = "https://github.com/Marescaa/wavemascot/releases/latest";
const FORO = "https://github.com/Marescaa/wavemascot/discussions";
const FOTO_VERSION = "1"; // subirla para que /setup vuelva a subir la foto de perfil

const DIA = 86400 * 1000;
const MES_TELEGRAM = 2592000; // Telegram solo acepta suscripciones de 30 días
const GRACIA = 12 * 3600 * 1000; // la renovación mensual puede llegar un rato después del vencimiento
const LOCALES = { es: "es-AR", en: "en-US", pt: "pt-BR" };

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
      "Los avisos por acá son de <b>WaveMascot Pro</b>, con {dias} días de prueba gratis. ¿Todavía no tenés " +
      "WaveMascot? La app es gratis 👇",
    descargar: "⬇️ Descargar WaveMascot",
    listo: "<b>¡Conectados{coma_nombre}! 🎉</b>\n\n" +
      "Desde ahora te aviso por acá cuando Claude Code:\n" +
      "✅ termine una tarea\n" +
      "✋ necesite tu permiso o te haga una pregunta\n" +
      "⚠️ llegue al límite de uso o tenga un error\n\n" +
      "Mientras estés en la compu te avisa la mascota en pantalla; acá te llegan cuando estás lejos. Eso y qué " +
      "avisos querés lo cambiás en <b>Ajustes → Celular</b>.\n\n{plan}" +
      "/help ayuda · /pro tu plan · /stop dejar de recibir avisos",
    vencido: "😕 Ese código no existe o ya venció (duran 15 minutos).\n\n" +
      "Sacá uno nuevo en WaveMascot → Ajustes → Celular → <b>Conectar con Telegram</b>.",
    ayuda: "<b>Cómo funciono</b> 🤖\n\n" +
      "WaveMascot vive en tu compu y me avisa cada vez que Claude Code termina o necesita algo; yo te lo paso por " +
      "acá, con un resumen y el nombre del proyecto.\n\n{estado}\n{plan}\n\n" +
      "<b>Comandos</b>\n/help — esta ayuda\n/pro — tu plan de WaveMascot Pro\n/stop — dejar de recibir avisos\n" +
      "/paysupport — ayuda con pagos\n\n" +
      "Para sumar otra compu, tocá <b>Conectar con Telegram</b> en WaveMascot desde esa compu.",
    compus: (n) => n === 0 ? "📭 Todavía no tenés ninguna compu conectada."
      : n === 1 ? "📱 Tenés <b>1 compu</b> conectada." : `📱 Tenés <b>${n} compus</b> conectadas.`,
    stop: "👋 Listo, no te mando más avisos.\n\nCuando quieras volver, tocá <b>Conectar con Telegram</b> en WaveMascot.",
    nada: "No tenías ninguna compu conectada. 🤷",
    descripcion: "👋 Soy Wave, la mascota de WaveMascot.\n\n" +
      "Te aviso por acá cuando Claude Code termina una tarea o necesita tu permiso, con un resumen de lo que hizo. " +
      "Así podés levantarte de la compu tranquilo.\n\n" +
      "Para conectarme: WaveMascot → Ajustes → Celular → Conectar con Telegram. Probalo gratis {dias} días.",
    corta: "Avisos de Claude Code en tu celular, con Wave animada 👋",
    permitir: "✅ Permitir",
    denegar: "❌ Denegar",
    permitido_tg: "✅ <b>Permitido</b> desde Telegram",
    denegado_tg: "❌ <b>Denegado</b> desde Telegram",
    permitido_compu: "✅ <b>Permitido</b> en la compu",
    denegado_compu: "❌ <b>Denegado</b> en la compu",
    resuelto_compu: "💻 Lo resolviste en la compu",
    permiso_vencido: "⏱ <b>Se venció</b>: respondé en la terminal",
    ok_permitido: "Permitido ✅",
    ok_denegado: "Denegado ❌",
    ya_resuelto: "Este pedido ya se resolvió",
    // WaveMascot Pro
    pro_cabeza: "⭐ <b>WaveMascot Pro</b>",
    pro_incluye: "Con Pro, Wave te escribe por acá:\n" +
      "🔔 cuando Claude Code termina, necesita algo o llega al límite\n" +
      "✋ con los botones <b>Permitir</b> y <b>Denegar</b>, sin volver a la compu\n" +
      "💻 desde todas tus compus, con un solo plan",
    pro_nuevo: (d) => `🎁 Tenés <b>${d} días de prueba gratis</b> desde que conectes tu primera compu.`,
    pro_prueba: (d, f) => d <= 1 ? "🎁 Estás en la prueba gratis: termina <b>hoy</b>."
      : `🎁 Estás en la prueba gratis: te quedan <b>${d} días</b> (hasta el ${f}).`,
    pro_vencido: "⏸ Tu prueba terminó y los avisos por Telegram están en pausa. Elegí un plan y vuelven al toque.",
    pro_mensual: (f) => `✅ <b>Sos Pro</b> · plan mensual. Se renueva el ${f}.`,
    pro_cancelado: (f) => `✅ <b>Sos Pro</b> hasta el ${f}. La renovación está cancelada.`,
    pro_regalo: (f) => `🎁 <b>Sos Pro</b> de regalo hasta el ${f}.`,
    pro_vitalicio: "💎 <b>Sos Pro de por vida.</b> ¡Gracias por bancar el proyecto!",
    pro_libre: "🎉 Por ahora Pro es gratis para todos: disfrutalo.",
    pro_elegi: "Elegí tu plan 👇 Se paga con <b>Telegram Stars</b>, desde el celu o la compu.",
    pro_pie: "<i>WaveMascot es gratis y open source; Pro mantiene el bot y el servidor. ¿Algo salió mal con un " +
      "pago? /paysupport</i>",
    boton_mensual: (s, usd) => `⭐ Mensual · ${usd} (${s} Stars)`,
    boton_vitalicio: (s, usd) => `💎 De por vida · ${usd} (${s} Stars)`,
    boton_cancelar: "Cancelar la renovación",
    boton_reactivar: "🔁 Reactivar la renovación",
    sus_cancelada: "Listo: no se renueva más. Seguís siendo Pro hasta el final del mes.",
    sus_reactivada: "Listo: se renueva sola cada mes.",
    sus_error: "No pude cambiarlo ahora; probá de nuevo en un rato.",
    fin_prueba: "⏸ <b>Terminó tu prueba de Pro</b>\n\n" +
      "Claude Code acaba de avisar algo, pero los avisos por Telegram ahora son de <b>WaveMascot Pro</b>. La " +
      "mascota en tu compu te sigue avisando gratis, como siempre.\n\nActivá Pro y vuelven al instante.",
    recordatorio: "⏳ <b>Tu prueba de Pro termina mañana.</b>\n\n" +
      "Para seguir recibiendo los avisos y los permisos por acá, activá Pro.",
    gracias: "<b>¡Gracias{coma_nombre}! Ya sos Pro 🎉</b>\n\n" +
      "Los avisos y los permisos por Telegram quedan activados en todas tus compus. WaveMascot se da cuenta " +
      "solo en unos segundos.\n\n/pro para ver tu plan",
    conectar_prueba: (d) => `🎁 Tenés <b>${d === 1 ? "1 día" : d + " días"} de Pro gratis</b> para probarlo ` +
      "todo. Después, /pro.",
    conectar_pro: "⭐ Tu cuenta es <b>Pro</b>: todo activado.",
    conectar_vencido: "⏸ Tu prueba de Pro ya terminó: los avisos quedan en pausa hasta que actives Pro con /pro.",
    ya_vitalicio: "Ya sos Pro de por vida: no hace falta pagar de nuevo 💎",
    pago_raro: "Este botón de pago no es válido: mandá /pro para ver los planes.",
    fac_mensual: ["WaveMascot Pro · Mensual", "Avisos de Claude Code en Telegram y Permitir/Denegar desde el " +
      "celular, en todas tus compus. Se renueva cada 30 días; lo cancelás cuando quieras con /pro."],
    fac_vitalicio: ["WaveMascot Pro · De por vida", "Avisos de Claude Code en Telegram y Permitir/Denegar " +
      "desde el celular, en todas tus compus. Pagás una sola vez y es tuyo para siempre."],
    soporte: "<b>Ayuda con pagos</b> 💳\n\nContame en un mensaje qué pasó (por ejemplo, si pagaste y no se " +
      "activó, o si querés un reembolso). Se lo paso al desarrollador y te responde por este chat.",
    soporte_foro: `<b>Ayuda con pagos</b> 💳\n\nEscribí en ${FORO} contando qué pasó y te respondemos.`,
    soporte_ok: "📨 Listo, se lo pasé. Te responden por acá.",
    respuesta: "💬 <b>Soporte de WaveMascot</b>\n\n",
    terminos: "<b>Términos de WaveMascot Pro</b>\n\n" +
      "• Pro habilita los avisos y los permisos por Telegram a través de este bot, en todas las compus que " +
      "conectes a tu cuenta.\n" +
      "• El plan mensual se renueva cada 30 días hasta que lo canceles con /pro. El de por vida se paga una vez.\n" +
      "• Se paga con Telegram Stars. Si algo sale mal con un pago, /paysupport.\n" +
      "• La app WaveMascot es gratis y open source: Pro no cambia nada de lo que funciona en tu compu.\n" +
      "• Los avisos pasan por el servidor de WaveMascot y no se guardan.",
    comandos: { help: "Cómo funciono y qué compus tenés conectadas", pro: "Tu plan de WaveMascot Pro",
                stop: "Dejar de recibir avisos", paysupport: "Ayuda con pagos", terms: "Términos de Pro" },
  },
  en: {
    saludo: "<b>Hi{coma_nombre}! I'm Wave 👋</b>\n\n" +
      "I'm the <b>WaveMascot</b> mascot. I message you here when Claude Code finishes a task or needs your " +
      "permission, so you don't have to keep staring at the computer.\n\n" +
      "<b>To connect me:</b>\n" +
      "1️⃣ Open WaveMascot → <b>Settings</b> → <b>Phone</b>\n" +
      "2️⃣ Tap <b>Connect Telegram</b>\n" +
      "3️⃣ This chat opens: tap <b>Start</b> (or send me the 6-letter code)\n\n" +
      "Notifications here are part of <b>WaveMascot Pro</b>, with a {dias}-day free trial. Don't have WaveMascot " +
      "yet? The app is free 👇",
    descargar: "⬇️ Download WaveMascot",
    listo: "<b>We're connected{coma_nombre}! 🎉</b>\n\n" +
      "From now on I'll let you know here when Claude Code:\n" +
      "✅ finishes a task\n" +
      "✋ needs your permission or asks you something\n" +
      "⚠️ hits the usage limit or runs into an error\n\n" +
      "While you're at the computer the on-screen mascot tells you; here you get them when you're away. You can " +
      "change that, and which notifications you want, in <b>Settings → Phone</b>.\n\n{plan}" +
      "/help help · /pro your plan · /stop stop notifications",
    vencido: "😕 That code doesn't exist or has expired (they last 15 minutes).\n\n" +
      "Get a new one in WaveMascot → Settings → Phone → <b>Connect Telegram</b>.",
    ayuda: "<b>How I work</b> 🤖\n\n" +
      "WaveMascot lives on your computer and tells me whenever Claude Code finishes or needs something; I pass it " +
      "on to you here, with a summary and the project name.\n\n{estado}\n{plan}\n\n" +
      "<b>Commands</b>\n/help — this help\n/pro — your WaveMascot Pro plan\n/stop — stop notifications\n" +
      "/paysupport — help with payments\n\n" +
      "To add another computer, tap <b>Connect Telegram</b> in WaveMascot on that computer.",
    compus: (n) => n === 0 ? "📭 You don't have any computer connected yet."
      : n === 1 ? "📱 You have <b>1 computer</b> connected." : `📱 You have <b>${n} computers</b> connected.`,
    stop: "👋 Done, no more notifications.\n\nWhenever you want to come back, tap <b>Connect Telegram</b> in WaveMascot.",
    nada: "You didn't have any computer connected. 🤷",
    descripcion: "👋 I'm Wave, the WaveMascot mascot.\n\n" +
      "I let you know here when Claude Code finishes a task or needs your permission, with a summary of what it " +
      "did. So you can step away from the computer without worrying.\n\n" +
      "To connect me: WaveMascot → Settings → Phone → Connect Telegram. Try it free for {dias} days.",
    corta: "Claude Code notifications on your phone, with Wave animated 👋",
    permitir: "✅ Allow",
    denegar: "❌ Deny",
    permitido_tg: "✅ <b>Allowed</b> from Telegram",
    denegado_tg: "❌ <b>Denied</b> from Telegram",
    permitido_compu: "✅ <b>Allowed</b> on the computer",
    denegado_compu: "❌ <b>Denied</b> on the computer",
    resuelto_compu: "💻 You handled it on the computer",
    permiso_vencido: "⏱ <b>Expired</b>: answer in the terminal",
    ok_permitido: "Allowed ✅",
    ok_denegado: "Denied ❌",
    ya_resuelto: "This request was already handled",
    // WaveMascot Pro
    pro_cabeza: "⭐ <b>WaveMascot Pro</b>",
    pro_incluye: "With Pro, Wave messages you here:\n" +
      "🔔 when Claude Code finishes, needs something or hits the limit\n" +
      "✋ with <b>Allow</b> and <b>Deny</b> buttons, without going back to the computer\n" +
      "💻 from all your computers, with a single plan",
    pro_nuevo: (d) => `🎁 You get a <b>${d}-day free trial</b> as soon as you connect your first computer.`,
    pro_prueba: (d, f) => d <= 1 ? "🎁 You're on the free trial: it ends <b>today</b>."
      : `🎁 You're on the free trial: <b>${d} days</b> left (until ${f}).`,
    pro_vencido: "⏸ Your trial is over and Telegram notifications are paused. Pick a plan and they're back right away.",
    pro_mensual: (f) => `✅ <b>You're Pro</b> · monthly plan. Renews on ${f}.`,
    pro_cancelado: (f) => `✅ <b>You're Pro</b> until ${f}. Renewal is canceled.`,
    pro_regalo: (f) => `🎁 <b>You're Pro</b> as a gift until ${f}.`,
    pro_vitalicio: "💎 <b>You're Pro for life.</b> Thanks for supporting the project!",
    pro_libre: "🎉 Pro is free for everyone for now: enjoy it.",
    pro_elegi: "Pick your plan 👇 You pay with <b>Telegram Stars</b>, from your phone or computer.",
    pro_pie: "<i>WaveMascot is free and open source; Pro keeps the bot and the server running. Something wrong " +
      "with a payment? /paysupport</i>",
    boton_mensual: (s, usd) => `⭐ Monthly · ${usd} (${s} Stars)`,
    boton_vitalicio: (s, usd) => `💎 Lifetime · ${usd} (${s} Stars)`,
    boton_cancelar: "Cancel renewal",
    boton_reactivar: "🔁 Turn renewal back on",
    sus_cancelada: "Done: it won't renew. You stay Pro until the end of the month.",
    sus_reactivada: "Done: it renews every month.",
    sus_error: "I couldn't change it right now; try again in a bit.",
    fin_prueba: "⏸ <b>Your Pro trial is over</b>\n\n" +
      "Claude Code just sent a notification, but Telegram notifications are now part of <b>WaveMascot Pro</b>. " +
      "The mascot on your computer keeps notifying you for free, as always.\n\nTurn on Pro and they're back " +
      "instantly.",
    recordatorio: "⏳ <b>Your Pro trial ends tomorrow.</b>\n\n" +
      "To keep getting notifications and permission requests here, turn on Pro.",
    gracias: "<b>Thank you{coma_nombre}! You're Pro now 🎉</b>\n\n" +
      "Telegram notifications and permissions are on for all your computers. WaveMascot picks it up by itself " +
      "in a few seconds.\n\n/pro to see your plan",
    conectar_prueba: (d) => `🎁 You get <b>${d === 1 ? "1 day" : d + " days"} of Pro for free</b> to try ` +
      "everything. After that, /pro.",
    conectar_pro: "⭐ Your account is <b>Pro</b>: everything's on.",
    conectar_vencido: "⏸ Your Pro trial is already over: notifications stay paused until you turn on Pro with /pro.",
    ya_vitalicio: "You're already Pro for life: no need to pay again 💎",
    pago_raro: "This payment button isn't valid: send /pro to see the plans.",
    fac_mensual: ["WaveMascot Pro · Monthly", "Claude Code notifications on Telegram and Allow/Deny from your " +
      "phone, on all your computers. Renews every 30 days; cancel anytime with /pro."],
    fac_vitalicio: ["WaveMascot Pro · Lifetime", "Claude Code notifications on Telegram and Allow/Deny from " +
      "your phone, on all your computers. Pay once and it's yours forever."],
    soporte: "<b>Help with payments</b> 💳\n\nTell me in one message what happened (for example, you paid and " +
      "it didn't activate, or you'd like a refund). I'll pass it to the developer, who'll answer you in this chat.",
    soporte_foro: `<b>Help with payments</b> 💳\n\nWrite at ${FORO} telling us what happened and we'll get back to you.`,
    soporte_ok: "📨 Done, I passed it on. You'll get an answer here.",
    respuesta: "💬 <b>WaveMascot support</b>\n\n",
    terminos: "<b>WaveMascot Pro terms</b>\n\n" +
      "• Pro turns on Telegram notifications and permissions through this bot, on every computer you connect to " +
      "your account.\n" +
      "• The monthly plan renews every 30 days until you cancel it with /pro. Lifetime is paid once.\n" +
      "• You pay with Telegram Stars. If something goes wrong with a payment, /paysupport.\n" +
      "• The WaveMascot app is free and open source: Pro doesn't change anything that works on your computer.\n" +
      "• Notifications go through the WaveMascot server and aren't stored.",
    comandos: { help: "How I work and which computers are connected", pro: "Your WaveMascot Pro plan",
                stop: "Stop notifications", paysupport: "Help with payments", terms: "Pro terms" },
  },
  pt: {
    saludo: "<b>Oi{coma_nombre}! Eu sou o Wave 👋</b>\n\n" +
      "Sou o mascote do <b>WaveMascot</b>. Eu te escrevo aqui quando o Claude Code termina uma tarefa ou precisa da " +
      "sua permissão, assim você não precisa ficar olhando o computador.\n\n" +
      "<b>Para me conectar:</b>\n" +
      "1️⃣ Abra o WaveMascot → <b>Ajustes</b> → <b>Celular</b>\n" +
      "2️⃣ Toque em <b>Conectar com o Telegram</b>\n" +
      "3️⃣ Este chat abre: toque em <b>Iniciar</b> (ou me mande o código de 6 letras)\n\n" +
      "Os avisos por aqui são do <b>WaveMascot Pro</b>, com {dias} dias de teste grátis. Ainda não tem o " +
      "WaveMascot? O app é grátis 👇",
    descargar: "⬇️ Baixar o WaveMascot",
    listo: "<b>Conectados{coma_nombre}! 🎉</b>\n\n" +
      "A partir de agora eu aviso aqui quando o Claude Code:\n" +
      "✅ terminar uma tarefa\n" +
      "✋ precisar da sua permissão ou te fizer uma pergunta\n" +
      "⚠️ chegar ao limite de uso ou tiver um erro\n\n" +
      "Enquanto você estiver no computador, o mascote avisa na tela; aqui os avisos chegam quando você está longe. " +
      "Isso e quais avisos você quer dá para mudar em <b>Ajustes → Celular</b>.\n\n{plan}" +
      "/help ajuda · /pro seu plano · /stop parar os avisos",
    vencido: "😕 Esse código não existe ou já venceu (duram 15 minutos).\n\n" +
      "Gere um novo em WaveMascot → Ajustes → Celular → <b>Conectar com o Telegram</b>.",
    ayuda: "<b>Como eu funciono</b> 🤖\n\n" +
      "O WaveMascot vive no seu computador e me avisa sempre que o Claude Code termina ou precisa de algo; eu te " +
      "passo aqui, com um resumo e o nome do projeto.\n\n{estado}\n{plan}\n\n" +
      "<b>Comandos</b>\n/help — esta ajuda\n/pro — seu plano do WaveMascot Pro\n/stop — parar os avisos\n" +
      "/paysupport — ajuda com pagamentos\n\n" +
      "Para adicionar outro computador, toque em <b>Conectar com o Telegram</b> no WaveMascot desse computador.",
    compus: (n) => n === 0 ? "📭 Você ainda não tem nenhum computador conectado."
      : n === 1 ? "📱 Você tem <b>1 computador</b> conectado." : `📱 Você tem <b>${n} computadores</b> conectados.`,
    stop: "👋 Pronto, não mando mais avisos.\n\nQuando quiser voltar, toque em <b>Conectar com o Telegram</b> no WaveMascot.",
    nada: "Você não tinha nenhum computador conectado. 🤷",
    descripcion: "👋 Eu sou o Wave, o mascote do WaveMascot.\n\n" +
      "Eu aviso aqui quando o Claude Code termina uma tarefa ou precisa da sua permissão, com um resumo do que ele " +
      "fez. Assim você pode sair do computador tranquilo.\n\n" +
      "Para me conectar: WaveMascot → Ajustes → Celular → Conectar com o Telegram. Teste grátis por {dias} dias.",
    corta: "Avisos do Claude Code no seu celular, com o Wave animado 👋",
    permitir: "✅ Permitir",
    denegar: "❌ Negar",
    permitido_tg: "✅ <b>Permitido</b> pelo Telegram",
    denegado_tg: "❌ <b>Negado</b> pelo Telegram",
    permitido_compu: "✅ <b>Permitido</b> no computador",
    denegado_compu: "❌ <b>Negado</b> no computador",
    resuelto_compu: "💻 Você resolveu no computador",
    permiso_vencido: "⏱ <b>Venceu</b>: responda no terminal",
    ok_permitido: "Permitido ✅",
    ok_denegado: "Negado ❌",
    ya_resuelto: "Este pedido já foi resolvido",
    // WaveMascot Pro
    pro_cabeza: "⭐ <b>WaveMascot Pro</b>",
    pro_incluye: "Com o Pro, o Wave te escreve aqui:\n" +
      "🔔 quando o Claude Code termina, precisa de algo ou chega ao limite\n" +
      "✋ com os botões <b>Permitir</b> e <b>Negar</b>, sem voltar ao computador\n" +
      "💻 de todos os seus computadores, com um só plano",
    pro_nuevo: (d) => `🎁 Você ganha <b>${d} dias de teste grátis</b> quando conectar seu primeiro computador.`,
    pro_prueba: (d, f) => d <= 1 ? "🎁 Você está no teste grátis: ele termina <b>hoje</b>."
      : `🎁 Você está no teste grátis: faltam <b>${d} dias</b> (até ${f}).`,
    pro_vencido: "⏸ Seu teste terminou e os avisos pelo Telegram estão pausados. Escolha um plano e eles voltam na hora.",
    pro_mensual: (f) => `✅ <b>Você é Pro</b> · plano mensal. Renova em ${f}.`,
    pro_cancelado: (f) => `✅ <b>Você é Pro</b> até ${f}. A renovação está cancelada.`,
    pro_regalo: (f) => `🎁 <b>Você é Pro</b> de presente até ${f}.`,
    pro_vitalicio: "💎 <b>Você é Pro para sempre.</b> Obrigado por apoiar o projeto!",
    pro_libre: "🎉 Por enquanto o Pro é grátis para todos: aproveite.",
    pro_elegi: "Escolha seu plano 👇 O pagamento é com <b>Telegram Stars</b>, pelo celular ou pelo computador.",
    pro_pie: "<i>O WaveMascot é grátis e open source; o Pro mantém o bot e o servidor. Algo deu errado com um " +
      "pagamento? /paysupport</i>",
    boton_mensual: (s, usd) => `⭐ Mensal · ${usd} (${s} Stars)`,
    boton_vitalicio: (s, usd) => `💎 Vitalício · ${usd} (${s} Stars)`,
    boton_cancelar: "Cancelar a renovação",
    boton_reactivar: "🔁 Reativar a renovação",
    sus_cancelada: "Pronto: não renova mais. Você continua Pro até o fim do mês.",
    sus_reactivada: "Pronto: renova sozinho todo mês.",
    sus_error: "Não consegui mudar agora; tente de novo daqui a pouco.",
    fin_prueba: "⏸ <b>Seu teste do Pro terminou</b>\n\n" +
      "O Claude Code acabou de avisar algo, mas os avisos pelo Telegram agora são do <b>WaveMascot Pro</b>. O " +
      "mascote no seu computador continua avisando de graça, como sempre.\n\nAtive o Pro e eles voltam na hora.",
    recordatorio: "⏳ <b>Seu teste do Pro termina amanhã.</b>\n\n" +
      "Para continuar recebendo os avisos e as permissões aqui, ative o Pro.",
    gracias: "<b>Obrigado{coma_nombre}! Agora você é Pro 🎉</b>\n\n" +
      "Os avisos e as permissões pelo Telegram ficam ativados em todos os seus computadores. O WaveMascot " +
      "percebe sozinho em alguns segundos.\n\n/pro para ver seu plano",
    conectar_prueba: (d) => `🎁 Você tem <b>${d === 1 ? "1 dia" : d + " dias"} de Pro grátis</b> para testar ` +
      "tudo. Depois, /pro.",
    conectar_pro: "⭐ Sua conta é <b>Pro</b>: tudo ativado.",
    conectar_vencido: "⏸ Seu teste do Pro já terminou: os avisos ficam pausados até você ativar o Pro com /pro.",
    ya_vitalicio: "Você já é Pro para sempre: não precisa pagar de novo 💎",
    pago_raro: "Este botão de pagamento não é válido: mande /pro para ver os planos.",
    fac_mensual: ["WaveMascot Pro · Mensal", "Avisos do Claude Code no Telegram e Permitir/Negar pelo celular, " +
      "em todos os seus computadores. Renova a cada 30 dias; cancele quando quiser com /pro."],
    fac_vitalicio: ["WaveMascot Pro · Vitalício", "Avisos do Claude Code no Telegram e Permitir/Negar pelo " +
      "celular, em todos os seus computadores. Pague uma vez e é seu para sempre."],
    soporte: "<b>Ajuda com pagamentos</b> 💳\n\nMe conte em uma mensagem o que aconteceu (por exemplo, se você " +
      "pagou e não ativou, ou se quer um reembolso). Eu passo para o desenvolvedor, que te responde neste chat.",
    soporte_foro: `<b>Ajuda com pagamentos</b> 💳\n\nEscreva em ${FORO} contando o que aconteceu e a gente responde.`,
    soporte_ok: "📨 Pronto, já passei. Você vai receber a resposta aqui.",
    respuesta: "💬 <b>Suporte do WaveMascot</b>\n\n",
    terminos: "<b>Termos do WaveMascot Pro</b>\n\n" +
      "• O Pro ativa os avisos e as permissões pelo Telegram através deste bot, em todos os computadores que " +
      "você conectar à sua conta.\n" +
      "• O plano mensal renova a cada 30 dias até você cancelar com /pro. O vitalício é pago uma vez.\n" +
      "• O pagamento é com Telegram Stars. Se algo der errado com um pagamento, /paysupport.\n" +
      "• O app WaveMascot é grátis e open source: o Pro não muda nada do que funciona no seu computador.\n" +
      "• Os avisos passam pelo servidor do WaveMascot e não são guardados.",
    comandos: { help: "Como eu funciono e quais computadores estão conectados", pro: "Seu plano do WaveMascot Pro",
                stop: "Parar os avisos", paysupport: "Ajuda com pagamentos", terms: "Termos do Pro" },
  },
};

export default {
  async fetch(pedido, env) {
    const url = new URL(pedido.url);
    try {
      if (url.pathname === "/telegram" && pedido.method === "POST") return await webhook(pedido, env);
      if (url.pathname === "/setup") return await setup(url, env);
      if (url.pathname === "/v1/planes" && pedido.method === "GET") return await planes(env);
      if (url.pathname === "/v1/registro" && pedido.method === "POST") return await registrar(env);
      if (url.pathname === "/v1/registro" && pedido.method === "DELETE") return await conLlave(pedido, env, desconectar);
      if (url.pathname === "/v1/codigo" && pedido.method === "POST") return await conLlave(pedido, env, nuevoCodigo);
      if (url.pathname === "/v1/estado" && pedido.method === "GET") return await conLlave(pedido, env, estado);
      if (url.pathname === "/v1/aviso" && pedido.method === "POST") return await conLlave(pedido, env, aviso);
      if (url.pathname === "/v1/permiso" && pedido.method === "POST") return await conLlave(pedido, env, pedirPermiso);
      const permiso = url.pathname.match(/^\/v1\/permiso\/([A-Za-z0-9]{20})(\/cerrar)?$/);
      if (permiso) {
        const accion = permiso[2] ? cerrarPermiso : esperarPermiso;
        return await conLlave(pedido, env, (p, e, hash, datos) => accion(p, e, hash, datos, permiso[1]));
      }
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
  if (env.TELEGRAM_FALSO) { // solo en pruebas locales (.dev.vars): no sale nada a Telegram
    console.log("telegram falso:", metodo, datos instanceof FormData ? "(archivo)" : JSON.stringify(datos));
    if (metodo === "createInvoiceLink") return { ok: true, result: "https://t.me/$falso-" + datos.payload };
    return { ok: true, result: { message_id: 1, username: "WaveNotificationBot" } };
  }
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
  // Con el plan de la cuenta de Telegram vinculada (la app lo muestra; decidir, decide este servidor).
  const plan = datos.chat ? planDe(env, await cuentaDe(env, datos.chat)) : null;
  return json({ ok: true, conectado: !!datos.chat, nombre: datos.nombre || "", bot: await nombreDelBot(env), plan,
                ...infoPlanes(env) });
}

async function planes(env) {
  // Público: precios y días de prueba, para la guía de Pro antes de conectar Telegram.
  return json({ ok: true, bot: await nombreDelBot(env), ...infoPlanes(env) });
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
  const origen = new URL(pedido.url).origin;
  const freno = await frenoPro(env, origen, datos.chat);
  if (freno) return freno;
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
  if (r.ok) await recordarFinDePrueba(env, origen, datos.chat);
  return json(r.ok ? { ok: true } : { ok: false, error: r.description || "Telegram no lo aceptó" }, r.ok ? 200 : 502);
}

// --- WaveMascot Pro -------------------------------------------------------------------------------

function cobrando(env) {
  return env.COBRAR !== "no"; // COBRAR = "no" (wrangler.toml) apaga el cobro: todo vuelve a ser gratis
}

function diasPrueba(env) {
  const dias = Number(env.DIAS_PRUEBA);
  return Number.isFinite(dias) && dias >= 0 ? dias : 7;
}

function precios(env) { // en Telegram Stars
  return { mensual: Number(env.PRECIO_MENSUAL) || 100, vitalicio: Number(env.PRECIO_VITALICIO) || 1500 };
}

function precioUsd(stars, idioma) {
  // Lo que salen esas Stars en la tienda de Telegram: 100 = US$ 1,99; 1.500 = US$ 29,99.
  const valor = (stars * 0.02 - 0.01).toFixed(2);
  return "US$ " + (idioma === "en" ? valor : valor.replace(".", ","));
}

function infoPlanes(env) {
  return { cobrando: cobrando(env), precios: precios(env), dias_prueba: diasPrueba(env) };
}

function fecha(ms, idioma) {
  return new Date(ms).toLocaleDateString(LOCALES[idioma] || "en-US", { day: "numeric", month: "long", timeZone: "UTC" });
}

function diasHasta(ms) {
  return Math.max(0, Math.ceil((ms - Date.now()) / DIA));
}

async function leerCuenta(env, chat) {
  return env.DATOS.get("cuenta:" + chat, "json");
}

async function guardarCuenta(env, chat, cuenta) {
  await env.DATOS.put("cuenta:" + chat, JSON.stringify(cuenta));
}

async function cuentaDe(env, chat, idioma) {
  // La cuenta se crea la primera vez que se la necesita (al vincular): ahí empieza la prueba gratis.
  let cuenta = await leerCuenta(env, chat);
  let cambio = !cuenta;
  cuenta = cuenta || { prueba: Date.now(), hasta: 0, vitalicio: false, renueva: false, pagos: [] };
  if (idioma && TEXTOS[idioma] && cuenta.idioma !== idioma) {
    cuenta.idioma = idioma;
    cambio = true;
  }
  if (cambio) await guardarCuenta(env, chat, cuenta);
  return cuenta;
}

function planDe(env, cuenta) {
  // {pro, tipo, hasta, renueva, dias}. tipo: libre, vitalicio, mensual, regalo, prueba o vencido.
  const plan = (pro, tipo, hasta = null, renueva = null) =>
    ({ pro, tipo, hasta, renueva, dias: hasta ? diasHasta(hasta) : null });
  if (!cobrando(env)) return plan(true, "libre");
  if (cuenta.vitalicio) return plan(true, "vitalicio");
  if (cuenta.hasta && Date.now() < cuenta.hasta + GRACIA) {
    return cuenta.regalo ? plan(true, "regalo", cuenta.hasta) : plan(true, "mensual", cuenta.hasta, !!cuenta.renueva);
  }
  const finPrueba = cuenta.prueba + diasPrueba(env) * DIA;
  if (Date.now() < finPrueba) return plan(true, "prueba", finPrueba);
  return plan(false, "vencido");
}

function textoPlan(env, t, idioma, cuenta) {
  if (!cuenta) return cobrando(env) ? t.pro_nuevo(diasPrueba(env)) : t.pro_libre;
  const plan = planDe(env, cuenta);
  const f = (ms) => fecha(ms, idioma);
  switch (plan.tipo) {
    case "libre": return t.pro_libre;
    case "vitalicio": return t.pro_vitalicio;
    case "mensual": return plan.renueva ? t.pro_mensual(f(plan.hasta)) : t.pro_cancelado(f(plan.hasta));
    case "regalo": return t.pro_regalo(f(plan.hasta));
    case "prueba": return t.pro_prueba(plan.dias, f(plan.hasta));
    default: return t.pro_vencido;
  }
}

async function enlaceFactura(env, plan, idioma) {
  // Un enlace de pago por plan, precio e idioma, creado una vez y reusado: quien lo paga queda en el pago
  // (successful_payment trae su chat), así que no hace falta uno por persona.
  const stars = precios(env)[plan];
  const clave = `factura:${plan}:${stars}:${idioma}`;
  const guardado = await env.DATOS.get(clave);
  if (guardado) return guardado;
  const t = TEXTOS[idioma] || TEXTOS.en;
  const [titulo, descripcion] = plan === "mensual" ? t.fac_mensual : t.fac_vitalicio;
  const datos = { title: titulo, description: descripcion, payload: "pro:" + plan, currency: "XTR",
                  prices: [{ label: titulo, amount: stars }] };
  if (plan === "mensual") datos.subscription_period = MES_TELEGRAM;
  const r = await telegram(env, "createInvoiceLink", datos);
  if (!r.ok) throw new Error("createInvoiceLink: " + r.description);
  await env.DATOS.put(clave, r.result);
  return r.result;
}

async function botonesPro(env, idioma, cuenta, primero = "mensual") {
  const t = TEXTOS[idioma] || TEXTOS.en;
  const plan = cuenta ? planDe(env, cuenta) : { tipo: "nuevo" };
  if (plan.tipo === "vitalicio" || plan.tipo === "libre") return [];
  const p = precios(env);
  const filas = [];
  if (plan.tipo !== "mensual") { // con la suscripción activa no se ofrece otra (cobraría dos veces)
    filas.push([{ text: t.boton_mensual(p.mensual, precioUsd(p.mensual, idioma)), url: await enlaceFactura(env, "mensual", idioma) }]);
  }
  filas.push([{ text: t.boton_vitalicio(p.vitalicio, precioUsd(p.vitalicio, idioma)), url: await enlaceFactura(env, "vitalicio", idioma) }]);
  if (primero === "vitalicio") filas.reverse();
  if (plan.tipo === "mensual") {
    filas.push([plan.renueva ? { text: t.boton_cancelar, callback_data: "s:cancelar" }
                             : { text: t.boton_reactivar, callback_data: "s:reactivar" }]);
  }
  return filas;
}

async function mandarPro(env, chat, idioma, cuenta, { intro = "", primero = "mensual", editar = 0 } = {}) {
  // El mensaje de /pro: cómo está tu plan, qué incluye y los botones para pagar (o para la renovación).
  const t = TEXTOS[idioma] || TEXTOS.en;
  const tipo = cuenta ? planDe(env, cuenta).tipo : "nuevo";
  const partes = intro ? [t[intro]] : [t.pro_cabeza, textoPlan(env, t, idioma, cuenta)];
  if (!["vitalicio", "mensual", "regalo", "libre"].includes(tipo)) partes.push(t.pro_incluye, t.pro_elegi);
  partes.push(t.pro_pie);
  let botones = [];
  try {
    botones = await botonesPro(env, idioma, cuenta, primero);
  } catch (e) { // sin los enlaces de pago, por lo menos el texto (y /pro más tarde los vuelve a intentar)
    console.log("botones de Pro", e && e.message);
  }
  const datos = { chat_id: chat, text: partes.join("\n\n"), parse_mode: "HTML", link_preview_options: { is_disabled: true },
                  reply_markup: { inline_keyboard: botones } };
  return editar ? telegram(env, "editMessageText", { ...datos, message_id: editar }) : telegram(env, "sendMessage", datos);
}

async function frenoPro(env, origen, chat, idioma) {
  // null si el aviso puede salir; si no, la respuesta 402 para la app. La primera vez que frena, el bot le
  // explica a la persona qué pasó (una sola vez, no con cada aviso).
  if (!cobrando(env)) return null;
  const cuenta = await cuentaDe(env, chat);
  const plan = planDe(env, cuenta);
  if (plan.pro) return null;
  if (!cuenta.avisado_fin) {
    cuenta.avisado_fin = true;
    await guardarCuenta(env, chat, cuenta);
    await mandarPro(env, chat, cuenta.idioma || idioma || "en", cuenta, { intro: "fin_prueba" });
  }
  return json({ ok: false, error: "hace falta WaveMascot Pro", pro: false, plan }, 402);
}

async function recordarFinDePrueba(env, origen, chat) {
  // Un día antes de que termine la prueba, una sola vez, después de un aviso que sí salió.
  if (!cobrando(env) || diasPrueba(env) < 2) return;
  const cuenta = await leerCuenta(env, chat);
  if (!cuenta || cuenta.recordado) return;
  const plan = planDe(env, cuenta);
  if (plan.tipo !== "prueba" || plan.hasta - Date.now() > DIA) return;
  cuenta.recordado = true;
  await guardarCuenta(env, chat, cuenta);
  await mandarPro(env, chat, cuenta.idioma || "en", cuenta, { intro: "recordatorio" });
}

async function antesDePagar(env, consulta) {
  // Telegram pregunta antes de cobrar: hay 10 segundos para decir que sí.
  const t = TEXTOS[(consulta.from && consulta.from.language_code || "en").slice(0, 2)] || TEXTOS.en;
  const plan = (/^pro:(mensual|vitalicio)$/.exec(consulta.invoice_payload || "") || [])[1];
  let error = "";
  if (!plan || consulta.currency !== "XTR") error = t.pago_raro;
  else if (plan === "vitalicio" && (await leerCuenta(env, consulta.from.id) || {}).vitalicio) error = t.ya_vitalicio;
  await telegram(env, "answerPreCheckoutQuery", error
    ? { pre_checkout_query_id: consulta.id, ok: false, error_message: error }
    : { pre_checkout_query_id: consulta.id, ok: true });
}

async function registrarPago(env, origen, mensaje, idioma, conNombre) {
  // Llegó un pago (el primero o una renovación mensual). Cada cobro se anota una sola vez.
  const pago = mensaje.successful_payment;
  const chat = mensaje.chat.id;
  const plan = (/^pro:(mensual|vitalicio)$/.exec(pago.invoice_payload || "") || [])[1] || "?";
  const cuenta = await cuentaDe(env, chat, idioma);
  cuenta.pagos = cuenta.pagos || [];
  if (cuenta.pagos.some((x) => x.id === pago.telegram_payment_charge_id)) return;
  cuenta.pagos = [...cuenta.pagos, { id: pago.telegram_payment_charge_id, plan, stars: pago.total_amount,
                                     fecha: new Date().toISOString(), renovacion: !!pago.is_recurring && !pago.is_first_recurring }].slice(-100);
  if (plan === "vitalicio") {
    if (cuenta.renueva && cuenta.cargo) { // ya no tiene sentido seguir cobrándole el mensual
      const r = await telegram(env, "editUserStarSubscription", { user_id: mensaje.from.id,
        telegram_payment_charge_id: cuenta.cargo, is_canceled: true });
      if (r.ok) cuenta.renueva = false;
    }
    cuenta.vitalicio = true;
  } else if (plan === "mensual") {
    const vence = pago.subscription_expiration_date ? pago.subscription_expiration_date * 1000
      : Math.max(Date.now(), cuenta.hasta || 0) + 30 * DIA;
    cuenta.hasta = Math.max(cuenta.hasta || 0, vence);
    cuenta.regalo = false;
    cuenta.renueva = true;
    cuenta.cargo = pago.telegram_payment_charge_id;
  }
  cuenta.avisado_fin = false;
  cuenta.recordado = true;
  await guardarCuenta(env, chat, cuenta);
  const renovacion = pago.is_recurring && !pago.is_first_recurring;
  if (!renovacion) {
    const t = TEXTOS[cuenta.idioma] || TEXTOS[idioma] || TEXTOS.en;
    await mandarGif(env, origen, chat, "festejo", conNombre(t.gracias));
  }
  await avisarDueno(env, `💰 ${renovacion ? "Renovación" : "Pago"}: ${plan} · ${pago.total_amount} ⭐ · chat ` +
                         `<code>${chat}</code>\n<code>${escapar(pago.telegram_payment_charge_id)}</code>`);
}

async function botonSuscripcion(env, consulta) {
  // "Cancelar / Reactivar la renovación" en el mensaje de /pro.
  const t = TEXTOS[(consulta.from && consulta.from.language_code || "en").slice(0, 2)] || TEXTOS.en;
  const cancelar = consulta.data === "s:cancelar";
  const chat = consulta.message && consulta.message.chat.id;
  const cuenta = chat && await leerCuenta(env, chat);
  if (!cuenta || !cuenta.cargo || chat !== consulta.from.id) {
    await telegram(env, "answerCallbackQuery", { callback_query_id: consulta.id });
    return;
  }
  const r = await telegram(env, "editUserStarSubscription", { user_id: consulta.from.id,
    telegram_payment_charge_id: cuenta.cargo, is_canceled: cancelar });
  if (r.ok) {
    cuenta.renueva = !cancelar;
    await guardarCuenta(env, chat, cuenta);
  }
  await telegram(env, "answerCallbackQuery", { callback_query_id: consulta.id, show_alert: true,
    text: r.ok ? (cancelar ? t.sus_cancelada : t.sus_reactivada) : t.sus_error });
  if (r.ok) await mandarPro(env, chat, cuenta.idioma || "en", cuenta, { editar: consulta.message.message_id });
}

async function avisarDueno(env, texto) {
  // DUENO: el id de chat de quien mantiene el bot (mandale /id). Le llegan los pagos y el soporte.
  if (env.DUENO) await telegram(env, "sendMessage", { chat_id: env.DUENO, text: texto, parse_mode: "HTML" });
}

async function comandoDueno(env, texto, responder) {
  // Comandos solo para DUENO. Devuelve true si el texto era uno de ellos.
  const partes = texto.trim().split(/\s+/);
  const orden = (partes[0] || "").toLowerCase();
  const chat = Number(partes[1]);
  if (!["/regalar", "/quitar", "/reembolsar", "/cuenta", "/responder"].includes(orden)) return false;
  if (!chat) {
    await responder("Uso:\n/cuenta CHAT\n/regalar CHAT DÍAS|siempre\n/quitar CHAT\n/reembolsar CHAT ID_DEL_PAGO\n" +
                    "/responder CHAT texto");
    return true;
  }
  if (orden === "/responder") {
    const mensaje = texto.trim().split(/\s+/).slice(2).join(" ");
    const cuenta = await leerCuenta(env, chat);
    const t = TEXTOS[cuenta && cuenta.idioma] || TEXTOS.en;
    const r = await telegram(env, "sendMessage", { chat_id: chat, text: t.respuesta + escapar(mensaje), parse_mode: "HTML" });
    await responder(r.ok ? "✓ Enviado" : "No se pudo: " + r.description);
    return true;
  }
  const cuenta = await leerCuenta(env, chat);
  if (orden === "/cuenta") {
    await responder(cuenta ? `<pre>${escapar(JSON.stringify({ ...cuenta, plan: planDe(env, cuenta) }, null, 1))}</pre>`
                           : "Ese chat no tiene cuenta.");
    return true;
  }
  const c = cuenta || { prueba: Date.now(), hasta: 0, vitalicio: false, renueva: false, pagos: [] };
  if (orden === "/regalar") {
    if ((partes[2] || "").toLowerCase() === "siempre") c.vitalicio = true;
    else {
      const dias = Number(partes[2]) || 30;
      c.hasta = Math.max(c.hasta || 0, Date.now()) + dias * DIA;
      c.regalo = !c.renueva;
    }
    c.avisado_fin = false;
  } else if (orden === "/quitar") {
    Object.assign(c, { vitalicio: false, hasta: 0, regalo: false, prueba: 0 });
  } else if (orden === "/reembolsar") {
    const id = partes[2] || "";
    const pago = (c.pagos || []).find((x) => x.id === id);
    if (!pago) {
      await responder("No encontré ese pago en la cuenta.");
      return true;
    }
    const r = await telegram(env, "refundStarPayment", { user_id: chat, telegram_payment_charge_id: id });
    if (!r.ok) {
      await responder("Telegram no lo reembolsó: " + r.description);
      return true;
    }
    pago.reembolsado = true;
    if (pago.plan === "vitalicio") c.vitalicio = false;
    else {
      if (c.renueva && c.cargo) { // que no le vuelva a cobrar el mes que viene
        await telegram(env, "editUserStarSubscription", { user_id: chat, telegram_payment_charge_id: c.cargo,
                                                          is_canceled: true });
      }
      Object.assign(c, { hasta: Math.min(c.hasta || 0, Date.now()), renueva: false });
    }
  }
  await guardarCuenta(env, chat, c);
  await responder(`✓ Listo. Ahora: <b>${planDe(env, c).tipo}</b>`);
  return true;
}

// --- permisos -------------------------------------------------------------------------------------

const LETRAS_ID = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789";

function cajaPermiso(env, id) {
  return env.PERMISOS.get(env.PERMISOS.idFromName(id));
}

async function alPermiso(env, id, accion, datos, consulta = "") {
  const r = await cajaPermiso(env, id).fetch("https://permiso/" + accion + consulta,
    datos ? { method: "POST", body: JSON.stringify(datos) } : {});
  return { estado: r.status, ...(await r.json()) };
}

async function pedirPermiso(pedido, env, hash, datos) {
  // La app manda el texto ya armado (en el idioma de sus ajustes): el bot le suma los botones.
  if (!datos.chat) return json({ ok: false, error: "no conectado", conectado: false }, 409);
  const entrada = await pedido.json();
  const texto = String(entrada.texto || "").slice(0, 3500);
  if (!texto.trim()) return json({ ok: false, error: "falta el texto" }, 400);
  const idioma = TEXTOS[entrada.idioma] ? entrada.idioma : "en";
  const freno = await frenoPro(env, new URL(pedido.url).origin, datos.chat, idioma);
  if (freno) return freno; // la compu sigue sola: el permiso se contesta en la terminal
  const espera = Math.min(600, Math.max(30, Number(entrada.espera) || 240));
  const t = TEXTOS[idioma];
  const id = azar(20, LETRAS_ID);
  const r = await telegram(env, "sendMessage", {
    chat_id: datos.chat, text: texto, parse_mode: "HTML",
    reply_markup: { inline_keyboard: [[{ text: t.permitir, callback_data: `p:${id}:a` },
                                       { text: t.denegar, callback_data: `p:${id}:d` }]] },
  });
  if (!r.ok) {
    if (r.error_code === 403) { // bloqueó al bot: queda desconectado
      await sacarDelChat(env, datos.chat, hash);
      await env.DATOS.put("inst:" + hash, JSON.stringify({ ...datos, chat: null }));
      return json({ ok: false, error: "el chat bloqueó al bot", conectado: false }, 409);
    }
    return json({ ok: false, error: r.description || "Telegram no lo aceptó" }, 502);
  }
  await alPermiso(env, id, "crear", { hash, chat: datos.chat, mensaje: r.result.message_id, texto, idioma,
                                      vence: Date.now() / 1000 + espera + 20 });
  return json({ ok: true, id });
}

async function esperarPermiso(pedido, env, hash, datos, id) {
  // Long polling: responde apenas tocás un botón, o a los ~25 s sin novedades (la app vuelve a preguntar).
  const segundos = Math.min(25, Math.max(1, Number(new URL(pedido.url).searchParams.get("segundos")) || 20));
  const r = await alPermiso(env, id, "esperar", null, `?hash=${hash}&segundos=${segundos}`);
  return json(r, r.estado);
}

async function cerrarPermiso(pedido, env, hash, datos, id) {
  // La compu lo resolvió (Wave o la terminal) o se cansó de esperar: el mensaje pierde los botones.
  const entrada = await pedido.json();
  const r = await alPermiso(env, id, "cerrar", { hash, motivo: entrada.motivo === "vencido" ? "vencido" : "compu",
                                                 decision: ["allow", "deny"].includes(entrada.decision) ? entrada.decision : null });
  if (r.ok && r.cambio) await editarPermiso(env, r.d);
  return json({ ok: r.ok }, r.estado);
}

async function editarPermiso(env, d) {
  const t = TEXTOS[d.idioma] || TEXTOS.en;
  const linea = d.origen === "telegram" ? (d.decision === "allow" ? t.permitido_tg : t.denegado_tg)
    : d.cerrado === "vencido" ? t.permiso_vencido
    : d.decision_compu === "allow" ? t.permitido_compu
    : d.decision_compu === "deny" ? t.denegado_compu : t.resuelto_compu;
  await telegram(env, "editMessageText", { chat_id: d.chat, message_id: d.mensaje, text: d.texto + "\n\n" + linea,
                                           parse_mode: "HTML", reply_markup: { inline_keyboard: [] } });
}

async function botonPermiso(env, consulta) {
  // Tocaron Permitir o Denegar: solo vale desde el chat que recibió el pedido, y una sola vez.
  const partes = /^p:([A-Za-z0-9]{20}):([ad])$/.exec(consulta.data || "");
  const t = TEXTOS[(consulta.from && consulta.from.language_code || "en").slice(0, 2)] || TEXTOS.en;
  if (!partes || !consulta.message) {
    await telegram(env, "answerCallbackQuery", { callback_query_id: consulta.id });
    return;
  }
  const decision = partes[2] === "a" ? "allow" : "deny";
  const r = await alPermiso(env, partes[1], "decidir", { decision, chat: consulta.message.chat.id });
  await telegram(env, "answerCallbackQuery", {
    callback_query_id: consulta.id,
    text: r.ok ? (decision === "allow" ? t.ok_permitido : t.ok_denegado) : t.ya_resuelto,
  });
  if (r.ok) await editarPermiso(env, r.d);
}

// Un pedido de permiso. Guarda: hash de la instalación, chat, id del mensaje, texto, idioma, vencimiento,
// y después la decisión (desde Telegram) o cómo se cerró (en la compu, o vencido).
export class Permisos {
  constructor(state, env) {
    this.state = state;
    this.env = env;
    this.esperando = [];
  }

  async fetch(pedido) {
    const url = new URL(pedido.url);
    const accion = url.pathname.slice(1);
    let d = await this.state.storage.get("d");
    if (accion === "crear") {
      d = await pedido.json();
      await this.state.storage.put("d", d);
      await this.state.storage.setAlarm(d.vence * 1000); // si la compu no lo cierra, se vence solo
      return json({ ok: true });
    }
    if (!d) return json({ ok: false, error: "no existe" }, 404);
    if (accion === "esperar") {
      if (url.searchParams.get("hash") !== d.hash) return json({ ok: false, error: "no es tuyo" }, 403);
      if (!d.decision && !d.cerrado) {
        const segundos = Number(url.searchParams.get("segundos")) || 20;
        await new Promise((listo) => {
          const reloj = setTimeout(listo, segundos * 1000);
          this.esperando.push(() => { clearTimeout(reloj); listo(); });
        });
        d = await this.state.storage.get("d");
      }
      return json({ ok: true, decision: d.decision || null, cerrado: d.cerrado || null });
    }
    const entrada = await pedido.json();
    if (accion === "decidir") {
      if (entrada.chat !== d.chat) return json({ ok: false, error: "otro chat" }, 403);
      if (d.decision || d.cerrado || Date.now() / 1000 > d.vence) return json({ ok: false, ya: true });
      d.decision = entrada.decision;
      d.origen = "telegram";
    } else if (accion === "cerrar") {
      if (entrada.hash !== d.hash) return json({ ok: false, error: "no es tuyo" }, 403);
      if (d.decision || d.cerrado) return json({ ok: true, cambio: false });
      d.cerrado = entrada.motivo;
      d.decision_compu = entrada.decision;
    } else {
      return json({ ok: false, error: "no existe" }, 404);
    }
    await this.state.storage.put("d", d);
    for (const despertar of this.esperando.splice(0)) despertar();
    return json({ ok: true, cambio: true, d });
  }

  async alarm() {
    const d = await this.state.storage.get("d");
    if (d && !d.decision && !d.cerrado) {
      d.cerrado = "vencido";
      await this.state.storage.put("d", d);
      await editarPermiso(this.env, d);
    }
    // Una hora después ya no sirve para nada: se borra.
    if (d && Date.now() / 1000 > d.vence + 3600) await this.state.storage.deleteAll();
    else await this.state.storage.setAlarm(Date.now() + 3600 * 1000);
  }
}

// --- lo que llega de Telegram ------------------------------------------------------------------

async function secretoWebhook(env) {
  return (await sha256("webhook:" + env.BOT_TOKEN)).slice(0, 48);
}

async function setup(url, env) {
  // Apunta el webhook a este servidor y deja el perfil del bot armado (descripción, comandos y foto, en
  // los tres idiomas). Se puede llamar las veces que sea: la foto solo se sube si cambió FOTO_VERSION.
  // Con el secreto CLAVE_SETUP, hay que pasarlo: /setup?clave=...
  if (env.CLAVE_SETUP && url.searchParams.get("clave") !== env.CLAVE_SETUP) return json({ ok: false }, 403);
  const r = await telegram(env, "setWebhook", {
    url: url.origin + "/telegram",
    secret_token: await secretoWebhook(env),
    allowed_updates: ["message", "callback_query", "pre_checkout_query"], // pre_checkout_query: los pagos
    drop_pending_updates: true,
  });
  const resultado = { ok: r.ok, webhook: r.description, bot: await nombreDelBot(env) };
  for (const [idioma, t] of Object.entries(TEXTOS)) {
    const codigo = idioma === "en" ? "" : idioma; // inglés es el de todos los demás idiomas
    const comandos = Object.entries(t.comandos).map(([command, description]) => ({ command, description }));
    const respuestas = await Promise.all([
      telegram(env, "setMyDescription", { description: t.descripcion.replace("{dias}", diasPrueba(env)),
                                          language_code: codigo }),
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
  if (novedad.pre_checkout_query) { // alguien está por pagar Pro
    await antesDePagar(env, novedad.pre_checkout_query);
    return new Response("ok");
  }
  if (novedad.callback_query) { // Permitir / Denegar en un pedido de permiso, o la renovación de Pro
    if ((novedad.callback_query.data || "").startsWith("s:")) await botonSuscripcion(env, novedad.callback_query);
    else await botonPermiso(env, novedad.callback_query);
    return new Response("ok");
  }
  const mensaje = novedad.message;
  if (!mensaje || !mensaje.chat || mensaje.chat.type !== "private") return new Response("ok");
  const idioma = (mensaje.from && mensaje.from.language_code || "en").slice(0, 2);
  const t = TEXTOS[idioma] || TEXTOS.en;
  const lengua = TEXTOS[idioma] ? idioma : "en";
  const chat = mensaje.chat.id;
  const nombre = escapar((mensaje.from && mensaje.from.first_name) || "");
  const conNombre = (texto) => texto.replace("{coma_nombre}", nombre ? ", " + nombre : "");
  const responder = (texto) => telegram(env, "sendMessage", { chat_id: chat, text: texto, parse_mode: "HTML",
                                                              link_preview_options: { is_disabled: true } });
  const saludar = () => mandarGif(env, origen, chat, "saludo", conNombre(t.saludo).replace("{dias}", diasPrueba(env)),
                                  [[{ text: t.descargar, url: DESCARGA }]]);
  const texto = (mensaje.text || "").trim();

  if (mensaje.successful_payment) {
    await registrarPago(env, origen, mensaje, lengua, conNombre);
    return new Response("ok");
  }
  if (env.DUENO && String(chat) === String(env.DUENO) && await comandoDueno(env, texto, responder)) {
    return new Response("ok");
  }
  if (/^\/id\b/i.test(texto)) {
    await responder(`<code>${chat}</code>`);
    return new Response("ok");
  }
  if (/^\/(paysupport|soporte|suporte)\b/i.test(texto)) {
    if (env.DUENO) await env.DATOS.put("soporte:" + chat, "1", { expirationTtl: 3600 });
    await responder(env.DUENO ? t.soporte : t.soporte_foro);
    return new Response("ok");
  }
  if (texto && !texto.startsWith("/") && await env.DATOS.get("soporte:" + chat)) {
    // El mensaje que siguió a /paysupport: va para quien mantiene el bot, con los pagos de esa cuenta.
    await env.DATOS.delete("soporte:" + chat);
    const cuenta = await leerCuenta(env, chat);
    const pagos = ((cuenta && cuenta.pagos) || []).slice(-5)
      .map((x) => `• ${x.fecha.slice(0, 10)} ${x.plan} ${x.stars}⭐${x.reembolsado ? " (reembolsado)" : ""}\n  <code>${escapar(x.id)}</code>`);
    const usuario = mensaje.from && mensaje.from.username ? " @" + escapar(mensaje.from.username) : "";
    await avisarDueno(env, `🆘 <b>Soporte</b> de ${nombre}${usuario} · chat <code>${chat}</code>\n\n${escapar(texto)}\n\n` +
                           (pagos.length ? "Pagos:\n" + pagos.join("\n") + "\n\n" : "Sin pagos.\n\n") +
                           `Responder: <code>/responder ${chat} </code>…`);
    await responder(t.soporte_ok);
    return new Response("ok");
  }
  if (/^\/(terms|terminos|termos)\b/i.test(texto)) {
    await responder(t.terminos);
    return new Response("ok");
  }
  const pedidoPro = /^\/(?:pro(?:@\w+)?|start\s+pro(?:_(mensual|vitalicio))?)$/i.exec(texto);
  if (pedidoPro) { // /pro, o el botón «Pagar» de la guía de la app (t.me/<bot>?start=pro_mensual)
    const cuenta = await leerCuenta(env, chat);
    if (cuenta && cuenta.idioma !== lengua) await cuentaDe(env, chat, lengua);
    await mandarPro(env, chat, lengua, cuenta, { primero: (pedidoPro[1] || "mensual").toLowerCase() });
    return new Response("ok");
  }

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
    const plan = textoPlan(env, t, lengua, await leerCuenta(env, chat));
    await responder(t.ayuda.replace("{estado}", t.compus(lista.length)).replace("{plan}", plan));
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
  const plan = planDe(env, await cuentaDe(env, chat, lengua)); // la primera compu arranca la prueba gratis
  const lineaPlan = plan.tipo === "libre" ? ""
    : plan.tipo === "prueba" ? t.conectar_prueba(plan.dias)
    : plan.pro ? t.conectar_pro : t.conectar_vencido;
  await mandarGif(env, origen, chat, "festejo", conNombre(t.listo).replace("{plan}", lineaPlan ? lineaPlan + "\n\n" : ""));
  return new Response("ok");
}

function escapar(texto) {
  return texto.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
