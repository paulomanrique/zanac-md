#include "game.h"
#include "player.h"
#include "entity.h"
#include "map_script.h"
#include "title.h"
#include "sound.h"
#include "hud.h"

AppState app_state = APP_TITLE;

static u8 s_over_cleared;
static u8 s_paused;
static u8 s_pause_ctr;
static u16 s_pause_under[5];
static u16 s_prev_joy;

/*
 * pause_handler 0x4DA5. MSX nametable @0x3800:
 *   0x396A = row 11 col 10 (5 tiles "PAUSE") -- playfield, not the
 *   right bar (lives @0x397A is row 11 col 26). Overlay on BG_A so
 *   it sits over the scrolling 192 band without touching WINDOW.
 */
#define PAUSE_COL   10
#define PAUSE_LEN   5

static u16 pause_row(void)
{
    return mode_text_row(11);
}

static u16 pause_read_tile(u16 x, u16 y)
{
    u16 addr = VDP_getPlaneAddress(BG_A, x, y);
    vu32 *ctrl = (vu32 *)VDP_CTRL_PORT;
    vu16 *data = (vu16 *)VDP_DATA_PORT;

    VDP_waitDMACompletion();
    VDP_setAutoInc(2);
    *ctrl = VDP_READ_VRAM_ADDR((u32)addr);
    return *data;
}

static void pause_save_tiles(void)
{
    u16 y = pause_row();
    u8 i;

    for (i = 0; i < PAUSE_LEN; i++)
        s_pause_under[i] = pause_read_tile((u16)(PAUSE_COL + i), y);
}

static void pause_draw_text(void)
{
    if (mode_get() == MODE_ORIGINAL)
    {
        hud_draw_str(BG_A, PAUSE_COL, pause_row(), "PAUSE");
        return;
    }
    VDP_setTextPalette(PAL0);
    VDP_setTextPriority(TRUE);
    VDP_drawTextBG(BG_A, "PAUSE", PAUSE_COL, pause_row());
}

static void pause_restore_tiles(void)
{
    u16 y = pause_row();
    u8 i;

    for (i = 0; i < PAUSE_LEN; i++)
        VDP_setTileMapXY(BG_A, s_pause_under[i], (u16)(PAUSE_COL + i), y);
}

static void pause_enter(void)
{
    s_paused = 1;
    s_pause_ctr = 0;
    sound_mute();
    pause_save_tiles();
    pause_draw_text();
}

static void pause_leave(void)
{
    pause_restore_tiles();
    sound_restore();
    s_paused = 0;
}

static void go_title(void)
{
    /* 0x4ACE on game_over_handler / credits_display. B-to-title is port-only. */
    if (s_paused)
        pause_leave();
    player_save_hiscore();
    entity_release();
    player_release();
    SPR_reset();
    app_state = APP_TITLE;
    title_enter();
}

static void game_boot(GameMode mode)
{
    mode_set(mode);
    mode_apply_video();
    if (mode == MODE_ORIGINAL)
        VDP_setEnable(FALSE);

    VDP_clearPlane(BG_A, TRUE);
    VDP_clearPlane(BG_B, TRUE);
    VDP_clearPlane(WINDOW, TRUE);
    SPR_reset();

    PAL_setColor(0, RGB24_TO_VDPCOLOR(mode == MODE_ORIGINAL ? 0x000000 : 0x000810));
    PAL_setColor(1, RGB24_TO_VDPCOLOR(0x000000));
    PAL_setColor(15, RGB24_TO_VDPCOLOR(0xE0E0E0));
    PAL_setColor(31, RGB24_TO_VDPCOLOR(0xF0D020));
    VDP_setBackgroundColor(0);
    VDP_setTextPalette(PAL0);
    mode_draw_letterbox();

    s_over_cleared = 0;
    s_paused = 0;
    s_pause_ctr = 0;
    /* Swallow the title START that launched us so it does not pause. */
    s_prev_joy = JOY_readJoypad(JOY_1);
    player_init();
    entity_init();
    hud_init();
    app_state = APP_GAME;
}

void game_start(GameMode mode)
{
    game_boot(mode);
    map_script_init();
}

void game_start_round(GameMode mode, u8 round)
{
    game_boot(mode);
    map_script_init_round(round);
}

void game_start_ending(GameMode mode)
{
    game_boot(mode);
    map_script_start_ending();
}

void game_update(void)
{
    u16 joy = JOY_readJoypad(JOY_1);
    u16 pressed = (u16)(joy & ~s_prev_joy);

    s_prev_joy = joy;

    if (player_is_over())
    {
        if (!s_over_cleared)
        {
            entity_release();
            s_over_cleared = 1;
            sound_play_gameover();
        }
        if (joy & (BUTTON_A | BUTTON_C | BUTTON_START | BUTTON_B))
            player_skip_over();

        map_script_update();
        player_update();
        map_script_draw_hud();
        player_draw_hud();
        player_draw_over();

        if (player_over_ready())
            go_title();
        return;
    }

    /* B returns to title so both modes can be tried without reset. */
    if (joy & BUTTON_B)
    {
        go_title();
        return;
    }

    if (map_script_credits_active())
    {
        map_script_update();
        player_update();
        map_script_draw_hud();
        player_draw_hud();
        map_script_draw_credits();
        if (map_script_credits_exit())
            go_title();
        return;
    }

    /* pause_handler 0x4DA5: MSX STOP -> START in play only. */
    if (s_paused)
    {
        if (pressed & BUTTON_START)
        {
            pause_leave();
            return;
        }
        /* E118 low 5 bits: draw at 0, restore at 16 (16 on / 16 off). */
        s_pause_ctr = (u8)((s_pause_ctr + 1) & 0x1F);
        if ((s_pause_ctr & 0x0F) == 0)
        {
            if (s_pause_ctr & 0x10)
                pause_restore_tiles();
            else
                pause_draw_text();
        }
        return;
    }
    if (pressed & BUTTON_START)
    {
        pause_enter();
        return;
    }

    map_script_update();
    player_update();
    entity_update();
    map_script_draw_hud();
    player_draw_hud();
}
