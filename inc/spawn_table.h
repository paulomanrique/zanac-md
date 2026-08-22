#ifndef SPAWN_TABLE_H
#define SPAWN_TABLE_H

#include <genesis.h>

/* Generated from zanac.asm DB bytes at 0xBE76 / 0xBE7C / 0xBECC. */
#define SPAWN_TYPE_LEN    96
#define SPAWN_TIMER_LEN   7
#define SPAWN_PAIR_LEN    80

extern const u8 spawn_type_list[SPAWN_TYPE_LEN];
extern const u8 spawn_timer_ramp[SPAWN_TIMER_LEN];
extern const u8 spawn_pair_table[SPAWN_PAIR_LEN];

#endif
