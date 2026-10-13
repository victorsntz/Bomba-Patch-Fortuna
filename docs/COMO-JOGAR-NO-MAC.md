# Como jogar o Bomba Patch no navegador (Mac)

Uma vez só, uns 40 minutos no total (a maior parte é o computador trabalhando
sozinho). Depois disso, para jogar é só o passo 5.

## 1. Instale o Docker Desktop

Baixe em https://www.docker.com/products/docker-desktop (escolha "Apple
Silicon" se o seu Mac é M1, M2, M3 ou M4; "Intel" se não for). Arraste para
Aplicativos, abra e deixe ele aberto. Quando a baleia na barra de cima parar
de se mexer, está pronto.

## 2. Abra o Terminal e baixe o kit

Aperte `Cmd + Espaço`, digite **Terminal** e Enter. Cole estas linhas (uma
de cada vez, Enter depois de cada):

```bash
cd ~
git clone -b claude/laughing-clarke-vz4bb2 https://github.com/victorsntz/Bomba-Patch-Fortuna
cd Bomba-Patch-Fortuna
```

Se o Mac pedir para instalar as "ferramentas de linha de comando", aceite e
repita a linha do `git clone` depois.

## 3. Prepare a máquina de tradução

```bash
./fortuna preparar
```

Na primeira vez ele monta o ambiente dentro do Docker. Vai aparecer muito
texto passando; é normal. Termina com "pronto".

## 4. Traduza o seu Bomba Patch

```bash
./fortuna portar bomba
```

Ele procura a ISO sozinho em Downloads, Mesa, Documentos e discos externos
(se o Mac perguntar se o Terminal pode ver essas pastas, deixe). Achando mais
de uma, ele mostra a lista e você digita o número. Se preferir apontar você
mesmo, digite `./fortuna portar bomba ` com espaço no fim, arraste a ISO do
Finder para dentro do Terminal e aperte Enter.

Ele reconhece o disco ("Disco reconhecido: Bomba Patch") e vai direto para a
versão navegador. Essa é a parte demorada: uns 20 a 40 minutos. Acabou quando
aparece "Página pronta".

## 5. Jogue

```bash
./fortuna jogar bomba
```

O jogo não aparece no Terminal. O Terminal é a cozinha: ele prepara e serve,
e o prato chega no **Chrome**, que abre sozinho em **http://localhost:8620**
(se não abrir, abra você nesse endereço). Clique em **Apito inicial**.

Deixe o Terminal aberto enquanto joga. Para parar, volte nele e aperte `Ctrl + C`.

## Perdeu o fio?

```bash
./fortuna checar
```

Confere cada etapa (Docker aberto, máquina pronta, jogo traduzido, ISO no
lugar) e diz qual é o próximo passo.

## Controles

| teclado | controle | no menu | na partida |
| --- | --- | --- | --- |
| setas | direcional | mover | mover |
| X | ○ | **confirmar** | lançamento |
| Z | ✕ | voltar | passe |
| A | □ | | chute |
| S | △ | | enfiada |
| W | R1 | | disparada |
| Q | L1 | | trocar jogador |
| Enter | Start | | pausa |

O Bomba Patch nasceu da versão japonesa do Winning Eleven: no menu quem
confirma é a **bolinha**.

## De dois, com controle Bluetooth

1. Ajustes do Sistema → Bluetooth. Ponha o controle em modo de pareamento:
   **Share + PS** (PS4) ou **Create + PS** (PS5), segurando até a luz piscar.
2. Com a página do jogo aberta, aperte um botão em cada controle.
3. O primeiro controle é o Jogador 1, o segundo é o Jogador 2. A página avisa
   "Controle 2 conectado: Jogador 2 em campo".

## Se algo der errado

- **"o kit roda dentro do Docker"**: o Docker Desktop não está instalado.
- **"o Docker Desktop está fechado"**: abra ele e espere a baleia parar.
- **"ainda não foi traduzido"**: falta o passo 4 (`portar`).
- **Página lenta**: use o Chrome atualizado. No Mac ele desenha pela placa de
  vídeo (WebGPU); outros navegadores podem cair no modo lento.
- **Rostos dos jogadores lisos, tipo máscara**: é um defeito conhecido que eu
  ainda estou consertando. O resto do jogo funciona.
- Qualquer outra coisa: tire um print do Terminal (`Cmd + Shift + 4`) e me
  mande, junto com o resultado do `./fortuna checar`.

A ISO e a versão traduzida ficam só no seu Mac. Nada disso vai para o GitHub.
