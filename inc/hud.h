#ifndef HUD_H
#define HUD_H

#include <genesis.h>

/* MSX right-panel layout (nametable cols 24-31). Original mode only. */
void hud_init(void);
void hud_draw_alc(void);
void hud_draw_round(u8 round);
void hud_draw_time(u8 on, u8 e155);
void hud_draw_player(void);

#endif
