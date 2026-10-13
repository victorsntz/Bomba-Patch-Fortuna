#!/usr/bin/env python3
"""Raio-x de um disco de PS2, sem rodar nada.

Abre a ISO, acha o executável que o SYSTEM.CNF manda carregar e conta o que o
jogo vai pedir ao console: chamadas ao sistema (syscalls), módulos do IOP (os
"drivers" de som, controle e cartão de memória) e as funções que esses módulos
importam. Depois compara com o que a máquina de tradução (engine/) já sabe
imitar e lista os buracos prováveis antes de gastar meia hora traduzindo.

uso: raio_x.py <jogo.iso> [--engine engine/] [--json] [--md relatorio.md]
"""

import argparse
import json
import os
import re
import struct
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ps2kit  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSINATURAS = [b'KONAMI', b'WINNING ELEVEN', b'PRO EVOLUTION', b'PES20', b'WE20', b'BOMBA', b'J.LEAGUE', b'MASTER LEAGUE']
MODULO_RE = re.compile(rb'(?:cdrom0?|rom0|host0?|mc0|cdfs|disk0):[\\/]?[A-Za-z0-9_\\/.]+(?:;1)?', re.IGNORECASE)


def tamanho(n):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return ('%.1f %s' % (n, unit)) if unit != 'B' else '%d B' % n
        n /= 1024.0


