# WaveMascot

[English](README.md) · [Español](README.es.md) · **Português**

<p align="center">
  <img src="docs/capturas/pt/aviso-listo.gif" alt="Wave comemorando acima de um aviso: Pronto! Terminei" width="300">
</p>

**Wave** é um mascote de desktop em pixel art para Windows e macOS que avisa quando o **Claude Code** termina,
precisa da sua permissão ou fica sem uso disponível, no lugar da notificação do sistema. Ele aparece pela borda da
tela, diz de qual chat e projeto vem o aviso e vai embora sozinho. Se você não estiver no computador, ele também pode
mandar mensagem no seu celular pelo Telegram, e de lá você pode **permitir ou negar** o que o Claude pede.

<p align="center">
  <a href="../../releases/latest/download/WaveMascot-Setup.exe"><b>⬇ Baixar para Windows</b></a>
  &nbsp;·&nbsp; <a href="../../releases/latest/download/WaveMascot-Mac-AppleSilicon.dmg"><b>⬇ Mac (chip Apple)</b></a>
  &nbsp;·&nbsp; <a href="../../releases/latest/download/WaveMascot-Mac-Intel.dmg"><b>⬇ Mac (Intel)</b></a>
  <br>
  <a href="#veja-em-ação">Veja em ação</a>
  &nbsp;·&nbsp; <a href="#instalação">Instalação</a>
  &nbsp;·&nbsp; <a href="../../discussions">Perguntas e ideias</a>
  &nbsp;·&nbsp; <a href="../../issues/new/choose">Relatar um problema</a>
</p>

