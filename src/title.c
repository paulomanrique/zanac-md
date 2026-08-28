#include "title.h"
#include "title_md.h"
#include "game.h"
#include "map_script.h"
#include "sound.h"
#include "resources.h"

#define TITLE_TILE_BASE     (TILE_USER_INDEX + 32)
#define TITLE_ZANAC_VDP     (TITLE_TILE_BASE + 256)
#define BG_TILE             TILE_USER_INDEX

#define PHASE_ATTRACT       0
#define PHASE_MAIN          1
#define PHASE_MODE          2

#define MENU_ROW0           TITLE_MD_PRESS_ROW
#define MENU_ROW1           (TITLE_MD_PRESS_ROW + 2)

#define PLANE_COLS          40
#define PLANE_ROWS          28

/* 1.5 s for the wordmark to clear the groove, on either video standard. */
#define INTRO_FRAMES_NTSC   90
#define INTRO_FRAMES_PAL    75

static u8 s_phase;
static u8 s_sel;
static u16 s_prev;
static u16 s_intro_t;
static u16 s_intro_len;
static u16 s_mdmark_vdp;

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

/* The MSX charset only holds space, digits, uppercase letters and '.'; every
 * other code point maps to a terrain tile. */
static u8 charset_tile(char c)
{
    u8 t = (u8)c;

    if (t >= 'a' && t <= 'z')
        t = (u8)(t - 'a' + 'A');
    if (t == ' ' || t == '.' || (t >= '0' && t <= '9') || (t >= 'A' && t <= 'Z'))
        return t;
    return ' ';
}

static void draw_str_pal(const char *s, u16 x, u16 y, u16 pal)
{
    while (*s)
    {
        u16 tile = (u16)(TITLE_TILE_BASE + charset_tile(*s));

        VDP_setTileMapXY(BG_A, TILE_ATTR_FULL(pal, FALSE, FALSE, FALSE, tile), x, y);
        x++;
        s++;
    }
}

static void draw_str_cx_pal(const char *s, u16 y, u16 pal)
{
    u16 len = (u16)strlen(s);
    u16 x = (len < 32) ? (u16)((32 - len) / 2) : 0;

    draw_str_pal(s, x, y, pal);
}

/* Color 0 is transparent on both planes, so an all-zero tile would let the
 * backdrop through. Index 1 is black in every text palette. */
static void load_bg_tile(void)
{
    static const u32 black[8] = {
        0x11111111, 0x11111111, 0x11111111, 0x11111111,
        0x11111111, 0x11111111, 0x11111111, 0x11111111
    };

    VDP_loadTileData(black, BG_TILE, 1, CPU);
}

/* BG_A is the lid of the groove: see-through above the slot so the blue rising
 * on BG_B shows against the backdrop, opaque black from the slot down so the
 * part of the wordmark that has not emerged yet stays buried. */
static void fill_bg(void)
{
    u16 attr = TILE_ATTR_FULL(PAL0, FALSE, FALSE, FALSE, BG_TILE);

    VDP_fillTileMapRect(BG_A, 0, 0, 0, PLANE_COLS, TITLE_GROOVE_ROW);
    VDP_fillTileMapRect(BG_A, attr, 0, TITLE_GROOVE_ROW,
                        PLANE_COLS, PLANE_ROWS - TITLE_GROOVE_ROW);
}

static void clear_rows(u16 from, u16 to)
{
    u16 attr = TILE_ATTR_FULL(PAL0, FALSE, FALSE, FALSE, BG_TILE);

    VDP_fillTileMapRect(BG_A, attr, 0, from, PLANE_COLS, (u16)(to - from + 1));
}

/* Blue wordmark on BG_B so it can be scrolled as a whole and pass behind the
 * MD mark, which lives on BG_A and never moves. */
static void draw_logo(void)
{
    VDP_waitDMACompletion();

    s_mdmark_vdp = TITLE_ZANAC_VDP + title_zanac.tileset->numTile;

    VDP_loadTileSet(title_zanac.tileset, TITLE_ZANAC_VDP, CPU);
    VDP_loadTileSet(title_mdmark.tileset, s_mdmark_vdp, CPU);

    VDP_setTileMapEx(BG_B, title_zanac.tilemap,
                     TILE_ATTR_FULL(PAL1, FALSE, FALSE, FALSE, TITLE_ZANAC_VDP),
                     TITLE_ZANAC_TILE_X, TITLE_ZANAC_TILE_Y,
                     0, 0, TITLE_ZANAC_TILE_W, TITLE_ZANAC_TILE_H, CPU);

    VDP_setTileMapEx(BG_A, title_mdmark.tilemap,
                     TILE_ATTR_FULL(PAL1, FALSE, FALSE, FALSE, s_mdmark_vdp),
                     TITLE_MDMARK_TILE_X, TITLE_MDMARK_TILE_Y,
                     0, 0, TITLE_MDMARK_TILE_W, TITLE_MDMARK_TILE_H, CPU);
}

