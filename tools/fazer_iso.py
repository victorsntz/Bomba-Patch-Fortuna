#!/usr/bin/env python3
"""Monta uma imagem ISO 9660 simples, do jeito que o PS2 lê um CD.

Serve para criar o disco de teste do kit (um programa caseiro com o SYSTEM.CNF
apontando para ele) e as imagens falsas que os testes usam. Só a biblioteca
padrão do Python, sem nada para instalar.

uso: fazer_iso.py <saida.iso> <ARQUIVO_NO_DISCO=caminho/local> [...] [--volume NOME]
     fazer_iso.py teste.iso SYSTEM.CNF=system.cnf FRTN_026.10=fortuna.elf MODULES/PAD.IRX=pad.irx
"""

import argparse
import datetime
import os
import shutil
import struct
import sys

SECTOR = 2048


def both16(value):
    return struct.pack('<H', value) + struct.pack('>H', value)


def both32(value):
    return struct.pack('<I', value) + struct.pack('>I', value)


def stamp7(when):
    return bytes([when.year - 1900, when.month, when.day, when.hour, when.minute, when.second, 0])


def stamp17(when):
    return when.strftime('%Y%m%d%H%M%S00').encode('ascii') + b'\x00'


def sectors(size):
    return max(1, (size + SECTOR - 1) // SECTOR)


class Directory:
    def __init__(self, name, parent):
        self.name = name
        self.parent = parent
        self.dirs = {}
        self.files = {}
        self.lba = 0
        self.size = 0
        self.number = 0


def record(name, lba, size, is_dir, when):
    """Um registro de diretório ISO 9660 (seção 9.1 da norma)."""
    ident = name if isinstance(name, bytes) else name.encode('ascii')
    length = 33 + len(ident)
    length += length % 2
    out = bytearray(length)
    out[0] = length
    out[2:10] = both32(lba)
    out[10:18] = both32(size)
    out[18:25] = stamp7(when)
    out[25] = 2 if is_dir else 0
    out[28:32] = both16(1)
    out[32] = len(ident)
    out[33:33 + len(ident)] = ident
    return bytes(out)


def directory_records(directory, when):
    parent = directory.parent or directory
    entries = [record(b'\x00', directory.lba, directory.size, True, when),
               record(b'\x01', parent.lba, parent.size, True, when)]
    children = [(n, d, True) for n, d in directory.dirs.items()] + [(n, f, False) for n, f in directory.files.items()]
    for name, item, is_dir in sorted(children, key=lambda c: c[0]):
        if is_dir:
            entries.append(record(name, item.lba, item.size, True, when))
        else:
            entries.append(record(name + ';1', item['lba'], item['size'], False, when))
    # um registro nunca atravessa o fim de um setor
    blob = bytearray()
    for entry in entries:
        if len(blob) % SECTOR + len(entry) > SECTOR:
            blob += b'\x00' * (SECTOR - len(blob) % SECTOR)
        blob += entry
    return bytes(blob)


def walk(directory):
    """Diretórios em largura, a ordem que a tabela de caminhos pede."""
    queue = [directory]
    for current in queue:
        queue.extend(current.dirs[n] for n in sorted(current.dirs))
    return queue


def path_table(dirs, big_endian):
    pack16 = '>H' if big_endian else '<H'
    pack32 = '>I' if big_endian else '<I'
    out = bytearray()
    for directory in dirs:
        ident = directory.name.encode('ascii') if directory.parent else b'\x00'
        parent_number = directory.parent.number if directory.parent else 1
        out += bytes([len(ident), 0]) + struct.pack(pack32, directory.lba) + struct.pack(pack16, parent_number) + ident
        if len(ident) % 2:
            out += b'\x00'
    return bytes(out)


def build(files, volume='FORTUNA', when=None):
    """files: dict {'CAMINHO/NO/DISCO': bytes}. Devolve os bytes da imagem."""
    import io
    out = io.BytesIO()
    write(out, files, volume, when)
    return out.getvalue()


def write(out, files, volume='FORTUNA', when=None):
    """Grava a imagem em `out` (arquivo aberto em modo binário). Os valores de `files` podem ser bytes ou o
    caminho de um arquivo local, que é copiado em pedaços: dá para montar um DVD inteiro sem caber na memória."""
    when = when or datetime.datetime(2026, 1, 1)
    root = Directory('', None)
    for path, data in files.items():
        parts = path.replace('\\', '/').strip('/').upper().split('/')
        current = root
        for part in parts[:-1]:
            current = current.dirs.setdefault(part, Directory(part, current))
        size = len(data) if isinstance(data, (bytes, bytearray)) else os.path.getsize(data)
        current.files[parts[-1]] = {'data': data, 'size': size, 'lba': 0}

    dirs = walk(root)
    for number, directory in enumerate(dirs, 1):
        directory.number = number

    # o tamanho de cada diretório depende só dos nomes, então dá pra medir antes de saber os endereços
    for directory in dirs:
        directory.size = sectors(len(directory_records(directory, when))) * SECTOR

    table_size = len(path_table(dirs, False))
    table_sectors = sectors(table_size)
    lba = 18
    l_table, lba = lba, lba + table_sectors
    m_table, lba = lba, lba + table_sectors
    for directory in dirs:
        directory.lba, lba = lba, lba + directory.size // SECTOR
    for directory in dirs:
        for name in sorted(directory.files):
            item = directory.files[name]
            item['lba'], lba = lba, lba + sectors(item['size'])
    total = lba

    def put(lba, blob):
        out.seek(lba * SECTOR)
        out.write(blob)

    pvd = bytearray(SECTOR)
    pvd[0:6] = b'\x01CD001'
    pvd[6] = 1
    pvd[8:40] = b'PLAYSTATION'.ljust(32)
    pvd[40:72] = volume.upper().encode('ascii')[:32].ljust(32)
    pvd[80:88] = both32(total)
    pvd[120:124] = both16(1)
    pvd[124:128] = both16(1)
    pvd[128:132] = both16(SECTOR)
    pvd[132:140] = both32(table_size)
    pvd[140:144] = struct.pack('<I', l_table)
    pvd[148:152] = struct.pack('>I', m_table)
    pvd[156:190] = record(b'\x00', root.lba, root.size, True, when)
    for start, end in ((190, 318), (318, 446), (446, 574), (574, 702), (702, 739), (739, 776), (776, 813)):
        pvd[start:end] = b' ' * (end - start)
    pvd[813:830] = stamp17(when)
    pvd[830:847] = stamp17(when)
    pvd[847:864] = b'0' * 16 + b'\x00'
    pvd[864:881] = b'0' * 16 + b'\x00'
    pvd[881] = 1
    put(0, bytes(16 * SECTOR))
    put(16, bytes(pvd))
    put(17, b'\xffCD001\x01'.ljust(SECTOR, b'\x00'))
    put(l_table, path_table(dirs, False))
    put(m_table, path_table(dirs, True))
    for directory in dirs:
        put(directory.lba, directory_records(directory, when))
        for item in directory.files.values():
            if isinstance(item['data'], (bytes, bytearray)):
                put(item['lba'], item['data'])
            else:
                out.seek(item['lba'] * SECTOR)
                with open(item['data'], 'rb') as src:
                    shutil.copyfileobj(src, out, 1 << 22)
    out.seek(total * SECTOR)
    out.truncate()


def main():
    parser = argparse.ArgumentParser(description='Monta uma ISO 9660 simples para PS2.')
    parser.add_argument('saida')
    parser.add_argument('arquivos', nargs='+', help='NOME_NO_DISCO=arquivo/local')
    parser.add_argument('--volume', default='FORTUNA')
    args = parser.parse_args()
    files = {}
    for spec in args.arquivos:
        inside, sep, local = spec.partition('=')
        if not sep:
            parser.error('use NOME_NO_DISCO=arquivo/local, recebi %r' % spec)
        files[inside] = local
    with open(args.saida, 'wb') as out:
        write(out, files, args.volume)
    print('%s: %d arquivos, %d KiB' % (args.saida, len(files), sum(os.path.getsize(p) for p in files.values()) >> 10))


if __name__ == '__main__':
    sys.exit(main())