> **Projeto não oficial.** Não é feito, endossado nem mantido pela Anthropic. Não usa logos, imagens, sons nem
> nenhum outro asset da Anthropic: o mascote, o ícone e os sons são originais e gerados por código
> (veja [THIRD_PARTY.md](THIRD_PARTY.md)).
>
> **Seus dados ficam no seu computador.** O resumo da última mensagem é montado lendo localmente o transcript que o
> Claude Code já guarda no seu disco. O WaveMascot só se conecta à internet para duas coisas, e dá para desligar as
> duas: procurar no GitHub se há uma versão nova (no máximo uma vez por dia) e, **só se você conectar o Telegram**,
> mandar o aviso para o seu celular (veja [Avisos no celular](#avisos-no-celular-telegram)).

## Veja em ação

### Um aviso para cada momento

Cada estado tem sua animação, seu som e seus botões. Com várias sessões ao mesmo tempo, os avisos entram na fila e
cada um diz de qual projeto vem.

<table>
  <tr>
    <td align="center"><img src="docs/capturas/pt/aviso-listo.gif" width="260" alt="Aviso de pronto"><br><b>Pronto</b><br>quanto demorou e um resumo</td>
    <td align="center"><img src="docs/capturas/pt/aviso-permiso.gif" width="260" alt="Aviso de permissão com Permitir e Negar"><br><b>Precisa de permissão</b><br>permita ou negue ali mesmo</td>
    <td align="center"><img src="docs/capturas/pt/aviso-pensando.gif" width="260" alt="Aviso de pensando"><br><b>Pensando</b><br>o Claude está trabalhando</td>
  </tr>
  <tr>
    <td align="center"><img src="docs/capturas/pt/aviso-subagente.gif" width="260" alt="Aviso de subagente"><br><b>Subagente</b><br>um ajudante terminou a parte dele</td>
    <td align="center"><img src="docs/capturas/pt/aviso-limite.gif" width="260" alt="Aviso de limite de uso"><br><b>Limite de uso</b><br>e quando ele renova</td>
    <td align="center"><img src="docs/capturas/pt/aviso-error.gif" width="260" alt="Aviso de erro da API"><br><b>Erro</b><br>quando a API falha</td>
  </tr>
</table>

### Quatro estilos (beta)

O estilo muda o rosto do Wave e como ele aparece, comemora e vai embora.

<p align="center">
  <img src="docs/estilos.gif" alt="Os quatro estilos comemorando: Clássico, Sakura, Ninja e Robô" width="760">
</p>

<table>
  <tr>
    <td align="center"><img src="docs/estilos/clasico.gif" width="300" alt="Clássico entra, comemora e vai embora"><br><b>Clássico</b><br>desliza pela borda</td>
    <td align="center"><img src="docs/estilos/sakura.gif" width="300" alt="Sakura chega flutuando entre pétalas"><br><b>Sakura</b><br>chega flutuando numa rajada de pétalas</td>
  </tr>
  <tr>
    <td align="center"><img src="docs/estilos/ninja.gif" width="300" alt="Ninja chega rolando numa nuvem de fumaça"><br><b>Ninja</b><br>chega escondido na fumaça e joga um shuriken</td>
    <td align="center"><img src="docs/estilos/robot.gif" width="300" alt="Robô chega voando com botas-foguete"><br><b>Robô</b><br>chega voando com botas-foguete e liga</td>
  </tr>
</table>

### Vista do seu jeito

Cores, chapéus, roupas e acessórios (ou seu próprio PNG/GIF), e combinam com todos os estilos.

<p align="center">
  <img src="docs/vestuario.gif" alt="Seis combinações de roupas" width="760">
</p>

### No seu celular

<p align="center">
  <img src="docs/capturas/pt/telegram.gif" alt="Ilustração do chat do Telegram: um aviso com o Wave animado e um pedido de permissão aprovado com o botão Permitir" width="320">
  <br><sub>Ilustração do chat com o @WaveNotificationBot (o visual do Telegram é recriado; o GIF e os textos são os reais).</sub>
</p>

### As configurações

<p align="center">
  <img src="docs/capturas/pt/ajustes-3-mascota.png" alt="Janela de configurações, aba Mascote: os quatro estilos, as cores e a pré-visualização" width="760">
</p>

<details>
<summary><b>Ver todas as abas</b></summary>

| | |
|---|---|
| <img src="docs/capturas/pt/ajustes-1-aviso.png" alt="Aba Aviso" width="380"><br>**Aviso** | <img src="docs/capturas/pt/ajustes-2-comportamiento.png" alt="Aba Comportamento" width="380"><br>**Comportamento** |
| <img src="docs/capturas/pt/ajustes-3-mascota.png" alt="Aba Mascote" width="380"><br>**Mascote** | <img src="docs/capturas/pt/ajustes-4-vestuario.png" alt="Aba Roupas" width="380"><br>**Roupas** |
| <img src="docs/capturas/pt/ajustes-5-sonido.png" alt="Aba Som e estilo" width="380"><br>**Som e estilo** | <img src="docs/capturas/pt/ajustes-6-celular.png" alt="Aba Celular" width="380"><br>**Celular** |

</details>

Todas as imagens saem do próprio app com [`tools/capturas.py`](tools/capturas.py); há mais em [`docs/`](docs).

## O que faz

- **Avisa quando o Claude termina** (`pronto`), **pede permissão**, está **pensando**, um **subagente** terminou,
  você chegou ao **limite de uso** ou houve um **erro**: cada estado tem sua animação e seu som.
- **Permitir / Negar pelo mascote** (hook `PermissionRequest`): responda sem ir ao terminal. Se você não escolher a
  tempo, decide o diálogo de sempre.
- **Avisos no celular** pelo Telegram, com o Wave animado, e **Permitir / Negar por lá** quando você não está.
- **Mostra o contexto certo**: título do chat, projeto, quanto demorou e um resumo curto da resposta.
  Com **várias sessões ao mesmo tempo**, cada aviso diz de qual projeto vem e os avisos entram na fila em vez de se
  sobrepor.
- **Não atrapalha**: horário de não perturbe, nada em tela cheia, nada se você já está olhando o terminal, duração
  mínima e silêncio rápido pelo ícone (ao lado do relógio no Windows, na barra de menus no Mac).
- **Modo companheira**: em vez de aparecer e sumir, fica pequena sobre a barra de tarefas (ou o Dock), passeia um
  pouco e dorme quando seu uso acaba, até renovar.
- **Personalizável**: quatro estilos (Clássico, Sakura, Ninja, Robô), cores, chapéus, roupas e acessórios, sua
  própria imagem (PNG/GIF), tamanho, canto, temas escuro/claro/destaque e um som por evento.
- **Avisa quando há uma versão nova**: no Windows ele se atualiza com um clique e mantém suas configurações.
- **No seu idioma**: inglês, espanhol e português. Vem em inglês; troque pela bandeirinha no alto das configurações.
- **Vários monitores**: o aviso aparece no monitor onde está a janela do Claude Code.
- **Nunca deixa o Claude Code lento**: o hook volta em milissegundos, nunca sai com erro e, se algo falha (sem áudio,
  configuração quebrada, sem tela, sem internet), anota no log e segue.

## Instalação

Você precisa do [Claude Code](https://docs.claude.com/en/docs/claude-code) (CLI, extensão ou app de desktop) e do
Windows 10 ou 11, ou do macOS 13 (Ventura) ou mais recente.

### Windows

#### Opção A: instalador (recomendada, não precisa de Python)

1. **[Baixe o `WaveMascot-Setup.exe`](../../releases/latest/download/WaveMascot-Setup.exe)** (sempre a última
   versão; também está em [Releases](../../releases/latest)).
2. Abra e clique em **Sim**. Ele é instalado em `%LOCALAPPDATA%\Programs\WaveMascot`, sem permissões de
   administrador.
3. Pronto: na próxima vez que o Claude Code terminar, o mascote aparece. Se o Claude Code já estava aberto, não precisa
   reiniciá-lo. Para usar em português, abra as configurações e escolha a bandeirinha.

> O Windows SmartScreen pode mostrar "O Windows protegeu o computador". Escolha **Mais informações → Executar assim
> mesmo**, ou use a opção B se preferir instalar pelo código-fonte. Você pode verificar o arquivo com o
> `SHA256SUMS.txt` do release.

#### Opção B: pelo código-fonte (Python 3.10 ou mais recente)

1. Baixe o código: [ZIP](../../archive/refs/heads/main.zip) (descompacte) ou
   `git clone https://github.com/Marescaa/wavemascot.git`.
2. Abra o PowerShell nessa pasta e execute:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install.ps1
   ```

O `install.ps1` instala PyQt6 e Pillow só se estiverem faltando. Opções: `-Python <caminho do python.exe>`,
`-Destination <pasta>`, `-NoStartup` (sem ícone ao iniciar o Windows).

### Mac

#### Opção A: o app (recomendada, não precisa de Python)

Você precisa do macOS 13 (Ventura) ou mais recente, em qualquer Mac.

1. **Baixe o arquivo do seu Mac.** Para saber qual: menu Apple → **Sobre Este Mac**.
   - Diz **Chip: Apple M1, M2, M3, M4…** → **[`WaveMascot-Mac-AppleSilicon.dmg`](../../releases/latest/download/WaveMascot-Mac-AppleSilicon.dmg)**
   - Diz **Processador: Intel** → **[`WaveMascot-Mac-Intel.dmg`](../../releases/latest/download/WaveMascot-Mac-Intel.dmg)**
2. **Abra o `.dmg`** (clique duas vezes em Downloads). Abre uma janela com o WaveMascot e a pasta Aplicativos:
   **arraste o WaveMascot para Aplicativos**. Depois você pode ejetar o disco WaveMascot na barra lateral do Finder.
3. **Abra o WaveMascot** em Aplicativos (ou pelo Spotlight: <kbd>⌘</kbd> <kbd>Espaço</kbd> e digite *WaveMascot*).
   Na primeira vez o macOS o bloqueia porque o app não é notarizado pela Apple (isso exige uma conta paga de
   desenvolvedor):
   - **macOS 15 (Sequoia) ou mais recente**: aparece *"A Apple não pôde verificar se o 'WaveMascot' está livre de
     malware…"*. Clique em **OK**, abra **Ajustes do Sistema → Privacidade e Segurança**, role até **Segurança** e
     clique em **Abrir Mesmo Assim** ao lado de *"O 'WaveMascot' foi bloqueado…"*. Confirme com **Abrir Mesmo Assim**
     e sua senha ou Touch ID.
   - **macOS 13 ou 14**: clique com o botão direito (ou <kbd>Control</kbd> + clique) no WaveMascot em Aplicativos →
     **Abrir**, e **Abrir** de novo.

   Só é preciso uma vez; as atualizações e os hooks não pedem de novo.
4. O WaveMascot pergunta **"Instalar o WaveMascot?"**: clique em **Sim**. Ele se conecta ao Claude Code e conta
   o que fez.
5. Pronto: o ícone do Wave aparece na **barra de menus** (no canto superior direito). Clique nele → **Testar aviso**
   para vê-lo. A partir de agora ele aparece sempre que o Claude Code termina ou precisa de algo, no terminal, no
   VS Code ou no app do Claude. Se o Claude Code já estava aberto, não precisa reiniciá-lo. Para usar em português,
   abra as configurações e escolha a bandeirinha.

Bom saber:

- **Não pede nenhuma permissão** (nem Acessibilidade, nem Gravação de Tela, nem notificações).
- Se você abri-lo direto do `.dmg` sem arrastar, ele se copia sozinho para Aplicativos.
- **Configurações**: ícone da barra de menus → **Abrir configurações**, `/wavemascot` no Claude Code, ou abrindo o
  WaveMascot de novo em Aplicativos.
- **Atualizar**: baixe o `.dmg` novo, arraste o WaveMascot para Aplicativos (**Substituir**) e abra-o uma vez.
- Na primeira vez o macOS mostra *"Itens em Segundo Plano Adicionados"*: é o ícone da barra de menus que abre ao
  iniciar a sessão. Dá para desligar nas configurações do WaveMascot ou em **Ajustes do Sistema → Geral → Itens de
  Início**.
- Para verificar o download: `shasum -a 256 ~/Downloads/WaveMascot-Mac-*.dmg` deve coincidir com o
  `SHA256SUMS.txt` do release.

#### Opção B: pelo código-fonte (Python 3.10 ou mais recente)

```bash
git clone https://github.com/Marescaa/wavemascot.git
cd wavemascot
./install.sh
```

O `install.sh` cria um ambiente Python próprio com PyQt6 e Pillow (o seu Python não é alterado). Opções:
`--python <caminho do python3>`, `--destination <pasta>`, `--no-startup` (sem ícone na barra de menus ao iniciar a
sessão).

### O que o instalador faz no seu computador

- **Copia o programa** para `%LOCALAPPDATA%\Programs\WaveMascot` (Windows) ou deixa o app em **Aplicativos** (Mac;
  se você abri-lo direto do `.dmg`, ele se copia para lá sozinho).
- **Conecta o Wave ao Claude Code**: adiciona algumas linhas (os *hooks*) em `~/.claude/settings.json` para que o
  Claude Code o chame quando termina ou precisa de algo. O que você já tinha nesse arquivo não é alterado, e antes de
  mudá-lo é salva uma cópia de segurança.
- **Cria o comando `/wavemascot`**, que abre as configurações pelo Claude Code.
- **Coloca o ícone do Wave ao lado do relógio** (Windows) ou **na barra de menus** (Mac, como item de início) toda vez
  que você liga o computador.

Não pede permissões de administrador e, se você desinstalar, tudo volta a ficar como estava.

## Configurações

Abra as configurações clicando no **ícone do Wave** (ao lado do relógio no Windows, na barra de menus no Mac), com
**`/wavemascot`** no Claude Code ou, no Mac, abrindo o WaveMascot em Aplicativos. As mudanças são salvas sozinhas e
valem a partir do próximo aviso; a pré-visualização mostra o aviso completo do jeito que vai aparecer. A
**bandeirinha** no canto superior direito troca o idioma.

| Aba | O que você muda |
|---|---|
| Aviso | Canto, tempo na tela, o que mostrar no aviso (resumo, chat, projeto, duração) e as mensagens |
| Comportamento | Modo aviso ou companheira (passeios, animações de espera, olhos), quais eventos avisam, não perturbe (horário, tela cheia, terminal em foco), duração mínima, Permitir/Negar pelo mascote |
| Mascote | Estilo (Clássico, Sakura, Ninja, Robô), cor, tom de pele (Ninja), tamanho e sua própria imagem |
| Roupas | Cabeça, roupas e acessórios (ou aleatório) |
| Som e estilo | Volume, som de cada evento, tema escuro / claro / destaque, ícone ao lado do relógio / na barra de menus, aviso de atualizações |
| Celular | Conectar o Telegram, quando mandar (só se você não estiver), quais avisos, com ou sem GIF, Permitir/Negar pelo Telegram |

Tudo fica em `~/.wavemascot/config.json`. Se o arquivo não existe ou tem um erro, o mascote usa os valores padrão.
Pelo ícone do Wave você também pode silenciar os avisos por uma hora ou até reativá-los.

> Para o mascote substituir a notificação do sistema, desligue as notificações do próprio Claude Code (nas
> configurações do app de desktop ou do seu terminal), assim você não recebe dois avisos.

### Avisos no celular (Telegram)

1. Nas configurações, abra a aba **Celular** e toque em **Conectar com o Telegram**.
2. O Telegram abre o chat com o bot oficial, **@WaveNotificationBot**, com um código de uso único. Toque em
   **Começar**. Pronto: não há nada para criar nem colar.

Por padrão ele só manda o aviso quando faz 3 minutos que você não mexe no computador (nem mouse nem teclado), assim
nada chega duas vezes; o silêncio e o não perturbe também valem. Quando o Claude pede permissão, a mensagem mostra o
comando completo com **Permitir** e **Negar**: vale o que responder primeiro (o celular, os botões do Wave ou o
terminal) e o outro lado se atualiza sozinho.

**Privacidade**: a chave do bot fica só num pequeno [Worker da Cloudflare](servidor/) que repassa cada mensagem ao
Telegram sem guardá-la. Cada instalação tem sua própria chave, que só pode escrever para o chat que vinculou. O que é
enviado é o que o aviso mostra (mensagem, resumo, projeto, título do chat, comando a aprovar). Mande `/stop` ao bot
ou toque em **Desconectar** para parar.

### Atualizações

O WaveMascot consulta o GitHub no máximo uma vez por dia. Quando há uma versão nova, o Wave avisa uma vez
(**Atualizar** / **Agora não**), aparece uma etiqueta «⬇ versão» ao lado da bandeirinha das configurações e o menu do
ícone oferece **Atualizar para a versão…**. No Windows, **Atualizar** baixa o instalador, confere com
`SHA256SUMS.txt` e instala sem perguntas, mantendo suas configurações; no Mac abre a página de download. Desligue em
**Som e estilo → Atualizações**.

## Desinstalação

- **Windows, instalado com o `.exe`**: menu Iniciar → *WaveMascot* → **Desinstalar WaveMascot**.
- **Windows, instalado com o `install.ps1`** (ou de qualquer forma):

  ```powershell
  powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
  ```

- **Mac**: ícone do Wave na barra de menus → **Desinstalar WaveMascot…** (ou `./uninstall.sh`, de qualquer forma). Se
  você só arrastar o app para o Lixo, o Claude Code continua funcionando normalmente: os hooks não fazem nada enquanto
  o app não estiver lá.

A desinstalação fecha o mascote, remove **só os hooks dele** de `~/.claude/settings.json` (com backup antes; os seus
ficam exatamente como estavam) e apaga o `/wavemascot`, os atalhos e o programa. Suas configurações em
`~/.wavemascot` são mantidas; para apagá-las também: `uninstall.ps1 -DeleteSettings` ou
`uninstall.sh --delete-settings`.

## Problemas frequentes

- **Não aparece**: veja `~/.wavemascot/mascota.log`; cada evento diz se avisou ou por que não (tela cheia, não
  perturbe, terminal em foco, evento desligado...). Ícone do Wave → *Testar aviso* força um.
- **Os hooks não rodam**: confira no Claude Code com `/hooks` se os do mascote estão lá.
- **Permitir/Negar**: no app de desktop o diálogo próprio continua aparecendo; vale a primeira resposta.
- **Mac: "Não é possível abrir o WaveMascot" ou "A Apple não pôde verificar…"**: veja o passo 3 de
  [Instalação → Mac](#mac).
- **Mac: não vejo o ícone na barra de menus**: nos Macs com notch, os ícones que não cabem ficam escondidos; feche
  algum outro app da barra ou abra as configurações com `/wavemascot`. Se você o fechou, abra o WaveMascot em
  Aplicativos.
- **Mac: recebo dois avisos**: desligue as notificações do seu terminal ou do app do Claude em **Ajustes do Sistema →
  Notificações**, assim só o Wave avisa.
- **Telegram: não chega nada**: por padrão os avisos só vão para o celular se faz 3 minutos que você não usa o
  computador; desligue «Só quando eu não estiver usando o computador» para testar. Se você bloqueou o bot ou mandou
  `/stop`, conecte de novo pela aba **Celular**.

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
python -m unittest discover tests          # testes do instalador, traduções, estilos, celular e atualizações
powershell -ExecutionPolicy Bypass -File .\build.ps1   # gera dist\WaveMascot-Setup.exe (no Windows)
./build-mac.sh                             # gera dist/WaveMascot-Mac-<chip>.dmg (num Mac)
python tools/capturas.py                   # redesenha as capturas e GIFs de docs/ a partir do app real
```

Ao enviar uma tag `v*` (por exemplo `v1.2.0`), o GitHub Actions gera o instalador do Windows e os dois `.dmg` do Mac
e os anexa ao release, com a seção do CHANGELOG daquela versão como notas. Cada push na `main` roda os testes no
Windows e no macOS.

| Arquivo | O que é |
|---|---|
| `mascota.py` | O hook e a janela do mascote |
| `ajustes.py` | A janela de configurações |
| `bandeja.py` | O ícone ao lado do relógio / na barra de menus |
| `sprites.py` | O pixel art, os estilos, os ícones e os sons (tudo gerado por código) |
| `celular.py` | Avisos e permissões pelo Telegram (cliente do Worker) |
| `actualizacion.py` | Procura versões novas no GitHub, baixa e instala |
| `idiomas.py` | Os textos em inglês, espanhol e português |
| `ventanas.py` | Janelas do Windows e do macOS: terminal hospedeiro, foco, tela cheia, monitores |
| `instalador.py` | Instalar / desinstalar (merge de hooks com backup); também é o instalador `.exe` e a primeira execução do app no Mac |
| `principal.py` | Ponto de entrada do `WaveMascot.exe` e do `WaveMascot.app` |
| `servidor/` | O Worker da Cloudflare por trás do @WaveNotificationBot |
| `tools/capturas.py` | Gera as imagens de `docs/` (fora da tela, sem tocar nas suas configurações) |

**Adicionar um idioma**: inclua em `IDIOMAS` no `idiomas.py` com uma tradução por texto; o `tests/test_idiomas.py`
avisa se faltar alguma.

## Licença

[MIT](LICENSE). O `.exe` e o app do Mac incluem PyQt6 (GPL v3) e outras bibliotecas; veja
[THIRD_PARTY.md](THIRD_PARTY.md).