/* t counts frames into the intro; at t == 0 the wordmark sits a full height
 * below its resting place, fully swallowed by the groove. */
static void intro_seek(u16 t)
{
    s16 off;

    s_intro_t = (t > s_intro_len) ? s_intro_len : t;
    off = (s16)(((u32)TITLE_ZANAC_TRAVEL * (s_intro_len - s_intro_t)) / s_intro_len);
    VDP_setVerticalScroll(BG_B, (s16)-off);
}

static bool intro_done(void)
{
    return s_intro_t >= s_intro_len;
}

static void draw_press_start(void)
{
    draw_str_cx_pal("PRESS START", TITLE_MD_PRESS_ROW, PAL3);
}

static void draw_menu(const char *first, const char *second)
{
    clear_rows(MENU_ROW0, MENU_ROW1);
    draw_str_cx_pal(first, MENU_ROW0, (s_sel == 0) ? PAL3 : PAL2);
    draw_str_cx_pal(second, MENU_ROW1, (s_sel == 0) ? PAL2 : PAL3);
}

static void draw_main_menu(void)
{
    draw_menu("START", "OPTIONS");
}

static void draw_mode_menu(void)
{
    draw_menu("ZANAC MSX ORIGINAL", "ZANAC MD");
}

static void load_title_tiles(void)
{
    VDP_loadTileData((const u32 *)charset_tiles, TITLE_TILE_BASE, 256, CPU);
}

static void setup_title_palettes(void)
{
    PAL_setPalette(PAL0, k_tms, CPU);
    PAL_setPalette(PAL1, title_md_palette, CPU);
    PAL_setPalette(PAL2, k_tms_dim, CPU);
    PAL_setPalette(PAL3, k_tms, CPU);
    VDP_setBackgroundColor(0);
}

static void draw_title_screen(void)
{
    fill_bg();
    draw_logo();
    intro_seek(0);
}

void title_enter(void)
{
    s_phase = PHASE_ATTRACT;
    s_sel = 0;
    s_prev = JOY_readJoypad(JOY_1);
    s_intro_t = 0;
    s_intro_len = IS_PAL_SYSTEM ? INTRO_FRAMES_PAL : INTRO_FRAMES_NTSC;

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
    draw_title_screen();
    sound_play_title();
}

void title_update(void)
{
    u16 joy = JOY_readJoypad(JOY_1);
    u16 pressed = joy & ~s_prev;

    if (s_phase == PHASE_ATTRACT)
    {
        if (!intro_done())
        {
            /* START during the intro snaps it to the end rather than being
             * swallowed; the player still presses again to open the menu. */
            intro_seek((pressed & BUTTON_START) ? s_intro_len : (u16)(s_intro_t + 1));
            if (intro_done())
                draw_press_start();
            s_prev = joy;
            return;
        }

        if (pressed & BUTTON_START)
        {
            s_phase = PHASE_MAIN;
            s_sel = 0;
            draw_main_menu();
        }
        s_prev = joy;
        return;
    }

    if (s_phase == PHASE_MAIN)
    {
        if (pressed & (BUTTON_UP | BUTTON_DOWN))
        {
            s_sel ^= 1;
            draw_main_menu();
        }

        if (pressed & BUTTON_START && s_sel == 0)
        {
            s_phase = PHASE_MODE;
            s_sel = 0;
            draw_mode_menu();
        }

        s_prev = joy;
        return;
    }

    if (pressed & (BUTTON_UP | BUTTON_DOWN))
    {
        s_sel ^= 1;
        draw_mode_menu();
    }

    if (pressed & BUTTON_START)
    {
        GameMode mode = (s_sel == 0) ? MODE_ORIGINAL : MODE_ZANAC_MD;

        /* Continue: title_screen_init 0x4254 skips the E701 := 1 at 0x4256 when
         * check_esc_key (0x43D2) reports ESC held, so the run resumes at the
         * last round reached instead of restarting at 1. C is the Mega Drive
         * stand-in; on a cold boot the saved round is still 1, which makes this
         * identical to a normal start.
         * B and A stay as the debug warps this screen replaced. */
        if (joy & BUTTON_C)
            game_start_round(mode, map_script_continue_round());
        else if (joy & BUTTON_B)
            game_start_ending(mode);
        else if (joy & BUTTON_A)
            game_start_round(mode, 8);
        else
            game_start(mode);
    }

    s_prev = joy;
}
