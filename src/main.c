#include <genesis.h>
#include "game.h"
#include "title.h"
#include "mode.h"
#include "sound.h"

int main(bool hardReset)
{
    (void)hardReset;

    VDP_setScreenWidth320();
    SPR_init();
    mode_init();
    sound_init();

    app_state = APP_TITLE;
    title_enter();

    while (TRUE)
    {
        if (app_state == APP_TITLE)
            title_update();
        else
            game_update();

        sound_tick();
        SPR_update();
        SYS_doVBlankProcess();
    }

    return 0;
}
