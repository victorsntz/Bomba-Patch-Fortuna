#!/usr/bin/env python3
"""Lê o que aconteceu na última rodada de teste e explica em português.

Quando o `fortuna portar` roda o jogo sem tela para descobrir código, a máquina
escreve um log (engine/games/<nome>/explore.log) e tira prints de tempos em
tempos (engine/games/<nome>/shots). Este script junta tudo num relatório:
onde parou, o que faltou, quais prints mudaram e o próximo passo, com o comando
de investigação pronto para cada endereço suspeito.

uso: diagnostico.py <nome> [--engine engine/] [--saida relatorios/<nome>]
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ps2kit  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PARADAS = {
    'frame limit reached': ('rodou até o fim do teste', 'Bom sinal: o jogo não travou durante a rodada.'),
    'deadlock: every thread waits and no event is pending': (
        'travou esperando algo que nunca chegou',
        'Todas as tarefas do jogo ficaram esperando. Quase sempre é um driver do IOP que não respondeu '
        '(veja "conversas sem resposta" e "funções que faltaram").'),
    'Exit': ('o jogo pediu para desligar', 'O próprio jogo chamou Exit. Pode ser erro de leitura de disco ou de cartão.'),
    'program asked to run another executable': (
        'o jogo quis carregar outro executável',
        'Alguns jogos trocam de executável no meio (menu e partida separados). A máquina ainda não faz isso.'),
    'bad entry': ('pulou para um código que não foi traduzido',
                  'A tradução não achou esse pedaço de código. A próxima rodada costuma resolver sozinha.'),
}

PADROES = [
    ('syscall', re.compile(r'\[sys\] unhandled syscall 0x([0-9A-Fa-f]+) from 0x([0-9A-Fa-f]{8})')),
    ('iop_falta', re.compile(r'\[iop\] missing (\w+) #(\d+) called from 0x([0-9A-Fa-f]{8})')),
    ('modulo_sem_elf', re.compile(r'\[iop\] (\S+) is not an ELF module')),
    ('modulo_ilegivel', re.compile(r'\[iop\] cannot read module (\S+)')),
    ('modulo_estranho', re.compile(r'\[iop\] (\S+) has no iopmod/load segment')),
    ('rpc_sem_servidor', re.compile(r'\[sif\] call (\d+) to unknown server 0x([0-9A-Fa-f]{8})')),
    ('iop_instrucao', re.compile(r'\[iop\] unknown instruction ([0-9A-Fa-f]{8}) at 0x([0-9A-Fa-f]{8})')),
    ('vif', re.compile(r'\[vif(\d)\] unknown command 0x([0-9A-Fa-f]{8})')),
    ('dispositivo', re.compile(r'\[io\] open (\S+) \(flags 0x[0-9A-Fa-f]+\) on unsupported device')),
    ('entrada_ruim', re.compile(r'\[ee\] bad entry into unit 0x([0-9A-Fa-f]{8}) for pc 0x([0-9A-Fa-f]{8})')),
    ('reboot', re.compile(r'\[sif\] IOP reboot requested with "([^"]*)"')),
    ('carregou', re.compile(r'\[loadfile\] (\S+)')),
]

SERVIDORES_RPC = {
    0x80000100: 'padman (controle)', 0x80000101: 'padman (controle)', 0x8000010F: 'padman (controle)',
    0x80000400: 'mcserv (memory card)', 0x80000701: 'sdrdrv/libsd (som)', 0x80000592: 'cdvdfsv (disco)',
    0x80000593: 'cdvdfsv (disco)', 0x80000595: 'cdvdfsv (disco)', 0x80000596: 'cdvdfsv (disco)', 0x80000597: 'cdvdfsv (disco)',
    0x80000001: 'fileio (arquivos)', 0x80000003: 'iopheap (memória do IOP)', 0x80000006: 'loadfile (módulos)',
}


def ler_log(path):
    achados = {k: [] for k, _ in PADROES}
    parada = None
    frames = None
    threads = []
    modulos_iop = []
    for line in open(path, encoding='utf-8', errors='replace'):
        line = line.rstrip('\n')
        m = re.match(r'\[ee\] halted: (.*)', line)
        if m and parada is None:
            parada = m.group(1)
        m = re.match(r'\[ee\] stopped after (\d+) frames', line)
        if m:
            frames = int(m.group(1))
        m = re.match(r'\[thread\] (\d+) status (\d+) prio (\d+) wait (\S+) pc 0x([0-9A-Fa-f]+) ra 0x([0-9A-Fa-f]+)', line)
        if m:
            threads.append({'id': int(m.group(1)), 'status': int(m.group(2)), 'espera': m.group(4), 'pc': int(m.group(5), 16), 'ra': int(m.group(6), 16)})
        m = re.match(r'\[iop\] module (\d+) (\S+) at 0x([0-9A-Fa-f]+)', line)
        if m:
            modulos_iop.append((int(m.group(3), 16), m.group(2)))
        for kind, pattern in PADROES:
            m = pattern.search(line)
            if m and m.groups() not in [a for a in achados[kind]]:
                achados[kind].append(m.groups())
    return {'parada': parada, 'frames': frames, 'achados': achados, 'threads': threads, 'modulos_iop': sorted(modulos_iop)}


def modulo_do_endereco(modulos, address):
    dono = None
    for base, name in modulos:
        if base <= address:
            dono = (name, address - base)
    return dono


def analisar_prints(shots_dir, saida):
    """Converte os prints em PNG e diz se a tela estava preta ou parada."""
    if not os.path.isdir(shots_dir):
        return []
    frames = sorted(f for f in os.listdir(shots_dir) if f.endswith('.ppm'))
    result = []
    previous = None
    for name in frames:
        try:
            width, height, rgb = ps2kit.ler_ppm(os.path.join(shots_dir, name))
        except (OSError, ValueError):
            continue
        sample = rgb[::97]
        brightness = sum(sample) / max(1, len(sample))
        png = name.replace('.ppm', '.png')
        ps2kit.salvar_png(os.path.join(saida, png), width, height, rgb)
        number = int(re.sub(r'\D', '', name) or 0)
        result.append({'frame': number, 'png': png, 'preta': brightness < 4, 'igual_anterior': rgb == previous})
        previous = rgb
    return result


def comando_investigar(name, address):
    return './fortuna investigar %s 0x%08X' % (name, address)


def montar(name, engine_dir, saida):
    game = os.path.join(engine_dir, 'games', name)
    log = os.path.join(game, 'explore.log')
    if not os.path.isfile(log):
        raise OSError('não achei %s. Rode ./fortuna portar %s antes.' % (log, name))
    os.makedirs(saida, exist_ok=True)
    nomes = ps2kit.nomes()
    r = ler_log(log)
    prints = analisar_prints(os.path.join(game, 'shots'), saida)
    a = r['achados']

    out = []
    add = out.append
    add('# Diagnóstico: %s' % name)
    add('')
    titulo, explicacao = PARADAS.get(r['parada'] or '', (r['parada'] or 'sem motivo no log', ''))
    add('**Como terminou:** %s%s.' % (titulo, ' depois de %d quadros (%.0f segundos de jogo)' % (r['frames'], r['frames'] / 60.0) if r['frames'] else ''))
    if explicacao:
        add('')
        add(explicacao)

    if prints:
        add('')
        add('## O que apareceu na tela')
        add('')
        last = prints[-1]
        add('Último print (quadro %d):' % last['frame'])
        add('')
        add('![último print](%s)' % last['png'])
        add('')
        pretas = [p['frame'] for p in prints if p['preta']]
        paradas = [p['frame'] for p in prints if p['igual_anterior']]
        if len(pretas) == len(prints):
            add('Todos os prints saíram pretos. O jogo não chegou a desenhar nada: o problema está antes da primeira tela.')
        elif pretas:
            add('Prints pretos nos quadros %s.' % ', '.join(map(str, pretas)))
        if len(paradas) >= 2 and paradas[-1] == last['frame']:
            add('A imagem parou de mudar a partir do quadro %d. Pode ser uma tela esperando botão ou o jogo congelado.' % paradas[0])
        add('')
        add('Sequência: ' + ' · '.join('[%d](%s)' % (p['frame'], p['png']) for p in prints))

    problemas = 0
    add('')
    add('## O que faltou na máquina')
    for module in [m[0] for m in a['modulo_sem_elf']] + [m[0] for m in a['modulo_ilegivel']]:
        problemas += 1
        add('')
        add('- **Módulo que não carregou:** `%s`. ' % module + (
            'Ele mora na ROM do console, que a máquina não tem. Solução: achar a cópia desse driver no disco '
            '(raio-x lista) ou escrever a versão própria dele em C++ no motor.' if module.lower().startswith('rom0:')
            else 'O arquivo não foi achado ou não é um módulo válido.'))
    for count, server in a['rpc_sem_servidor']:
        problemas += 1
        sid = int(server, 16)
        add('')
        add('- **Conversa sem resposta:** o jogo chamou o serviço 0x%08X%s no IOP e ninguém atendeu. '
            'Normalmente é o driver que não carregou na linha acima.' % (sid, ' (%s)' % SERVIDORES_RPC[sid] if sid in SERVIDORES_RPC else ''))
    for number, pc in a['syscall']:
        problemas += 1
        n = int(number, 16)
        add('')
        add('- **Syscall 0x%02X %s** chamada do endereço 0x%s. A máquina respondeu 0 e seguiu. Se o jogo travou logo depois, '
            'é o primeiro suspeito.' % (n, ps2kit.nome_syscall(nomes, n) or '(sem nome conhecido)', pc))
        add('  Investigar: `%s`' % comando_investigar(name, int(pc, 16)))
    for library, index, pc in a['iop_falta']:
        problemas += 1
        dono = modulo_do_endereco(r['modulos_iop'], int(pc, 16))
        add('')
        add('- **Função do IOP que faltou:** `%s #%s` %s, chamada %s. A máquina devolveu 0 no lugar.' % (
            library, index, ps2kit.nome_iop(nomes, library, int(index)) or '',
            'pelo módulo %s (posição 0x%X dentro dele)' % dono if dono else 'do endereço 0x%s do IOP' % pc))
    for word, pc in a['iop_instrucao']:
        problemas += 1
        add('')
        add('- **Instrução desconhecida no IOP:** %s em 0x%s. Bug ou lacuna no interpretador do processador do IOP.' % (word, pc))
    for unit, command in a['vif']:
        problemas += 1
        add('')
        add('- **Comando de vídeo desconhecido** no VIF%s: 0x%s. É coisa do caminho de gráficos 3D.' % (unit, command))
    for device, in a['dispositivo']:
        problemas += 1
        add('')
        add('- **Dispositivo que a máquina não conhece:** o jogo tentou abrir `%s`.' % device)
    for unit, pc in a['entrada_ruim']:
        add('')
        add('- Código não traduzido em 0x%s. A próxima rodada do `portar` costuma achar sozinha.' % pc)
    if not problemas:
        add('')
        add('Nada faltou nessa rodada. 🎉')

    if a['reboot'] or a['carregou']:
        add('')
        add('## Drivers que o jogo carregou')
        add('')
        for path, in a['reboot']:
            add('- reiniciou o IOP com `%s`' % path)
        for path, in a['carregou']:
            add('- `%s`' % path)

    vivos = [t for t in r['threads'] if t['status'] in (1, 2, 4)]
    if vivos and r['parada'] != 'frame limit reached':
        add('')
        add('## Onde cada tarefa do jogo estava quando parou')
        add('')
        for t in vivos:
            estado = {1: 'rodando', 2: 'pronta', 4: 'esperando'}.get(t['status'], str(t['status']))
            add('- tarefa %d, %s, no endereço 0x%08X (veio de 0x%08X). Investigar: `%s`' % (
                t['id'], estado, t['pc'], t['ra'], comando_investigar(name, t['ra'])))

    add('')
    add('## Próximo passo')
    add('')
    if problemas:
        add('Leve este relatório para o Claude Code (com o REA instalado) e peça: '
            '"leia relatorios/%s/DIAGNOSTICO.md, investigue o primeiro problema e proponha a correção no motor". '
            'O passo a passo está em docs/INVESTIGAR.md.' % name)
    elif r['parada'] == 'frame limit reached':
        add('A rodada chegou ao fim sem faltar nada. Se os prints mostram o jogo andando, gere a versão web e jogue: `./fortuna jogar %s`.' % name)
    else:
        add('Nada faltou, mas o jogo parou. Rode de novo com mais quadros (`./fortuna portar %s --frames 7200`) e compare.' % name)

    report = os.path.join(saida, 'DIAGNOSTICO.md')
    with open(report, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out) + '\n')
    return report, r, problemas


def main():
    parser = argparse.ArgumentParser(description='Explica a última rodada de teste de um jogo.')
    parser.add_argument('nome')
    parser.add_argument('--engine', default=os.path.join(ROOT, 'engine'))
    parser.add_argument('--saida')
    args = parser.parse_args()
    saida = args.saida or os.path.join(ROOT, 'relatorios', args.nome)
    try:
        report, r, problemas = montar(args.nome, args.engine, saida)
    except OSError as e:
        sys.exit('diagnóstico: %s' % e)
    titulo = PARADAS.get(r['parada'] or '', (r['parada'] or '?',))[0]
    print('%s: %s, %d problema(s). Relatório: %s' % (args.nome, titulo, problemas, os.path.relpath(report, ROOT)))


if __name__ == '__main__':
    main()
