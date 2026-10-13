#!/usr/bin/env python3
"""Serve a versão web do jogo e o disco, do jeito que o navegador exige.

A página usa várias tarefas em paralelo (SharedArrayBuffer), então precisa dos
cabeçalhos COOP e COEP. O disco é lido em pedaços (HTTP Range): só o executável
desce inteiro, o resto vem conforme o jogo pede. Tudo fica na sua máquina.

uso: servir.py <pasta da versão web> <disco.iso> [--porta 8620] [--host 127.0.0.1]
"""

import argparse
import http.server
import os
import re
import shutil

TIPOS = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.wasm': 'application/wasm',
         '.data': 'application/octet-stream', '.png': 'image/png', '.svg': 'image/svg+xml', '.ico': 'image/x-icon'}


def handler(build, disc):
    class Handler(http.server.BaseHTTPRequestHandler):
        def alvo(self):
            path = self.path.split('?', 1)[0]
            if path in ('/', '/index.html'):
                path = '/ps2web.html'
            if path == '/disc.iso':
                return disc
            name = os.path.normpath(path.lstrip('/'))
            if name.startswith('..') or os.sep in name:
                return None
            full = os.path.join(build, name)
            return full if os.path.isfile(full) else None

        def cabecalhos(self, path, length, encoding=None):
            self.send_header('Content-Type', TIPOS.get(os.path.splitext(path)[1], 'application/octet-stream'))
            if encoding:
                self.send_header('Content-Encoding', encoding)
                self.send_header('Vary', 'Accept-Encoding')
            self.send_header('Content-Length', str(length))
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
            self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
            self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
            self.end_headers()

        def do_HEAD(self):
            path = self.alvo()
            if not path:
                self.send_error(404)
                return
            self.send_response(200)
            self.cabecalhos(path, os.path.getsize(path))

        def do_GET(self):
            path = self.alvo()
            if not path:
                self.send_error(404)
                return
            packed = path + '.gz'
            if ('Range' not in self.headers and 'gzip' in self.headers.get('Accept-Encoding', '')
                    and os.path.isfile(packed) and os.path.getmtime(packed) >= os.path.getmtime(path)):
                self.send_response(200)
                self.cabecalhos(path, os.path.getsize(packed), 'gzip')
                with open(packed, 'rb') as f:
                    shutil.copyfileobj(f, self.wfile, 1 << 20)
                return
            size = os.path.getsize(path)
            start, end = 0, size - 1
            m = re.match(r'bytes=(\d+)-(\d*)', self.headers.get('Range', ''))
            if m:
                start = int(m.group(1))
                end = min(int(m.group(2)) if m.group(2) else size - 1, size - 1)
                if start > end:
                    self.send_error(416)
                    return
                self.send_response(206)
                self.send_header('Content-Range', 'bytes %d-%d/%d' % (start, end, size))
            else:
                self.send_response(200)
            self.cabecalhos(path, end - start + 1)
            with open(path, 'rb') as f:
                f.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = f.read(min(left, 1 << 20))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)

        def log_message(self, fmt, *args):
            pass

    return Handler


def main():
    parser = argparse.ArgumentParser(description='Serve a versão web do jogo.')
    parser.add_argument('build')
    parser.add_argument('disco')
    parser.add_argument('--porta', type=int, default=8620)
    parser.add_argument('--host', default='127.0.0.1')
    args = parser.parse_args()
    build, disc = os.path.abspath(args.build), os.path.abspath(args.disco)
    for path in (os.path.join(build, 'ps2web.html'), disc):
        if not os.path.isfile(path):
            raise SystemExit('não achei %s' % path)
    server = http.server.ThreadingHTTPServer((args.host, args.porta), handler(build, disc))
    print('Bola rolando em http://localhost:%d/  (Ctrl+C encerra)' % args.porta, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
