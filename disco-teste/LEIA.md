# Disco de teste

Checagem interna do kit, não é jogo. Um programinha de PS2 escrito do zero
(`fortuna.c`) que desenha um campo e uma bola e lê o controle. O
`./fortuna teste` passa ele pela máquina inteira para provar que o computador
dá conta antes de gastar tempo com o Bomba Patch.

A ISO pronta (`fortuna-teste.iso`) vai no repositório para ninguém precisar
instalar o ps2dev. Ela leva o `sio2man.irx` e o `padman.irx` do
[ps2sdk](https://github.com/ps2dev/ps2sdk) e o programa usa o
[gsKit](https://github.com/ps2dev/gsKit), ambos com licença AFL 2.0.

Para recompilar: instale o [ps2dev](https://github.com/ps2dev/ps2dev), defina
`PS2DEV` e `PS2SDK` e rode `make` nesta pasta.