def analisar(iso_path, engine_dir):
    iso = ps2kit.Iso(iso_path)
    nomes = ps2kit.nomes()
    out = {
        'arquivo': os.path.basename(iso_path),
        'tamanho': os.path.getsize(iso_path),
        'volume': iso.volume,
        'camadas': len(iso.layers),
        'arquivos': len(iso.files()),
        'problemas': [],
    }

    cnf = iso.find('SYSTEM.CNF')
    if not cnf:
        out['problemas'].append('O disco não tem SYSTEM.CNF. Não é um disco de jogo de PS2 (ou é de PS1).')
        return out
    fields = ps2kit.ler_system_cnf(iso.read(cnf).decode('ascii', 'replace'))
    out['system_cnf'] = fields
    boot = fields.get('BOOT2')
    if not boot:
        out['problemas'].append('O SYSTEM.CNF não tem BOOT2 (disco de PS1?).')
        return out
    program, serial, region = ps2kit.nome_do_boot(boot)
    out['executavel'] = {'nome': program, 'serial': serial, 'regiao': region, 'video': fields.get('VMODE')}
    entry = iso.find(program)
    if not entry:
        out['problemas'].append('O SYSTEM.CNF aponta para %s, mas esse arquivo não está no disco.' % program)
        return out
    elf = ps2kit.Elf(iso.read(entry), program)
    if not elf.is_r5900:
        out['problemas'].append('%s não é um executável do processador do PS2 (máquina %d, flags 0x%08X).' % (program, elf.machine, elf.flags))
    funcs = elf.functions()
    code = sum(e - s for s, e, _ in elf.code_ranges())
    out['executavel'].update({
        'tamanho': len(elf.data), 'codigo': code, 'entrada': '0x%08X' % elf.entry, 'r5900': elf.is_r5900,
        'funcoes_com_nome': len(funcs),
        'segmentos': [{'endereco': '0x%08X' % s['vaddr'], 'tamanho': s['memsz'], 'executavel': bool(s['flags'] & 1)}
                      for s in elf.segments if s['type'] == 1],
    })

    upper = elf.data.upper()
    out['assinaturas'] = {sig.decode(): upper.count(sig) for sig in ASSINATURAS if upper.count(sig)}

    pedidos = sorted({m.group().decode('ascii', 'replace') for m in MODULO_RE.finditer(elf.data)
                      if m.group().upper().endswith((b'.IRX', b'.IRX;1', b'.IMG', b'.IMG;1')) or m.group().lower().startswith(b'rom0:')})
    out['caminhos_no_executavel'] = pedidos

    # módulos do IOP no disco, dentro de imagens IOPRP e dentro de pacotes; overlays de código
    modules = []
    overlays = {}
    for f in iso.files():
        upper_path = f['path'].upper()
        if upper_path.endswith('.IRX'):
            data = iso.read(f)
            modules.append(('disco', f['path'], data))
        elif upper_path.endswith('.IMG') and f['size'] < 8 << 20:
            for name, data in ps2kit.romdir(iso.read(f)):
                if data[:4] == b'\x7fELF':
                    modules.append(('ioprp', f['path'] + ':' + name, data))
        elif f['size'] < 64 << 20 and iso.read(f, 0, 4) in (b'AFS\x00', b'\x00\x06\x00\x00', b'MWo3'):
            data = iso.read(f)
            items = [(0, len(data))] if data[:4] == b'MWo3' else ps2kit.entradas_empacotadas(data)
            for index, (offset, size) in enumerate(items):
                blob = data[offset:offset + size]
                ov = ps2kit.overlay_mwo3(blob)
                if ov:
                    ov['arquivo'] = f['path']
                    overlays.setdefault(ov['nome'], ov)
                elif blob[:4] == b'\x7fELF' and len(blob) > 52 and struct.unpack_from('<H', blob, 16)[0] in ps2kit.ET_IRX:
                    modules.append(('pacote', '%s#%d' % (f['path'], index), blob))
    out['overlays'] = sorted(overlays.values(), key=lambda o: (o['endereco'], o['nome']))
    info = []
    exports = {}
    imports = {}
    for origin, path, data in modules:
        try:
            m = ps2kit.Elf(data, path)
        except ValueError:
            continue
        mod = m.iopmod() or {}
        item = {'origem': origin, 'caminho': path, 'nome': mod.get('nome'), 'versao': mod.get('versao'),
                'exporta': [lib for lib, _ in m.iop_exports()], 'importa': sorted({lib for lib, _ in m.iop_imports()})}
        info.append(item)
        if origin == 'disco':
            for lib, count in m.iop_exports():
                exports[lib] = max(exports.get(lib, 0), count)
            for lib, indexes in m.iop_imports():
                for i in indexes:
                    imports.setdefault(lib, {}).setdefault(i, set()).add(os.path.basename(path))
    out['modulos_iop'] = info

    cobertura = ps2kit.motor_cobertura(engine_dir) if engine_dir else None
    out['motor_encontrado'] = cobertura is not None
    syscalls = elf.syscalls()
    out['syscalls'] = [{'numero': '%s0x%02X' % ('-' if n < 0 else '', abs(n)), 'nome': ps2kit.nome_syscall(nomes, n), 'vezes': c}
                       for n, c in sorted(syscalls.items(), key=lambda kv: abs(kv[0]))]

    previsao = {'syscalls': [], 'iop': [], 'rom0': []}
    if cobertura:
        for n, c in sorted(syscalls.items(), key=lambda kv: abs(kv[0])):
            if abs(n) not in cobertura['syscalls']:
                previsao['syscalls'].append({'numero': '%s0x%02X' % ('-' if n < 0 else '', abs(n)),
                                             'nome': ps2kit.nome_syscall(nomes, n), 'vezes': c})
        for lib in sorted(imports):
            if lib in exports:
                continue  # outro módulo do disco fornece essa biblioteca
            have = cobertura['iop'].get(lib, {})
            for index in sorted(imports[lib]):
                if index in have:
                    continue
                previsao['iop'].append({'biblioteca': lib, 'indice': index, 'nome': ps2kit.nome_iop(nomes, lib, index),
                                        'quem_chama': sorted(imports[lib][index])})
        disc_names = {(m.get('nome') or '').upper() for m in info if m['origem'] == 'disco'}
        disc_files = {os.path.splitext(os.path.basename(m['caminho']))[0].upper() for m in info if m['origem'] == 'disco'}
        for p in pedidos:
            if not p.lower().startswith('rom0:'):
                continue
            name = re.split(r'[\\/:]', p)[-1].split(';')[0].upper()
            if name in ('ROMVER', 'OSDSYS', 'UDNL') or '.' in name:
                continue  # UDNL é o reinício do IOP com uma imagem IOPRP, que a máquina já trata
            previsao['rom0'].append({'modulo': name, 'tem_copia_no_disco': name in disc_names or name in disc_files})
    out['previsao'] = previsao

    if out['problemas']:
        out['veredito'] = 'vermelho'
    elif not cobertura:
        out['veredito'] = 'sem motor'
    elif previsao['iop'] or any(not m['tem_copia_no_disco'] for m in previsao['rom0']):
        out['veredito'] = 'amarelo'
    else:
        out['veredito'] = 'verde'
    return out


