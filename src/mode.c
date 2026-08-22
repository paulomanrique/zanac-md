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
        /* Right 8 tiles (4 double-cols) + full 28-row height. */
        VDP_setWindowHPos(TRUE, 12);
        VDP_setWindowVPos(FALSE, 28);
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

    attr = TILE_ATTR_FULL(PAL0, TRUE, FALSE, FALSE, LETTER_TILE);
    /* Screen rows 0-1 and 26-27: 16px letterbox. Leave cols 24-31 to WINDOW. */
    VDP_fillTileMapRect(BG_A, attr, 0, 0, MODE_BAR_COL, 2);
    VDP_fillTileMapRect(BG_A, attr, 0, 26, MODE_BAR_COL, 2);
}