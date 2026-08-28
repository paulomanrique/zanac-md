#include "hud.h"
#include "mode.h"
#include "player.h"
#include "entity.h"

#define HUD_COL         MODE_BAR_COL
#define HUD_TEXT        (MODE_BAR_COL + 1)
#define HUD_VAL         (MODE_BAR_COL + 2)

static u8 s_hud_ready;

static u16 hud_y(u16 msx_row)
{
    return mode_text_row(msx_row);
}

static void hud_clear_row(u16 row)
{
    VDP_clearTextBG(WINDOW, HUD_TEXT, row, (u16)(MODE_BAR_W - 1));
}

static void hud_put(u16 col, u16 row, const char *s)
{
    VDP_drawTextBG(WINDOW, s, col, row);
}

/* MSX write_digit_to_vram 0x4B83: 2 decimal digits, leading zero -> space. */
static void hud_digit2(u16 col, u16 row, u8 val)
{
    char buf[3];

    if (val >= 100)
        val = 99;
    buf[0] = (val >= 10) ? (char)('0' + (val / 10)) : ' ';
    buf[1] = (char)('0' + (val % 10));
    buf[2] = 0;
    hud_clear_row(row);
    hud_put(col, row, buf);
}

/* MSX 0x4B8D entry: 3 decimal digits, leading zeros blanked. */
static void hud_digit3(u16 col, u16 row, u8 val)
{
    char buf[4];
    u8 d2;
    u8 d1;
    u8 d0;
    u8 nz = 0;

    if (val > 999)
        val = 999;
    d2 = (u8)(val / 100);
    d1 = (u8)((val / 10) % 10);
    d0 = (u8)(val % 10);

    buf[0] = (d2 || nz) ? (char)('0' + d2) : ' ';
    if (d2)
        nz = 1;
    buf[1] = (d1 || nz) ? (char)('0' + d1) : ' ';
    if (d1)
        nz = 1;
    buf[2] = (char)('0' + d0);
    buf[3] = 0;
    hud_clear_row(row);
    hud_put(col, row, buf);
}

/* MSX render_score_bcd: 6 digits, leading zeros -> spaces. */
static void hud_score6(u16 col, u16 row, u32 score)
{
    char buf[7];
    u8 i;
    u8 nz = 0;

    if (score > 999999UL)
        score = 999999UL;

    for (i = 0; i < 6; i++)
    {
        u32 div = 1;
        u8 k;
        u8 d;

        for (k = 0; k < (u8)(5 - i); k++)
            div *= 10;
        d = (u8)((score / div) % 10);
        if (d || nz)
        {
            buf[i] = (char)('0' + d);
            nz = 1;
        }
        else
            buf[i] = ' ';
    }
    buf[6] = 0;
    VDP_clearTextBG(WINDOW, HUD_COL, row, 7);
    hud_put(col, row, buf);
}

/* MSX render_hex_byte 0x4C74: one byte as two uppercase hex digits. */
static void hud_hex2(u16 col, u16 row, u8 val)
{
    static const char HEX[] = "0123456789ABCDEF";
    char buf[3];

    buf[0] = HEX[(val >> 4) & 0xF];
    buf[1] = HEX[val & 0xF];
    buf[2] = 0;
    hud_put(col, row, buf);
}

static void hud_draw_border(void)
{
    u16 y;
    u8 i;

    for (i = 0; i < 14; i++)
    {
        y = hud_y((u16)(10 + i));
        hud_put(HUD_COL, y, "|");
    }
}

static void hud_draw_static_labels(void)
{
    u16 y;

    hud_draw_border();

    /* Horizontal labels (draw_hud_labels @0x4BD4). */
    hud_put(HUD_TEXT, hud_y(7), "SCORE");
    hud_put(HUD_TEXT, hud_y(4), "TOP");
    hud_put(HUD_TEXT, hud_y(12), "ALC");
    hud_put(HUD_TEXT, hud_y(10), "ZANAC");
    hud_put(HUD_TEXT, hud_y(15), "LEVEL");
    hud_put(HUD_TEXT, hud_y(18), "FIRE ");

    /* Initial zeroed score rows (render_score_row2 / render_topscore_row2). */
    y = hud_y(8);
    hud_score6(HUD_COL, y, 0);
    y = hud_y(5);
    hud_score6(HUD_COL, y, player_hiscore());
}

void hud_init(void)
{
    s_hud_ready = 0;
    if (mode_get() != MODE_ORIGINAL)
        return;

    VDP_setTextPalette(PAL0);
    hud_draw_static_labels();
    s_hud_ready = 1;
}

void hud_draw_alc(void)
{
    u16 y;
    u16 x;

    if (!s_hud_ready)
        return;

    /* base_encounter_ctrl 0xBFD6 -> render_hex_byte x3 @0x3859 (row 2 col 25). */
    y = hud_y(2);
    hud_clear_row(y);
    x = HUD_TEXT;
    hud_hex2(x, y, entity_e12e());
    x = (u16)(x + 2);
    hud_hex2(x, y, entity_e132());
    x = (u16)(x + 2);
    hud_hex2(x, y, entity_e130());
}

void hud_draw_round(u8 round)
{
    if (!s_hud_ready)
        return;
    /* render_round_digit -> 0x3A1B row 16 col 27. */
    hud_digit2((u16)(HUD_COL + 3), hud_y(16), round);
}

void hud_draw_time(u8 on, u8 e155)
{
    u16 row;

    if (!s_hud_ready)
        return;

    row = hud_y(21);
    if (!on)
    {
        hud_clear_row(row);
        return;
    }

    {
        static const char HEX[] = "0123456789ABCDEF";
        char tb[8];

        tb[0] = 'T';
        tb[1] = 'I';
        tb[2] = 'M';
        tb[3] = 'E';
        tb[4] = HEX[(e155 >> 4) & 0xF];
        tb[5] = HEX[e155 & 0xF];
        tb[6] = 0;
        hud_clear_row(row);
        hud_put(HUD_TEXT, row, tb);
    }
}

void hud_draw_player(void)
{
    u32 top;
    u8 lives;
    u8 fire;

    if (!s_hud_ready)
        return;

    VDP_setTextPalette(PAL0);

    /* SCORE @0x3918 row 8 col 24. */
    hud_score6(HUD_COL, hud_y(8), player_score());

    /* TOP @0x38B8 row 5 col 24. */
    top = player_top_display();
    if (!player_top_flash_blank())
        hud_score6(HUD_COL, hud_y(5), top);
    if (player_top_flash_active())
        player_top_flash_tick();

    /* update_status_bar: level @0x39BB row 13 col 27. */
    hud_digit2((u16)(HUD_COL + 3), hud_y(13), player_shot_level());

    /* Lives @0x397A row 11: MSX DEC E10A before 3-digit write; skip if zero. */
    lives = player_lives();
    if (!lives)
        hud_clear_row(hud_y(11));
    else
        hud_digit3(HUD_VAL, hud_y(11), (u8)(lives - 1));

    /* update_fire_display @0x7594. */
    fire = player_fire_num();
    {
        char fb[3];
        fb[0] = (char)('0' + (fire % 10));
        fb[1] = 0;
        hud_put((u16)(HUD_TEXT + 5), hud_y(18), fb);
    }
    if (!fire)
        hud_clear_row(hud_y(19));
    else
        hud_digit3(HUD_VAL, hud_y(19), player_fire_ammo());
}
