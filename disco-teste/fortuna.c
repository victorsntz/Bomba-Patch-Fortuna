/*
 * Disco de Teste Fortuna
 *
 * Um programinha de PS2 feito do zero (código aberto, sem nada da Konami) para
 * testar a máquina de tradução antes de usar o disco do Bomba Patch. Desenha um
 * campo, um placar e uma bola. A bola anda sozinha até alguém mexer no controle;
 * quando entra no gol, o placar sobe.
 *
 * Ele carrega os módulos do controle do próprio disco (cdrom0:\MODULES\...), do
 * mesmo jeito que o PES faz, então também testa esse caminho.
 */

#include <kernel.h>
#include <sifrpc.h>
#include <loadfile.h>
#include <libpad.h>
#include <gsKit.h>
#include <dmaKit.h>
#include <string.h>

static char pad_area[256] __attribute__((aligned(64)));

#define RGB(r, g, b) GS_SETREG_RGBAQ(r, g, b, 0x80, 0x00)

/* paleta: verde de gramado, dourado de taça, branco de cal e o azul da noite de jogo */
#define GRAMA_A RGB(0x0B, 0x6B, 0x3A)
#define GRAMA_B RGB(0x09, 0x5E, 0x33)
#define CAL     RGB(0xF4, 0xF1, 0xE8)
#define OURO    RGB(0xF2, 0xC2, 0x30)
#define NOITE   RGB(0x0A, 0x1F, 0x44)
#define BRASA   RGB(0xFF, 0x4D, 0x2E)

/* fonte 5x7: cada linha é um byte, bits 4..0 da esquerda para a direita */
static const struct { char c; unsigned char rows[7]; } FONT[] = {
    {'A', {0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11}}, {'B', {0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E}},
    {'C', {0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E}}, {'D', {0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E}},
    {'E', {0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F}}, {'F', {0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10}},
    {'G', {0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F}}, {'I', {0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E}},
    {'L', {0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F}}, {'M', {0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11}},
    {'N', {0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11}}, {'O', {0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E}},
    {'P', {0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10}}, {'R', {0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11}},
    {'S', {0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E}}, {'T', {0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04}},
    {'U', {0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E}}, {'X', {0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11}},
    {'0', {0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E}}, {'1', {0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E}},
    {'2', {0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F}}, {'3', {0x1F, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0E}},
    {'4', {0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02}}, {'5', {0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E}},
    {'6', {0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E}}, {'7', {0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08}},
    {'8', {0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E}}, {'9', {0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C}},
    {'!', {0x04, 0x04, 0x04, 0x04, 0x04, 0x00, 0x04}},
};

static const unsigned char *glyph(char c)
{
    for (unsigned i = 0; i < sizeof(FONT) / sizeof(FONT[0]); i++)
        if (FONT[i].c == c) return FONT[i].rows;
    return 0;
}

static void text(GSGLOBAL *gs, const char *s, float x, float y, float px, u64 color)
{
    for (; *s; s++, x += 6 * px) {
        const unsigned char *rows = glyph(*s);
        if (!rows) continue;
        for (int r = 0; r < 7; r++)
            for (int c = 0; c < 5; c++)
                if (rows[r] & (0x10 >> c))
                    gsKit_prim_sprite(gs, x + c * px, y + r * px, x + (c + 1) * px, y + (r + 1) * px, 2, color);
    }
}

static float text_width(const char *s, float px) { return strlen(s) * 6 * px - px; }

static void rect_outline(GSGLOBAL *gs, float x1, float y1, float x2, float y2, float w, u64 color)
{
    gsKit_prim_sprite(gs, x1, y1, x2, y1 + w, 1, color);
    gsKit_prim_sprite(gs, x1, y2 - w, x2, y2, 1, color);
    gsKit_prim_sprite(gs, x1, y1, x1 + w, y2, 1, color);
    gsKit_prim_sprite(gs, x2 - w, y1, x2, y2, 1, color);
}

/* círculos feitos de faixas horizontais, como pixel art. Sem triângulo e sem libm */
static int isqrt(int v)
{
    int r = 0;
    while ((r + 1) * (r + 1) <= v) r++;
    return r;
}

static void disc(GSGLOBAL *gs, float cx, float cy, int r, u64 color)
{
    for (int dy = -r; dy < r; dy++) {
        int y = dy < 0 ? dy + 1 : dy;
        int half = isqrt(r * r - y * y);
        gsKit_prim_sprite(gs, cx - half, cy + dy, cx + half, cy + dy + 1, 3, color);
    }
}

static void ring(GSGLOBAL *gs, float cx, float cy, int r, int w, u64 color)
{
    int inner = r - w;
    for (int dy = -r; dy < r; dy++) {
        int y = dy < 0 ? dy + 1 : dy;
        int outer_half = isqrt(r * r - y * y);
        int inner_half = y * y < inner * inner ? isqrt(inner * inner - y * y) : 0;
        if (inner_half == 0) {
            gsKit_prim_sprite(gs, cx - outer_half, cy + dy, cx + outer_half, cy + dy + 1, 1, color);
        } else {
            gsKit_prim_sprite(gs, cx - outer_half, cy + dy, cx - inner_half, cy + dy + 1, 1, color);
            gsKit_prim_sprite(gs, cx + inner_half, cy + dy, cx + outer_half, cy + dy + 1, 1, color);
        }
    }
}

static int pad_ready;

