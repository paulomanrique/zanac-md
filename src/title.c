#include "title.h"
#include "title_logo.h"
#include "game.h"
#include "map_script.h"
#include "sound.h"
#include "resources.h"
#include "player.h"
#include "mode.h"

/*
 * Original boot is MSX title_intro_seq 0x5A11:
 *   ev3, load_logo_tiles, wait_frames B=2, SCORE/TOP, 5-row swirl along
 *   logo_swirl_path 0x5B59, draw_title_text, wait fire_edge 0x46BC.
 * Fire during the swirl RET C skips the rest of the intro (logo settles).
 *
 * Mode pick is port-only and stays small: FIRE/START = Original, a dim
 * "ZANAC MD" row can be highlighted. Do not open an SGDK START/OPTIONS menu.
 */

#define TITLE_TILE_BASE     (TILE_USER_INDEX + 32)
#define BG_TILE             TILE_USER_INDEX
#define TITLE_NT0           2               /* 16px letterbox → MSX row 0 */
#define TITLE_COLS          32
#define LOGO_SRC_STRIDE     19              /* draw_logo_row 0x5BCD A*19 */
#define LOGO_ERASE_ROW      5
#define SWIRL_WAIT          2               /* wait_frames B=2 at 0x5AA9 */

#define PHASE_PREWAIT       0
#define PHASE_SWIRL         1
#define PHASE_WAIT          2

static u8 s_phase;
static u8 s_sel;            /* 0 Original, 1 Zanac MD */
static u16 s_prev;
static u8 s_wait;
static u8 s_swirl[5];       /* E1FA..E1FE */

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

static const u16 k_tms_dim[16] = {
    RGB24_TO_VDPCOLOR(0x000000),
    RGB24_TO_VDPCOLOR(0x000000),
    RGB24_TO_VDPCOLOR(0x0F5A1E),
    RGB24_TO_VDPCOLOR(0x2A6335),
    RGB24_TO_VDPCOLOR(0x25266A),
    RGB24_TO_VDPCOLOR(0x383572),
    RGB24_TO_VDPCOLOR(0x5F2422),
    RGB24_TO_VDPCOLOR(0x1D696E),
    RGB24_TO_VDPCOLOR(0x712625),
    RGB24_TO_VDPCOLOR(0x733636),
    RGB24_TO_VDPCOLOR(0x5F5725),
    RGB24_TO_VDPCOLOR(0x675C39),
    RGB24_TO_VDPCOLOR(0x0F4F1A),
    RGB24_TO_VDPCOLOR(0x5A2953),
    RGB24_TO_VDPCOLOR(0x5C5C5C),
    RGB24_TO_VDPCOLOR(0x737373)
};

static u8 charset_tile(char c)
{
    u8 t = (u8)c;

    if (t >= 'a' && t <= 'z')
        t = (u8)(t - 'a' + 'A');
    if (t == ' ' || t == '.' || t == '@'
        || (t >= '0' && t <= '9') || (t >= 'A' && t <= 'Z'))
        return t;
    return ' ';
}

static void put_tile(u16 x, u16 y, u8 tid, u16 pal)
{
    u16 tile = (u16)(TITLE_TILE_BASE + tid);

    VDP_setTileMapXY(BG_A, TILE_ATTR_FULL(pal, FALSE, FALSE, FALSE, tile), x, y);
}

static void draw_str_pal(const char *s, u16 x, u16 y, u16 pal)
{
    while (*s)
    {
        put_tile(x, y, charset_tile(*s), pal);
        x++;
        s++;
    }
}

static void draw_str_cx_pal(const char *s, u16 y, u16 pal)
{
    u16 len = (u16)strlen(s);
    u16 x = (len < TITLE_COLS) ? (u16)((TITLE_COLS - len) / 2) : 0;

    draw_str_pal(s, x, y, pal);
}

static u16 fire_mask(void)
{
    return (u16)(BUTTON_A | BUTTON_C | BUTTON_START);
}

static int fire_edge(u16 pressed)
{
    return (pressed & fire_mask()) != 0;
}

static void load_bg_tile(void)
{
    static const u32 black[8] = {
        0x11111111, 0x11111111, 0x11111111, 0x11111111,
        0x11111111, 0x11111111, 0x11111111, 0x11111111
    };

    VDP_loadTileData(black, BG_TILE, 1, CPU);
}

static void fill_letterbox(void)
{
    u16 attr = TILE_ATTR_FULL(PAL0, FALSE, FALSE, FALSE, BG_TILE);

    VDP_fillTileMapRect(BG_A, attr, 0, 0, TITLE_COLS, TITLE_NT0);
    VDP_fillTileMapRect(BG_A, attr, 0, 26, TITLE_COLS, 2);
}

static void fill_playfield(void)
{
    u16 attr = TILE_ATTR_FULL(PAL0, FALSE, FALSE, FALSE, BG_TILE);

    VDP_fillTileMapRect(BG_A, attr, 0, TITLE_NT0, TITLE_COLS, 24);
}

