#include <genesis.h>
#include "game.h"
#include "title.h"
#include "mode.h"
#include "sound.h"

/* MSX vblank_isr 0x43DA calls psg_sound_tick 0x4E7B after SAT DMA and
 * scroll_vram_write — once per vblank, never gated on the game loop. */
static void vint_psg(void)
{
    sound_tick();
}

int main(bool hardReset)
{
    (void)hardReset;

    VDP_setScreenWidth320();
    SPR_init();
    mode_init();
    sound_init();
    SYS_setVIntCallback(vint_psg);

    app_state = APP_TITLE;
    title_enter();

    while (TRUE)
    {
        if (app_state == APP_TITLE)
            title_update();
        else
            game_update();

        SPR_update();
        SYS_doVBlankProcess();
    }

    return 0;
}
