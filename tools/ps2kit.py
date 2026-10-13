"""Peças para ler um disco de PS2 sem dependência nenhuma além do Python.

- Iso: lê imagens ISO 9660 de CD e DVD (inclusive as duas camadas de um DVD9)
- Elf: lê executáveis do PS2 (o do processador principal, EE) e módulos do IOP (IRX)
- motor_cobertura: lê o código da máquina de tradução e descobre o que ela já imita
- salvar_png: grava uma imagem PNG (para os prints que o diagnóstico guarda)

Tudo aqui só lê bytes. Nada roda o jogo.
"""

import os
import re
import struct
import zlib

SECTOR = 2048
HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- disco

class Iso:
    def __init__(self, path):
        self.path = path
        self.file = open(path, 'rb')
        self.size = os.path.getsize(path)
        pvd = self._sector(16)
        if pvd[:6] != b'\x01CD001':
            raise ValueError('não parece uma ISO de PS2: falta o descritor de volume no setor 16')
        self.layers = [(0, pvd)]
        first = struct.unpack_from('<I', pvd, 80)[0]
        # DVD9: a segunda camada tem seu próprio descritor logo depois do fim da primeira
        for sector in range(first, min(first + 64, self.size // SECTOR)):
            data = self._sector(sector)
            if data[:6] == b'\x01CD001':
                self.layers.append((sector - 16, data))
                break
        self.volume = pvd[40:72].decode('ascii', 'replace').strip()
        self._files = None

    def _sector(self, n, count=1):
        self.file.seek(n * SECTOR)
        return self.file.read(count * SECTOR)

    def files(self):
        if self._files is None:
            found = []
            for base, pvd in self.layers:
                root_lba, root_size = struct.unpack_from('<I', pvd, 158)[0], struct.unpack_from('<I', pvd, 166)[0]
                self._walk(base, root_lba, root_size, '', found, set())
            self._files = found
        return self._files

    def _walk(self, base, lba, size, prefix, found, seen):
        if (base, lba) in seen or size > 64 * SECTOR * 64:
            return
        seen.add((base, lba))
        data = self._sector(base + lba, (size + SECTOR - 1) // SECTOR)
        offset = 0
        while offset < len(data) and offset < size:
            length = data[offset]
            if length == 0:
                offset = (offset // SECTOR + 1) * SECTOR
                continue
            rec = data[offset:offset + length]
            offset += length
            if len(rec) < 34:
                break
            extent, extent_size = struct.unpack_from('<I', rec, 2)[0], struct.unpack_from('<I', rec, 10)[0]
            name = rec[33:33 + rec[32]]
            if name in (b'\x00', b'\x01'):
                continue
            name = name.decode('ascii', 'replace').split(';')[0]
            if rec[25] & 2:
                self._walk(base, extent, extent_size, prefix + name + '/', found, seen)
            else:
                found.append({'path': prefix + name, 'sector': base + extent, 'size': extent_size})

    def find(self, path):
        wanted = path.replace('\\', '/').strip('/').split(';')[0].upper()
        if ':' in wanted:
            wanted = wanted.split(':', 1)[1].strip('/')
        for entry in self.files():
            if entry['path'].upper() == wanted:
                return entry
        return None

    def read(self, entry, offset=0, size=None):
        size = entry['size'] - offset if size is None else min(size, entry['size'] - offset)
        self.file.seek(entry['sector'] * SECTOR + offset)
        return self.file.read(max(0, size))


def ler_system_cnf(text):
    fields = {}
    for line in text.replace('\r', '').split('\n'):
        key, sep, value = line.partition('=')
        if sep:
            fields[key.strip().upper()] = value.strip()
    return fields


REGIOES = {
    'SLUS': 'EUA', 'SCUS': 'EUA', 'SLES': 'Europa', 'SCES': 'Europa', 'SCED': 'Europa',
    'SLPM': 'Japão', 'SLPS': 'Japão', 'SCPS': 'Japão', 'SLAJ': 'Ásia', 'SCAJ': 'Ásia',
    'SLKA': 'Coreia', 'SCKA': 'Coreia',
}


def nome_do_boot(boot2):
    """cdrom0:\\SLUS_212.67;1 -> ('SLUS_212.67', 'SLUS-21267', 'EUA')"""
    name = boot2.replace('/', '\\').split('\\')[-1].split(';')[0].strip()
    m = re.match(r'^([A-Z]{4})_(\d{3})\.(\d{2})$', name.upper())
    if not m:
        return name, None, None
    prefix, a, b = m.groups()
    return name, '%s-%s%s' % (prefix, a, b), REGIOES.get(prefix)


# ---------------------------------------------------------------- executáveis

ET_IRX = (0xFF80, 0xFF81)


class Elf:
    def __init__(self, data, name=''):
        if data[:4] != b'\x7fELF':
            raise ValueError('%s não é ELF' % name)
        if data[4] != 1 or data[5] != 1:
            raise ValueError('%s não é um ELF de 32 bits little endian, como os do PS2' % name)
        self.data = data
        self.name = name
        (self.type, self.machine, _, self.entry, phoff, shoff, self.flags, _, phentsize, phnum,
         shentsize, shnum, shstrndx) = struct.unpack_from('<HHIIIIIHHHHHH', data, 16)
        self.segments = []
        for i in range(phnum):
            o = phoff + i * phentsize
            if o + 32 > len(data):
                break
            ptype, off, vaddr, _, filesz, memsz, pflags, _ = struct.unpack_from('<8I', data, o)
            self.segments.append({'type': ptype, 'offset': off, 'vaddr': vaddr, 'filesz': filesz, 'memsz': memsz, 'flags': pflags})
        self.sections = []
        if shoff and shnum and shoff + shnum * shentsize <= len(data):
            raw = [struct.unpack_from('<10I', data, shoff + i * shentsize) for i in range(shnum)]
            names_at = raw[shstrndx][4] if shstrndx < len(raw) else 0
            for s in raw:
                name_end = data.find(b'\x00', names_at + s[0])
                self.sections.append({'name': data[names_at + s[0]:name_end].decode('ascii', 'replace'),
                                      'type': s[1], 'addr': s[3], 'offset': s[4], 'size': s[5], 'link': s[6], 'entsize': s[9]})

    @property
    def is_irx(self):
        return self.type in ET_IRX

    @property
    def is_r5900(self):
        return self.machine == 8 and (self.flags & 0x00FF0000) == 0x00920000

    def words(self, start=0, end=None):
        end = len(self.data) if end is None else min(end, len(self.data))
        start -= start % 4
        for o in range(start, end - 3, 4):
            yield o, struct.unpack_from('<I', self.data, o)[0]

    def code_ranges(self):
        ranges = [(s['offset'], s['offset'] + s['filesz'], s['vaddr']) for s in self.segments if s['type'] == 1 and s['flags'] & 1]
        if not ranges:
            ranges = [(s['offset'], s['offset'] + s['filesz'], s['vaddr']) for s in self.segments if s['type'] == 1]
        return ranges

    def functions(self):
        """Símbolos de função (quando o executável não foi 'limpo')."""
        found = {}
        for sec in self.sections:
            if sec['type'] != 2 or not sec['entsize']:  # SHT_SYMTAB
                continue
            strtab = self.sections[sec['link']] if sec['link'] < len(self.sections) else None
            for o in range(sec['offset'], sec['offset'] + sec['size'], sec['entsize']):
                name_off, value, size, info, _, _ = struct.unpack_from('<IIIBBH', self.data, o)
                if info & 0xF != 2 or not strtab:  # STT_FUNC
                    continue
                start = strtab['offset'] + name_off
                name = self.data[start:self.data.find(b'\x00', start)].decode('ascii', 'replace')
                if name:
                    found[value] = name
        return found

    # --- processador principal (EE)

    def syscalls(self):
        """Números de syscall que o código chama: procura `syscall` com `li v1, N` logo antes."""
        counts = {}
        for start, end, _ in self.code_ranges():
            prev = [0, 0, 0]
            for _, w in self.words(start, end):
                if (w & 0xFC00003F) == 0x0000000C:
                    for p in prev:
                        top = p >> 16
                        if top in (0x2403, 0x6403):  # addiu/daddiu v1, zero, N
                            n = p & 0xFFFF
                            n = n - 0x10000 if n & 0x8000 else n
                            counts[n] = counts.get(n, 0) + 1
                            break
                        if top == 0x3403:  # ori v1, zero, N
                            counts[p & 0xFFFF] = counts.get(p & 0xFFFF, 0) + 1
                            break
                prev = [w] + prev[:2]
        return counts

    def strings(self, minimum=5):
        for m in re.finditer(rb'[\x20-\x7e]{%d,}' % minimum, self.data):
            yield m.start(), m.group().decode('ascii')

    # --- módulos do IOP

    def iopmod(self):
        """Nome e versão gravados no próprio módulo (.iopmod)."""
        for s in self.segments:
            if s['type'] == 0x70000080:
                return self._iopmod_at(s['offset'])
        for sec in self.sections:
            if sec['type'] == 0x70000080:
                return self._iopmod_at(sec['offset'])
        return None

    def _iopmod_at(self, o):
        if o + 26 > len(self.data):
            return None
        moduleinfo = struct.unpack_from('<I', self.data, o)[0]
        version = struct.unpack_from('<H', self.data, o + 24)[0]
        end = self.data.find(b'\x00', o + 26)
        name = self.data[o + 26:end].decode('ascii', 'replace')
        if not name and moduleinfo != 0xFFFFFFFF:
            # módulos feitos com o ps2sdk deixam o nome vazio aqui e guardam um ponteiro para ele
            name = self._string_at_vaddr(self._word_at_vaddr(moduleinfo))
        return {'nome': name or None, 'versao': '%d.%d' % (version >> 8, version & 0xFF)}

    def _file_offset(self, vaddr):
        for s in self.segments:
            if s['type'] == 1 and s['vaddr'] <= vaddr < s['vaddr'] + s['filesz']:
                return s['offset'] + vaddr - s['vaddr']
        return None

    def _word_at_vaddr(self, vaddr):
        o = self._file_offset(vaddr)
        return struct.unpack_from('<I', self.data, o)[0] if o is not None and o + 4 <= len(self.data) else None

    def _string_at_vaddr(self, vaddr):
        o = self._file_offset(vaddr) if vaddr is not None else None
        if o is None:
            return ''
        end = self.data.find(b'\x00', o, o + 64)
        text = self.data[o:end if end >= 0 else o + 64]
        return text.decode('ascii', 'replace') if re.match(rb'^[\x20-\x7e]+$', text) else ''

    def iop_imports(self):
        """[(biblioteca, [índices])] das tabelas de importação (magia 0x41E00000)."""
        found = []
        for o, w in self.words():
            if w != 0x41E00000 or o + 20 > len(self.data):
                continue
            library = self.data[o + 12:o + 20].split(b'\x00')[0].decode('ascii', 'replace')
            indexes = []
            stub = o + 20
            while stub + 8 <= len(self.data):
                w0, w1 = struct.unpack_from('<II', self.data, stub)
                if w0 != 0x03E00008 or (w1 & 0xFFFF0000) != 0x24000000:
                    break
                indexes.append(w1 & 0xFFFF)
                stub += 8
            if library and indexes:
                found.append((library, indexes))
        return found

    def iop_exports(self):
        """[(biblioteca, quantidade de funções)] das tabelas de exportação (magia 0x41C00000)."""
        found = []
        for o, w in self.words():
            if w != 0x41C00000 or o + 20 > len(self.data):
                continue
            library = self.data[o + 12:o + 20].split(b'\x00')[0].decode('ascii', 'replace')
            count = 0
            p = o + 20
            while p + 4 <= len(self.data) and struct.unpack_from('<I', self.data, p)[0]:
                count += 1
                p += 4
            if library and re.match(r'^[A-Za-z0-9_]+$', library):
                found.append((library, count))
        return found


# ---------------------------------------------------------------- imagens IOPRP

def romdir(data):
    """Arquivos dentro de uma imagem IOPRP (formato ROMDIR do BIOS). [(nome, bytes)]"""
    start = data.find(b'RESET\x00\x00\x00\x00\x00')
    if start < 0:
        return []
    entries = []
    o = start
    while o + 16 <= len(data):
        name = data[o:o + 10].split(b'\x00')[0].decode('ascii', 'replace')
        if not name:
            break
        size = struct.unpack_from('<I', data, o + 12)[0]
        entries.append((name, size))
        o += 16
    files = []
    at = start
    for name, size in entries:
        files.append((name, data[at:at + size]))
        at += (size + 15) & ~15
    return files


# ---------------------------------------------------------------- cobertura da máquina

def motor_cobertura(engine_dir):
    """O que a máquina de tradução já imita, lido direto do código dela."""
    runtime = os.path.join(engine_dir, 'runtime', 'src')
    if not os.path.isdir(runtime):
        return None
    syscalls = set()
    kernel = open(os.path.join(runtime, 'kernel.cpp'), encoding='utf-8', errors='replace').read()
    body = kernel[kernel.find('void handle_syscall'):]
    body = body[:body.find('default:')]
    for m in re.finditer(r'case\s+(0x[0-9A-Fa-f]+|\d+)\s*:', body):
        syscalls.add(int(m.group(1), 0))
    iop = {}
    libraries = set()
    for folder, _, files in os.walk(runtime):
        for file in files:
            if not file.endswith('.cpp'):
                continue
            text = open(os.path.join(folder, file), encoding='utf-8', errors='replace').read()
            for m in re.finditer(r'\bdef\(\s*"(\w+)"\s*,\s*(\d+)\s*,\s*"(\w+)"', text):
                iop.setdefault(m.group(1), {})[int(m.group(2))] = m.group(3)
            for m in re.finditer(r'register_hle_library\(\s*"(\w+)"', text):
                libraries.add(m.group(1))
    return {'syscalls': syscalls, 'iop': iop, 'bibliotecas': libraries | set(iop)}


def nomes():
    path = os.path.join(HERE, 'dados', 'nomes_ps2.json')
    try:
        import json
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except OSError:
        return {'syscalls_ee': {}, 'bibliotecas_iop': {}}


def nome_syscall(table, n):
    key = '-0x%02X' % -n if n < 0 else '0x%02X' % n
    return table['syscalls_ee'].get(key) or table['syscalls_ee'].get('0x%02X' % abs(n))


def nome_iop(table, library, index):
    return table['bibliotecas_iop'].get(library, {}).get(str(index))


# ---------------------------------------------------------------- imagens

def ler_ppm(path):
    with open(path, 'rb') as f:
        data = f.read()
    m = re.match(rb'P6\s+(\d+)\s+(\d+)\s+255\s', data)
    if not m:
        raise ValueError('%s não é um PPM binário de 8 bits' % path)
    width, height = int(m.group(1)), int(m.group(2))
    return width, height, data[m.end():m.end() + width * height * 3]


def salvar_png(path, width, height, rgb):
    def chunk(kind, body):
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xFFFFFFFF)
    stride = width * 3
    raw = b''.join(b'\x00' + rgb[y * stride:(y + 1) * stride] for y in range(height))
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')
    with open(path, 'wb') as f:
        f.write(png)
