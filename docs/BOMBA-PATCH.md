# Engenharia reversa do Bomba Patch

Diário do que o disco revelou e do que a máquina de tradução precisou aprender.
Só fatos, nomes e endereços. Nenhum byte do jogo mora neste repositório.

## O disco

| arquivo | o que é |
| --- | --- |
| `SYSTEM.CNF` | manda o console carregar `SLPM_663.74`, vídeo NTSC, versão 1.02 |
| `SLPM_663.74` | executável principal. Serial japonês (SLPM-66374): a base é um Winning Eleven da Konami. Modificado em dezembro de 2025, que é a mão da equipe do Bomba Patch |
| `ROMLIST.DIR` | índice de 78 bytes com os AFS que o jogo procura na partida |
| `IOP/` | drivers do segundo processador (som, controle, cartão, USB) e a imagem `IOPRP300.IMG` |
| `MODULE.AFS` | os mesmos 12 drivers, empacotados no formato da Konami (começa com `0x600`) |
| `BOOT.AFS` | 7 itens; o primeiro é o overlay `bootset.ovl` |
| `OVER.AFS` | 36 overlays de código (7,3 MB) |
| `0_TEXT.AFS`, `J_TEXT.AFS` | gráficos e textos (o "estádio") |
| `0_SOUND.AFS`, `J_SOUND.AFS` | sons e narração |

## Achado 1: o executável é só a portaria

O `SLPM_663.74` tem 1,9 MB de código. O resto, 7,3 MB, vem em **overlays**:
pedaços de código no formato `MWo3` do compilador Metrowerks, que o jogo lê do
disco e põe sempre no mesmo endereço, um por cima do outro.

Cabeçalho de 64 bytes, carregado junto com o código:

| deslocamento | campo |
| --- | --- |
| `0x00` | `MWo3` |
| `0x04` | número do overlay |
| `0x08` | endereço onde ele mora |
| `0x0C` | tamanho do código |
| `0x10` | tamanho dos dados |
| `0x14` | tamanho do bss |
| `0x18` | fim de código e dados na memória |
| `0x20` | nome (`game.ovl`, `title.ovl`...) |

Prova de que o cabeçalho vai para a memória: medindo os `jal` internos, no
`select.ovl` 396 de 425 caem no início de uma função contando o cabeçalho, e
zero sem contar.

Quem divide endereço com quem:

| endereço | overlays |
| --- | --- |
| `0x005FA000` | gameanime2_dummy, memorycard |
| `0x007DD000` | leagueWork, netlib, training_challenge, training_explanation, training_situation |
| `0x00889800` | formation, select1 |
| `0x008CB000` | bootset, ending, enter, mc_conv, result, title, training_free |
| `0x00904000` | defaultdataset, **game** (3,5 MB, a partida), league_common, lobby, select |
| `0x00AB8800` | connect, leaguecup, **masterleague** |
| `0x00B68800` | edit, https |
| `0x00C9A800` | realcondition (+ E, F, G, I, S), training_common |
| `0x00D0A000` | ime |
| `0x00E0A000` | dlheaparea |
| `0x03000000` | filelist (só em kit de desenvolvimento, fora dos 32 MB do console) |

**Conserto:** `patches/0002`. O tradutor lê os overlays (`--overlays`) e o
despachante descobre qual está na memória olhando cabeçalho, número, nome e
algumas palavras de código.

Dois detalhes que a primeira versão do conserto deixou passar:

- o executável e os overlays se chamam por `jal` com endereço absoluto. Olhando
  um arquivo de cada vez, o tradutor não via as ~1.800 funções do executável
  que só os overlays chamam, e o jogo parava a cada uma. Agora todas as
  chamadas cruzadas viram ponto de entrada já na primeira passada (no sentido
  executável → overlay, só onde o overlay realmente abre uma função, porque
  outros overlays ocupam o mesmo endereço).
- o Metrowerks alinha cada função em 16 bytes com zeros depois do `jr ra`; a
  regra de "início de função" precisa pular esse enchimento.

## Achado 2: 39 terrenos, quase todos vazios

O executável declara 39 segmentos de memória. 38 vêm sem nenhum byte: são o
espaço reservado para os overlays. A máquina achava que esses zeros eram código
e traduzia 26 MB de nada. E um deles fica em `0x03000000`, além da memória do
console, o que fazia o carregador recusar o executável inteiro.

**Conserto:** `patches/0001`. Só conta como código o que vem do arquivo, e o
segmento vazio fora da memória é pulado com aviso.

## Achado 3: os drivers

O jogo reinicia o IOP com `rom0:UDNL cdrom0:\IOP\IOPRP300.IMG;1` (a máquina já
trata) e carrega da memória os 12 drivers do `MODULE.AFS`: sio2man, mtapman,
padman, mcman, mcserv, libsd, sdrdrv, o áudio CRI ADX 9.44, usbd, o teclado USB
da Konami, cdvdstm e um driver de som próprio (`AUDIO.IRX`). Todos rodaram no
interpretador do IOP na primeira tentativa.

O raio-x ainda aponta funções que esses drivers importam e a máquina não tem:
`cdvdman` (streaming de disco), `ioman` #20/#21 (registrar dispositivo) e
`secrman` #4/#5 (autenticação do memory card). Ficam no radar.

## Linha do tempo das tentativas

| tentativa | o que aconteceu |
| --- | --- |
| 1 | carregador recusou o executável (segmento em `0x03000000`) |
| 2 | reiniciou o IOP, carregou os 12 drivers, leu `ROMLIST.DIR`, abriu os AFS e parou em `0x008CC320`, dentro do `bootset.ovl` |
| 3 | com suporte a overlays: entrou no `bootset.ovl` (a checagem do memory card) e foi parando em funções do executável que só os overlays chamam, uma por rodada |
| 4 | com as chamadas cruzadas: em andamento |
