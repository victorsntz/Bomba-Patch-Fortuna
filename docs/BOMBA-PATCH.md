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

## Achado 4: o vídeo que não existe

Depois da abertura da Equipe Bomba Patch, o `title.ovl` manda tocar
`cdrom0:\WE10_OP.PSS;1`, o vídeo de abertura do Winning Eleven 10. Esse
arquivo não está no disco do Bomba Patch, e o tocador desiste. Na faxina
(`0x1308F8` no executável) ele:

1. desliga a interrupção de VBlank (causa 2) com `DisableIntc`
2. remove o tratador dele com `RemoveIntcHandler`
3. religa o VBlank **se a remoção responder diferente de zero**

No console, `RemoveIntcHandler` responde quantos tratadores ainda sobram naquela
causa. Como o jogo tem o dele (`0x145EB0`, que conta os quadros), sobra um e o
VBlank volta. A máquina respondia sempre 0: o VBlank ficava desligado e o jogo
esperava para sempre, no laço de `0x139AC8`, um quadro que não vinha.

**Conserto:** `patches/0005`. `RemoveIntcHandler` e `RemoveDmacHandler` agora
respondem quantos tratadores restam na mesma causa ou canal.

## Achado 5: chamadas que o tradutor não via

Além dos `jal`, os overlays saltam para o executável com `j` (chamada de cauda),
o executável chama funções "folha" dos overlays (que não abrem espaço na pilha)
e monta endereços na hora com `lui` + `addiu`. Cada um desses custava uma rodada
de teste. O `patches/0002` passou a oferecer todos como candidatos, conferidos
pelo próprio tradutor, e o jogo agora roda os 90 segundos do teste sem parar
por código não traduzido.

## Dois jogadores

O PS2 de mentira tinha as duas portas de controle, mas só a primeira ligada, e a
página lia só um controle. `patches/0004` deixa a porta 2 ligável a qualquer
momento e a página passa a ler dois controles: teclado e primeiro controle são o
Jogador 1, o segundo controle é o Jogador 2. Testado no disco de teste com dois
controles simulados no navegador.

## Linha do tempo das tentativas

| tentativa | o que aconteceu |
| --- | --- |
| 1 | carregador recusou o executável (segmento em `0x03000000`) |
| 2 | reiniciou o IOP, carregou os 12 drivers, leu `ROMLIST.DIR`, abriu os AFS e parou em `0x008CC320`, dentro do `bootset.ovl` |
| 3 | com suporte a overlays: entrou no `bootset.ovl` (a checagem do memory card) e foi parando em funções do executável que só os overlays chamam, uma por rodada |
| 4 | com as chamadas cruzadas: tela do memory card e abertura da Equipe Bomba Patch aparecem; depois tela preta |
| 5 | tela preta explicada: vídeo `WE10_OP.PSS` ausente e VBlank desligado na faxina do tocador (achado 4) |
| 6 | com o `patches/0005`: passou do vídeo e chegou na tela de título |
| 7 | tradutor com ponteiros e chamadas de cauda: **menu principal na tela** (Duelo, Master Liga, Liga, Copa...), rodando os 90 segundos sem parar |
| 8 | o "baixo" no menu chamou atalhos de uma instrução do `select1.ovl` (`j` direto para o executável) que o verificador do tradutor recusava; corrigido no `patches/0001` |
| 9 | X a cada 2 segundos no menu: nada acontece. A base é japonesa, então quem confirma é a bolinha (○) |
| 10 | com ○: Selecionar Time, Menu de Configuração, carregamento, Maracanã em 3D, torcida, entrada em campo e escalação |
| 11 | rodada de 3 min 30 s com chute e corrida: **partida rolando**, placar, relógio, radar, Casé TV e placas Bomba Patch |

## O que falta

- **Rostos dos jogadores:** a geometria aparece (olhos, nariz, dentes), mas a
  pele sai lisa, sem a textura do rosto. O Winning Eleven monta cada rosto numa
  textura em tempo real; algo nessa composição não acontece no "pintor" (GS) da
  máquina. Investigando com despejo da memória de vídeo na hora da escalação.
- **Versão navegador:** compilando e testando no Chrome.
- **Vídeo de abertura:** o disco não traz `WE10_OP.PSS`, então o jogo pula o
  vídeo (como no PS2).
