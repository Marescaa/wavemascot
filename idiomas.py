"""Textos de WaveMascot en inglés, español y portugués.

Las claves son los textos en español tal como están en el código: t("Abrir ajustes") devuelve la
traducción al idioma elegido con la banderita de los ajustes (por defecto, inglés). Los campos entre
llaves se completan con t("Hola {nombre}", nombre="Wave"). Agregar un idioma: sumarlo a IDIOMAS y una
traducción por texto (tests/test_idiomas.py avisa si falta alguna).
"""

from __future__ import annotations

IDIOMAS = {"en": "English", "es": "Español", "pt": "Português"}
POR_DEFECTO = "en"
_actual = POR_DEFECTO


def usar(idioma: str | None) -> None:
    global _actual
    _actual = idioma if idioma in IDIOMAS else POR_DEFECTO


def actual() -> str:
    return _actual


def t(texto: str, **datos) -> str:
    if _actual != "es":
        texto = TEXTOS.get(texto, {}).get(_actual, texto)
    return texto.format(**datos) if datos else texto


TEXTOS: dict[str, dict[str, str]] = {
    # --- avisos de la mascota --------------------------------------------------------
    "¡Listo!": {"en": "Done!", "pt": "Pronto!"},
    "¡Listo! Terminé": {"en": "Done! All finished", "pt": "Pronto! Terminei"},
    "Necesito tu permiso": {"en": "I need your permission", "pt": "Preciso da sua permissão"},
    "Necesito permiso para usar {herramienta}": {"en": "I need permission to use {herramienta}",
                                                 "pt": "Preciso de permissão para usar {herramienta}"},
    "Tengo una pregunta para vos": {"en": "I have a question for you", "pt": "Tenho uma pergunta para você"},
    "Te estoy esperando": {"en": "I'm waiting for you", "pt": "Estou esperando você"},
    "Algo salió mal": {"en": "Something went wrong", "pt": "Algo deu errado"},
    "Pensando…": {"en": "Thinking…", "pt": "Pensando…"},
    "Terminó un subagente": {"en": "A subagent finished", "pt": "Um subagente terminou"},
    "Terminó el subagente {nombre}": {"en": "Subagent {nombre} finished", "pt": "O subagente {nombre} terminou"},
    "Llegué al límite de uso": {"en": "I hit the usage limit", "pt": "Cheguei ao limite de uso"},
    "Error de la API ({error})": {"en": "API error ({error})", "pt": "Erro da API ({error})"},
    "desconocido": {"en": "unknown", "pt": "desconhecido"},
    "¿Permitir {herramienta}?": {"en": "Allow {herramienta}?", "pt": "Permitir {herramienta}?"},
    "esta acción": {"en": "this action", "pt": "esta ação"},
    "Permitir": {"en": "Allow", "pt": "Permitir"},
    "Denegar": {"en": "Deny", "pt": "Negar"},
    "Ir a la terminal": {"en": "Go to terminal", "pt": "Ir ao terminal"},
    "Permitido ✓": {"en": "Allowed ✓", "pt": "Permitido ✓"},
    "Denegado": {"en": "Denied", "pt": "Negado"},
    "Zzz… se terminó el límite de uso": {"en": "Zzz… out of usage for now", "pt": "Zzz… o limite de uso acabou"},
    "Me despierto a las {hora}": {"en": "I'll wake up at {hora}", "pt": "Acordo às {hora}"},
    "Me despierto cuando me vuelvas a escribir": {"en": "I'll wake up when you write to me again",
                                                  "pt": "Acordo quando você me escrever de novo"},
    # menú de la compañera y del ícono junto al reloj
    "Abrir ajustes": {"en": "Open settings", "pt": "Abrir configurações"},
    "Volver a la esquina": {"en": "Back to the corner", "pt": "Voltar para o canto"},
    "Pasar a modo aviso": {"en": "Switch to notice mode", "pt": "Mudar para o modo aviso"},
    "Ocultar hasta el próximo aviso": {"en": "Hide until the next notice", "pt": "Ocultar até o próximo aviso"},
    "Probar aviso": {"en": "Test notice", "pt": "Testar aviso"},
    "Silenciar por 1 hora": {"en": "Mute for 1 hour", "pt": "Silenciar por 1 hora"},
    "Silenciar hasta que los reactive": {"en": "Mute until I turn them back on", "pt": "Silenciar até eu reativar"},
    "Reactivar avisos ({estado})": {"en": "Turn notices back on ({estado})", "pt": "Reativar avisos ({estado})"},
    "Modo compañera (fija en pantalla)": {"en": "Companion mode (stays on screen)",
                                          "pt": "Modo companheira (fica na tela)"},
    "Abrir al iniciar Windows": {"en": "Open when Windows starts", "pt": "Abrir ao iniciar o Windows"},
    "Salir": {"en": "Quit", "pt": "Sair"},
    "avisos activos": {"en": "notices on", "pt": "avisos ativos"},
    "avisos silenciados": {"en": "notices muted", "pt": "avisos silenciados"},
    "silenciada hasta las {hora}": {"en": "muted until {hora}", "pt": "silenciada até as {hora}"},
    "Prueba desde el ícono": {"en": "Test from the tray icon", "pt": "Teste pelo ícone"},
    "Prueba desde ajustes": {"en": "Test from settings", "pt": "Teste pelas configurações"},

    # --- ventana de ajustes ----------------------------------------------------------
    "Ajustes de WaveMascot": {"en": "WaveMascot settings", "pt": "Configurações do WaveMascot"},
    "Cómo y dónde te avisa cuando Claude Code termina o necesita algo": {
        "en": "How and where it lets you know when Claude Code finishes or needs something",
        "pt": "Como e onde ela avisa quando o Claude Code termina ou precisa de algo"},
    "Notificación": {"en": "Notice", "pt": "Aviso"},
    "Comportamiento": {"en": "Behavior", "pt": "Comportamento"},
    "Mascota": {"en": "Mascot", "pt": "Mascote"},
    "Vestuario": {"en": "Outfits", "pt": "Roupas"},
    "Sonido y estilo": {"en": "Sound and style", "pt": "Som e estilo"},
    "Vista previa": {"en": "Preview", "pt": "Pré-visualização"},
    "Los cambios se guardan solos": {"en": "Changes are saved automatically", "pt": "As alterações são salvas sozinhas"},
    "Guardando…": {"en": "Saving…", "pt": "Salvando…"},
    "✓ Guardado en {archivo}": {"en": "✓ Saved to {archivo}", "pt": "✓ Salvo em {archivo}"},
    "No se pudo guardar: {error}": {"en": "Couldn't save: {error}", "pt": "Não foi possível salvar: {error}"},
    "Restablecer valores": {"en": "Reset to defaults", "pt": "Restaurar padrões"},
    "Cerrar": {"en": "Close", "pt": "Fechar"},
    "Restablecer": {"en": "Reset", "pt": "Restaurar"},
    "¿Volver a los valores por defecto? Las imágenes propias quedan guardadas.": {
        "en": "Go back to the default settings? Your own images stay saved.",
        "pt": "Voltar às configurações padrão? Suas imagens continuam salvas."},
    # estados (vista previa y sonidos)
    "Listo": {"en": "Done", "pt": "Pronto"},
    "Permiso": {"en": "Permission", "pt": "Permissão"},
    "Pensando": {"en": "Thinking", "pt": "Pensando"},
    "Subagente": {"en": "Subagent", "pt": "Subagente"},
    "Límite": {"en": "Limit", "pt": "Limite"},
    "Error": {"en": "Error", "pt": "Erro"},
    # pestaña Notificación
    "Esquina de la pantalla": {"en": "Screen corner", "pt": "Canto da tela"},
    "Arriba a la derecha": {"en": "Top right", "pt": "Superior direito"},
    "Arriba a la izquierda": {"en": "Top left", "pt": "Superior esquerdo"},
    "Abajo a la derecha": {"en": "Bottom right", "pt": "Inferior direito"},
    "Abajo a la izquierda": {"en": "Bottom left", "pt": "Inferior esquerdo"},
    "Duración en pantalla": {"en": "Time on screen", "pt": "Tempo na tela"},
    "Mostrar en el cartel": {"en": "Show in the notice", "pt": "Mostrar no aviso"},
    "Resumen del último mensaje": {"en": "Summary of the last message", "pt": "Resumo da última mensagem"},
    "Duración de la tarea": {"en": "Task duration", "pt": "Duração da tarefa"},
    "Proyecto o carpeta": {"en": "Project or folder", "pt": "Projeto ou pasta"},
    "Título del chat": {"en": "Chat title", "pt": "Título do chat"},
    "Mensajes": {"en": "Messages", "pt": "Mensagens"},
    "Cuando termina (Stop)": {"en": "When it finishes (Stop)", "pt": "Quando termina (Stop)"},
    "Cuando necesita algo (Notification)": {"en": "When it needs something (Notification)",
                                            "pt": "Quando precisa de algo (Notification)"},
    "Vacío = texto automático": {"en": "Empty = automatic text", "pt": "Vazio = texto automático"},
    "Podés usar {mensaje} (el texto original del aviso, por ejemplo «Necesito permiso para usar Bash»), "
    "{proyecto} y {chat}.": {
        "en": "You can use {mensaje} (the original notice text, for example “I need permission to use Bash”), "
              "{proyecto} and {chat}.",
        "pt": "Você pode usar {mensaje} (o texto original do aviso, por exemplo “Preciso de permissão para usar "
              "Bash”), {proyecto} e {chat}."},
    "Probar aviso «{estado}»": {"en": "Test “{estado}” notice", "pt": "Testar aviso “{estado}”"},
    "Muestra el aviso real en tu pantalla, con lo guardado.": {
        "en": "Shows the real notice on your screen, with what's saved.",
        "pt": "Mostra o aviso real na sua tela, com o que está salvo."},
    # textos de ejemplo de la vista previa
    "Necesito permiso para usar Bash": {"en": "I need permission to use Bash", "pt": "Preciso de permissão para usar Bash"},
    "Error de la API": {"en": "API error", "pt": "Erro da API"},
    "Terminó el subagente Explore": {"en": "Subagent Explore finished", "pt": "O subagente Explore terminou"},
    "mi-proyecto": {"en": "my-project", "pt": "meu-projeto"},
    "Agregué la validación y los tests pasan.": {"en": "I added the validation and the tests pass.",
                                                 "pt": "Adicionei a validação e os testes passam."},
    "npm install --save-dev vitest": {"en": "npm install --save-dev vitest", "pt": "npm install --save-dev vitest"},
    "Arreglá el bug del login": {"en": "Fix the login bug", "pt": "Corrija o bug do login"},
    "Encontré 3 archivos que usan el hook.": {"en": "I found 3 files that use the hook.",
                                              "pt": "Encontrei 3 arquivos que usam o hook."},
    "Claude usage limit reached. Your limit will reset at 3pm.": {
        "en": "Claude usage limit reached. Your limit will reset at 3pm.",
        "pt": "Claude usage limit reached. Your limit will reset at 3pm."},
    "API Error: 500 Internal server error": {"en": "API Error: 500 Internal server error",
                                             "pt": "API Error: 500 Internal server error"},
    # pestaña Comportamiento
    "Modo": {"en": "Mode", "pt": "Modo"},
    "Aviso": {"en": "Notice", "pt": "Aviso"},
    "Compañera": {"en": "Companion", "pt": "Companheira"},
    "Aviso: aparece desde el borde y se va sola. Compañera: vive sobre la barra de tareas (arrastrala a donde "
    "quieras), crece para avisarte y se duerme si se termina el límite de uso.": {
        "en": "Notice: slides in from the edge and leaves on its own. Companion: lives on the taskbar (drag it "
              "wherever you like), grows to let you know and falls asleep when you run out of usage.",
        "pt": "Aviso: aparece pela borda e vai embora sozinha. Companheira: vive sobre a barra de tarefas (arraste "
              "para onde quiser), cresce para avisar e dorme quando o limite de uso acaba."},
    "Esperar chiquita, parada sobre la barra de tareas": {"en": "Wait small, standing on the taskbar",
                                                          "pt": "Esperar pequena, em pé sobre a barra de tarefas"},
    "Dar una caminatita de vez en cuando": {"en": "Go for a little walk now and then",
                                            "pt": "Dar uma voltinha de vez em quando"},
    "Animaciones de reposo al azar": {"en": "Random idle animations", "pt": "Animações aleatórias em repouso"},
    "Los ojos siguen al cursor": {"en": "Eyes follow the cursor", "pt": "Os olhos seguem o cursor"},
    "Avisar": {"en": "Notify", "pt": "Avisar"},
    "Cuando termina": {"en": "When it finishes", "pt": "Quando termina"},
    "Cuando necesita algo (permisos, preguntas)": {"en": "When it needs something (permissions, questions)",
                                                   "pt": "Quando precisa de algo (permissões, perguntas)"},
    "Mientras piensa": {"en": "While it's thinking", "pt": "Enquanto pensa"},
    "Cuando termina un subagente": {"en": "When a subagent finishes", "pt": "Quando um subagente termina"},
    "Límite de uso o error de la API": {"en": "Usage limit or API error", "pt": "Limite de uso ou erro da API"},
    "No molestar": {"en": "Do not disturb", "pt": "Não perturbe"},
    "Silenciar entre": {"en": "Mute between", "pt": "Silenciar entre"},
    "y": {"en": "and", "pt": "e"},
    "Escribí la hora o cambiala con la ruedita del mouse o las flechas": {
        "en": "Type the time or change it with the mouse wheel or the arrow keys",
        "pt": "Digite a hora ou mude com a rodinha do mouse ou as setas"},
    "Silenciar si hay algo en pantalla completa (juegos, videos, presentaciones)": {
        "en": "Mute when something is full screen (games, videos, presentations)",
        "pt": "Silenciar se algo estiver em tela cheia (jogos, vídeos, apresentações)"},
    "No avisar si la terminal o el editor de Claude ya tiene el foco": {
        "en": "Don't notify if Claude's terminal or editor already has focus",
        "pt": "Não avisar se o terminal ou o editor do Claude já estiver em foco"},
    "Avisar «terminó» solo si la tarea duró más de": {"en": "Only notify “done” if the task took longer than",
                                                      "pt": "Só avisar “terminou” se a tarefa durou mais de"},
    "Siempre": {"en": "Always", "pt": "Sempre"},
    "Acciones": {"en": "Actions", "pt": "Ações"},
    "Aprobar o denegar permisos desde la mascota": {"en": "Approve or deny permissions from the mascot",
                                                    "pt": "Aprovar ou negar permissões pelo mascote"},
    "Esperar mi respuesta": {"en": "Wait for my answer", "pt": "Esperar minha resposta"},
    "Si no elegís a tiempo, decide el diálogo de permisos de siempre. Las preguntas (AskUserQuestion) se "
    "contestan en la terminal.": {
        "en": "If you don't choose in time, the usual permission dialog decides. Questions (AskUserQuestion) are "
              "answered in the terminal.",
        "pt": "Se você não escolher a tempo, decide o diálogo de permissões de sempre. As perguntas "
              "(AskUserQuestion) são respondidas no terminal."},
    "Botón «Ir a la terminal» en el cartel": {"en": "“Go to terminal” button in the notice",
                                              "pt": "Botão “Ir ao terminal” no aviso"},
    # pestaña Sonido y estilo
    "Sonido": {"en": "Sound", "pt": "Som"},
    "Activado": {"en": "On", "pt": "Ligado"},
    "Desactivado": {"en": "Off", "pt": "Desligado"},
    "Volumen": {"en": "Volume", "pt": "Volume"},
    "Sonido de cada evento": {"en": "Sound for each event", "pt": "Som de cada evento"},
    "Sin sonido": {"en": "No sound", "pt": "Sem som"},
    "Escuchar": {"en": "Listen", "pt": "Ouvir"},
    "Arpegio": {"en": "Arpeggio", "pt": "Arpejo"},
    "Doble tono": {"en": "Double tone", "pt": "Tom duplo"},
    "Pop": {"en": "Pop", "pt": "Pop"},
    "Campanita": {"en": "Little bell", "pt": "Sininho"},
    "Burbujas": {"en": "Bubbles", "pt": "Bolhas"},
    "Suave": {"en": "Soft", "pt": "Suave"},
    "Triste": {"en": "Sad", "pt": "Triste"},
    "Grave": {"en": "Low", "pt": "Grave"},
    "Tema": {"en": "Theme", "pt": "Tema"},
    "Oscuro": {"en": "Dark", "pt": "Escuro"},
    "Claro": {"en": "Light", "pt": "Claro"},
    "Acento": {"en": "Accent", "pt": "Destaque"},
    "El cartel del aviso y esta ventana. Acento pinta el cartel con el color de cada estado.": {
        "en": "The notice and this window. Accent paints the notice with each state's color.",
        "pt": "O aviso e esta janela. Destaque pinta o aviso com a cor de cada estado."},
    "Ícono junto al reloj": {"en": "Tray icon", "pt": "Ícone ao lado do relógio"},
    "Click en el ícono de la mascota (junto al reloj) para volver a estos ajustes; click derecho para silenciar "
    "o cambiar de modo.": {
        "en": "Click the mascot icon (next to the clock) to come back to these settings; right-click to mute or "
              "switch modes.",
        "pt": "Clique no ícone do mascote (ao lado do relógio) para voltar a estas configurações; clique com o botão "
              "direito para silenciar ou mudar de modo."},
    "No se pudo crear el acceso directo de inicio": {"en": "Couldn't create the startup shortcut",
                                                     "pt": "Não foi possível criar o atalho de inicialização"},
    # pestaña Mascota
    "Color": {"en": "Color", "pt": "Cor"},
    "Terracota": {"en": "Terracotta", "pt": "Terracota"},
    "Menta": {"en": "Mint", "pt": "Menta"},
    "Lavanda": {"en": "Lavender", "pt": "Lavanda"},
    "Naranja": {"en": "Orange", "pt": "Laranja"},
    "Rosa": {"en": "Pink", "pt": "Rosa"},
    "Celeste": {"en": "Sky blue", "pt": "Azul-celeste"},
    "Amarillo": {"en": "Yellow", "pt": "Amarelo"},
    "Grafito": {"en": "Graphite", "pt": "Grafite"},
    "Tamaño": {"en": "Size", "pt": "Tamanho"},
    "Chica": {"en": "Small", "pt": "Pequena"},
    "Mediana": {"en": "Medium", "pt": "Média"},
    "Grande": {"en": "Large", "pt": "Grande"},
    "Enorme": {"en": "Huge", "pt": "Enorme"},
    "Imagen propia": {"en": "Your own image", "pt": "Imagem própria"},
    "Mascota dibujada": {"en": "Drawn mascot", "pt": "Mascote desenhado"},
    "Agregar PNG/GIF…": {"en": "Add PNG/GIF…", "pt": "Adicionar PNG/GIF…"},
    "Quitar": {"en": "Remove", "pt": "Remover"},
    "Una imagen propia reemplaza a la mascota dibujada en los tres estados (los GIF animados también andan). "
    "Se guarda una copia en ~/.wavemascot/imagenes.": {
        "en": "Your own image replaces the drawn mascot in every state (animated GIFs work too). A copy is saved in "
              "~/.wavemascot/imagenes.",
        "pt": "Uma imagem própria substitui o mascote desenhado em todos os estados (GIFs animados também "
              "funcionam). Uma cópia é salva em ~/.wavemascot/imagenes."},
    "Elegí una imagen para la mascota": {"en": "Choose an image for the mascot", "pt": "Escolha uma imagem para o mascote"},
    "Imágenes": {"en": "Images", "pt": "Imagens"},
    "Imagen no válida": {"en": "Invalid image", "pt": "Imagem inválida"},
    "No pude leer esa imagen. Probá con un PNG o GIF de menos de 20 MB.": {
        "en": "I couldn't read that image. Try a PNG or GIF under 20 MB.",
        "pt": "Não consegui ler essa imagem. Tente um PNG ou GIF com menos de 20 MB."},
    "Quitar imagen": {"en": "Remove image", "pt": "Remover imagem"},
    "¿Quitar «{nombre}»? Tu archivo original no se toca.": {
        "en": "Remove “{nombre}”? Your original file is not touched.",
        "pt": "Remover “{nombre}”? Seu arquivo original não é alterado."},
    # pestaña Vestuario
    "Cabeza": {"en": "Head", "pt": "Cabeça"},
    "Ropa": {"en": "Clothes", "pt": "Roupa"},
    "Accesorio": {"en": "Accessory", "pt": "Acessório"},
    "Chispa": {"en": "Sparkle", "pt": "Brilho"},
    "Brote": {"en": "Sprout", "pt": "Broto"},
    "Luna": {"en": "Moon", "pt": "Lua"},
    "Orejas": {"en": "Ears", "pt": "Orelhas"},
    "Gorro": {"en": "Beanie", "pt": "Gorro"},
    "Galera": {"en": "Top hat", "pt": "Cartola"},
    "Corona": {"en": "Crown", "pt": "Coroa"},
    "Gorra": {"en": "Cap", "pt": "Boné"},
    "Nada": {"en": "None", "pt": "Nada"},
    "Remera": {"en": "T-shirt", "pt": "Camiseta"},
    "Bufanda": {"en": "Scarf", "pt": "Cachecol"},
    "Moño": {"en": "Bow tie", "pt": "Gravata-borboleta"},
    "Corbata": {"en": "Tie", "pt": "Gravata"},
    "Capa": {"en": "Cape", "pt": "Capa"},
    "Anteojos": {"en": "Glasses", "pt": "Óculos"},
    "Lentes de sol": {"en": "Sunglasses", "pt": "Óculos de sol"},
    "Auriculares": {"en": "Headphones", "pt": "Fones"},
    "Flor": {"en": "Flower", "pt": "Flor"},
    "Estás usando una imagen propia: elegí cualquier prenda o color para volver a la mascota dibujada.": {
        "en": "You're using your own image: pick any outfit or color to go back to the drawn mascot.",
        "pt": "Você está usando uma imagem própria: escolha qualquer roupa ou cor para voltar ao mascote desenhado."},
    "Al azar": {"en": "Random", "pt": "Aleatório"},
    "Sacar todo": {"en": "Remove all", "pt": "Tirar tudo"},

    # --- instalador ------------------------------------------------------------------
    "Abre los ajustes de {nombre}": {"en": "Opens the {nombre} settings", "pt": "Abre as configurações do {nombre}"},
    "Ajustes de {nombre}": {"en": "{nombre} settings", "pt": "Configurações do {nombre}"},
    "Desinstalar {nombre}": {"en": "Uninstall {nombre}", "pt": "Desinstalar {nombre}"},
    "{nombre} (ícono junto al reloj)": {"en": "{nombre} (tray icon)", "pt": "{nombre} (ícone ao lado do relógio)"},
    "{nombre} {version} ({tipo}) en {destino}": {"en": "{nombre} {version} ({tipo}) in {destino}",
                                                 "pt": "{nombre} {version} ({tipo}) em {destino}"},
    "ejecutable": {"en": "executable", "pt": "executável"},
    "código fuente": {"en": "source code", "pt": "código-fonte"},
    "hooks agregados a {ruta} (backup: {copia})": {"en": "hooks added to {ruta} (backup: {copia})",
                                                   "pt": "hooks adicionados a {ruta} (backup: {copia})"},
    "hooks agregados a {ruta} (archivo nuevo)": {"en": "hooks added to {ruta} (new file)",
                                                 "pt": "hooks adicionados a {ruta} (arquivo novo)"},
    "reemplazados los hooks de una versión anterior de la mascota ({eventos}); vuelven a su lugar si "
    "desinstalás": {
        "en": "replaced the hooks from an earlier version of the mascot ({eventos}); they come back if you uninstall",
        "pt": "substituídos os hooks de uma versão anterior do mascote ({eventos}); eles voltam se você desinstalar"},
    "comando /wavemascot: {ruta}": {"en": "/wavemascot command: {ruta}", "pt": "comando /wavemascot: {ruta}"},
    "ya existe un /wavemascot tuyo en {ruta}: no lo toco": {
        "en": "you already have your own /wavemascot in {ruta}: leaving it alone",
        "pt": "você já tem um /wavemascot seu em {ruta}: não vou mexer nele"},
    "ícono junto al reloj al iniciar Windows": {"en": "tray icon when Windows starts",
                                                "pt": "ícone ao lado do relógio ao iniciar o Windows"},
    "accesos en el menú Inicio: {carpeta}": {"en": "Start menu shortcuts: {carpeta}",
                                             "pt": "atalhos no menu Iniciar: {carpeta}"},
    "desinstalando {nombre} de {destino}": {"en": "uninstalling {nombre} from {destino}",
                                            "pt": "desinstalando {nombre} de {destino}"},
    "{ruta} borrado (lo había creado el instalador; backup: {copia})": {
        "en": "{ruta} deleted (the installer had created it; backup: {copia})",
        "pt": "{ruta} apagado (o instalador o tinha criado; backup: {copia})"},
    "hooks de la mascota quitados de {ruta} (backup: {copia})": {
        "en": "mascot hooks removed from {ruta} (backup: {copia})",
        "pt": "hooks do mascote removidos de {ruta} (backup: {copia})"},
    "comando /wavemascot borrado": {"en": "/wavemascot command deleted", "pt": "comando /wavemascot apagado"},
    "repuesto el acceso directo que había antes: {nombre}": {"en": "restored the shortcut that was there before: {nombre}",
                                                             "pt": "restaurado o atalho que existia antes: {nombre}"},
    "accesos directos borrados": {"en": "shortcuts deleted", "pt": "atalhos apagados"},
    "configuración borrada (~/.wavemascot)": {"en": "settings deleted (~/.wavemascot)",
                                              "pt": "configurações apagadas (~/.wavemascot)"},
    "tu configuración queda en ~/.wavemascot (borrala a mano si no la querés)": {
        "en": "your settings stay in ~/.wavemascot (delete it by hand if you don't want them)",
        "pt": "suas configurações ficam em ~/.wavemascot (apague manualmente se não quiser)"},
    "la carpeta {destino} no la creó el instalador: no la borro": {
        "en": "the installer didn't create {destino}: not deleting it",
        "pt": "a pasta {destino} não foi criada pelo instalador: não vou apagá-la"},
    "la carpeta {destino} se borra en unos segundos": {"en": "{destino} will be deleted in a few seconds",
                                                       "pt": "a pasta {destino} será apagada em alguns segundos"},
    "carpeta {destino} borrada": {"en": "{destino} deleted", "pt": "pasta {destino} apagada"},
    "al instalador le falta app.zip (se arma con build.ps1)": {
        "en": "the installer is missing app.zip (it's built with build.ps1)",
        "pt": "falta o app.zip no instalador (ele é gerado com build.ps1)"},
    "{ruta} no es JSON válido ({error}); no lo modifico. Arreglalo y volvé a probar.": {
        "en": "{ruta} is not valid JSON ({error}); not changing it. Fix it and try again.",
        "pt": "{ruta} não é um JSON válido ({error}); não vou alterá-lo. Corrija e tente de novo."},
    "{ruta} no tiene el formato esperado (un objeto JSON); no lo modifico.": {
        "en": "{ruta} doesn't have the expected format (a JSON object); not changing it.",
        "pt": "{ruta} não tem o formato esperado (um objeto JSON); não vou alterá-lo."},
    "¿Desinstalar {nombre}?\n\nSe quitan solo sus hooks de ~/.claude/settings.json (con backup); los tuyos "
    "quedan como estaban.": {
        "en": "Uninstall {nombre}?\n\nOnly its hooks are removed from ~/.claude/settings.json (with a backup); "
              "yours stay as they were.",
        "pt": "Desinstalar o {nombre}?\n\nSó os hooks dele são removidos de ~/.claude/settings.json (com backup); "
              "os seus ficam como estavam."},
    "¿Instalar {nombre} {version}?\n\nSe instala en {destino} y se agregan sus hooks a ~/.claude/settings.json "
    "sin tocar los que ya tengas (antes se guarda un backup).": {
        "en": "Install {nombre} {version}?\n\nIt goes into {destino} and its hooks are added to "
              "~/.claude/settings.json without touching the ones you already have (a backup is saved first).",
        "pt": "Instalar o {nombre} {version}?\n\nEle é instalado em {destino} e os hooks dele são adicionados a "
              "~/.claude/settings.json sem mexer nos que você já tem (antes é salvo um backup)."},
    "No se pudo completar:\n\n{error}": {"en": "Couldn't finish:\n\n{error}", "pt": "Não foi possível concluir:\n\n{error}"},
    "Listo.": {"en": "Done.", "pt": "Pronto."},
}
