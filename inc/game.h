#ifndef GAME_H
#define GAME_H

#include <genesis.h>
#include "mode.h"

typedef enum {
    APP_TITLE = 0,
    APP_GAME  = 1
} AppState;

extern AppState app_state;

void game_start(GameMode mode);
void game_start_round(GameMode mode, u8 round);
void game_start_ending(GameMode mode);
void game_update(void);

#endif
