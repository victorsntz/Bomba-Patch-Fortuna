# Bomba Patch Fortuna

Bomba Patch no navegador. Sem emulador.

O código do jogo de PS2 é traduzido, peça por peça, para um formato que o
navegador roda (WebAssembly), e a parte que o console fazia sozinho (som,
controle, disco, vídeo) é imitada por uma máquina de tradução. A ISO e tudo o
que sai dela ficam só no seu computador.

**No Mac?** O passo a passo mastigado está em [docs/COMO-JOGAR-NO-MAC.md](docs/COMO-JOGAR-NO-MAC.md).

## Onde estamos

O Bomba Patch traduzido já vai do memory card ao menu, escolha de times e
partida rolando, no executor nativo e no navegador. Dois jogadores com controle
Bluetooth funcionam. Falta consertar os rostos dos jogadores (saem lisos). O
diário da engenharia reversa está em [docs/BOMBA-PATCH.md](docs/BOMBA-PATCH.md).

## Do zero até o apito inicial

Precisa de: Mac ou Linux (no Windows, use o WSL2 com Ubuntu), Git e uns 5 GB
livres. No Mac, também o [Docker Desktop](https://www.docker.com/products/docker-desktop):
o kit entra nele sozinho.

```bash
git clone https://github.com/victorsntz/Bomba-Patch-Fortuna
cd Bomba-Patch-Fortuna
./fortuna preparar                         # uma vez só, demora uns minutos
./fortuna raio-x ~/Downloads/bomba.iso     # olha o disco e prevê o que vai faltar
./fortuna portar bomba                     # acha a ISO sozinho (ou passe o caminho)
./fortuna jogar bomba                      # abre o Chrome em http://localhost:8620
```

O jogo aparece no navegador, não no Terminal: o Terminal só serve a página e
precisa ficar aberto enquanto você joga. Perdeu o fio? `./fortuna checar` diz
em que etapa você está.

Abra no Chrome ou no Edge. Teclado: setas mexem, Z passa, X lança, A chuta,
S enfia, W dispara, Enter é start. Controle USB também funciona.

O Bomba Patch nasceu da versão japonesa do Winning Eleven, então nos menus é
a **bolinha (○, tecla X)** que confirma e o **✕ (tecla Z)** que volta.

## De dois, com controle Bluetooth

1. Pareie os controles no Mac: Ajustes do Sistema → Bluetooth (controle de PS4,
   PS5, Xbox ou Switch Pro). Para entrar em modo de pareamento, segure
   **Share + PS** no controle de PS4 ou **Create + PS** no de PS5 até a luz piscar.
2. Abra o jogo no Chrome ou no Edge (`./fortuna jogar bomba`).
3. Aperte qualquer botão em cada controle. Por privacidade, o navegador só
   enxerga um controle depois que ele é usado na página.

O primeiro controle (e o teclado) é o Jogador 1. O segundo é o Jogador 2: a
página avisa "Controle 2 conectado: Jogador 2 em campo" e liga a segunda porta
do PS2 na hora.

## Se travar

Vai travar na primeira tentativa, e tudo bem: a máquina de tradução só rodou
dois jogos até hoje (Gran Turismo 4 e God of War II). O Bomba Patch é o
terceiro. O ciclo é sempre o mesmo:

```bash
./fortuna diagnostico bomba             # onde parou, o que faltou, com prints
./fortuna investigar bomba 0x0012ABCD   # abre o código do jogo naquele ponto
```

O diagnóstico fica em `relatorios/bomba/DIAGNOSTICO.md`. Cada conserto na
máquina vira um arquivo em `patches/` e entra sozinho no próximo `portar`.

## Os comandos

| comando | o que faz |
| --- | --- |
| `preparar` | baixa a máquina de tradução na versão fixada em `UPSTREAM.lock` e compila |
| `raio-x <iso>` | lê o disco sem rodar nada: executável, drivers, buracos prováveis |
| `cerebro <iso>` | separa num zip de ~10 MB só o que a engenharia reversa precisa |
| `portar <nome> <iso>` | traduz, roda sem tela para achar código escondido e gera a página |
| `diagnostico <nome>` | explica a última rodada em português |
| `investigar <nome> <endereço>` | assembly, pseudocódigo em C e quem chama, via Ghidra |
| `rea <nome>` | o que o [REA](https://github.com/morluto/rea) consegue ver do executável e dos drivers |
| `jogar <nome>` | serve a página do jogo e abre o navegador |
| `checar [nome]` | confere Docker, máquina, jogo e ISO e diz o próximo passo |
| `teste` | checagem interna: roda um disco de teste mínimo para provar que o computador dá conta |

## E o REA?

O [REA](https://github.com/morluto/rea) é a ferramenta de engenharia reversa
que pediu este projeto. Testado na versão 6.4.0 com um executável de PS2 de
verdade:

- inventário e impressão digital (formato, SHA-256) do executável e dos drivers: funciona
- análise profunda pelo Ghidra: recusada. O REA ainda não tem perfil para o
  processador do PS2 (MIPS R5900). Ele tem um perfil assim para o PSP, então
  o caminho existe
- leitura de estrutura (`inspect-binary-layout`): recusada, só aceita ELF de 64 bits

Por isso o `./fortuna investigar` pergunta primeiro ao REA e, quando ele
recusa, chama o Ghidra direto, que é o mesmo motor que o REA usa por baixo.
No dia em que o REA aceitar PS2, o kit passa a usar ele sem mudar nada.

## Regras da casa

- Nenhuma ISO, nenhum pedaço de ISO e nada gerado a partir dela vai para o
  GitHub. O `.gitignore` já barra, mas vale o aviso: o código traduzido é do
  jogo, e o jogo é da Konami.
- Use só discos que você tem.
- Bomba Patch, Winning Eleven, Pro Evolution Soccer e PlayStation são marcas
  dos seus donos. Este projeto não tem ligação com eles.

## De onde vêm as peças

- máquina de tradução: [ps2-web-recomp](https://github.com/snuri00/ps2-web-recomp) (MIT), fixada em `UPSTREAM.lock`
- página do jogo: a do ps2-web-recomp com a cara Fortuna, gerada por `tools/gerar_cara.py`
- nomes de funções do PS2: cabeçalhos do [ps2sdk](https://github.com/ps2dev/ps2sdk) (AFL 2.0), em `tools/dados/`
- investigação: [Ghidra](https://github.com/NationalSecurityAgency/ghidra) e [REA](https://github.com/morluto/rea)
