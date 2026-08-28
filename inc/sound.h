#ifndef SOUND_H
#define SOUND_H

#include <genesis.h>

/* MSX AY track interpreter driving the MD PSG (SN76489).
 * Event IDs match zanac-re subsystem O (27 events @0x5234). */

#define SND_EV_THEME      1
#define SND_EV_ROUND8     2
#define SND_EV_TITLE      3
#define SND_EV_GAMEOVER   4
#define SND_EV_CHAIN5     5   /* chained from ev12 (0x87 05) */
#define SND_EV_FIRE       6
#define SND_EV_INTRO      7
#define SND_EV_EXTRA      8   /* extra-life; E102 bit2 (0x4A61) */
#define SND_EV_HISCORE    9   /* hi-score; E102 bit2 (0x4A20) */
#define SND_EV_ROUNDVAR   10  /* logo-reload BGM (0x4133); orb warp old&new&7==0 */
#define SND_EV_CLEARJING  11  /* level-complete (0x40EA); type-72 dest!=0 */
#define SND_EV_BOSS       12  /* round/boss (0x924B); chains ev5 */
#define SND_EV_SHOT       13
#define SND_EV_DEATH      16  /* type-60 death init 0x86C0 */
#define SND_EV_EHIT       17  /* enemy hit 0x8495 / 0x8B87 */
#define SND_EV_EXPLODE    18
#define SND_EV_PLASMA     19  /* fire 6 expire 0x7516 */
#define SND_EV_BASEHIT    20  /* base hit 0x8438 */
#define SND_EV_EHIT2      21  /* type 66 volley 0x8025 (bit0 path) */
#define SND_EV_LIGHTBAR   22  /* light-bar spawn 0x8654 (LD A,0x16) */
#define SND_EV_PICKUP     23  /* power-chip 0x78C1 */
#define SND_EV_FIRE_EXPIRE 24
#define SND_EV_FANFARE    25  /* round banner / 0x9044 */
#define SND_EV_CLEAR_A    26  /* round-clear 0x917A C=0x1A */
#define SND_EV_CLEAR_B    27  /* round-clear 0x917A C=0x1B */

void sound_init(void);
void sound_tick(void);
void sound_stop_all(void);
/* mute_sound 0x5208 E200=3 / restore_sound 0x520E E200=0 */
void sound_mute(void);
void sound_restore(void);
void sound_play_event(u8 ev);
/* SUB_ram_92d0: slot2 event>>1==0x0D (ev 26/27) or slot3 event>>1==0x04 (ev 8/9). */
u8   sound_jingle_waiting(void);
/* SUB_ram_5211: PF_VENV fade on slots 0-2 (rate 8, ceil 0). */
void sound_fade(void);

void sound_play_title(void);
void sound_play_round(u8 round);
/* Any stage-BGM event (1/2/7/10) still running on slots 0-2. */
u8   sound_bgm_active(void);
void sound_play_shot(void);
void sound_play_explode(void);
void sound_play_gameover(void);

#endif