def analisar_cerebro(zip_path, engine_dir):
    """Aceita o zip do `fortuna cerebro`: remonta uma ISO pequena com ele e analisa."""
    import fazer_iso
    files = {}
    volume = 'CEREBRO'
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            if info.filename == 'VOLUME.TXT':
                volume = z.read(info).decode('ascii', 'replace').strip() or volume
            else:
                files[info.filename] = z.read(info)
    with tempfile.TemporaryDirectory() as tmp:
        iso = os.path.join(tmp, os.path.basename(zip_path)[:-4] + '.iso')
        with open(iso, 'wb') as f:
            f.write(fazer_iso.build(files, volume))
        r = analisar(iso, engine_dir)
    r['arquivo'] = os.path.basename(zip_path) + ' (só o cérebro)'
    r['tamanho'] = os.path.getsize(zip_path)
    return r


def texto(r):
    lines = []
    add = lines.append
    add('RAIO-X  %s' % r['arquivo'])
    add('  disco      %s, volume "%s", %d camada(s), %d arquivos' % (tamanho(r['tamanho']), r['volume'], r['camadas'], r['arquivos']))
    for p in r['problemas']:
        add('  PROBLEMA   %s' % p)
    exe = r.get('executavel')
    if exe:
        add('  boot       %s%s%s, vídeo %s' % (exe['nome'], ' (%s)' % exe['serial'] if exe.get('serial') else '',
                                             ', ' + exe['regiao'] if exe.get('regiao') else '', exe.get('video') or '?'))
    if exe and 'codigo' in exe:
        add('  código     %s de código de máquina, entrada %s, processador %s' % (
            tamanho(exe['codigo']), exe['entrada'], 'do PS2 (R5900)' if exe['r5900'] else 'estranho'))
        if exe['funcoes_com_nome']:
            add('  símbolos   %d funções com nome. Ótimo: investigar fica bem mais fácil.' % exe['funcoes_com_nome'])
        else:
            add('  símbolos   nenhum nome de função (executável limpo). Normal em jogo comercial.')
    if r.get('assinaturas'):
        add('  marcas     ' + ', '.join('%s (%dx)' % kv for kv in r['assinaturas'].items()))
    mods = r.get('modulos_iop') or []
    if mods:
        add('')
        add('DRIVERS DO IOP (o segundo processador, que cuida de som, controle, disco e memory card)')
        for m in mods:
            add('  %-6s %-34s %s %s' % (m['origem'], m['caminho'][-34:], m.get('nome') or '?', m.get('versao') or ''))
    ovs = r.get('overlays') or []
    if ovs:
        enderecos = {}
        for o in ovs:
            enderecos.setdefault(o['endereco'], []).append(o['nome'])
        add('')
        add('CÓDIGO EM OVERLAYS: %d pedaços (%s) que o jogo carrega por cima um do outro' % (
            len(ovs), tamanho(sum(o['codigo'] for o in ovs))))
        for at, names in sorted(enderecos.items()):
            add('  0x%08X  %s' % (at, ', '.join(names)))
        add('  Sem suporte a overlays MWo3, a máquina trava no primeiro deles (patches/0002 resolve).')
    if r.get('caminhos_no_executavel'):
        add('')
        add('O EXECUTÁVEL CITA ESTES ARQUIVOS DE MÓDULO')
        for p in r['caminhos_no_executavel']:
            add('  ' + p)
    if r.get('syscalls'):
        add('')
        add('CHAMADAS AO SISTEMA: %d tipos diferentes' % len(r['syscalls']))
    prev = r.get('previsao') or {}
    if r.get('motor_encontrado'):
        add('')
        add('PREVISÃO DE BURACOS NA MÁQUINA')
        rom0_missing = [m for m in prev.get('rom0', []) if not m['tem_copia_no_disco']]
        rom0_copy = [m for m in prev.get('rom0', []) if m['tem_copia_no_disco']]
        if rom0_missing:
            add('  Quase certo de dar trabalho: módulos que o jogo pede à ROM do console, que a')
            add('  máquina não tem e que não estão no disco')
            for m in rom0_missing:
                add('    rom0:%s' % m['modulo'])
        if prev.get('iop'):
            add('  Pode travar: funções do IOP que os drivers do disco chamam e ninguém fornece')
            for f in prev['iop']:
                add('    %s #%d %-28s pedida por %s' % (f['biblioteca'], f['indice'], f['nome'] or '', ', '.join(f['quem_chama'])))
        if rom0_copy:
            add('  Vale olhar: o jogo pede à ROM módulos que também estão no disco')
            for m in rom0_copy:
                add('    rom0:%s' % m['modulo'])
        if prev.get('syscalls'):
            add('  Provavelmente inofensivo: syscalls que aparecem no código mas a máquina não')
            add('  imita (se o jogo chamar, ela responde 0 e segue; muita coisa nem é chamada)')
            add('    ' + ', '.join('%s %s' % (x['numero'], x['nome'] or '?') for x in prev['syscalls']))
        if not any(prev.values()):
            add('  nenhum buraco visível daqui. O teste de verdade é rodar (./fortuna portar).')
    elif r.get('executavel'):
        add('')
        add('Sem a pasta engine/ não dá para prever buracos. Rode ./fortuna preparar e repita.')
    add('')
    add({'verde': 'VEREDITO  verde: nada grave à primeira vista. Bora portar.',
         'amarelo': 'VEREDITO  amarelo: deve precisar de ajuste na máquina. A lista acima é o mapa da mina.',
         'vermelho': 'VEREDITO  vermelho: esse arquivo não serve do jeito que está.',
         'sem motor': 'VEREDITO  falta preparar a máquina para comparar.'}[r.get('veredito', 'vermelho')])
    return '\n'.join(lines)


def markdown(r):
    return '# Raio-x de %s\n\n```\n%s\n```\n' % (r['arquivo'], texto(r))


def main():
    parser = argparse.ArgumentParser(description='Raio-x de um disco de PS2.')
    parser.add_argument('iso')
    parser.add_argument('--engine', default=os.path.join(ROOT, 'engine'))
    parser.add_argument('--json', action='store_true', help='imprime o resultado em JSON')
    parser.add_argument('--md', help='também grava um relatório em Markdown neste caminho')
    args = parser.parse_args()
    try:
        if args.iso.lower().endswith('.zip'):
            r = analisar_cerebro(args.iso, args.engine)
        else:
            r = analisar(args.iso, args.engine)
    except (OSError, ValueError, zipfile.BadZipFile) as e:
        sys.exit('raio-x: %s' % e)
    if args.md:
        with open(args.md, 'w', encoding='utf-8') as f:
            f.write(markdown(r))
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=1, default=list))
    else:
        print(texto(r))
    return 0 if r.get('veredito') != 'vermelho' else 1


if __name__ == '__main__':
    sys.exit(main())
