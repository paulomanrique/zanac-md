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

void mode_init(void);
void mode_set(GameMode mode);
GameMode mode_get(void);
const ModeAssets *mode_assets(void);
void mode_apply_video(void);

/* Sim Y -> sprite/plane screen Y (Original +16). */
s16  mode_draw_y(s16 y);
u16  mode_y_off(void);
u16  mode_text_row(u16 msx_row);

/* Black letterbox rows 0-1 / 26-27 + right bar (Original only). */
void mode_draw_letterbox(void);

#endif