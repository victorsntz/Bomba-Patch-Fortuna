#!/usr/bin/env python3
"""Gera overlay/web/shell.html: a página do jogo com a cara Fortuna.

Parte da página original do motor (engine/web/shell.html no commit fixado em
UPSTREAM.lock, licença MIT) e troca só visual e textos. Toda a lógica de jogo,
controle, áudio e memory card continua a do motor. Se o motor mudar e algum
trecho não bater mais, o script para e diz qual, em vez de gerar algo quebrado.

uso: gerar_cara.py   (precisa da pasta engine/ preparada)
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'overlay', 'web', 'shell.html')

ESTILO = '''<style>
  :root {
    color-scheme: dark;
    --noite: #0a1f44; --noite-funda: #06132b; --grama: #0b6b3a; --grama-2: #095e33;
    --ouro: #f2c230; --cal: #f4f1e8; --brasa: #ff4d2e; --linha: rgba(244, 241, 232, 0.16);
    --texto: #e9e6dc; --texto-fraco: #a9b4c8;
  }
  html, body { margin: 0; height: 100%; background: var(--noite-funda); color: var(--texto); font: 14px system-ui, -apple-system, "Segoe UI", sans-serif; }
  body { display: flex; flex-direction: column; }
  #stage { flex: 1; display: flex; align-items: center; justify-content: center; min-height: 0; }
  canvas { width: 100%; height: 100%; display: block; background: #000; }
  #bar { display: flex; flex-wrap: wrap; gap: 10px 14px; align-items: center; padding: 8px 14px; background: var(--noite); border-top: 3px solid var(--ouro); }
  #bar::before { content: "FORTUNA"; font: italic 900 15px "Arial Black", "Helvetica Neue", system-ui, sans-serif; letter-spacing: 0.06em; color: var(--ouro); }
  #status { flex: 1; min-width: 160px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  #stats { font-variant-numeric: tabular-nums; color: var(--texto-fraco); font-size: 12px; }
  select, button { font: inherit; }
  select { background: var(--noite-funda); color: var(--cal); border: 1px solid var(--linha); padding: 6px 8px; border-radius: 6px; }
  button { background: transparent; color: var(--cal); border: 1px solid var(--linha); padding: 7px 14px; border-radius: 6px; cursor: pointer; }
  button:hover { border-color: var(--ouro); color: var(--ouro); }
  #overlay {
    position: fixed; inset: 0; display: flex; align-items: center; justify-content: center; padding: 16px; z-index: 2;
    background:
      radial-gradient(ellipse at center, rgba(6, 19, 43, 0.35) 0%, rgba(6, 19, 43, 0.92) 70%),
      repeating-linear-gradient(90deg, var(--grama) 0 80px, var(--grama-2) 80px 160px);
  }
  #panel { display: flex; flex-direction: column; align-items: center; gap: 18px; max-width: 560px; width: 100%; text-align: center; }
  .marca { display: flex; flex-direction: column; align-items: center; line-height: 0.92; transform: skew(-8deg); }
  .marca .bomba { font: 900 clamp(22px, 5vw, 34px) "Arial Black", "Helvetica Neue", system-ui, sans-serif; letter-spacing: 0.08em; color: var(--cal); }
  .marca .fortuna { font: 900 clamp(48px, 13vw, 92px) "Arial Black", "Helvetica Neue", system-ui, sans-serif; letter-spacing: 0.02em; color: var(--ouro); text-shadow: 0 4px 0 var(--noite-funda); }
  .sub { margin: 0; color: var(--texto); opacity: 0.85; }
  #help { margin: 0; line-height: 1.5; color: var(--ouro); background: rgba(6, 19, 43, 0.75); padding: 10px 14px; border-radius: 8px; border-left: 3px solid var(--brasa); text-align: left; }
  #start {
    background: var(--ouro); color: var(--noite-funda); border: 0; border-radius: 999px; padding: 14px 34px;
    font: 900 18px "Arial Black", "Helvetica Neue", system-ui, sans-serif; letter-spacing: 0.04em; text-transform: uppercase;
    box-shadow: 0 6px 0 #b8901c; transition: transform 0.08s ease, box-shadow 0.08s ease;
  }
  #start:hover:not(:disabled) { color: var(--noite-funda); transform: translateY(-1px); }
  #start:active:not(:disabled) { transform: translateY(4px); box-shadow: 0 2px 0 #b8901c; }
  #start:disabled { background: rgba(244, 241, 232, 0.15); color: var(--texto-fraco); box-shadow: none; cursor: default; }
  .teclas { display: grid; grid-template-columns: auto 1fr auto 1fr; gap: 6px 12px; margin: 0; padding: 12px 16px; font-size: 13px; text-align: left;
    background: rgba(6, 19, 43, 0.75); border: 1px solid var(--linha); border-radius: 10px; }
  .teclas dt { color: var(--ouro); font-weight: 700; white-space: nowrap; }
  .teclas dd { margin: 0; color: var(--texto); }
  @media (max-width: 520px) { .teclas { grid-template-columns: auto 1fr; } }
  body.touch .teclas { display: none; }
  .controls { display: none; }'''

LEGENDA = '''<dl class="teclas" aria-label="Controles no teclado">
    <dt>Setas</dt><dd>direcional</dd><dt>I J K L</dt><dd>analógico</dd>
    <dt>Z · ✕</dt><dd>passe · volta</dd><dt>X · ○</dt><dd>lançamento · confirma</dd>
    <dt>A · □</dt><dd>chute</dd><dt>S · △</dt><dd>enfiada</dd>
    <dt>W · R1</dt><dd>disparada</dd><dt>Q · L1</dt><dd>trocar jogador</dd>
    <dt>Enter</dt><dd>start</dd><dt>F</dt><dd>tela cheia</dd>
    <dt>🎮 1</dt><dd>jogador 1</dd><dt>🎮 2</dt><dd>jogador 2</dd>
  </dl>'''

# leitura dos controles para dois jogadores: teclado, toque e o primeiro controle são o jogador 1; o segundo controle
# é o jogador 2, e a porta 2 do PS2 só liga quando ele aparece (precisa do patches/0004 no motor)
CONTROLES_INICIO = "let lastPad = -1, lastPressure = '', lastStrong = 0, lastWeak = 0, rumbleAt = 0;"
CONTROLES_FIM = '// some browsers cannot show a canvas'
CONTROLES = r"""const portas = [0, 1].map(() => ({ ultimo: -1, pressao: '', forte: 0, fraco: 0, vibrouEm: 0 }));
let segundoLigado = false;
const motorStrength = (v) => v < 16 ? 0 : Math.sqrt(v / 255);
window.addEventListener('gamepadconnected', (e) => {
  const lista = navigator.getGamepads ? Array.from(navigator.getGamepads()).filter(Boolean) : [];
  note(lista.length > 1 ? 'Controle 2 conectado: Jogador 2 em campo' : 'Controle conectado: Jogador 1 (' + e.gamepad.id.split('(')[0].trim() + ')');
});
function lerControle(pad, base) {
  const s = { buttons: base.buttons, lx: base.lx, ly: base.ly, rx: 128, ry: 128, pressure: new Array(16).fill(255) };
  for (const [index, bit] of padButtons) {
    const b = pad.buttons[index];
    if (!b || !(b.pressed || b.value > 0.05)) continue;
    s.buttons |= 1 << bit;
    if (!(base.buttons & (1 << bit))) s.pressure[bit] = Math.max(1, Math.round((b.value > 0 ? b.value : 1) * 255));
  }
  if (pad.axes.length >= 4) {
    if (s.lx === 128) s.lx = axis(pad.axes[0]);
    if (s.ly === 128) s.ly = axis(pad.axes[1]);
    s.rx = axis(pad.axes[2]);
    s.ry = axis(pad.axes[3]);
  }
  return s;
}
function enviar(porta, s, gamepad) {
  const p = portas[porta];
  const state = s.buttons + s.lx * 65536 + s.ly * 16777216 + s.rx * 4294967296 + s.ry * 1099511627776;
  if (state !== p.ultimo) {
    p.ultimo = state;
    Module._ps2web_pad_at(porta, s.buttons, s.lx, s.ly, s.rx, s.ry);
  }
  const packed = [0, 1, 2, 3].map((i) => s.pressure[i * 4] | (s.pressure[i * 4 + 1] << 8) | (s.pressure[i * 4 + 2] << 16) | (s.pressure[i * 4 + 3] << 24));
  if (packed.join() !== p.pressao) {
    p.pressao = packed.join();
    Module._ps2web_pressure_at(porta, packed[0], packed[1], packed[2], packed[3]);
  }
  const rumble = Module._ps2web_rumble_at(porta), now = performance.now();
  const strong = motorStrength(rumble >> 8), weak = rumble & 1;
  const actuator = gamepad && gamepad.vibrationActuator;
  if (actuator && (Math.abs(strong - p.forte) > 0.08 || weak !== p.fraco || ((strong || weak) && now - p.vibrouEm > 100))) {
    p.forte = strong;
    p.fraco = weak;
    p.vibrouEm = now;
    const done = strong || weak ? actuator.playEffect('dual-rumble', { duration: 200, weakMagnitude: weak, strongMagnitude: strong }) : actuator.reset();
    if (done && done.catch) done.catch(() => {});
  }
}
function pollInput() {
  let buttons = touchPad.buttons, lx = 128, ly = 128;
  for (const k of keys) if (k in keyMap) buttons |= 1 << keyMap[k];
  if (keys.has('KeyJ')) lx = 0;
  if (keys.has('KeyL')) lx = 255;
  if (keys.has('KeyI')) ly = 0;
  if (keys.has('KeyK')) ly = 255;
  if (touchPad.stick) {
    lx = axis(touchPad.x);
    ly = axis(touchPad.y);
  }
  const pads = navigator.getGamepads ? Array.from(navigator.getGamepads()).filter(Boolean) : [];
  const jogador1 = pads[0] ? lerControle(pads[0], { buttons, lx, ly })
                           : { buttons, lx, ly, rx: 128, ry: 128, pressure: new Array(16).fill(255) };
  enviar(0, jogador1, pads[0]);
  const querSegundo = pads.length > 1;
  if (querSegundo !== segundoLigado) {
    segundoLigado = querSegundo;
    Module._ps2web_pad_connected(1, querSegundo ? 1 : 0);
    if (!querSegundo) note('Controle 2 saiu: Jogador 2 no banco');
  }
  if (querSegundo) enviar(1, lerControle(pads[1], { buttons: 0, lx: 128, ly: 128 }), pads[1]);
}

