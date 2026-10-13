#!/usr/bin/env python3
"""Gera tools/dados/nomes_ps2.json a partir dos cabeçalhos do ps2sdk.

O JSON traduz números em nomes: "syscall 0x3C" vira SetupThread, "libsd #5" vira
sceSdSetParam. São só números e nomes de função, tirados dos cabeçalhos públicos
do ps2sdk (https://github.com/ps2dev/ps2sdk, licença AFL 2.0). Rode de novo
quando quiser atualizar:

    PS2SDK=/opt/ps2dev/ps2sdk python3 tools/gerar_nomes.py
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'dados', 'nomes_ps2.json')


def syscalls(sdk):
    names = {}
    path = os.path.join(sdk, 'ee', 'include', 'syscallnr.h')
    for line in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'#define\s+__NR_(\w+)\s+\(?\s*(-?)\s*(0x[0-9a-fA-F]+|\d+)\s*\)?', line)
        if not m:
            continue
        name, minus, value = m.groups()
        number = int(value, 0)
        # o mesmo número com sinal negativo é a versão para rodar dentro de interrupção (iXxx)
        key = '-0x%02X' % number if minus else '0x%02X' % number
        names.setdefault(key, name.lstrip('_'))
    return names


def iop_imports(sdk):
    table = {}
    root = os.path.join(sdk, 'iop', 'include')
    for folder, _, files in os.walk(root):
        for file in sorted(files):
            if not file.endswith('.h'):
                continue
            library = None
            for line in open(os.path.join(folder, file), encoding='utf-8', errors='replace'):
                t = re.search(r'DECLARE_IMPORT_TABLE\(\s*(\w+)\s*,', line)
                if t:
                    library = t.group(1)
                    continue
                i = re.search(r'DECLARE_IMPORT\(\s*(\d+)\s*,\s*(\w+)\s*\)', line)
                if i and library:
                    table.setdefault(library, {}).setdefault(i.group(1), i.group(2))
    return {lib: dict(sorted(funcs.items(), key=lambda kv: int(kv[0]))) for lib, funcs in sorted(table.items())}


def main():
    sdk = os.environ.get('PS2SDK')
    if not sdk or not os.path.isdir(sdk):
        sys.exit('defina PS2SDK com a pasta do ps2sdk instalado')
    data = {
        'fonte': 'cabeçalhos do ps2sdk (https://github.com/ps2dev/ps2sdk), licença AFL 2.0',
        'syscalls_ee': syscalls(sdk),
        'bibliotecas_iop': iop_imports(sdk),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write('\n')
    print('%s: %d syscalls, %d bibliotecas do IOP' % (OUT, len(data['syscalls_ee']), len(data['bibliotecas_iop'])))


if __name__ == '__main__':
    main()
