#include "mode.h"
#include "resources.h"

static GameMode s_mode;
static ModeAssets s_original;
static ModeAssets s_md;
static const ModeAssets *s_cur;

#define LETTER_TILE     TILE_USER_INDEX

static void load_letter_tile(void)
{
    /* Color 1 = black (color 0 is always transparent on MD). */
    static const u32 black[8] = {
        0x11111111, 0x11111111, 0x11111111, 0x11111111,
        0x11111111, 0x11111111, 0x11111111, 0x11111111
    };

    VDP_loadTileData(black, LETTER_TILE, 1, CPU);
    PAL_setColor(1, RGB24_TO_VDPCOLOR(0x000000));
}

void mode_init(void)
{
    s_original.ship = &spr_ship;
    s_original.screen_width = 256;
    s_original.playfield_w = 256;
    s_original.playfield_h = 192;
    s_original.y_off = 16;
    s_original.name = "ORIGINAL";

    s_md.ship = &spr_ship;
    s_md.screen_width = 320;
    s_md.playfield_w = 320;
    s_md.playfield_h = 224;
    s_md.y_off = 0;
    s_md.name = "ZANAC MD";

    s_mode = MODE_ZANAC_MD;
    s_cur = &s_md;
}

void mode_set(GameMode mode)
{
    s_mode = mode;
    s_cur = (mode == MODE_ORIGINAL) ? &s_original : &s_md;
}

GameMode mode_get(void)
{
    return s_mode;
}

const ModeAssets *mode_assets(void)
{
    return s_cur;
}

s16 mode_draw_y(s16 y)
{
    return (s16)(y + (s16)s_cur->y_off);
}

s16 mode_draw_x(s16 x, u8 sat_col)
{
    /* TMS9918 SAT colour bit7 = Early Clock: hardware draws at SAT_X-32.
     * Ship, shots, and EC enemies all use this so SAT overlap = graphic
     * overlap. Collision never calls this (4560 is SAT vs SAT). */
    if (s_mode == MODE_ORIGINAL && (sat_col & 0x80))
        return (s16)(x - 32);
    return x;
}

u16 mode_letter_attr(void)
{
    return TILE_ATTR_FULL(PAL0, TRUE, FALSE, FALSE, LETTER_TILE);
}

int mode_hud_overlap(s16 draw_x, u16 width)
{
    s16 bar;
    s16 right;

    if (s_mode != MODE_ORIGINAL)
        return 0;
    bar = (s16)MODE_BAR_PX;
    if (draw_x >= bar)
        return 1;
    right = (s16)(draw_x + (s16)width);
    return (right > bar);
}

u16 mode_y_off(void)
{
    return s_cur->y_off;
}

u16 mode_text_row(u16 msx_row)
{
    return (u16)(msx_row + (s_cur->y_off / 8));
}

void mode_apply_video(void)
{
    if (s_mode == MODE_ORIGINAL)
    {
        VDP_setScreenWidth256();
        /* L-window: rows 0-1 full width (16px letterbox) so BG_B wrap/peek
         * in NT 31 cannot show through a transparent BG_A cell. Rows 2-27
         * keep the right 8 tiles (WHP 12 = col 24). Bottom 16px stays BG_A. */
        VDP_setWindowHPos(TRUE, 12);
        VDP_setWindowVPos(FALSE, 2);
        load_letter_tile();
        PAL_setColor(0, RGB24_TO_VDPCOLOR(0x000000));
        VDP_setBackgroundColor(0);
    }
    else
    {
        VDP_setWindowOff();
        VDP_setScreenWidth320();
    }
}

void mode_draw_letterbox(void)
{
    u16 attr;

    if (s_mode != MODE_ORIGINAL)
        return;

    attr = mode_letter_attr();
    /* Screen rows 0-1 and 26-27: 16px letterbox. Full H32 width so
     * transparent WINDOW cells in cols 24-31 cannot show BG_B wrap. */
    VDP_fillTileMapRect(BG_A, attr, 0, 0, MODE_H32_COLS, 2);
    VDP_fillTileMapRect(BG_A, attr, 0, 26, MODE_H32_COLS, 2);
    /* WPV=2: rows 0-1 are full-width WINDOW. Opaque PAL0 black here hides
     * the NT 31 peek that VSCROLL parks in screen Y 8-15. HUD cols 24-31
     * of the bottom bar stay WINDOW so tile 0 cannot stripe the corner. */
    VDP_fillTileMapRect(WINDOW, attr, 0, 0, MODE_H32_COLS, 2);
    VDP_fillTileMapRect(WINDOW, attr, MODE_BAR_COL, 26, MODE_BAR_W, 2);
}