static void start_pad(void)
{
    SifInitRpc(0);
    int a = SifLoadModule("cdrom0:\\MODULES\\SIO2MAN.IRX;1", 0, NULL);
    int b = SifLoadModule("cdrom0:\\MODULES\\PADMAN.IRX;1", 0, NULL);
    if (a < 0 || b < 0) return;
    padInit(0);
    pad_ready = padPortOpen(0, 0, pad_area) != 0;
}

static u32 read_pad(void)
{
    struct padButtonStatus status;
    if (!pad_ready) return 0;
    if (padGetState(0, 0) != PAD_STATE_STABLE) return 0;
    if (padRead(0, 0, &status) == 0) return 0;
    /* tudo apertado ao mesmo tempo é leitura de controle ainda acordando, não jogada */
    if (status.btns == 0) return 0;
    return 0xffff ^ status.btns;
}

int main(void)
{
    start_pad();

    GSGLOBAL *gs = gsKit_init_global();
    gs->PrimAlphaEnable = GS_SETTING_OFF;
    gs->ZBuffering = GS_SETTING_OFF;
    gs->DoubleBuffering = GS_SETTING_ON;
    dmaKit_init(D_CTRL_RELE_OFF, D_CTRL_MFD_OFF, D_CTRL_STS_UNSPEC, D_CTRL_STD_OFF, D_CTRL_RCYC_8, 1 << DMA_CHANNEL_GIF);
    dmaKit_chan_init(DMA_CHANNEL_GIF);
    gsKit_init_screen(gs);
    gsKit_mode_switch(gs, GS_ONESHOT);

    const float W = gs->Width, H = gs->Height;
    const float top = 64, left = 40, right = W - 40, bottom = H - 24;
    const float mid_x = (left + right) / 2, mid_y = (top + bottom) / 2;
    const float goal_half = 40;

    float bx = mid_x, by = mid_y, vx = 2.6f, vy = 1.7f;
    int home = 0, away = 0, celebrate = 0, manual = 0, frame = 0;
    char score[8];

    for (;;) {
        u32 buttons = read_pad();
        if (buttons) manual = 1;
        if (manual) {
            vx = vy = 0;
            if (buttons & PAD_LEFT) vx = -4;
            if (buttons & PAD_RIGHT) vx = 4;
            if (buttons & PAD_UP) vy = -4;
            if (buttons & PAD_DOWN) vy = 4;
            if (buttons & PAD_CROSS) { vx *= 2; vy *= 2; }
        }
        bx += vx;
        by += vy;
        if (by < top + 8) { by = top + 8; vy = -vy; }
        if (by > bottom - 8) { by = bottom - 8; vy = -vy; }
        int in_goal_mouth = by > mid_y - goal_half && by < mid_y + goal_half;
        if (bx < left + 8 || bx > right - 8) {
            if (in_goal_mouth && !celebrate) {
                if (bx > mid_x) home++; else away++;
                celebrate = 90;
                bx = mid_x;
                by = mid_y;
            } else {
                bx = bx < mid_x ? left + 8 : right - 8;
                vx = -vx;
            }
        }

        gsKit_clear(gs, NOITE);
        for (int i = 0; i < 10; i++) {
            float x1 = left + (right - left) * i / 10, x2 = left + (right - left) * (i + 1) / 10;
            gsKit_prim_sprite(gs, x1, top, x2, bottom, 0, (i & 1) ? GRAMA_B : GRAMA_A);
        }
        rect_outline(gs, left, top, right, bottom, 3, CAL);
        gsKit_prim_sprite(gs, mid_x - 1.5f, top, mid_x + 1.5f, bottom, 1, CAL);
        ring(gs, mid_x, mid_y, 46, 3, CAL);
        rect_outline(gs, left, mid_y - 90, left + 70, mid_y + 90, 3, CAL);
        rect_outline(gs, right - 70, mid_y - 90, right, mid_y + 90, 3, CAL);
        gsKit_prim_sprite(gs, left - 10, mid_y - goal_half, left, mid_y + goal_half, 1, OURO);
        gsKit_prim_sprite(gs, right, mid_y - goal_half, right + 10, mid_y + goal_half, 1, OURO);

        /* placar: FORTUNA à esquerda, gols no meio, modo à direita */
        gsKit_prim_sprite(gs, 0, 0, W, 48, 1, NOITE);
        gsKit_prim_sprite(gs, 0, 46, W, 50, 1, OURO);
        text(gs, "FORTUNA", 24, 12, 3, OURO);
        score[0] = '0' + home % 10; score[1] = ' '; score[2] = 'X'; score[3] = ' '; score[4] = '0' + away % 10; score[5] = 0;
        text(gs, score, (W - text_width(score, 3)) / 2, 12, 3, CAL);
        const char *mode = manual ? "CONTROLE" : (pad_ready ? "AUTO" : "SEM PAD");
        text(gs, mode, W - 24 - text_width(mode, 2), 17, 2, (frame / 30) & 1 ? CAL : OURO);

        disc(gs, bx + 2, by + 3, 8, RGB(0x05, 0x40, 0x22));
        disc(gs, bx, by, 8, CAL);

        if (celebrate) {
            celebrate--;
            float s = 8;
            text(gs, "GOL!", (W - text_width("GOL!", s)) / 2, mid_y - 3.5f * s, s, (celebrate / 6) & 1 ? OURO : BRASA);
        }

        gsKit_queue_exec(gs);
        gsKit_sync_flip(gs);
        frame++;
    }
    return 0;
}
