#include "title.h"
#include "game.h"
#include "map_script.h"
#include "sound.h"
#include "resources.h"
#include "player.h"

#define TITLE_TILE_BASE     (TILE_USER_INDEX + 32)
#define TITLE_BAND0         2       /* first row of the 192 band (Y+16) */
#define TITLE_BAND1         25      /* last row of the 192 band */

static u8 s_sel;
static u16 s_prev;

/* Same TMS9918 set map_script.c uses on PAL3. */
static const u16 k_tms[16] = {
    RGB24_TO_VDPCOLOR(0x000000),
    RGB24_TO_VDPCOLOR(0x000000),
    RGB24_TO_VDPCOLOR(0x21C842),
    RGB24_TO_VDPCOLOR(0x5EDC78),
    RGB24_TO_VDPCOLOR(0x5455ED),
    RGB24_TO_VDPCOLOR(0x7D76FC),
    RGB24_TO_VDPCOLOR(0xD4524D),
    RGB24_TO_VDPCOLOR(0x42EBF5),
    RGB24_TO_VDPCOLOR(0xFC5554),
    RGB24_TO_VDPCOLOR(0xFF7978),
    RGB24_TO_VDPCOLOR(0xD4C154),
    RGB24_TO_VDPCOLOR(0xE6CE80),
    RGB24_TO_VDPCOLOR(0x21B03B),
    RGB24_TO_VDPCOLOR(0xC95BBA),
    RGB24_TO_VDPCOLOR(0xCCCCCC),
    RGB24_TO_VDPCOLOR(0xFFFFFF)
};

static void draw_str(const char *s, u16 x, u16 y)
{
    u16 attr;

    while (*s)
    {
        attr = TILE_ATTR_FULL(PAL3, TRUE, FALSE, FALSE,
                              (u16)(TITLE_TILE_BASE + (u8)*s));
        VDP_setTileMapXY(BG_A, attr, x, y);
        x++;
        s++;
    }
}

static void draw_str_cx(const char *s, u16 y)
{
    u16 len = (u16)strlen(s);
    u16 x = (len < 32) ? (u16)((32 - len) / 2) : 0;

    draw_str(s, x, y);
}

static void draw_letterbox(void)
{
    u16 attr = TILE_ATTR_FULL(PAL3, TRUE, FALSE, FALSE, TITLE_TILE_BASE);
    u16 x, y;

    /* Tile 0 is blank. Fill rows 0-1 / 26-27 — stay in the 192 band. */
    for (y = 0; y < 2; y++)
        for (x = 0; x < 32; x++)
            VDP_setTileMapXY(BG_A, attr, x, y);
    for (y = 26; y < 28; y++)
        for (x = 0; x < 32; x++)
            VDP_setTileMapXY(BG_A, attr, x, y);
}

static void draw_logo(void)
{
    /* Native 8x8 charset, no 2x stretch. MSX logo sits in the upper band. */
    draw_str_cx("ZANAC", TITLE_BAND0 + 4);
}

static void draw_credits(void)
{
    /* draw_title_text 0x5AC8: MSX name-table rows 15-18. +2 for Y+16. */
    draw_str_cx("GAME DESIGNED BY COMPILE", TITLE_BAND0 + 13);
    draw_str_cx("PRODUCED      BY AII", TITLE_BAND0 + 14);
    draw_str_cx("PRESENTED     BY PONY INC.", TITLE_BAND0 + 15);
    draw_str_cx("COPYRIGHT 1986 PONY INC.", TITLE_BAND0 + 16);
}

static void draw_hiscore(void)
{
    /* Original title_screen_init draws TOP on the HUD (0x49a7).
     * Port title has no HUD; show the same value without touching menu items. */
    char line[12];
    u32 n = player_hiscore();
    u8 i;

    line[0] = 'T';
    line[1] = 'O';
    line[2] = 'P';
    line[3] = ' ';
    if (n > 999999UL)
        n = 999999UL;
    for (i = 0; i < 6; i++)
    {
        u32 div = 1;
        u8 k;
        for (k = 0; k < (u8)(5 - i); k++)
            div *= 10;
        line[4 + i] = (char)('0' + (u8)((n / div) % 10));
    }
    line[10] = 0;
    draw_str_cx(line, TITLE_BAND0 + 6);
}

static void draw_menu(void)
{
    VDP_setTextPalette(s_sel == 0 ? PAL1 : PAL0);
    VDP_drawText(s_sel == 0 ? "> Original" : "  Original", 10, TITLE_BAND0 + 8);

    VDP_setTextPalette(s_sel == 1 ? PAL1 : PAL0);
    VDP_drawText(s_sel == 1 ? "> Zanac MD" : "  Zanac MD", 10, TITLE_BAND0 + 10);

    VDP_setTextPalette(PAL0);
    VDP_drawText("D-Pad + START", 9, TITLE_BAND1);
}

void title_enter(void)
{
    s_sel = 0;
    s_prev = JOY_readJoypad(JOY_1);

    VDP_setWindowOff();
    VDP_setScreenWidth256();
    VDP_setBackgroundColor(0);
    PAL_setColor(0, RGB24_TO_VDPCOLOR(0x000000));
    PAL_setColor(15, RGB24_TO_VDPCOLOR(0xF0F0F0));
    PAL_setColor(31, RGB24_TO_VDPCOLOR(0xF0D020));
    VDP_setTextPalette(PAL0);

    map_script_reset_scroll();
    VDP_clearPlane(BG_A, TRUE);
    VDP_clearPlane(BG_B, TRUE);
    SPR_reset();

    VDP_loadTileData((const u32 *)charset_tiles, TITLE_TILE_BASE, 256, CPU);
    PAL_setPalette(PAL3, k_tms, CPU);

    draw_letterbox();
    draw_logo();
    draw_hiscore();
    draw_credits();
    draw_menu();
    sound_play_title();
}

void title_update(void)
{
    u16 joy = JOY_readJoypad(JOY_1);
    u16 pressed = joy & ~s_prev;

    if (pressed & (BUTTON_UP | BUTTON_DOWN))
    {
        s_sel ^= 1;
        draw_menu();
    }

    if (pressed & BUTTON_START)
    {
        GameMode mode = (s_sel == 0) ? MODE_ORIGINAL : MODE_ZANAC_MD;

        /* Debug warp (verify ending): hold C = credits, hold A = round 8. */
        if (joy & BUTTON_C)
            game_start_ending(mode);
        else if (joy & BUTTON_A)
            game_start_round(mode, 8);
        else
            game_start(mode);
    }

    s_prev = joy;
}