"""

TROCAS = [
    ('<html lang="en">', '<html lang="pt-BR">'),
    ('<title>ps2-web-recomp</title>', '<title>Bomba Patch Fortuna</title>\n<meta name="theme-color" content="#0a1f44">'),
    # o estilo inteiro até as regras dos controles de toque, que ficam como estão
    (None, None),
    ('controles', None),
    ('<span id="status">Loading…</span>', '<span id="status">Aquecendo…</span>'),
    ('title="Internal resolution, the page reloads to apply it"', 'title="Resolução interna. A página recarrega para aplicar"'),
    ('aria-label="Resolution"', 'aria-label="Resolução"'),
    ('<button id="controls-toggle" type="button" hidden>Hide controls</button>', '<button id="controls-toggle" type="button" hidden>Esconder controles</button>'),
    ('title="Download the memory card in slot 1 as a .ps2 file">Export card</button>', 'title="Baixa o memory card do slot 1 como arquivo .ps2">Salvar memory card</button>'),
    ('title="Put a .ps2 memory card file in slot 1">Import card</button>', 'title="Coloca um arquivo .ps2 no slot 1">Carregar memory card</button>'),
    ('title="Fullscreen (F or double click)">Fullscreen</button>', 'title="Tela cheia (F ou clique duplo)">Tela cheia</button>'),
    ('<button id="exit-fullscreen" type="button">Exit fullscreen</button>', '<button id="exit-fullscreen" type="button">Sair da tela cheia</button>'),
    ('<div id="overlay"><div id="panel"><p id="help" hidden></p><button id="start" disabled>Loading…</button></div></div>',
     '<div id="overlay"><div id="panel">\n  <div class="marca" aria-label="Bomba Patch Fortuna"><span class="bomba">BOMBA PATCH</span><span class="fortuna">FORTUNA</span></div>\n'
     '  <p class="sub">Traduzido do PS2 para o navegador. Sem emulador.</p>\n  <p id="help" hidden></p>\n'
     '  <button id="start" disabled>Aquecendo…</button>\n  ' + LEGENDA + '\n</div></div>'),
    ("note('Nothing saved on the memory card yet');", "note('O memory card ainda está vazio');"),
    ("note('That is not an 8 MB PS2 memory card image (' + CARD_BYTES + ' bytes)');", "note('Esse arquivo não é um memory card de PS2 de 8 MB (' + CARD_BYTES + ' bytes)');"),
    ("note('That file is not a formatted PS2 memory card');", "note('Esse arquivo não é um memory card de PS2 formatado');"),
    ("if (!confirm('Replace the memory card in slot 1 with ' + file.name + '? The page reloads to use it.')) return;",
     "if (!confirm('Trocar o memory card do slot 1 por ' + file.name + '? A página recarrega para usar.')) return;"),
    ("note('Import failed: ' + e.message);", "note('Não deu para carregar: ' + e.message);"),
    ("missing.push('cross-origin isolation (COOP and COEP headers)');", "missing.push('isolamento de origem (cabeçalhos COOP e COEP; abra pelo ./fortuna jogar)');"),
    ("missing.push('WebAssembly exception handling (try_table)');", "missing.push('exceções de WebAssembly (try_table)');"),
    ("missing.push('WebAssembly tail calls');", "missing.push('chamadas de cauda de WebAssembly');"),
    ("controlsButton.textContent = hideControls ? 'Show controls' : 'Hide controls';", "controlsButton.textContent = hideControls ? 'Mostrar controles' : 'Esconder controles';"),
    ("fullscreenButton.textContent = on ? 'Exit fullscreen' : 'Fullscreen';", "fullscreenButton.textContent = on ? 'Sair da tela cheia' : 'Tela cheia';"),
    ("if (firefox) return 'WebGPU is turned off in this Firefox, so the game runs on the slow software renderer. Set dom.webgpu.enabled to true in about:config and reload.';",
     "if (firefox) return 'O WebGPU está desligado neste Firefox, então o jogo desenha pela CPU e fica lento. Em about:config, ligue dom.webgpu.enabled e recarregue.';"),
    ("if (linux && onCpu) return 'WebGPU runs on the CPU here, so the game is slow. Turn on chrome://flags/#enable-vulkan as well, then restart the browser.';",
     "if (linux && onCpu) return 'Aqui o WebGPU roda pela CPU e o jogo fica lento. Ligue também chrome://flags/#enable-vulkan e reinicie o navegador.';"),
    ("if (linux) return 'WebGPU is turned off in this browser, so the game runs on the slow software renderer. Turn on chrome://flags/#enable-unsafe-webgpu and chrome://flags/#enable-vulkan, then restart the browser.';",
     "if (linux) return 'O WebGPU está desligado neste navegador e o jogo vai desenhar pela CPU, devagar. Ligue chrome://flags/#enable-unsafe-webgpu e chrome://flags/#enable-vulkan e reinicie o navegador.';"),
    ("return 'This browser has no WebGPU, so the game runs on the slow software renderer. A current Chrome, Edge or Safari is much faster.';",
     "return 'Este navegador não tem WebGPU, então o jogo desenha pela CPU e fica lento. Chrome, Edge ou Safari atualizados são bem mais rápidos.';"),
    ("return 'WebGPU unavailable, software renderer';", "return 'sem WebGPU, desenho pela CPU';"),
    ("return 'WebGPU has no adapter, software renderer';", "return 'WebGPU sem placa de vídeo, desenho pela CPU';"),
    ("return 'Firefox, frames copied to the page';", "return 'Firefox, quadros copiados para a página';"),
    ("return 'GPU cannot draw to the page, copying frames';", "return 'a placa não desenha direto na página, copiando quadros';"),
    ("statusEl.textContent = progress ? 'Downloading game data, ' + (Number(progress[1]) / 1048576).toFixed(1) + ' MB unpacked' : text;",
     "statusEl.textContent = progress ? 'Baixando o jogo, ' + (Number(progress[1]) / 1048576).toFixed(1) + ' MB' : text;"),
    ("start.textContent = 'Start';", "start.textContent = 'Apito inicial';"),
    ("statusEl.textContent = (Module.discSize ? 'Disc ' + (Module.discSize / 1073741824).toFixed(2) + ' GB' : 'No disc image at ' + Module.discUrl) + ', ' + gpu;",
     "statusEl.textContent = (Module.discSize ? 'Disco de ' + (Module.discSize / 1073741824).toFixed(2) + ' GB' : 'Sem disco em ' + Module.discUrl) + ', ' + gpu;"),
    ("help.textContent = 'This browser cannot run the game yet. It lacks ' + missing.join(', ') + '. A current Chrome or Edge has everything it needs.';",
     "help.textContent = 'Este navegador ficou no banco de reservas: falta ' + missing.join(', ') + '. Chrome ou Edge atualizados têm tudo.';"),
    ("document.getElementById('start').textContent = 'Unsupported browser';", "document.getElementById('start').textContent = 'Navegador no banco';"),
    ("statusEl.textContent = 'Running, ' + Module.gpuInfo;", "statusEl.textContent = 'Bola rolando, ' + Module.gpuInfo;"),
    ("statsEl.textContent = 'frame ' + Module._ps2web_frames() + '   ' + (frames * 1000 / span).toFixed(1) + ' fps (' + (shown * 1000 / span).toFixed(0) + ' on screen)   GPU '",
     "statsEl.textContent = 'quadro ' + Module._ps2web_frames() + '   ' + (frames * 1000 / span).toFixed(1) + ' fps (' + (shown * 1000 / span).toFixed(0) + ' na tela)   GPU '"),
]


def original():
    engine = os.path.join(ROOT, 'engine')
    try:
        return subprocess.run(['git', '-C', engine, 'show', 'HEAD:web/shell.html'], check=True, capture_output=True, text=True).stdout
    except (OSError, subprocess.CalledProcessError):
        sys.exit('preciso da pasta engine/ preparada (./fortuna preparar)')


def main():
    html = original()
    for old, new in TROCAS:
        if old == 'controles':
            start, end = html.index(CONTROLES_INICIO), html.index(CONTROLES_FIM)
            html = html[:start] + CONTROLES + html[end:]
            continue
        if old is None:
            start = html.index('<style>')
            end = html.index('  .controls { display: none; }') + len('  .controls { display: none; }')
            html = html[:start] + ESTILO + html[end:]
            continue
        if html.count(old) != 1:
            sys.exit('o trecho mudou no motor e não bate mais:\n  %s' % old[:120])
        html = html.replace(old, new)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        doctype = '<!doctype html>\n'
        assert html.startswith(doctype)
        f.write(doctype + '<!-- Gerado por tools/gerar_cara.py a partir de web/shell.html do ps2-web-recomp (MIT, Samir Nuri). -->\n' + html[len(doctype):])
    print('%s gerado (%d trocas)' % (os.path.relpath(OUT, ROOT), len(TROCAS)))


if __name__ == '__main__':
    main()
