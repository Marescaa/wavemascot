# WaveMascot

[English](README.md) · [Español](README.es.md) · **Português**

<p align="center">
  <img src="docs/demo.gif" alt="O mascote em seus diferentes estados" width="224">
</p>

**Wave** é um mascote de área de trabalho em pixel art para Windows que avisa quando o **Claude Code** termina,
precisa da sua permissão ou fica sem uso disponível, no lugar da notificação do Windows. Ele aparece pela borda da
tela, diz de qual chat e projeto vem o aviso e vai embora sozinho.

<p align="center">
  <a href="../../releases/latest/download/WaveMascot-Setup.exe"><b>⬇ Baixar para Windows</b></a>
  &nbsp;·&nbsp; <a href="#instalação">Instalação</a>
  &nbsp;·&nbsp; <a href="../../discussions">Perguntas e ideias</a>
  &nbsp;·&nbsp; <a href="../../issues/new/choose">Relatar um problema</a>
</p>

> **Projeto não oficial.** Não é feito, endossado nem mantido pela Anthropic. Não usa logos, imagens, sons nem nenhum
> outro asset da Anthropic: o mascote, o ícone e os sons são originais e gerados por código
> (veja [THIRD_PARTY.md](THIRD_PARTY.md)).
>
> **Tudo roda no seu computador.** O mascote não se conecta à internet nem envia dados para lugar nenhum. O resumo da
> última mensagem é montado lendo localmente o transcript que o Claude Code já guarda no seu disco, e não sai dali.

## O que faz

- **Avisa quando o Claude termina** (`pronto`), **pede permissão**, está **pensando**, um **subagente** terminou,
  você chegou ao **limite de uso** ou houve um **erro**: cada estado tem sua animação e seu som.
- **Permitir / Negar pelo mascote** (hook `PermissionRequest`): responda sem ir ao terminal. Se você não escolher a
  tempo, decide o diálogo de sempre.
- **Mostra o contexto certo**: título do chat, projeto, quanto demorou e um resumo curto da resposta.
  Com **várias sessões ao mesmo tempo**, cada aviso diz de qual projeto vem e os avisos entram na fila em vez de se
  sobrepor.
- **Não incomoda**: horário de não perturbe, nada sobre aplicativos em tela cheia, nada se você já está olhando o
  terminal, duração mínima e silêncio rápido pelo ícone ao lado do relógio.
- **Modo companheira**: em vez de aparecer e sumir, fica pequena sobre a barra de tarefas, passeia um pouco e dorme
  quando o uso acaba, até ser renovado.
- **Personalizável**: cores, chapéus, roupas e acessórios, sua própria imagem (PNG/GIF), tamanho, canto, temas
  escuro/claro/destaque e um som por evento.
- **No seu idioma**: inglês, espanhol e português. Vem em inglês; mude com a bandeirinha no topo das configurações.
- **Vários monitores**: o aviso aparece no monitor onde está a janela do Claude Code.
- **Nunca atrasa o Claude Code**: o hook volta em milissegundos, nunca sai com erro e, se algo falhar (sem áudio,
  configuração quebrada, sem tela), registra no log e segue.

## Instalação

Requisitos: Windows 10 ou 11 e [Claude Code](https://docs.claude.com/en/docs/claude-code) (CLI, extensão ou app de
desktop).

### Opção A: instalador (recomendada, não precisa de Python)

1. **[Baixe o `WaveMascot-Setup.exe`](../../releases/latest/download/WaveMascot-Setup.exe)** (sempre a última
   versão; também está em [Releases](../../releases/latest)).
2. Abra e clique em **Sim**. Ele é instalado em `%LOCALAPPDATA%\Programs\WaveMascot`, sem permissões de
   administrador.
3. Pronto: na próxima vez que o Claude Code terminar, o mascote aparece. Se o Claude Code já estava aberto, não precisa
   reiniciá-lo. Para usar em português, abra as configurações e escolha a bandeirinha.

> O Windows SmartScreen pode mostrar "O Windows protegeu o computador". Escolha **Mais informações → Executar assim
> mesmo**, ou use a opção B se preferir instalar pelo código-fonte. Você pode verificar o arquivo com o
> `SHA256SUMS.txt` do release.

### Opção B: pelo código-fonte (Python 3.10 ou mais recente)

1. Baixe o código: [ZIP](../../archive/refs/heads/main.zip) (descompacte) ou
   `git clone https://github.com/Marescaa/wavemascot.git`.