static void load_title_tiles(void)
{
    VDP_loadTileData((const u32 *)charset_tiles, TITLE_TILE_BASE, 256, CPU);
    /* load_logo_tiles 0x5C3C: overlay SCREEN2 tiles 0xB0.. into the charset. */
    VDP_loadTileData((const u32 *)logo_tiles,
                     (u16)(TITLE_TILE_BASE + LOGO_TILE_MSX_FIRST),
                     LOGO_TILE_COUNT, CPU);
}

static void setup_title_palettes(void)
{
    PAL_setPalette(PAL0, k_tms, CPU);
    PAL_setPalette(PAL1, k_tms, CPU);
    PAL_setPalette(PAL2, k_tms_dim, CPU);
    PAL_setPalette(PAL3, k_tms, CPU);
    VDP_setBackgroundColor(0);
}

/* 0x3803 SCORE / 0x3811 TOP, then render_lives_score 0x4996. */
static void draw_score_top(void)
{
    char buf[8];
    u32 n;
    u8 i;
    u8 nz;
    u32 div;
    u8 d;
    u16 row = TITLE_NT0;

    draw_str_pal("SCORE", 3, row, PAL3);
    draw_str_pal("TOP", 17, row, PAL3);

    n = player_score();
    if (n > 999999UL)
        n = 999999UL;
    nz = 0;
    for (i = 0; i < 6; i++)
    {
        u8 k;

        div = 1;
        for (k = 0; k < (u8)(5 - i); k++)
            div *= 10;
        d = (u8)((n / div) % 10);
        if (d || nz || i == 5)
        {
            buf[i] = (char)('0' + d);
            nz = 1;
        }
        else
            buf[i] = ' ';
    }
    buf[6] = 0;
    draw_str_pal(buf, 9, row, PAL3);

    n = player_hiscore();
    if (n > 999999UL)
        n = 999999UL;
    nz = 0;
    for (i = 0; i < 6; i++)
    {
        u8 k;

        div = 1;
        for (k = 0; k < (u8)(5 - i); k++)
            div *= 10;
        d = (u8)((n / div) % 10);
        if (d || nz || i == 5)
        {
            buf[i] = (char)('0' + d);
            nz = 1;
        }
        else
            buf[i] = ' ';
    }
    buf[6] = 0;
    draw_str_pal(buf, 21, row, PAL3);
}

/* draw_logo_row 0x5BA0. src_row 5 is the blank strip used to erase. */
static void draw_logo_row(u8 src_row, u8 col, u8 row)
{
    u8 n = LOGO_DRAW_COLS;
    u8 i;
    const u8 *src;
    u16 nt_row;

    if (row >= 24)
        return;
    if (col >= 32)
        return;
    if (col >= 0x0E)
        n = (u8)((u8)~col + 0x21);
    nt_row = (u16)(TITLE_NT0 + row);
    src = logo_tile_rows + (u16)src_row * LOGO_SRC_STRIDE;
    for (i = 0; i < n; i++)
        put_tile((u16)(col + i), nt_row, src[i], PAL3);
}

static void lookup_swirl(u8 a, u8 *col, u8 *row)
{
    u8 i = (u8)(a << 1);

    *col = logo_swirl_path[i];
    *row = logo_swirl_path[i + 1];
}

/* draw_title_text 0x5AC8. Nametable rows + letterbox. */
static void draw_title_text(void)
{
    static const u8 k_mark0[3] = { 0xE7, 0xE9, 0xEB };
    static const u8 k_mark1[3] = { 0xE8, 0xEA, 0xEC };
    u8 i;

    draw_str_pal("GAME DESIGNED BY COMPILE", 3, (u16)(TITLE_NT0 + 15), PAL3);
    draw_str_pal("PRODUCED      BY AII", 3, (u16)(TITLE_NT0 + 16), PAL3);
    draw_str_pal("PRESENTED     BY PONY INC.", 3, (u16)(TITLE_NT0 + 17), PAL3);
    draw_str_pal("COPYRIGHT @ 1986 PONY INC.", 3, (u16)(TITLE_NT0 + 18), PAL3);
    for (i = 0; i < 3; i++)
    {
        put_tile((u16)(14 + i), (u16)(TITLE_NT0 + 20), k_mark0[i], PAL3);
        put_tile((u16)(14 + i), (u16)(TITLE_NT0 + 21), k_mark1[i], PAL3);
    }
}

static void swirl_init(void)
{
    u8 i;
    u8 a = 0x1C;

    for (i = 0; i < 5; i++)
    {
        s_swirl[i] = a;
        a = (u8)(a + 4);
    }
}

