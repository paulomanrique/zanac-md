#ifndef MODE_H
#define MODE_H

#include <genesis.h>

typedef enum {
    MODE_ORIGINAL = 0,
    MODE_ZANAC_MD = 1
} GameMode;

/*
 * Asset pack for the active mode. Simulation stays in MSX space;
 * this struct is the render skin. Swap the pointers later to drop
 * in a 320-wide art pack without touching game logic.
 *
 * Original: MSX SCREEN2 256x192 letterboxed in MD H32 256x224
 * (16px top + 16px bottom). Right status bar is 8 tiles / 64px
 * (nametable cols 24-31) overlaid on the 256 map ? sprites stay 0-255 X.
 */
typedef struct {
    const SpriteDefinition *ship;
    u16 screen_width;
    u16 playfield_w;
    u16 playfield_h;
    u16 y_off;          /* screen Y = sim Y + y_off */
    const char *name;
} ModeAssets;

#define MODE_BAR_COL    24
#define MODE_BAR_W      8
#define MODE_SCREEN_H   224
#define MODE_BAR_PX     (MODE_BAR_COL * 8)  /* HUD starts at x=192 */
#define MODE_SPR_W      16                  /* MSX 16x16 SAT; occupancy clip */
/* MSX clamps X to 0x28..0xC8, but cols 24-31 are HUD — keep the ship in 0-191. */
#define MODE_SHIP_MIN_X 0x28
#define MODE_SHIP_MAX_X ((MODE_BAR_COL * 8) - 16)

void mode_init(void);
void mode_set(GameMode mode);
GameMode mode_get(void);
const ModeAssets *mode_assets(void);
void mode_apply_video(void);

/* Sim Y -> sprite/plane screen Y (Original +16). */
s16  mode_draw_y(s16 y);
/* Sim X -> sprite screen X. Original: SAT color bit7 (TMS EC) is X-32.
 * AABBs use this visual X for both sides; stored entity X stays MSX SAT X. */
s16  mode_draw_x(s16 x, u8 sat_col);
u16  mode_y_off(void);
u16  mode_text_row(u16 msx_row);

/* PAL0 priority black tile used by BG_A letterbox and BG_B unused wrap rows. */
u16  mode_letter_attr(void);
/* 1 if [draw_x, draw_x+width) intersects WINDOW cols 24-31 (x>=192). */
int  mode_hud_overlap(s16 draw_x, u16 width);

/* Black letterbox rows 0-1 / 26-27 + right bar (Original only). */
void mode_draw_letterbox(void);

#endif