2. Abra o PowerShell nessa pasta e execute:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1
   ```

O `install.ps1` instala PyQt6 e Pillow só se estiverem faltando. Opções: `-Python <caminho do python.exe>`,
`-Destination <pasta>`, `-NoStartup` (sem ícone ao iniciar o Windows).

### O que o instalador faz no seu PC

- **Copia o programa** para `%LOCALAPPDATA%\Programs\WaveMascot`.
- **Conecta o Wave ao Claude Code**: adiciona algumas linhas (os *hooks*) em `~/.claude/settings.json` para que o
  Claude Code o chame quando termina ou precisa de algo. O que você já tinha nesse arquivo não é alterado, e antes de
  mudá-lo é salva uma cópia de segurança.
- **Cria o comando `/wavemascot`**, que abre as configurações pelo Claude Code.
- **Coloca o ícone do Wave ao lado do relógio** toda vez que você liga o computador.

Não pede permissões de administrador e, se você desinstalar, tudo volta a ficar como estava.

## Configurações

Abra as configurações clicando no **ícone ao lado do relógio** ou com **`/wavemascot`** no Claude Code. As
alterações são salvas sozinhas e valem a partir do próximo aviso; a pré-visualização mostra como vai ficar. A
**bandeirinha** no canto superior direito muda o idioma.

<p align="center">
  <img src="docs/ajustes.pt.png" alt="Janela de configurações do WaveMascot: aba Roupas com a pré-visualização do aviso e a bandeirinha de idioma" width="760">
</p>

| Aba | O que dá para ajustar |
|---|---|
| Aviso | Canto, tempo na tela, o que mostrar no aviso (resumo, chat, projeto, duração) e as mensagens |
| Comportamento | Modo aviso ou companheira (passeios, animações em repouso, olhar), quais eventos avisam, não perturbe (horário, tela cheia, terminal em foco), duração mínima, Permitir/Negar pelo mascote |
| Mascote | Cor, tamanho e imagem própria |
| Roupas | Cabeça, roupa e acessórios (ou aleatório) |
| Som e estilo | Volume, som de cada evento, tema escuro / claro / destaque, ícone ao lado do relógio |

Tudo fica em `~/.wavemascot/config.json`. Se o arquivo não existir ou tiver um erro, o mascote usa os valores
padrão. Pelo ícone ao lado do relógio você também pode silenciar os avisos por uma hora ou até reativá-los.

> Para que o mascote substitua a notificação do Windows, desative as notificações do próprio Claude Code (nas
> configurações do app de desktop ou do seu terminal), assim você não recebe dois avisos.

## Desinstalação

- **Instalado com o `.exe`**: menu Iniciar → *WaveMascot* → **Desinstalar WaveMascot**.
- **Instalado com o `install.ps1`** (ou de qualquer forma):

  ```powershell
  powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
  ```

A desinstalação fecha o mascote, remove **só os hooks dele** de `~/.claude/settings.json` (com backup antes; os seus
ficam exatamente como estavam) e apaga o `/wavemascot`, os atalhos e a pasta do programa. Suas configurações em
`~/.wavemascot` são mantidas; para apagá-las também: `uninstall.ps1 -DeleteSettings`.

## Problemas frequentes

- **Não aparece**: veja `~/.wavemascot/mascota.log`; cada evento diz se avisou ou por que não (tela cheia, não
  perturbe, terminal em foco, evento desligado...). Ícone ao lado do relógio → *Testar aviso* força um.
- **Os hooks não rodam**: confira no Claude Code com `/hooks` se os do mascote estão lá.
- **Permitir/Negar**: no app de desktop o diálogo próprio continua aparecendo; vale a primeira resposta.

## Perguntas, ideias e relatos

- **Tem uma pergunta ou uma ideia?** Escreva em [Discussions](../../discussions): lá se conversa, se propõem roupas
  ou estados novos e se compartilham configurações.
- **Algo não funciona?** Abra uma [issue](../../issues/new/choose) com o modelo de erro (inclua as últimas linhas do
  log, sem dados privados).
- **Quer propor algo concreto?** Use o modelo de ideia em [issues](../../issues/new/choose).

Pode escrever em português, inglês ou espanhol. Pull requests são bem-vindos: antes de enviar um, rode os testes
(`python -m unittest discover tests`).

## Desenvolvimento

```powershell
python -m unittest discover tests          # testes do instalador (merge de hooks) e das traduções
powershell -ExecutionPolicy Bypass -File .\build.ps1   # gera dist\WaveMascot-Setup.exe
```

Ao enviar uma tag `v*` (por exemplo `v1.1.0`), o GitHub Actions gera o instalador e o anexa ao release.

| Arquivo | O que é |
|---|---|
| `mascota.py` | O hook e a janela do mascote |
| `ajustes.py` | A janela de configurações |
| `bandeja.py` | O ícone ao lado do relógio |
| `sprites.py` | O pixel art e os sons (tudo gerado por código) |
| `idiomas.py` | Os textos em inglês, espanhol e português |
| `ventanas.py` | Janelas do Windows: foco, tela cheia, monitores |
| `instalador.py` | Instalar / desinstalar (merge de hooks com backup); também é o instalador `.exe` |
| `principal.py` | Ponto de entrada do `WaveMascot.exe` |

**Adicionar um idioma**: inclua-o em `IDIOMAS` no `idiomas.py` com uma tradução por texto; o `tests/test_idiomas.py`
avisa se faltar alguma.

## Licença

[MIT](LICENSE). O `.exe` inclui PyQt6 (GPL v3) e outras bibliotecas; veja [THIRD_PARTY.md](THIRD_PARTY.md).