/* One body of LAB_ram_5a4a. Returns 1 when all 5 rows have reached 0. */
static int swirl_step(void)
{
    u8 i;
    u8 done = 0;
    u8 col;
    u8 row;
    u8 a;

    for (i = 0; i < 5; i++)
    {
        a = s_swirl[i];
        if (!a || a >= 0x1C)
            continue;
        lookup_swirl(a, &col, &row);
        draw_logo_row(LOGO_ERASE_ROW, col, (u8)(row + i));
    }

    draw_title_text();

    for (i = 0; i < 5; i++)
    {
        a = s_swirl[i];
        a--;
        if ((s8)a < 0)
        {
            done++;
            a++;
        }
        s_swirl[i] = a;
        if (a >= 0x1C)
            continue;
        lookup_swirl(a, &col, &row);
        draw_logo_row(i, col, (u8)(row + i));
    }
    return (done >= 5);
}

static void swirl_settle(void)
{
    u8 i;
    u8 col;
    u8 row;

    lookup_swirl(0, &col, &row);
    for (i = 0; i < 5; i++)
        draw_logo_row(i, col, (u8)(row + i));
    draw_title_text();
}

static void draw_mode_hint(void)
{
    /* Small, not a full menu. Default Original; MD is the dim second line. */
    draw_str_cx_pal("FIRE START", (u16)(TITLE_NT0 + 22), PAL3);
    draw_str_cx_pal("ORIGINAL", (u16)(TITLE_NT0 + 23),
                    (s_sel == 0) ? PAL3 : PAL2);
    draw_str_cx_pal("ZANAC MD", (u16)(TITLE_NT0 + 24),
                    (s_sel == 0) ? PAL2 : PAL3);
}

static void enter_wait(void)
{
    s_phase = PHASE_WAIT;
    s_sel = 0;
    swirl_settle();
    draw_mode_hint();
}

static void confirm_start(void)
{
    GameMode mode = (s_sel == 0) ? MODE_ORIGINAL : MODE_ZANAC_MD;
    u16 joy = JOY_readJoypad(JOY_1);

    /* Debug warps stay START-held modifiers so fire (A/C) starts the game. */
    if ((joy & BUTTON_START) && (joy & BUTTON_C))
        game_start_round(mode, map_script_continue_round());
    else if ((joy & BUTTON_START) && (joy & BUTTON_B))
        game_start_ending(mode);
    else if ((joy & BUTTON_START) && (joy & BUTTON_A))
        game_start_round(mode, 8);
    else
        game_start(mode);
}

void title_enter(void)
{
    s_phase = PHASE_PREWAIT;
    s_sel = 0;
    s_prev = JOY_readJoypad(JOY_1);
    s_wait = SWIRL_WAIT;
    swirl_init();

    VDP_setEnable(FALSE);
    VDP_setWindowOff();
    VDP_setScreenWidth256();

    map_script_reset_scroll();
    VDP_setScrollingMode(HSCROLL_PLANE, VSCROLL_PLANE);
    VDP_setHorizontalScroll(BG_A, 0);
    VDP_setVerticalScroll(BG_A, 0);
    VDP_setHorizontalScroll(BG_B, 0);
    VDP_setVerticalScroll(BG_B, 0);
    VDP_clearPlane(BG_A, TRUE);
    VDP_clearPlane(BG_B, TRUE);
    VDP_clearPlane(WINDOW, TRUE);
    SPR_reset();

    load_bg_tile();
    setup_title_palettes();
    load_title_tiles();
    fill_playfield();
    fill_letterbox();
    sound_play_title();
}

void title_update(void)
{
    u16 joy = JOY_readJoypad(JOY_1);
    u16 pressed = (u16)(joy & ~s_prev);

    if (s_phase == PHASE_PREWAIT)
    {
        /* 0x5A11 fire_edge before load still applies: skip straight to wait. */
        if (fire_edge(pressed))
        {
            VDP_setEnable(TRUE);
            draw_score_top();
            enter_wait();
            s_prev = joy;
            return;
        }
        if (s_wait)
        {
            s_wait--;
            if (!s_wait)
            {
                VDP_setEnable(TRUE);
                draw_score_top();
                s_phase = PHASE_SWIRL;
                s_wait = 0;
            }
        }
        s_prev = joy;
        return;
    }

    if (s_phase == PHASE_SWIRL)
    {
        if (fire_edge(pressed))
        {
            enter_wait();
            s_prev = joy;
            return;
        }
        if (s_wait)
        {
            s_wait--;
            s_prev = joy;
            return;
        }
        if (swirl_step())
            enter_wait();
        else
            s_wait = SWIRL_WAIT;
        s_prev = joy;
        return;
    }

    if (pressed & (BUTTON_UP | BUTTON_DOWN))
    {
        s_sel ^= 1;
        draw_mode_hint();
    }

    if (fire_edge(pressed))
    {
        if (joy & BUTTON_DOWN)
            s_sel = 1;
        confirm_start();
    }

    s_prev = joy;
}
