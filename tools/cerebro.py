#!/usr/bin/env python3
"""Separa o "cérebro" de uma ISO de PS2 num zip pequeno.

O cérebro é o que a engenharia reversa precisa: o SYSTEM.CNF, o executável que
ele manda carregar e os drivers do IOP (.IRX e imagens .IMG). Costuma dar uns
10 MB, contra 4 GB da ISO inteira. Gramado, rostos e narração ficam de fora.

uso: cerebro.py <jogo.iso> [saida.zip]
"""

import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ps2kit  # noqa: E402

LIMITE_IMG = 16 << 20


def escolher(iso):
    cnf = iso.find('SYSTEM.CNF')
    if not cnf:
        raise ValueError('a ISO não tem SYSTEM.CNF; não parece jogo de PS2')
    boot = ps2kit.ler_system_cnf(iso.read(cnf).decode('ascii', 'replace')).get('BOOT2', '')
    program = ps2kit.nome_do_boot(boot)[0]
    chosen = [cnf]
    for entry in iso.files():
        upper = entry['path'].upper()
        if entry is cnf:
            continue
        if upper == program.upper() or upper.endswith('.IRX') or (upper.endswith('.IMG') and entry['size'] <= LIMITE_IMG):
            chosen.append(entry)
        elif upper.endswith('.ELF') and entry['size'] <= LIMITE_IMG:
            chosen.append(entry)
    if not any(e['path'].upper() == program.upper() for e in chosen):
        raise ValueError('o SYSTEM.CNF aponta para %s, que não está no disco' % program)
    return chosen


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__.strip().splitlines()[-1])
    source = sys.argv[1]
    target = sys.argv[2] if len(sys.argv) > 2 else 'cerebro-' + os.path.splitext(os.path.basename(source))[0] + '.zip'
    try:
        iso = ps2kit.Iso(source)
        chosen = escolher(iso)
    except (OSError, ValueError) as e:
        sys.exit('cérebro: %s' % e)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('VOLUME.TXT', iso.volume + '\n')
        for entry in chosen:
            z.writestr(entry['path'], iso.read(entry))
    total = sum(e['size'] for e in chosen)
    print('%s: %d arquivos, %.1f MB antes de compactar (a ISO tem %.1f MB)' % (
        target, len(chosen), total / 1048576.0, os.path.getsize(source) / 1048576.0))
    for entry in chosen:
        print('  %s' % entry['path'])


if __name__ == '__main__':
    main()
