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
    "Abrir al iniciar sesión": {"en": "Open at login", "pt": "Abrir ao iniciar a sessão"},  # macOS
    "Desinstalar {nombre}…": {"en": "Uninstall {nombre}…", "pt": "Desinstalar {nombre}…"},
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
    "Aviso: aparece desde el borde y se va sola. Compañera: vive sobre el Dock (arrastrala a donde quieras), "
    "crece para avisarte y se duerme si se termina el límite de uso.": {
        "en": "Notice: slides in from the edge and leaves on its own. Companion: lives on the Dock (drag it "
              "wherever you like), grows to let you know and falls asleep when you run out of usage.",
        "pt": "Aviso: aparece pela borda e vai embora sozinha. Companheira: vive sobre o Dock (arraste para onde "
              "quiser), cresce para avisar e dorme quando o limite de uso acaba."},
    "Esperar chiquita, parada sobre el Dock": {"en": "Wait small, standing on the Dock",
                                               "pt": "Esperar pequena, em pé sobre o Dock"},
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
    "Ícono en la barra de menús": {"en": "Menu bar icon", "pt": "Ícone na barra de menus"},
    "Click en el ícono de la mascota (en la barra de menús) para volver a estos ajustes, silenciar los avisos o "
    "cambiar de modo.": {
        "en": "Click the mascot icon (in the menu bar) to come back to these settings, mute notices or switch "
              "modes.",
        "pt": "Clique no ícone do mascote (na barra de menus) para voltar a estas configurações, silenciar os "
              "avisos ou mudar de modo."},
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
    "Sombra": {"en": "Shadow", "pt": "Sombra"},
    "Acero": {"en": "Steel", "pt": "Aço"},
    "Carmesí": {"en": "Crimson", "pt": "Carmesim"},
    "Bosque": {"en": "Forest", "pt": "Floresta"},
    "Noche": {"en": "Night", "pt": "Noite"},
    "de {estilo}": {"en": "for {estilo}", "pt": "do {estilo}"},
    "Cada estilo guarda su propio color: cambiar este no cambia el de los otros.": {
        "en": "Each style keeps its own color: changing this one doesn't change the others.",
        "pt": "Cada estilo guarda a própria cor: mudar esta não muda a dos outros."},
    "Estilo": {"en": "Style", "pt": "Estilo"},
    "BETA": {"en": "BETA", "pt": "BETA"},
    "Clásico": {"en": "Classic", "pt": "Clássico"},
    "Sakura": {"en": "Sakura", "pt": "Sakura"},
    "Ninja": {"en": "Ninja", "pt": "Ninja"},
    "Robot": {"en": "Robot", "pt": "Robô"},
    "Cambia la cara de la mascota y cómo aparece, festeja y se va. El vestuario se mantiene.": {
        "en": "Changes the mascot's face and how it shows up, celebrates and leaves. The outfit stays.",
        "pt": "Muda o rosto do mascote e como ele aparece, comemora e vai embora. A roupa continua."},
    "Piel": {"en": "Skin", "pt": "Pele"},
    "Clara": {"en": "Light", "pt": "Clara"},
    "Trigueña": {"en": "Tan", "pt": "Morena clara"},
    "Morena": {"en": "Brown", "pt": "Morena"},
    "Oscura": {"en": "Dark", "pt": "Escura"},
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
    "ícono en la barra de menús al iniciar sesión": {"en": "menu bar icon at login",
                                                     "pt": "ícone na barra de menus ao iniciar a sessão"},
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
    "acceso de inicio borrado": {"en": "login item removed", "pt": "item de início removido"},
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
    "No pude reemplazar {destino} ({error}). Arrastrá {nombre} a Aplicaciones desde el Finder y abrila desde "
    "ahí.": {
        "en": "Couldn't replace {destino} ({error}). Drag {nombre} to Applications in the Finder and open it from "
              "there.",
        "pt": "Não foi possível substituir {destino} ({error}). Arraste o {nombre} para Aplicativos no Finder e "
              "abra-o de lá."},
    "desde el código fuente se instala con install.sh": {"en": "from source, install it with install.sh",
                                                         "pt": "a partir do código-fonte, instale com install.sh"},
    "Sí": {"en": "Yes", "pt": "Sim"},
    "No": {"en": "No", "pt": "Não"},
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
    # --- avisos al celular (Telegram) ----------------------------------------------------
    "Te manda los avisos a Telegram, con Wave animada: te enterás aunque no estés en la compu. Te escribe el bot "
    "oficial, @WaveNotificationBot.": {
        "en": "Sends your notifications to Telegram, with Wave animated: you'll know even when you're away from the "
              "computer. They come from the official bot, @WaveNotificationBot.",
        "pt": "Manda os avisos para o Telegram, com o Wave animado: você fica sabendo mesmo longe do computador. "
              "Quem escreve é o bot oficial, @WaveNotificationBot."},
    "Conectar con Telegram": {"en": "Connect Telegram", "pt": "Conectar com o Telegram"},
    "Tu código:": {"en": "Your code:", "pt": "Seu código:"},
    "Abrir @WaveNotificationBot": {"en": "Open @WaveNotificationBot", "pt": "Abrir @WaveNotificationBot"},
    "Copiar código": {"en": "Copy code", "pt": "Copiar código"},
    "Cancelar": {"en": "Cancel", "pt": "Cancelar"},
    "Se abre Telegram con el código listo: tocá «Iniciar» y listo. También podés escribirle el código al bot. "
    "Vence en 15 minutos.": {
        "en": "Telegram opens with the code ready: tap \u201cStart\u201d and you're done. You can also type the "
              "code to the bot. It expires in 15 minutes.",
        "pt": "O Telegram abre com o código pronto: toque em \u201cIniciar\u201d e pronto. Você também pode "
              "escrever o código para o bot. Ele vence em 15 minutos."},
    "Los avisos pasan por el servidor de WaveMascot para llegar a Telegram; no se guardan. Para dejar de "
    "recibirlos: Desconectar, o mandale /stop al bot.": {
        "en": "Notifications go through the WaveMascot server to reach Telegram; they aren't stored. To stop "
              "them: Disconnect, or send /stop to the bot.",
        "pt": "Os avisos passam pelo servidor do WaveMascot para chegar ao Telegram; não são guardados. Para "
              "parar: Desconectar, ou mande /stop para o bot."},
    "✓ Conectado al Telegram de {nombre}": {"en": "✓ Connected to {nombre}'s Telegram",
                                            "pt": "✓ Conectado ao Telegram de {nombre}"},
    "✓ Conectado a Telegram": {"en": "✓ Connected to Telegram", "pt": "✓ Conectado ao Telegram"},
    "Sin conectar: tocá el botón, se abre Telegram y tocás «Iniciar».": {
        "en": "Not connected: tap the button, Telegram opens and you tap \u201cStart\u201d.",
        "pt": "Não conectado: toque no botão, o Telegram abre e você toca em \u201cIniciar\u201d."},
    "Preparando tu código…": {"en": "Getting your code…", "pt": "Preparando seu código…"},
    "El código venció. Tocá «Conectar con Telegram» para sacar otro.": {
        "en": "The code expired. Tap \u201cConnect Telegram\u201d to get a new one.",
        "pt": "O código venceu. Toque em \u201cConectar com o Telegram\u201d para gerar outro."},
    "Esperando que le mandes el código al bot…": {"en": "Waiting for you to send the code to the bot…",
                                                  "pt": "Esperando você mandar o código para o bot…"},
    "No pude conectarme con el servidor de WaveMascot ({error}). Probá de nuevo en un rato.": {
        "en": "Couldn't reach the WaveMascot server ({error}). Try again in a while.",
        "pt": "Não consegui falar com o servidor do WaveMascot ({error}). Tente de novo daqui a pouco."},
    "Telegram se desconectó (¿le mandaste /stop al bot?). Conectalo de nuevo cuando quieras.": {
        "en": "Telegram got disconnected (did you send /stop to the bot?). Connect it again whenever you want.",
        "pt": "O Telegram foi desconectado (você mandou /stop para o bot?). Conecte de novo quando quiser."},
    "¿Dejar de mandar avisos a Telegram? Podés volver a conectarlo cuando quieras.": {
        "en": "Stop sending notifications to Telegram? You can connect it again anytime.",
        "pt": "Parar de mandar avisos para o Telegram? Você pode conectar de novo quando quiser."},
    "Celular": {"en": "Phone", "pt": "Celular"},
    "Telegram": {"en": "Telegram", "pt": "Telegram"},
    "Mandarme los avisos a Telegram": {"en": "Send my notifications to Telegram", "pt": "Mandar os avisos para o Telegram"},
    "Mandar un aviso de prueba": {"en": "Send a test notification", "pt": "Mandar um aviso de teste"},
    "Desconectar": {"en": "Disconnect", "pt": "Desconectar"},
    "Cuándo": {"en": "When", "pt": "Quando"},
    "Solo si no estoy usando la compu": {"en": "Only when I'm not using the computer",
                                         "pt": "Só quando eu não estiver usando o computador"},
    "Sin tocar el mouse ni el teclado por": {"en": "No mouse or keyboard for", "pt": "Sem mexer no mouse nem no teclado por"},
    "Si estás en la compu te avisa solo la mascota, así no te llega todo dos veces. El silencio y el «no molestar» "
    "también valen para Telegram.": {
        "en": "When you're at the computer only the mascot lets you know, so you don't get everything twice. "
              "Mute and Do Not Disturb apply to Telegram too.",
        "pt": "Se você estiver no computador, só o mascote avisa, assim nada chega duas vezes. O silêncio e o "
              "\u201cnão perturbe\u201d também valem para o Telegram."},
    "Qué avisos": {"en": "Which notifications", "pt": "Quais avisos"},
    "Cuando llega al límite de uso": {"en": "When it hits the usage limit", "pt": "Quando chega ao limite de uso"},
    "Cuando hay un error de la API": {"en": "When there's an API error", "pt": "Quando há um erro da API"},
    "Con Wave animada (GIF)": {"en": "With Wave animated (GIF)", "pt": "Com o Wave animado (GIF)"},
    "✓ Mensaje enviado: mirá tu Telegram.": {"en": "✓ Message sent: check your Telegram.",
                                            "pt": "✓ Mensagem enviada: olhe o seu Telegram."},
    "No se pudo mandar ({error}).": {"en": "Couldn't send it ({error}).", "pt": "Não foi possível mandar ({error})."},
    "Mandando…": {"en": "Sending…", "pt": "Mandando…"},
    # --- versiones nuevas (actualizacion.py) -----------------------------------------------
    "¡Hay una versión nueva de WaveMascot!": {"en": "There's a new version of WaveMascot!",
                                              "pt": "Tem uma versão nova do WaveMascot!"},
    "Versión {version}": {"en": "Version {version}", "pt": "Versão {version}"},
    "Tenés la {version}": {"en": "You have {version}", "pt": "Você tem a {version}"},
    "Actualizar": {"en": "Update", "pt": "Atualizar"},
    "Ahora no": {"en": "Not now", "pt": "Agora não"},
    "Hay una versión nueva": {"en": "A new version is available", "pt": "Tem uma versão nova"},
    "⬆ Actualizar a la versión {version}…": {"en": "⬆ Update to version {version}…",
                                             "pt": "⬆ Atualizar para a versão {version}…"},
    "Actualizar ahora": {"en": "Update now", "pt": "Atualizar agora"},
    "Descargar": {"en": "Download", "pt": "Baixar"},
    "Ver novedades": {"en": "What's new", "pt": "Ver novidades"},
    "Hay una versión nueva: {version}": {"en": "A new version is out: {version}", "pt": "Tem uma versão nova: {version}"},
    "Tenés la {version}. Mirá qué trae en «Ver novedades».": {
        "en": "You have {version}. See what's in it under \u201cWhat's new\u201d.",
        "pt": "Você tem a {version}. Veja o que ela traz em \u201cVer novidades\u201d."},
    "Buscando la versión nueva…": {"en": "Looking for the new version…", "pt": "Procurando a versão nova…"},
    "Bajando la versión {version}…": {"en": "Downloading version {version}…", "pt": "Baixando a versão {version}…"},
    "{porcentaje} % · cuando termine, WaveMascot se cierra y vuelve a abrir sola.": {
        "en": "{porcentaje} % · when it's done, WaveMascot closes and reopens on its own.",
        "pt": "{porcentaje} % · quando terminar, o WaveMascot fecha e abre de novo sozinho."},
    "Instalando la versión {version}…": {"en": "Installing version {version}…", "pt": "Instalando a versão {version}…"},
    "WaveMascot se cierra y vuelve a abrir sola en unos segundos.": {
        "en": "WaveMascot will close and reopen on its own in a few seconds.",
        "pt": "O WaveMascot vai fechar e abrir de novo sozinho em alguns segundos."},
    "No se pudo actualizar": {"en": "Couldn't update", "pt": "Não foi possível atualizar"},
    "{error}. Probá de nuevo o bajala desde «Ver novedades».": {
        "en": "{error}. Try again or download it from \u201cWhat's new\u201d.",
        "pt": "{error}. Tente de novo ou baixe em \u201cVer novidades\u201d."},
    "Actualizaciones": {"en": "Updates", "pt": "Atualizações"},
    "Avisarme cuando haya una versión nueva": {"en": "Tell me when there's a new version",
                                               "pt": "Me avisar quando houver uma versão nova"},
    "Buscar ahora": {"en": "Check now", "pt": "Procurar agora"},
    "Buscando…": {"en": "Checking…", "pt": "Procurando…"},
    "Tenés la versión {version}.": {"en": "You have version {version}.", "pt": "Você tem a versão {version}."},
    "Tenés la versión {version}: es la última.": {"en": "You have version {version}: it's the latest.",
                                                   "pt": "Você tem a versão {version}: é a mais recente."},
    "Tenés la {actual}; hay una nueva: {version}.": {"en": "You have {actual}; a new one is out: {version}.",
                                                     "pt": "Você tem a {actual}; tem uma nova: {version}."},
    "Tenés la versión {version}. No pude buscar si hay una nueva ({error}).": {
        "en": "You have version {version}. Couldn't check for a new one ({error}).",
        "pt": "Você tem a versão {version}. Não consegui procurar uma nova ({error})."},
    # --- permisos desde Telegram --------------------------------------------------------------
    "Permisos": {"en": "Permissions", "pt": "Permissões"},
    "Aprobar o denegar permisos desde Telegram": {"en": "Allow or deny permissions from Telegram",
                                                  "pt": "Permitir ou negar permissões pelo Telegram"},
    "Te llega el comando completo con los botones Permitir y Denegar. Si no contestás a tiempo, queda el "
    "diálogo de siempre en la terminal. Las preguntas de Claude se contestan en la terminal.": {
        "en": "You get the full command with Allow and Deny buttons. If you don't answer in time, the usual dialog "
              "stays in the terminal. Claude's questions are answered in the terminal.",
        "pt": "Chega o comando completo com os botões Permitir e Negar. Se você não responder a tempo, fica o "
              "diálogo de sempre no terminal. As perguntas do Claude são respondidas no terminal."},
    "Permitido desde Telegram ✓": {"en": "Allowed from Telegram ✓", "pt": "Permitido pelo Telegram ✓"},
    "Denegado desde Telegram": {"en": "Denied from Telegram", "pt": "Negado pelo Telegram"},
    # --- WaveMascot Pro (guia_pro.py) -------------------------------------------------------------------
    "WaveMascot Pro: tocá para ver cómo desbloquearlo": {"en": "WaveMascot Pro: tap to see how to unlock it",
                                                         "pt": "WaveMascot Pro: toque para ver como desbloquear"},
    "Telegram es parte de WaveMascot Pro": {"en": "Telegram is part of WaveMascot Pro",
                                            "pt": "O Telegram faz parte do WaveMascot Pro"},
    "Conectalo y probalo gratis {dias} días. Todo lo demás es gratis para siempre.": {
        "en": "Connect it and try it free for {dias} days. Everything else is free forever.",
        "pt": "Conecte e teste grátis por {dias} dias. Todo o resto é grátis para sempre."},
    "{dias} días de prueba gratis": {"en": "{dias}-day free trial", "pt": "{dias} dias de teste grátis"},
    "Cómo funciona": {"en": "How it works", "pt": "Como funciona"},
    "Prueba gratis de Pro": {"en": "Pro free trial", "pt": "Teste grátis do Pro"},
    "Te queda menos de un día de prueba.": {"en": "Less than a day of trial left.",
                                            "pt": "Falta menos de um dia de teste."},
    "Te quedan {dias} días (hasta el {fecha}).": {"en": "{dias} days left (until {fecha}).",
                                                  "pt": "Faltam {dias} dias (até {fecha})."},
    "Prueba gratis · último día": {"en": "Free trial · last day", "pt": "Teste grátis · último dia"},
    "Prueba gratis · quedan {dias} días": {"en": "Free trial · {dias} days left",
                                           "pt": "Teste grátis · faltam {dias} dias"},
    "Pasarme a Pro": {"en": "Go Pro", "pt": "Virar Pro"},
    "Sos Pro": {"en": "You're Pro", "pt": "Você é Pro"},
    "Sos Pro ✓": {"en": "You're Pro ✓", "pt": "Você é Pro ✓"},
    "Mi plan": {"en": "My plan", "pt": "Meu plano"},
    "Plan mensual · se renueva el {fecha}": {"en": "Monthly plan · renews on {fecha}",
                                             "pt": "Plano mensal · renova em {fecha}"},
    "Plan mensual · termina el {fecha}": {"en": "Monthly plan · ends on {fecha}", "pt": "Plano mensal · termina em {fecha}"},
    "De regalo hasta el {fecha}": {"en": "A gift until {fecha}", "pt": "De presente até {fecha}"},
    "Sos Pro de por vida": {"en": "You're Pro for life", "pt": "Você é Pro para sempre"},
    "Pro de por vida ✓": {"en": "Pro for life ✓", "pt": "Pro vitalício ✓"},
    "Es tuyo para siempre, en todas tus compus. ¡Gracias por bancar el proyecto!": {
        "en": "It's yours forever, on all your computers. Thanks for supporting the project!",
        "pt": "É seu para sempre, em todos os seus computadores. Obrigado por apoiar o projeto!"},
    "Los avisos a Telegram están en pausa": {"en": "Telegram notifications are paused",
                                             "pt": "Os avisos pelo Telegram estão pausados"},
    "Terminó tu prueba de Pro. Activalo y vuelven al instante.": {
        "en": "Your Pro trial is over. Turn it on and they're back instantly.",
        "pt": "Seu teste do Pro terminou. Ative e eles voltam na hora."},
    "Tu prueba terminó": {"en": "Your trial is over", "pt": "Seu teste terminou"},
    "Desbloquear Pro": {"en": "Unlock Pro", "pt": "Desbloquear o Pro"},
    "Claude Code te avisa en el celular, y le das permiso desde donde estés.": {
        "en": "Claude Code notifies you on your phone, and you give it permission from wherever you are.",
        "pt": "O Claude Code te avisa no celular, e você dá permissão de onde estiver."},
    "Los tests pasan ✓": {"en": "Tests pass ✓", "pt": "Os testes passam ✓"},
    "Qué incluye": {"en": "What's included", "pt": "O que inclui"},
    "Avisos en tu celular": {"en": "Notifications on your phone", "pt": "Avisos no seu celular"},
    "Cuando Claude Code termina, necesita algo o llega al límite, te escribe Wave.": {
        "en": "When Claude Code finishes, needs something or hits the limit, Wave messages you.",
        "pt": "Quando o Claude Code termina, precisa de algo ou chega ao limite, o Wave te escreve."},
    "Permisos a distancia": {"en": "Remote permissions", "pt": "Permissões a distância"},
    "Permitir o Denegar con un toque, sin volver a la compu.": {
        "en": "Allow or Deny with one tap, without going back to the computer.",
        "pt": "Permitir ou Negar com um toque, sem voltar ao computador."},
    "Todas tus compus": {"en": "All your computers", "pt": "Todos os seus computadores"},
    "Un solo Pro para todas las compus que conectes a tu Telegram.": {
        "en": "One Pro for every computer you connect to your Telegram.",
        "pt": "Um só Pro para todos os computadores que você conectar ao seu Telegram."},
    "Bancás el open source": {"en": "You back open source", "pt": "Você apoia o open source"},
    "Mantenés el bot y el servidor, y la app sigue gratis para todos.": {
        "en": "You keep the bot and the server running, and the app stays free for everyone.",
        "pt": "Você mantém o bot e o servidor, e o app continua grátis para todos."},
    "Siempre gratis": {"en": "Always free", "pt": "Sempre grátis"},
    "La mascota, los avisos en pantalla, los estilos, el vestuario y todo lo demás. Sin cuentas ni límites.": {
        "en": "The mascot, on-screen notifications, styles, outfits and everything else. No accounts, no limits.",
        "pt": "O mascote, os avisos na tela, os estilos, o figurino e todo o resto. Sem contas nem limites."},
    "Cómo desbloquearlo": {"en": "How to unlock it", "pt": "Como desbloquear"},
    "Tu plan": {"en": "Your plan", "pt": "Seu plano"},
    "Conectá tu Telegram": {"en": "Connect your Telegram", "pt": "Conecte seu Telegram"},
    "Elegí tu plan": {"en": "Pick your plan", "pt": "Escolha seu plano"},
    "Mensual": {"en": "Monthly", "pt": "Mensal"},
    "De por vida": {"en": "Lifetime", "pt": "Vitalício"},
    "/ mes": {"en": "/ month", "pt": "/ mês"},
    "una vez": {"en": "once", "pt": "uma vez"},
    "{stars} Stars · mes a mes": {"en": "{stars} Stars · cancel anytime", "pt": "{stars} Stars · mês a mês"},
    "{stars} Stars · un solo pago": {"en": "{stars} Stars · pay once", "pt": "{stars} Stars · um só pagamento"},
    "Pagá con Telegram Stars": {"en": "Pay with Telegram Stars", "pt": "Pague com Telegram Stars"},
    "Ver mi plan en Telegram": {"en": "See my plan on Telegram", "pt": "Ver meu plano no Telegram"},
    "Listo": {"en": "Done", "pt": "Pronto"},
    "¿Por qué es pago? WaveMascot es y va a seguir siendo gratis y open source. Pro paga el bot y el servidor que "
    "llevan los avisos hasta tu celular, y te deja cancelar cuando quieras.": {
        "en": "Why is it paid? WaveMascot is and will stay free and open source. Pro pays for the bot and the server "
              "that carry notifications to your phone, and you can cancel anytime.",
        "pt": "Por que é pago? O WaveMascot é e vai continuar grátis e open source. O Pro paga o bot e o servidor "
              "que levam os avisos até o seu celular, e você cancela quando quiser."},
    "¡Ya sos Pro!": {"en": "You're Pro now!", "pt": "Agora você é Pro!"},
    "Desde el bot ves tu plan y cancelás o reactivás la renovación cuando quieras.": {
        "en": "In the bot you can see your plan and cancel or turn renewal back on anytime.",
        "pt": "No bot você vê seu plano e cancela ou reativa a renovação quando quiser."},
    "Los avisos y los permisos por Telegram ya andan en todas tus compus.": {
        "en": "Telegram notifications and permissions now work on all your computers.",
        "pt": "Os avisos e as permissões pelo Telegram já funcionam em todos os seus computadores."},
    "Conectado al Telegram de {nombre}": {"en": "Connected to {nombre}'s Telegram",
                                          "pt": "Conectado ao Telegram de {nombre}"},
    "Conectado a Telegram": {"en": "Connected to Telegram", "pt": "Conectado ao Telegram"},
    "Tocá «Iniciar» en Telegram (o mandale el código {codigo} al bot).": {
        "en": "Tap “Start” in Telegram (or send the code {codigo} to the bot).",
        "pt": "Toque em “Iniciar” no Telegram (ou mande o código {codigo} para o bot)."},
    "Se abre Telegram y tocás «Iniciar». Ahí arranca tu prueba gratis de {dias} días.": {
        "en": "Telegram opens and you tap “Start”. That starts your {dias}-day free trial.",
        "pt": "O Telegram abre e você toca em “Iniciar”. Aí começa seu teste grátis de {dias} dias."},
    "Abrir Telegram de nuevo": {"en": "Open Telegram again", "pt": "Abrir o Telegram de novo"},
    "Esperando el pago": {"en": "Waiting for the payment", "pt": "Esperando o pagamento"},
    "Cuando Telegram lo confirme, WaveMascot se da cuenta solo.": {
        "en": "As soon as Telegram confirms it, WaveMascot picks it up by itself.",
        "pt": "Quando o Telegram confirmar, o WaveMascot percebe sozinho."},
    "Abrir el pago de nuevo": {"en": "Open the payment again", "pt": "Abrir o pagamento de novo"},
    "Te abro el chat del bot con el botón de pago. Pagás desde el celular o la compu, y las Stars se compran ahí "
    "mismo.": {
        "en": "I'll open the bot's chat with the payment button. Pay from your phone or computer; you can buy Stars "
              "right there.",
        "pt": "Eu abro o chat do bot com o botão de pagamento. Você paga pelo celular ou pelo computador, e as Stars "
              "se compram ali mesmo."},
    "Pagar {precio} en Telegram": {"en": "Pay {precio} on Telegram", "pt": "Pagar {precio} no Telegram"},
    "Primero conectá tu Telegram": {"en": "Connect your Telegram first", "pt": "Primeiro conecte seu Telegram"},
    "✓ Ya sos Pro: los avisos a Telegram están activados.": {
        "en": "✓ You're Pro: Telegram notifications are on.",
        "pt": "✓ Agora você é Pro: os avisos pelo Telegram estão ativados."},
    "Disponible con WaveMascot Pro": {"en": "Available with WaveMascot Pro", "pt": "Disponível com o WaveMascot Pro"},
    "Terminó tu prueba gratis. Con Pro vuelven los avisos y los permisos desde el celular, en todas tus compus.": {
        "en": "Your free trial is over. With Pro, notifications and permissions from your phone come back, on all "
              "your computers.",
        "pt": "Seu teste grátis terminou. Com o Pro, os avisos e as permissões pelo celular voltam, em todos os seus "
              "computadores."},
    "Conectá Telegram y probalo gratis {dias} días, sin tarjeta.": {
        "en": "Connect Telegram and try it free for {dias} days, no card needed.",
        "pt": "Conecte o Telegram e teste grátis por {dias} dias, sem cartão."},
    "Probar gratis {dias} días": {"en": "Try it free for {dias} days", "pt": "Testar grátis por {dias} dias"},
    "No se mandó: terminó tu prueba de Pro y los avisos a Telegram están en pausa.": {
        "en": "Not sent: your Pro trial is over and Telegram notifications are paused.",
        "pt": "Não foi enviado: seu teste do Pro terminou e os avisos pelo Telegram estão pausados."},
}
