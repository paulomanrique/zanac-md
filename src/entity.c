#include "entity.h"
#include "player.h"
#include "mode.h"
#include "spawn_table.h"
#include "map_script.h"
#include "resources.h"
#include "sound.h"

/*
 * Entity slots + spawn ticker.
 *
 * Shots: type 2, Y-only. vy/cap from shot_power_table[shot_level].
 * Fire:  type 3, E380.
 *   0 All-Range  - xvel_table[E10C] dir, vel word0->Y word1->X, speed 0xC2 (~12px)
 *   1 Straight   - Y-only vy=-2, fire_dec_ammo per spawn, die+E14D==0 -> reset
 *   2 Field      - auto (fire_select writes E380=3), Y=player_Y-8, persist hits
 *   3 Circular   - snowflake/orb, 16-dir orbit around clamped ship, fire_life_timer
 *   4 Vibrator   - lg_circle, rise + X bang-bang around anchor, persist hit->ev24
 *   5 Rewinder   - target, X follows ship, vy=-2 then +4/256 rewind, ammo shots
 *   6 Plasma     - no persistent entity (explode_enemies + ev19)
 *   7 High Speed - comet, fire0_dir_table fan, speed 0xC3, fire_life_timer
 * Enemies: G group-1 airborne + round-1 pickups that the spawn_table emits
 *   4-6     box     - 7826: Yvel 8.8 01C0 (bflags Y-only), 5 hp;
 *           type 4 drops 3 type-38; type 5 none; type 6 chip.
 *           Port: dest/bind/script/timer 8.8 (like type20/guns).
 *   10      duster  - 7a2a: Yvel 8.8 0300, +0c=0x13 (Y|X|X-homing),
 *           x_accel +16=8 tgt +14 (X<0x88?FF:00), +17=1; random_x 71c5.
 *           Port: dest/bind/script/timer 8.8 (like type20/26); aux=+14 tgt.
 *   12-15   teruzo  - 7b07: +0c=3 +17=4 set_velocity_from_dir 8.8;
 *           teruzo_motion_tables dir every 8f (+1f). Port: apply_dir_88
 *           speed 4; aux=+18 idx, clock=+1f; dest/bind/script/timer 8.8.
 *   16-18   luster  - 7beb/7c8a/7cb3: Yvel 8.8 0200; 16 +0c=1 Y-only
 *           sides 40/B0; 17 +0c=0x13 Xvel FC00 X-home accel 40 iters 4
 *           tgt=spawn X sides 30/B0; 18 +0c=0x13 Xvel +/-0300 X-home
 *           accel 0e iters 2 tgt FF/00 sides 60/90 fire +1d=30->37.
 *           Port: dest/bind/script/timer 8.8; aux=+14; clock=+1d.
 *           16/17->38 (dir +1d); 18->37 aim.
 *   56      sig     - 819d: E=4, join 81a8 speed 5 set_velocity_from_dir 8.8
 *           +0c=3; SAT 0x70. Same path as 59 (drop integer apply_dir).
 *   59      sideways 8269: +0x1a&0x0F dir, join 81a8 speed 5
 *           set_velocity_from_dir 8.8 +0c=3; SAT 0x70. From pairdesc 57/58,
 *           stealth 66 (808a x5), swoop28 8ddb C=4. Port: KIND_SIG variant 59
 *           + apply_dir_88(...,5) + 8.8 step (shares 81a8 with type56).
 *   63      chip    - pickup, raises shot_level
 *   68      proto_box -> 3 boxes (types 4/5/6)
 *   80      husk    - 8e14: bfb3+ev18+849c first frame, then 8f45 / clear
 *   83      fire-up - 8e3a: Yvel FFE0 8.8; SAT 0x24/0x81 blank vs 0x04/8eaf[+1c]; collect fire_select
 *   44      ground  - 82d0: aim_4c91+set_vel 8.8 speed (R&3)+1, +0c=3, 3 hp;
 *           SAT 0x40 plane / col-marker 0x44 plane_compl (cyan 0x83);
 *           spr FRAME_PLANE (compl folded; marker occupancy).
 *   64      proto   - table-driven converter (spawn_type_list[E130/2+R&3])
 *   70/71   idol    - nametable totem (no SAT); HP 6; -> type 72 orb + bfc8 + type-81 child
 *   72      orb     - 8983: Yvel 8.8 0xFFF8 (yel) / 0xFFF0 (blk); +0x1e=4;
 *           70 expires; 71 black warp. Port: bind/timer 8.8; clock=+0x1b;
 *           script=+0x1e; aux=anim; yellow 8a26+ev19 / black map_script_warp
 *   81      husk-src- nametable (no SAT); HP 4; 880d->8824 type-80 husk + 88c2
 *   82      firebox - nametable digit 0x30+fire# (87e2, no SAT); HP 4; 880d->8874 type 83 + 88d8
 *   84-86   wide_var - nametable (no SAT); 8EB7 wave-spawner; HP 4; death 8854 type-80 husk + 88ab tiles
 *   87      wide    - nametable (no SAT); HP 3; 880d->8892 type-80 husk + 88b1
 *   88      wide    - nametable (no SAT); HP 3; 880d->8892 type-80 husk + 88cb
 *   89      wide    - nametable (no SAT); HP 3; 880d->8892 then 8874: R&7 fire-up + 88d8
 *   46-55   gun     - 8094 ground-gun pairs; Yvel 8.8 0150 (bflags Y-only),
 *           fire 38/21 via 816d/8ddb. SAT 0x48 loga_A / fire 0x4c compl;
 *           spawn_col_marker. Port: dest/bind/script/timer 8.8;
 *           aux=ang|side|latch, clock=+0x18 period. Osc bit5 pauses bind=0;
 *           spr FRAME_LOGA (compl folded); fire flash -> LOGA_C on primary.
 *   61      descender - 8302: Yvel 8.8 0200 (+0c=1), halt Y=0x60
 *           (+1e=0x20, +0c=0), then rise Yvel FC00. Port: dest/bind/
 *           script/timer 8.8; clock=+1e (was integer vy=2/-4).
 *   65-66   stealth - table X, 4/7 hp, 7f99: +17=1 set_vel 8.8 +0c=3;
 *           volley 8084/8087/808a (20/59). Port: dest/bind/script/timer;
 *           clock=+1d period.
 *   67      med_circle - 839f: +0c=3 +17=3 HP5; +1b=0x78 reaim,
 *           +1c=0x1e phases; on 0: aim_4c91+set_vel speed 3, reload
 *           +1b=0x32+(R&0x1e); +05 bit0 arms motion, bit1 stops reaim.
 *           SAT 0x20 pat 8. Port: clock=+1b; aux=phase|mot|stop; 8.8;
 *           spr FRAME_MED_CIRCLE.
 *   73-79   base    - nametable-only (sat_col=0 like MSX); HP from base_segment_table
 *   7-9     umber   - 791d: Yvel 8.8 0300, +0c=0x09 (Y|Y-homing), +15=0x10
 *           iters +17=1, tgt +13 unset (0). Burst at Yvel==0: 7x38 / 2x41;
 *           type9 +1d=8 -> type20. Port: dest/bind/script/timer 8.8; clock=+1d.
 *   11/69   spawner - 7ad4/7a67: E130 table, interval 0x28, drift on fire
 *           +/-2 bounce u8 X>=0xC0, 8ddb C=3/5, E12D.bit3 gate
 *   22-25   veybar  - 7d0f/7db4: Yvel 8.8 0400, +15=0x14 iters 1, tgt 0;
 *           shared active 7d4c: morph fire @clock 0x20 -> type37 (7d8c).
 *           22/23 +0c=0x09 (Xvel armed, motion off until morph): 7d95
 *           +17=4, 4c91, set_velocity_from_dir, then +17=1 / +15=0x0c /
 *           SET +0c.1 before type37 (parent re-aim; drops spawn +/-1 Xvel).
 *           24/25 +0c=0x1b X-home accel 0x10 clock 0x58, morph spawns
 *           type37 only (no re-aim / X-arm; already on).
 *           Morph SAT telegraph 7d73: when clock<0x40 and (RRCA x2) only
 *           bits 2-3 set, (IX+03)=0x94-E and marker +0x14; fire @0xa0.
 *           Port: dest/bind/script/timer 8.8; clock=+1d; aux=flags(22/23)
 *           or X-tgt(24/25); spr FRAME_VEYBAR_0..4 (compl folded; marker occupancy).
 *   26-29   swooper 7de2/7e78: 8.8 Xvel (FF40/00C0/FE00/0200), Yvel 0280,
 *           +0c=0x0F (Y|X motion|anim|Y_homing), accel +15=07 iters +17=1,
 *           Y tgt +13 unset (0); fire +1e (18/18/04/04)->20; child +1d 37/20/59/41
 *           via 8ddb C=0x04. Anim table 0x7E68/0x7E70 pats 43-46 (+0d/+0e=4,
 *           +0x10=4); 71f6 marker SAT=parent+0x10 (pats 47-50).
 *           +04 body: A 0x8E (7e68), B 0x87 (7e70) via sat_col remap.
 *           Port: dest/bind/script/timer 8.8; aux=child, clock=fire;
 *           spr FRAME_SPINNER_0..3 (compl folded; marker occupancy).
 *   30/32   gswoop 7e9c: 8.8 Yvel 0180 (32: FF00 + Y=D0 sense), Xvel 0180
 *           (32 flip 0100); +0c=1 Y then 2 X; pair child type+1 at X=C0
 *           Xvel FE80 (32: FF00). Port: dest/bind/script/timer 8.8; aux=sib,
 *           clock=+0c|sense|lock|xor. +04^=0x06/frame (sat_col); merge |dx|<0x0B:
 *           +03=0xf4, sib->type40, X+5, +0c=1, SET lock (7f5b-7f78).
 *   31/33   tracker - 7f84: Y-then-X (playerY CP + bit6 CCF); +04^=0x06
 *           @ 7f73; pat 51 sat 0xCC. Stream init ~7f99/807c (no volley).
 *           Also gswoop 30/32 child (own+1) pre-init sat 0xf0 degid_right.
 *   34      stealth - 7f99 shared 65/66: cruise 8.8 speed 1; 3x38 volley
 *   62      invisible_riser 8709: Yvel 8.8 FF80, every-16f NT poke;
 *           type61 death gate (E140&3F)==(E103&3F) -> 62; else E148>=5
 *           -> 83. Ship touch: INC lives + ev8. Port: bind/timer 8.8;
 *           clock=+0d.
 *   36      flash   - 8296: Yvel 8.8 0080 (+0c=1), attr XOR 0x0e
 *           each frame, then entity_update + 7904 (HP16). SAT 0x34
 *           pat 13. Port: dest/bind/script/timer 8.8; spr FRAME_BOLT;
 *           vis toggle ~ XOR.
 *   57-58   pairdesc- 81d1: descend Yvel 8.8 0200 (+1f=0x20) then
 *           convert to type 59 (4c91 aim); 59 is 8.8 set_vel speed 5.
 *           SAT 0x6C pat 27 (57) / 0x68 pat 26 (58); color 0x8F.
 *           Port: bind=0x0200; clock=+1f; timer=Yfrac; FRAME_SIG_DOUBLE/TRIPLE.
 *   20      lead_homing 8668: +0c=0x0B Y-home tgt 0xFF accel 0x0C iters 1;
 *           Xvel 8.8: hi=(R&3)-2, lo=L (same prng); dest/script like other leads.
 *           Stream-capable (is_port_type): random_x 71c5 Y=0 + type20_init_vel;
 *           also child of umber-9 / stealth-65.
 *   37      lead_bullet 84dd/84e3: +0c=3 +17=3, player_pos_snapshot 4c8b
 *           (= aim_4c91 + set_velocity_from_dir 8.8 speed 3). Plain 37 no XOR.
 *   42      proto_bullet 85cc: CALL 84e3 (type37 init), type:=0xA5, XOR R into
 *           X/Y vel low (8.8); port keeps variant 42 + 8.8 step. Type 79 every-4th.
 *   43      proto_fragment 85d6: CALL 8507 (type38 init), type:=0xA6, same XOR;
 *           port keeps variant 43 + 8.8 step. Base fire 74/76/77/78 via 8dd9;
 *           74/77 C from +0x13 (vx), 76 DEC+mirror, 79 INC+&3 (ROM cadence).
 *   21      light_bar 863b: +0x17=4, dir=+0x1a&0x0F, set_vel 8.8, SFX ev0x16;
 *           SAT 0x18 pat 6. Port: spr FRAME_LIGHT_BAR.
 *   38      burst_fragment 8507: +0x17=3, dir=+0x1a&0x0F, set_vel 8.8 (42/43 path sans XOR)
 *   45      light_bar_var 85ee/8608: 3 HP, speed (R&1)+2 via apply_dir_88,
 *           re-aim every 40f (+0x1a += (R&8)-4); aux packs speed|dir, clock=+0x1c;
 *           SAT 0x18 pat 6 (active also toggles 0x20 med). Port: FRAME_LIGHT_BAR.
 *
 * Round 1's map-script never fires cmd 0; the MSX main loop still
 * runs ground_struct_spawn_ctrl with E12D bit1 set at game start.
 * Stream: update_spawn_table_ptr (BE7C->E133 slice + E135/E136 count +
 * timer) and every-16th slot -> type 61 (BF5D/BF94).
 */

#define FRAME_SHOT      0
#define FRAME_DUSTER    1
#define FRAME_TERUZO    2
#define FRAME_LUSTER    3
#define FRAME_BOX       4
#define FRAME_CHIP      5
#define FRAME_LEAD      6
#define FRAME_SIG       7
#define FRAME_SHOT_D    8
#define FRAME_SHOT_T    9
#define FRAME_FIRE      10  /* pat 3 target */
#define FRAME_CIRCLE    11  /* pat 9 lg_circle */
#define FRAME_COMET     12  /* pat 2 comet */
#define FRAME_DEGID_L   13  /* pat 59 degid_left  SAT 0xec */
#define FRAME_DEGID_R   14  /* pat 60 degid_right SAT 0xf0 */
#define FRAME_DEGID     15  /* pat 61 degid_complete SAT 0xf4 */
#define FRAME_VEYBAR_0  16  /* pat 33 SAT 0x84 */
#define FRAME_VEYBAR_1  17  /* pat 34 SAT 0x88 */
#define FRAME_VEYBAR_2  18  /* pat 35 SAT 0x8c */
#define FRAME_VEYBAR_3  19  /* pat 36 SAT 0x90 */
#define FRAME_VEYBAR_4  20  /* pat 37 SAT 0x94 */
/* type39 col-marker complements (SAT primary+0x14); 71f6 dual-SAT sibling */
#define FRAME_VEYBAR_C0 21  /* pat 38 SAT 0x98 */
#define FRAME_VEYBAR_C1 22  /* pat 39 SAT 0x9c */
#define FRAME_VEYBAR_C2 23  /* pat 40 SAT 0xa0 */
#define FRAME_VEYBAR_C3 24  /* pat 41 SAT 0xa4 */
#define FRAME_VEYBAR_C4 25  /* pat 42 SAT 0xa8 */
#define FRAME_DUSTER_C  26  /* pat 23 */
#define FRAME_TERUZO_C  27  /* pat 25 */
#define FRAME_BOX_C     28  /* pat 54 */
#define FRAME_LUSTER_C  29  /* pat 32 */
#define FRAME_UMBER     30  /* pat 55 */
#define FRAME_UMBER_C   31  /* pat 57 */
#define FRAME_STEALTH   32  /* pat 51 SAT 0xCC */
#define FRAME_STEALTH_C 33  /* pat 52 SAT 0xD0 */
/* edge-swooper 26-29: anim table 0x7E68/0x7E70 pats 43-46; compl sat+0x10 */
#define FRAME_SPINNER_0 34  /* pat 43 SAT 0xAC */
#define FRAME_SPINNER_1 35  /* pat 44 SAT 0xB0 */
#define FRAME_SPINNER_2 36  /* pat 45 SAT 0xB4 */
#define FRAME_SPINNER_3 37  /* pat 46 SAT 0xB8 */
#define FRAME_SPINNER_C0 38 /* pat 47 SAT 0xBC */
#define FRAME_SPINNER_C1 39 /* pat 48 SAT 0xC0 */
#define FRAME_SPINNER_C2 40 /* pat 49 SAT 0xC4 */
#define FRAME_SPINNER_C3 41 /* pat 50 SAT 0xC8 */
#define FRAME_SART      42  /* pat 62 sart SAT 0xF8 */
#define FRAME_SART_C    43  /* pat 63 sart_compl SAT 0xFC */
#define FRAME_LOGA      44  /* pat 18 loga_A SAT 0x48 */
#define FRAME_LOGA_C    45  /* pat 19 loga_A_compl SAT 0x4C */
#define FRAME_PLANE     46  /* pat 16 plane SAT 0x40 */
#define FRAME_PLANE_C   47  /* pat 17 plane_compl SAT 0x44 */
#define FRAME_BOLT      48  /* pat 13 super_hard_bolt SAT 0x34 */
#define FRAME_LIGHT_BAR 49  /* pat 6 light_bar SAT 0x18 */
#define FRAME_SIG_TRIPLE 50 /* pat 26 sig_triple SAT 0x68 type 58 */
#define FRAME_SIG_DOUBLE 51 /* pat 27 sig_double SAT 0x6C type 57 */
#define FRAME_MED_CIRCLE 52 /* pat 8 medium_circle SAT 0x20 type 67 */
#define FRAME_LUSTER_A   53 /* pat 29 luster_A SAT 0x74 type 18 */
#define FRAME_LUSTER_A_C 54 /* pat 31 luster_A_compl SAT 0x7C */
#define FRAME_UMBER_B    55 /* pat 56 umber_B SAT 0xE0 type 9 */
#define FRAME_UMBER_B_C  56 /* pat 58 umber_B_compl SAT 0xE8 */


#define KIND_SHOT       2
#define KIND_FIRE       3
#define KIND_BOX        4
#define KIND_DUSTER     10
#define KIND_TERUZO     12
#define KIND_LUSTER     16
#define KIND_EBULLET    37
#define KIND_SIG        56
#define KIND_CHIP       63
#define KIND_GROUND     44
#define KIND_WIDE       70
#define KIND_ORB        72
#define KIND_FIREBOX    82
#define KIND_FIREUP     83
#define KIND_HUSK       80  /* type 0x50; handler_type80 8e14 */
#define KIND_GUN        46
#define KIND_DESCEND    61
#define KIND_RISER      62  /* type 0x3E; handler_type62 8709 */
#define KIND_STEALTH    65
#define KIND_CIRCLE     67
#define KIND_BASE       73
#define KIND_UMBER      7
#define KIND_SPAWNER    69
#define KIND_VEYBAR     22
#define KIND_SWOOP      26
#define KIND_GSWOOP     30
#define KIND_TRACKER    31  /* type 31/33; handler 7f84 / epilogue 7f73 */
#define KIND_FLASH      36
#define KIND_PAIRDESC   57
#define KIND_EXPL       35  /* type 0x23 explosion (8bc1 / explode_enemies) */
#define KIND_PDEAD      60  /* type 0x3C player death FX 0x869E / 0x86F3 */

typedef struct {
    u8  alive;
    u8  kind;
    u8  variant;
    u8  hp;
    u8  timer;
    u8  script;
    s16 x;
    s16 y;
    s8  vx;
    s8  vy;
    u8  ground;     /* 1 = scroll-locked (Y += 1 / frame) */
    u8  aux;        /* type41: (count<<5)|(sense&0x10)|(heading&15)
                     * type45: (speed<<4)|(dir&15); swoop 26-29: child type +0x1d
                     * gswoop 30/32: paired sibling slot index (0xFF=none)
                     * tracker 31/33: paired parent slot (0xFF=stream spawn)
                     * gun 46-55: ang(low4)|side(0x10)|latch(0x40)
                     * teruzo 12-15: +0x18 script index; off 8.8 fracs
                     * type67: +0x1c phase(low5)|mot 0x40|stop 0x80
                     * type36: SAT attr (XOR 0x0e); 8.8 uses dest/bind/script/timer */
    u8  clock;      /* type45: re-aim +0x1c (0x28); base: 8fde +0x1c idx; swoop: fire +0x1e;
                     * gswoop/tracker: +0c (1/2) | bit2 xor-phase | bit6 sense | bit7 lock;
                     * gun 46-55: fire countdown +0x18; teruzo +0x1f;
                     * pairdesc 57/58: +0x1f descend; descender 61: +0x1e;
                     * type67: +0x1b reaim (0x78 then 0x32+(R&0x1e));
                     * stealth 34/65/66: +0x1d volley period; off 8.8 fracs */
    u8  sat;        /* MSX SAT_NAME (+0x03); indexes collision_size_table */
    u8  sat_col;    /* MSX SAT_COLOR (+0x04); TMS ink = low nibble */
    u8  frame;      /* current spr_objs frame (for sat_col remap) */
    u16 dest;       /* idol warp ptr or fire# */
    u16 bind;       /* 8948 nametable VRAM, SET 7 */
    Sprite *spr;
    u8  marker;     /* 1 = type39 sibling for check_col_clear; no MD sprite (folded) */
} Slot;

static Slot s_shot[SHOT_SLOTS];
static Slot s_fire;
static Slot s_en[ENEMY_SLOTS];

static u8  s_spawn_ctrl;
static u8  s_spawn_timer;
static u8  s_spawn_reload;
static u8  s_spawn_base;      /* E133 slice offset into spawn_type_list */
static u8  s_e135;            /* spawn_subtable_ctr */
static u8  s_e136;            /* spawn_subtable_max (count) */
static u8  s_stream_slot;     /* E126 stream_slot_ctr; every-16th -> type 61 */
static u8  s_e124;            /* type35 burst counter; title init = 6 */
static u8  s_e125;            /* bit0 -> BFA0 immediate type 44 */
static u16 s_rng;
static u8  s_box_seq;
static u8  s_fireup_seq;

/* ALC accumulators: E12E/E12F spawn_pos, E131 level_seg, E132 cmd-12 bias. */
static u8  s_spawn_pos_hi;
static u8  s_spawn_pos_lo;
static u8  s_e130;          /* SUB_bfc8 encounter B / disp_c */
static u8  s_e131;
static u8  s_e132;
static u8  s_e141;          /* 76bc shot counter; cleared on type35 init */
static u8  s_e142;          /* 8457 rate-table index; cleared on type35 init */
static u8  s_alc_shots;     /* E140: INC on successful shot spawn (76e5) */
static u8  s_alc_events;

/* shot_power_table 0x778F: vy, cap, sprite-frame (pats 10/11/12). */
static const u8 k_shot_power[6][3] = {
    { 4, 2, FRAME_SHOT },
    { 6, 3, FRAME_SHOT },
    { 8, 2, FRAME_SHOT_D },
    { 9, 3, FRAME_SHOT_D },
    { 10, 2, FRAME_SHOT_T },
    { 14, 3, FRAME_SHOT_T },
};

/* shot_rate_table 0x7761: cadence-2 -> spawn-schedule advance.
 * Type35 8457 indexes [E142+1] with E142<0x11, so indices 1..17; bytes
 * 16..17 are the load_shot_params opcodes at 0x7771 (0x21,0x8F). */
static const u8 k_shot_rate[18] = {
    0x20, 0x10, 0x0A, 0x08, 0x06, 0x05, 0x04, 0x04,
    0x03, 0x03, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02,
    0x21, 0x8F
};

/* xvel_table 0x7758: E10C 0-8 -> 16-dir index (fire 0). */
static const u8 k_xvel_dir[9] = {
    0x06, 0x08, 0x0A, 0x04, 0x0C, 0x0C, 0x02, 0x00, 0x0E
};

/* fire0_dir_table 0x7321: used by fire 7 (not fire 0). E10C 0-8. */
static const u8 k_fire7_dir[9] = {
    0x0B, 0x0B, 0x0B, 0x0C, 0x0C, 0x0C, 0x0D, 0x0D, 0x0D
};

/* vel_dir_table 0x4D65 unit X,Y (mag 128). Fire 3 applies word0=X to Y, word1=Y to X. */
static const s16 k_unit_x[16] = {
       0,   48,   90,  118,  128,  118,   90,   48,
       0,  -48,  -90, -118, -128, -118,  -90,  -48
};
static const s16 k_unit_y[16] = {
     128,  118,   90,   48,    0,  -48,  -90, -118,
    -128, -118,  -90,  -48,    0,   48,   90,  118
};

/* Fire 3/4/5 8.8 accumulators (single type-3 slot). */
static s16 s_fyoff;
static s16 s_fxoff;
static s16 s_fvy;
static s16 s_fvx;
static s16 s_faccel;
static s16 s_fanchor;
static u8  s_fdir;
static u8  s_fexpire;
static u8  s_f6cd;

/* vel_dir_table integer approx (legacy apply_dir); 8.8 uses k_unit_*. */
static const s8 k_dir_vx[16] = {
     0,  1,  1,  2,  2,  2,  1,  1,
     0, -1, -1, -2, -2, -2, -1, -1
};
static const s8 k_dir_vy[16] = {
     2,  2,  1,  1,  0, -1, -1, -2,
    -2, -2, -1, -1,  0,  1,  1,  2
};

/*
 * teruzo_motion_tables 0x7B83/98/AE/CC.
 * Each script is 16-dir indices; bit7 = hold forever.
 */
static const u8 tz_dir0[] = {
    0x08,0x08,0x08,0x08,0x07,0x06,0x05,0x04,
    0x03,0x02,0x01,0x00,0x0F,0x0E,0x0D,0x0C,0x0B,0x8A
};
static const u8 tz_dir1[] = {
    0x00,0x00,0x00,0x00,0x00,0x01,0x02,0x03,
    0x04,0x05,0x06,0x07,0x08,0x09,0x0A,0x0B,0x0C,0x0D,0x8E
};
static const u8 tz_dir2[] = {
    0x06,0x06,0x06,0x06,0x06,0x06,0x06,0x06,0x06,0x06,0x06,0x06,
    0x04,0x02,0x00,0x0E,0x0E,0x0E,0x0E,0x0E,0x0E,0x0E,0x0E,
    0x0D,0x0C,0x0B,0x8A
};
static const u8 tz_dir3[] = {
    0x00,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,0x02,
    0x04,0x06,0x08,0x0A,0x0A,0x0A,0x0A,0x0A,0x0A,0x0A,0x0A,
    0x0B,0x0C,0x0D,0x8E
};
static const u8 *const tz_dirs[4] = { tz_dir0, tz_dir1, tz_dir2, tz_dir3 };
static const u8 tz_dir_n[4] = { 18, 19, 27, 27 };
static const s16 tz_yx[4][2] = {
    { 112, 208 }, { 112, 16 }, { 32, 208 }, { 32, 16 }
};
/* Block byte 2: lower 0x8A / upper 0x89. */
static const u8 tz_col[4] = { 0x8A, 0x8A, 0x89, 0x89 };

/* proto_box_type_table first groups (values 4/5/6). */
static const u8 k_box_types[] = {
    5,6,5, 4,5,6, 5,4,4, 5,5,5, 4,6,4
};

static void spr_sync(Slot *s)
{
    s16 dy = mode_draw_y(s->y);

    if (s->spr)
        SPR_setPosition(s->spr, s->x, dy);
}

/* MSX spawn_col_marker (0x71da): type39 slot, color 0x81 black complement via
 * 71f6. Primaries are folded (rebuild_sprites.py); ASSETS-MD forbids a second
 * MD sprite. Track occupancy only so check_col_clear still sees virtual 0x27.
 * frame arg kept for call-site morph symmetry (veybar/spinner SAT+offset). */
static void marker_place(Slot *s, u16 frame)
{
    (void)frame;
    s->marker = 1;
}

static void marker_kill(Slot *s)
{
    s->marker = 0;
}

/* spr_objs frame -> MSX SAT_NAME (primary). Complements folded into primary. */
static const u8 k_frame_sat[57] = {
    0x28, /* 0  FRAME_SHOT */
    0x58, /* 1  FRAME_DUSTER */
    0x60, /* 2  FRAME_TERUZO */
    0x78, /* 3  FRAME_LUSTER */
    0xD4, /* 4  FRAME_BOX */
    0x00, /* 5  FRAME_CHIP */
    0x1C, /* 6  FRAME_LEAD */
    0x70, /* 7  FRAME_SIG */
    0x2C, /* 8  FRAME_SHOT_D */
    0x30, /* 9  FRAME_SHOT_T */
    0x0C, /* 10 FRAME_FIRE */
    0x24, /* 11 FRAME_CIRCLE */
    0x08, /* 12 FRAME_COMET */
    0xEC, /* 13 FRAME_DEGID_L */
    0xF0, /* 14 FRAME_DEGID_R */
    0xF4, /* 15 FRAME_DEGID */
    0x84, /* 16 FRAME_VEYBAR_0 */
    0x88, /* 17 */
    0x8C, /* 18 */
    0x90, /* 19 */
    0x94, /* 20 */
    0x98, /* 21 FRAME_VEYBAR_C0 */
    0x9C, /* 22 */
    0xA0, /* 23 */
    0xA4, /* 24 */
    0xA8, /* 25 */
    0x5C, /* 26 FRAME_DUSTER_C */
    0x64, /* 27 FRAME_TERUZO_C */
    0xD8, /* 28 FRAME_BOX_C */
    0x80, /* 29 FRAME_LUSTER_C */
    0xDC, /* 30 FRAME_UMBER */
    0xE4, /* 31 FRAME_UMBER_C */
    0xCC, /* 32 FRAME_STEALTH */
    0xD0, /* 33 FRAME_STEALTH_C */
    0xAC, /* 34 FRAME_SPINNER_0 */
    0xB0, /* 35 */
    0xB4, /* 36 */
    0xB8, /* 37 */
    0xBC, /* 38 FRAME_SPINNER_C0 */
    0xC0, /* 39 */
    0xC4, /* 40 */
    0xC8, /* 41 */
    0xF8, /* 42 FRAME_SART */
    0xFC, /* 43 FRAME_SART_C */
    0x48, /* 44 FRAME_LOGA */
    0x4C, /* 45 FRAME_LOGA_C */
    0x40, /* 46 FRAME_PLANE */
    0x44, /* 47 FRAME_PLANE_C */
    0x34, /* 48 FRAME_BOLT */
    0x18, /* 49 FRAME_LIGHT_BAR */
    0x68, /* 50 FRAME_SIG_TRIPLE */
    0x6C, /* 51 FRAME_SIG_DOUBLE */
    0x20, /* 52 FRAME_MED_CIRCLE */
    0x74, /* 53 FRAME_LUSTER_A */
    0x7C, /* 54 FRAME_LUSTER_A_C  pat31 SAT 0x7C */
    0xE0, /* 55 FRAME_UMBER_B */
    0xE8  /* 56 FRAME_UMBER_B_C */
};


/* Frame -> baked TMS body index in objs.png (rebuild_sprites.py). */
static const u8 k_frame_color[57] = {
    15, 9, 10, 14, 15, 11, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15,
    7, 7, 7, 7, 7,
    1, 1, 1, 1, 1,
    1, 1, 1, 1,
    15, 1, 8, 1,
    14, 14, 14, 14, 1, 1, 1, 1,
    7, 1, 15, 1, 7, 1, 15, 4, 15, 15, 6,
    11, 1, 7, 1
};

static void remap_tiles(u8 *dst, const u8 *src, u16 nbytes, u8 from, u8 to)
{
    u16 i;

    for (i = 0; i < nbytes; i++)
    {
        u8 b = src[i];
        u8 hi = (u8)(b >> 4);
        u8 lo = (u8)(b & 0x0F);

        if (hi == from)
            hi = to;
        if (lo == from)
            lo = to;
        dst[i] = (u8)((hi << 4) | lo);
    }
}

/* Upload spr_objs frame tiles, remapping baked TMS body -> sat_col low nibble.
 * PAL2 indices match rebuild_sprites / TMS low nibble. Complement (1) untouched. */
static void spr_upload_color(Slot *s)
{
    Sprite *sp = s->spr;
    TileSet *ts;
    u8 baked;
    u8 want;
    u16 nbytes;
    u16 vaddr;
    const u8 *src;
    u8 *buf;

    if (!sp || !sp->frame || s->frame >= 57)
        return;
    ts = sp->frame->tileset;
    if (!ts || !ts->numTile)
        return;

    baked = k_frame_color[s->frame];
    /* Complement-only / blank frames keep verbatim pixels. */
    if (baked <= 1)
        want = baked;
    else if (s->sat_col)
        want = (u8)(s->sat_col & 0x0F);
    else
        want = baked;

    nbytes = (u16)(ts->numTile * 32);
    vaddr = (u16)((sp->attribut & TILE_INDEX_MASK) * 32);
    src = (const u8 *)FAR_SAFE(ts->tiles, nbytes);

    if (want == baked)
    {
        DMA_queueDma(DMA_VRAM, (void *)src, vaddr, (u16)(nbytes / 2), 2);
        return;
    }

    buf = DMA_allocateAndQueueDma(DMA_VRAM, vaddr, (u16)(nbytes / 2), 2);
    if (!buf)
    {
        DMA_queueDma(DMA_VRAM, (void *)src, vaddr, (u16)(nbytes / 2), 2);
        return;
    }
    remap_tiles(buf, src, nbytes, baked, want);
}

static void spr_frame_cb(Sprite *sp)
{
    Slot *s = (Slot *)(u32)sp->data;

    /* We own tile upload so sat_col remaps are not overwritten. */
    sp->status &= (u16)~SPR_FLAG_AUTO_TILE_UPLOAD;
    if (s)
        spr_upload_color(s);
}

static void spr_set_sat_col(Slot *s, u8 col)
{
    s->sat_col = col;
    if (s->spr && s->spr->frame)
        spr_upload_color(s);
}

static void spr_place(Slot *s, u16 frame)
{
    s16 prev;

    if (frame < 57)
        s->sat = k_frame_sat[frame];
    s->frame = (u8)frame;
    if (!s->spr)
    {
        s->spr = SPR_addSpriteEx(&spr_objs, s->x, mode_draw_y(s->y),
                                 TILE_ATTR(PAL2, TRUE, FALSE, FALSE),
                                 SPR_FLAG_AUTO_VRAM_ALLOC | SPR_FLAG_AUTO_VISIBILITY);
        if (s->spr)
        {
            s->spr->data = (u32)s;
            SPR_setFrameChangeCallback(s->spr, spr_frame_cb);
            SPR_setAnimAndFrame(s->spr, 0, frame);
        }
    }
    else
    {
        prev = s->spr->frameInd;
        spr_sync(s);
        SPR_setAnimAndFrame(s->spr, 0, frame);
        /* Same frame: engine skips callback â€” push tint now. */
        if (prev == (s16)frame)
            spr_upload_color(s);
    }
}

static void spr_kill(Slot *s)
{
    marker_kill(s);
    if (s->spr)
    {
        SPR_releaseSprite(s->spr);
        s->spr = NULL;
    }
    s->alive = 0;
    s->kind = 0;
    s->variant = 0;
    s->hp = 0;
    s->timer = 0;
    s->script = 0;
    s->ground = 0;
    s->aux = 0;
    s->clock = 0;
    s->sat = 0;
    s->sat_col = 0;
    s->frame = 0;
    s->dest = 0;
    s->bind = 0;
}

static u8 rnd(void)
{
    s_rng = (u16)(s_rng * 2053 + 13849);
    return (u8)(s_rng >> 8);
}

static Slot *free_enemy(void)
{
    u8 i;
    for (i = 0; i < ENEMY_SLOTS; i++)
        if (!s_en[i].alive)
            return &s_en[i];
    return NULL;
}

/* type 0x23 / handler_type35: +0x18=0; first frame arms 84d1 + SFX/score. */
static void spawn_expl(s16 x, s16 y)
{
    Slot *e = free_enemy();

    if (!e)
        return;
    e->alive = 1;
    e->kind = KIND_EXPL;
    e->variant = 0;
    e->hp = 0;
    e->timer = 0;
    e->script = 0;
    e->ground = 0;
    e->aux = 0;
    e->clock = 0;
    e->dest = 0;
    e->bind = 0;
    e->x = x;
    e->y = y;
    e->vx = 0;
    e->vy = 0;
    e->spr = NULL;
    e->marker = 0;
    spr_place(e, FRAME_LEAD);
}

/* LAB_ram_8bc1 / SUB_ram_8bca: type 0x23 at (X,Y) +/- (R&0x1F)-0x0F. */
static void scatter_expl(s16 x, s16 y)
{
    u8 ry = rnd();
    u8 rx = rnd();

    spawn_expl((s16)(x + (s16)((ry & 0x1F) - 0x0F)),
               (s16)(y + (s16)((rx & 0x1F) - 0x0F)));
}

/* 0x84D1 type35 anim: (sat_name,sat_color) pairs; init +0F=1 skips frame 0. */
static const u8 k_t35_frame[6] = {
    FRAME_LEAD, FRAME_LEAD, FRAME_MED_CIRCLE, FRAME_CIRCLE, FRAME_MED_CIRCLE, FRAME_LEAD
};
static const u8 k_t35_col[6] = {
    0x48, 0x8A, 0x8E, 0x8F, 0x8D, 0x89
};

/* 0x86F3 type60 death: 11 (sat_name,sat_color); +0F=1 skips empty frame 0.
 * expand lead->med->lg then contract; tick_rate=4; +0C=4 bit2-only. */
static const u8 k_t60_frame[11] = {
    0, FRAME_LEAD, FRAME_LEAD, FRAME_MED_CIRCLE, FRAME_MED_CIRCLE,
    FRAME_CIRCLE, FRAME_CIRCLE, FRAME_MED_CIRCLE, FRAME_MED_CIRCLE,
    FRAME_LEAD, FRAME_LEAD
};
static const u8 k_t60_col[11] = {
    0xC9, 0x86, 0x8F, 0x88, 0x8F, 0x89, 0x8F, 0x88, 0x89, 0x86, 0x8F
};

/* Remap living slot -> type 0x23. score_t is +0x18 for 4a6a (0 = scatter). */
static void become_expl(Slot *e, u8 score_t)
{
    marker_kill(e);
    e->kind = KIND_EXPL;
    e->variant = score_t;
    e->hp = 0;
    e->timer = 0;
    e->script = 0;          /* first frame: ALC + SFX + score + 84d1 arm */
    e->ground = 0;
    e->aux = 0;
    e->clock = 0;
    e->vx = 0;
    e->vy = 0;
    if (e->spr)
        SPR_setAnimAndFrame(e->spr, 0, FRAME_LEAD);
    else
        spr_place(e, FRAME_LEAD);
}

/* handler_type60 0x869E: fire_reset + SRL E132/E12E + ev16 + arm 86F3.
 * Runs in an enemy slot (MD ship is separate); clear sets E102 bit0. */
void entity_spawn_pdeath(s16 x, s16 y)
{
    Slot *e = free_enemy();

    /* 86b7/86bc: SRL E132, SRL E12E (ease ALC on death). */
    s_e132 = (u8)(s_e132 >> 1);
    s_spawn_pos_hi = (u8)(s_spawn_pos_hi >> 1);

    if (!e)
    {
        /* No slot: still signal death->continue so lives/respawn proceed. */
        sound_play_event(SND_EV_DEATH);
        player_e102_set(0x01);
        return;
    }
    e->alive = 1;
    e->kind = KIND_PDEAD;
    e->variant = 60;
    e->hp = 0;
    e->timer = 0;
    e->script = 0;          /* first frame: SFX + 86F3 arm */
    e->ground = 0;
    e->aux = 0;
    e->clock = 0;
    e->dest = 0;
    e->bind = 0;
    e->x = x;
    e->y = y;
    e->vx = 0;
    e->vy = 0;
    e->spr = NULL;
    e->marker = 0;
    e->sat = 0;
    e->sat_col = 0;
    e->frame = 0;
}

static int aabb(s16 x1, s16 y1, s16 w1, s16 h1,
                s16 x2, s16 y2, s16 w2, s16 h2)
{
    return (x1 < (s16)(x2 + w2)) && ((s16)(x1 + w1) > x2)
        && (y1 < (s16)(y2 + h2)) && ((s16)(y1 + h1) > y2);
}


/* collision_size_table 0x45C9: Y/X half-sizes interleaved, indexed by
 * sat_name>>1. Hitbox = [pos+half, pos+16-half] => origin pos+half,
 * size 16-2*half (hitbox_setup_ix 0x45A0). Bytes through 0x4648 cover
 * sat_name 0x00..0xFE (high patterns read past the 32-byte KB'd core). */
static const u8 k_col_size[128] = {
    0x00, 0x00, 0x03, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x03, 0x03, 0x05, 0x00, 0x06, 0x06,
    0x01, 0x01, 0x00, 0x00, 0x00, 0x06, 0x00, 0x03, 0x00, 0x00, 0x02, 0x02, 0x04, 0x04, 0x04, 0x04,
    0x02, 0x01, 0x02, 0x01, 0x00, 0x03, 0x00, 0x03, 0x00, 0x02, 0x00, 0x02, 0x00, 0x03, 0x00, 0x00,
    0x02, 0x02, 0x00, 0x00, 0x00, 0x01, 0x02, 0x01, 0x02, 0x06, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00,
    0x00, 0x00, 0x02, 0x00, 0x04, 0x00, 0x06, 0x00, 0x04, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0x01, 0x02, 0x03, 0x02, 0x07, 0x02, 0x03, 0x02, 0x01,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x02,
    0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x03, 0x00, 0x03, 0x00, 0x02, 0x00, 0x02, 0x00, 0x02
};

#define SAT_PLAYER  0x38  /* pat14 ship; half 4,4 => 8x8 */

static void hitbox_of(u8 sat, s16 x, s16 y, s16 *ox, s16 *oy, s16 *ow, s16 *oh)
{
    u8 idx = (u8)(sat >> 1);
    u8 hy = k_col_size[idx];
    u8 hx = k_col_size[(u8)(idx + 1)];
    if (hx > 7) hx = 7;
    if (hy > 7) hy = 7;
    *ox = (s16)(x + (s16)hx);
    *oy = (s16)(y + (s16)hy);
    *ow = (s16)(16 - (s16)(hx << 1));
    *oh = (s16)(16 - (s16)(hy << 1));
}

static int hit_overlap(s16 x1, s16 y1, u8 sat1, s16 x2, s16 y2, u8 sat2)
{
    s16 ax, ay, aw, ah, bx, by, bw, bh;
    hitbox_of(sat1, x1, y1, &ax, &ay, &aw, &ah);
    hitbox_of(sat2, x2, y2, &bx, &by, &bw, &bh);
    return aabb(ax, ay, aw, ah, bx, by, bw, bh);
}

/* death_transition_table 0x716B (collision_response 0x453E): type&0x7F ->
 * post-collision class/type written back to both parties. "Classes": */
#define CLS_NONE   0x00  /* inactive */
#define CLS_FIRE19 0x13  /* fire weapon -> type 19 converter */
#define CLS_EXPL   0x23  /* standard enemy explosion (type 35) */
#define CLS_MARK   0x27  /* col-marker stays type 39 */
#define CLS_CLEAR  0x28  /* instant despawn (type 40) */
#define CLS_PDEAD  0x3C  /* player death explosion (type 60) */
#define CLS_BASE   0x50  /* base/structure damage (type 80 husk) */

static const u8 k_death_trans[90] = {
    0x00, 0x3C, 0x28, 0x13, 0x23, 0x23, 0x23, 0x23, 0x23, 0x23, 0x23, 0x23, 0x23, 0x23, 0x23, 0x23,
    0x23, 0x23, 0x23, 0x23, 0x23, 0x23, 0x23, 0x23, 0x23, 0x23, 0x23, 0x23, 0x23, 0x23, 0x23, 0x23,
    0x23, 0x23, 0x23, 0x23, 0x23, 0x28, 0x28, 0x27, 0x28, 0x28, 0x28, 0x28, 0x23, 0x23, 0x23, 0x23,
    0x23, 0x23, 0x23, 0x23, 0x23, 0x23, 0x23, 0x23, 0x23, 0x23, 0x23, 0x23, 0x3C, 0x23, 0x28, 0x28,
    0x28, 0x23, 0x23, 0x23, 0x28, 0x28, 0x50, 0x50, 0x28, 0x50, 0x50, 0x50, 0x50, 0x50, 0x50, 0x50,
    0x28, 0x50, 0x28, 0x28, 0x50, 0x50, 0x50, 0x50, 0x50, 0x50
};

/* Which entity_post leg runs on MSX (gates which AABB overlaps count). */
#define POST_SHOT  0x01  /* check_hit_shots 44F9 / shots-only 44CA / full 44BA */
#define POST_SHIP  0x02  /* check_hit_player 44D4 / ship-only 44B0/44A6 / full */
#define POST_PICK  0x04  /* ship touch = pickup; handler restores player after 453E */

static u8 slot_msx_type(const Slot *e)
{
    u8 k = e->kind;
    u8 v = e->variant;

    if (k == KIND_EBULLET || k == KIND_BOX || k == KIND_LUSTER || k == KIND_SIG
        || k == KIND_GROUND || k == KIND_WIDE || k == KIND_FIREBOX
        || k == KIND_STEALTH || k == KIND_GUN || k == KIND_UMBER
        || k == KIND_VEYBAR || k == KIND_SWOOP || k == KIND_GSWOOP
        || k == KIND_TRACKER || k == KIND_PAIRDESC || k == KIND_BASE
        || k == KIND_DESCEND || k == KIND_TERUZO)
    {
        if (v)
            return v;
    }
    if (k == KIND_FIREUP) return 83;
    if (k == KIND_HUSK) return 80;
    if (k == KIND_ORB) return 72;
    if (k == KIND_CHIP) return 63;
    if (k == KIND_RISER) return 62;
    if (k == KIND_SPAWNER) return (v ? v : 69);
    return k;
}

static u8 death_class(u8 t)
{
    t &= 0x7F;
    if (t >= 90)
        return CLS_EXPL;
    return k_death_trans[t];
}

/* MSX post-path by type (confirmed handlers). Default = full 44BA. */
static u8 post_flags(u8 t)
{
    t &= 0x7F;
    /* 44B0 ship-only pickups: remap then restore player */
    if (t == 62 || t == 63 || t == 72 || t == 83)
        return (u8)(POST_SHIP | POST_PICK);
    /* 44A6 ship-only hostiles - player shots pass through.
     * Scoped to KIND_EBULLET in enemy_takes_shots (not bare type id). */
    if (t == 20 || t == 37 || t == 38 || t == 41 || t == 42 || t == 43)
        return POST_SHIP;
    /* no entity_post: spawners, explosion, husk, marker, clear */
    if (t == 11 || t == 69 || t == 35 || t == 60 || t == 80 || t == 39 || t == 40 || t == 0)
        return 0;
    /* 44CA shots-only ground structures / bases / firebox / wide */
    if (t == 70 || t == 71 || t == 81 || t == 82
        || (t >= 73 && t <= 79) || (t >= 84 && t <= 89))
        return POST_SHOT;
    /* full entity_post 44BA (airborne, type21/36/44/45, guns, ...) */
    return (u8)(POST_SHOT | POST_SHIP);
}

/* Shot AABB gate. 44A6 leads/fragments are unshootable only as KIND_EBULLET.
 * Type 21/45 light bars are also KIND_EBULLET but use 44BA (shootable).
 * Non-bullet kinds still take shots if type-id glitched into ship-only. */
static int enemy_takes_shots(const Slot *e)
{
    u8 et = slot_msx_type(e);
    u8 pf = post_flags(et);

    if (pf & POST_PICK)
        return 0;
    if (!pf)
        return 0;
    if (e->kind == KIND_EBULLET
        && (et == 20 || et == 37 || et == 38 || et == 41 || et == 42 || et == 43))
        return 0;
    if (pf & POST_SHOT)
        return 1;
    if (e->kind != KIND_EBULLET && e->kind != KIND_CHIP && e->kind != KIND_ORB
        && e->kind != KIND_FIREUP && e->kind != KIND_RISER
        && e->kind != KIND_EXPL && e->kind != KIND_HUSK
        && e->kind != KIND_SPAWNER)
        return 1;
    return 0;
}

static void apply_dir(Slot *e, u8 dir)
{
    e->vx = k_dir_vx[dir & 15];
    e->vy = k_dir_vy[dir & 15];
}

static void apply_dir_fast(Slot *e, u8 dir)
{
    /* set_velocity_from_dir: vel_dir word0 -> IX+8/9 (Y), word1 -> IX+0a/0b (X).
     * Fire 0 speed 0xC2 = x3 x4 x2 on unit 128 -> 12 px/frame cardinal. */
    e->vx = (s8)(k_dir_vy[dir & 15] * 6);
    e->vy = (s8)(k_dir_vx[dir & 15] * 6);
}

static void apply_dir_fire7(Slot *e, u8 dir)
{
    /* Fire 7 speed 0xC3: same prescale x4, count 3 vs fire 0 count 2. */
    e->vx = (s8)(k_dir_vy[dir & 15] * 9);
    e->vy = (s8)(k_dir_vx[dir & 15] * 9);
}

static s16 clamp16(s16 v, s16 lo, s16 hi)
{
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

static void alc_recompute(void)
{
    u16 pos;
    u8 half;
    u8 de;
    u8 off;
    u8 count;
    u8 idx;
    u8 r;

    /* update_spawn_table_ptr 0xBE27:
     * A = E12E + E132, sat 0xFF, clamp 0xA0 -> 0x9F.
     * DE = (A>>1) & 0x7E -> BE7C pair {offset, count};
     * E135 clamp if >= count; E136 = count;
     * timer from BE76[A>>5]; E133 = BECC + offset. */
    pos = (u16)s_spawn_pos_hi + (u16)s_e132;
    if (pos > 0xFF)
        pos = 0xFF;
    if (pos >= 0xA0)
        pos = 0x9F;
    half = (u8)(pos >> 1);
    de = (u8)(half & 0x7E);
    if (de + 1u >= SPAWN_PAIR_LEN)
        de = (u8)(SPAWN_PAIR_LEN - 2);
    off = spawn_pair_table[de];
    count = spawn_pair_table[de + 1];
    if (s_e135 >= count)
        s_e135 = 0;
    s_e136 = count;
    s_spawn_base = off;
    idx = (u8)(half >> 4);          /* pos >> 5 */
    if (idx >= SPAWN_TIMER_LEN)
        idx = SPAWN_TIMER_LEN - 1;
    r = spawn_timer_ramp[idx];
    /* BE27 writes both E137 (live) and E138 (reload). reload 0 would
     * DEC-wrap to 255 on MSX; keep a 255-frame stall. */
    s_spawn_reload = r ? r : 255;
    s_spawn_timer = s_spawn_reload;
}

static void spawn_pos_add(u8 n)
{
    /* BF7A lo half: E12F += n; on carry INC E12E sat 0xFF (silent, no
     * sticky bit0). Caller does BF8C INC E142. Slice chase is sticky
     * bit0-only via BE27 from dec/inc_encounter_a / cmd12 / shot carry. */
    u16 lo = (u16)s_spawn_pos_lo + n;
    s_spawn_pos_lo = (u8)lo;
    if (lo > 0xFF)
    {
        s_spawn_pos_hi++;
        if (!s_spawn_pos_hi)
            s_spawn_pos_hi--;
    }
}

static void apply_dir_88(Slot *e, u8 dir, u8 speed);

static void teruzo_step(Slot *e)
{
    /* 7b55-7b78: every 8f read dir from script; set_velocity_from_dir
     * speed +17=4. Preserve X/Y fracs (Original only writes vel words). */
    u8 si = e->variant & 3;
    u8 idx = e->aux;
    u8 d;
    u8 xf;
    u8 yf;

    if (idx >= tz_dir_n[si])
        idx = (u8)(tz_dir_n[si] - 1);
    d = tz_dirs[si][idx];
    xf = e->script;
    yf = e->timer;
    apply_dir_88(e, d, 4);
    e->script = xf;
    e->timer = yf;
    if (!(d & 0x80) && (u8)(idx + 1) < tz_dir_n[si])
        e->aux = (u8)(idx + 1);
}

static void spawn_duster(Slot *e)
{
    /* handler_type10_duster 0x7a2a.
     * 8.8 packing matches type20/26: dest=Xvel, bind=Yvel,
     * script=Xfrac, timer=Yfrac. aux=+0x14 X-home tgt.
     * +0c=0x13 Y|X motion|X_homing; Yvel 0x0300; +16=8, +17=1. */
    u8 r1 = rnd();
    u8 r2 = rnd();
    u8 x;

    e->kind = KIND_DUSTER;
    e->variant = 0;
    e->hp = 1;
    e->ground = 0;
    /* random_x_pos 71c5: X=(H&0x7f)+(L&0x1f)+0x28, Y=0 */
    x = (u8)((r1 & 0x7f) + (r2 & 0x1f) + 0x28);
    e->x = (s16)x;
    e->y = 0;
    e->vx = 0;
    e->vy = 0;
    e->dest = 0;            /* Xvel 8.8 start 0 */
    e->bind = 0x0300;       /* Yvel 8.8: vy=3 vy_frac=0 */
    e->script = 0;          /* X frac */
    e->timer = 0;           /* Y frac */
    /* +0x14: X<0x88 -> 0xFF else 0x00 (drift toward opposite edge) */
    e->aux = (x < 0x88) ? 0xFF : 0x00;
    e->clock = 0;
    e->alive = 1;
    spr_place(e, FRAME_DUSTER);
    marker_place(e, FRAME_DUSTER_C);  /* spawn_col_marker SAT 0x5C */
}

static void duster_step(Slot *e)
{
    /* entity_update 4898 +0c=0x13: X_homing then Y/X 8.8 motion.
     * X_homing_sub 496B: tgt=aux(+14), accel=+16=8, B=+17=1.
     * vx/vy 0 so shared pass inert. */
    u16 xvel = e->dest;
    s32 xpos;
    s32 ypos;

    if ((u8)e->x != e->aux)
    {
        if ((u8)e->x < e->aux)
            xvel = (u16)(xvel + 0x0008);
        else
            xvel = (u16)(xvel - 0x0008);
    }
    e->dest = xvel;

    ypos = ((s32)e->y << 8) | (u8)e->timer;
    ypos += (s16)e->bind;
    e->timer = (u8)ypos;
    e->y = (s16)(ypos >> 8);

    xpos = ((s32)e->x << 8) | (u8)e->script;
    xpos += (s16)xvel;
    e->script = (u8)xpos;
    e->x = (s16)(xpos >> 8);
    e->vx = 0;
    e->vy = 0;
}

static void spawn_luster(Slot *e, u8 type)
{
    /* handler_type16 0x7beb / type17 0x7c8a / type18 0x7cb3.
     * 8.8 packing matches type10 duster: dest=Xvel, bind=Yvel,
     * script=Xfrac, timer=Yfrac. aux=+14 X-home tgt; clock=+1d.
     * All: Yvel 0x0200, Y=0. Children: 16/17->38, 18->37 aim. */
    u8 right = rnd() & 1;

    e->kind = KIND_LUSTER;
    e->variant = type;
    e->hp = 1;
    e->ground = 0;
    e->bind = 0x0200;       /* Yvel 8.8: +09=2 */
    e->script = 0;          /* X frac */
    e->timer = 0;           /* Y frac */
    e->y = 0;
    e->vx = 0;
    e->vy = 0;
    e->alive = 1;
    if (type == 18)
    {
        /* +0c=0x13; +16=0x0e; +17=2; +1d=0x30; sides 60/ff or 90/00 */
        e->x = right ? 0x90 : 0x60;
        e->dest = right ? 0x0300 : 0xFD00;
        e->aux = right ? 0x00 : 0xFF;   /* +14 X-home tgt */
        e->clock = 0x30;                /* +1d fire */
    }
    else if (type == 17)
    {
        /* +0c=0x13; Xvel 0xFC00; +16=0x40; +17=4; sides 30/01 or B0/07 */
        e->x = right ? 0xB0 : 0x30;
        e->dest = 0xFC00;
        e->aux = (u8)e->x;              /* +14 = spawn X */
        e->clock = right ? 7 : 1;       /* +1d dir for type38 */
    }
    else
    {
        /* type16: +0c=0x01 Y-only; sides 40/01 or B0/07; +1e band 0xC0 */
        e->x = right ? 0xB0 : 0x40;
        e->dest = 0;
        e->aux = 0;
        e->clock = right ? 7 : 1;       /* +1d dir for type38 */
    }
    if (type == 18)
    {
        spr_place(e, FRAME_LUSTER_A);     /* pat 29 SAT 0x74 color 0x8B */
        marker_place(e, FRAME_LUSTER_A_C); /* pat 31 */
    }
    else
    {
        spr_place(e, FRAME_LUSTER);       /* pat 30 SAT 0x78 color 0x8E */
        marker_place(e, FRAME_LUSTER_C);  /* pat 32 */
    }
}

static void spawn_teruzo(Slot *e, u8 type)
{
    /* MSX: (type & ~1) + random bit picks one of the four corner scripts.
     * 7b37 +0c=3 X|Y; 7b49 +17=4; 7b41 +1f=1; 7b45 +18=0. */
    u8 pair = (u8)((type & 0xFE) == 14 ? 2 : 0);
    u8 si = (u8)(pair + (rnd() & 1));

    e->kind = KIND_TERUZO;
    e->variant = si;
    e->hp = 1;
    e->aux = 0;                 /* +0x18 script index */
    e->clock = 1;               /* +0x1F=1 first dir next frame */
    e->x = tz_yx[si][1];
    e->y = tz_yx[si][0];
    e->dest = 0;                /* Xvel 8.8 */
    e->bind = 0;                /* Yvel 8.8 */
    e->script = 0;              /* X frac */
    e->timer = 0;               /* Y frac */
    e->vx = 0;
    e->vy = 0;
    e->alive = 1;
    e->sat_col = tz_col[si];
    spr_place(e, FRAME_TERUZO);
    marker_place(e, FRAME_TERUZO_C);  /* spawn_col_marker SAT 0x64 */
}

static void spawn_box(Slot *e, u8 type, s16 x, s16 y)
{
    /* handler_type4_box 0x7826 (types 4/5/6 share): after countdown
     * IX+08=0xC0 Yvel.lo, +0c=1 Y_motion. Port keeps integer vy=1
     * (prior approx) and packs frac 0xC0 like type20/guns:
     * dest=Xvel, bind=Yvel, script=Xfrac, timer=Yfrac. */
    e->kind = KIND_BOX;
    e->variant = type;
    e->hp = 5;                  /* handler_type4_box +0x19 = 5 */
    e->ground = 0;
    e->x = x;
    e->y = y;
    e->vx = 0;
    e->vy = 0;
    e->dest = 0;                /* Xvel 8.8 (Y-only) */
    e->bind = 0x01C0;           /* Yvel 8.8: vy=1 vy_frac=0xC0 */
    e->script = 0;              /* X frac */
    e->timer = 0;               /* Y frac */
    e->alive = 1;
    spr_place(e, FRAME_BOX);
    marker_place(e, FRAME_BOX_C);  /* spawn_col_marker SAT 0xD8 */
}

static void spawn_chip_at(s16 x, s16 y)
{
    /* Free-spawn chip: Y-only 8.8 at 1.0 px/frame (prior integer vy=1).
     * Box-6 death converts in-place and keeps the box bind=0x01C0. */
    Slot *e = free_enemy();
    if (!e)
        return;
    e->kind = KIND_CHIP;
    e->variant = 0;
    e->hp = 1;
    e->ground = 0;
    e->x = x;
    e->y = y;
    e->vx = 0;
    e->vy = 0;
    e->dest = 0;
    e->bind = 0x0100;
    e->script = 0;
    e->timer = 0;
    e->alive = 1;
    spr_place(e, FRAME_CHIP);
}

static void apply_dir_88(Slot *e, u8 dir, u8 speed);

/* handler_type56_sig_single @ 819d: E=4 then 81a8 (speed 5,
 * set_velocity_from_dir, +0c=3). Shares ROM 81a8 with type59. */
static void spawn_sig(Slot *e)
{
    const ModeAssets *a = mode_assets();

    e->kind = KIND_SIG;
    e->variant = 56;
    e->hp = 1;
    e->ground = 0;
    e->x = 8;
    e->y = (s16)(16 + (rnd() % (a->playfield_h / 2)));
    apply_dir_88(e, 4, 5);      /* E=4; +0x17=5 -> set_velocity_from_dir */
    e->alive = 1;
    e->sat_col = 0x8F;           /* +04; XOR 0x09 each frame @ 81c3 */
    spr_place(e, FRAME_SIG);
}

static void spawn_ebullet_dir(s16 x, s16 y, u8 dir)
{
    Slot *e = free_enemy();
    if (!e)
        return;
    e->kind = KIND_EBULLET;
    e->variant = 37;  /* MSX type37 lead; dir is aim only (was mis-typed as type) */
    e->hp = 1;
    e->timer = 0;
    e->script = 0;
    e->x = x;
    e->y = y;
    apply_dir(e, dir);
    e->alive = 1;
    spr_place(e, FRAME_LEAD);
}

static void spawn_fireup(Slot *e)
{
    const ModeAssets *a = mode_assets();

    e->kind = KIND_FIREUP;
    e->variant = (u8)(s_fireup_seq & 7);  /* +0x1c weapon number 0-7 */
    s_fireup_seq++;
    e->hp = 1;
    e->timer = 0;
    e->script = 0;
    e->x = (s16)(24 + (rnd() % (a->playfield_w - 48)));
    e->y = (s16)(a->playfield_h - 24);
    e->vx = 0;
    e->vy = 0;
    e->alive = 1;
    spr_place(e, FRAME_CIRCLE);
}

static u8 aim_4c91(s16 x, s16 y);

static void spawn_ground_fall(Slot *e, u8 type, s16 x, s16 y, u16 dest)
{
    /* handler_type44_ground_structure 0x82d0:
     * +0x17 = (R&3)+1; player_pos_snapshot 4c8b (= aim_4c91 +
     * set_velocity_from_dir 8.8); +0c=3 X|Y motion; +03=0x40 plane,
     * +04=0x83 cyan; spawn_col_marker SAT 0x44. Port: dest/bind/
     * script/timer 8.8 like type20/37; vx/vy 0 so shared pass inert.
     * cmd1 type 0x45 writes script pattern into +0x03 (dest low). */
    u8 speed = (u8)((rnd() & 3) + 1);
    u8 sat = (u8)((dest & 0xFF) ? (dest & 0xFF) : 0x40);

    e->kind = KIND_GROUND;
    e->variant = type;
    e->hp = 3;
    e->ground = 0;
    e->dest = dest;
    e->x = x;
    e->y = y;
    e->alive = 1;
    apply_dir_88(e, aim_4c91(x, y), speed);
    spr_place(e, FRAME_PLANE);       /* visual plane; hitbox from sat */
    e->sat = sat;
    marker_place(e, FRAME_PLANE_C);  /* spawn_col_marker SAT 0x44 */
}

/* Type 80: handler_type80 8e14. dest = +0x18 subtype for 849c (0 after 90dc). */
static void spawn_husk_at(Slot *e, s16 x, s16 y)
{
    e->kind = KIND_HUSK;
    e->variant = 80;
    e->hp = 0;
    e->timer = 0;
    e->script = 0;
    e->ground = 1;
    e->dest = 0;
    e->bind = 0;
    e->x = x;
    e->y = y;
    e->vx = 0;
    e->vy = 0;
    e->alive = 1;
    spr_place(e, FRAME_BOX);
}

/* structure_award_index_table 0x4B29, types 0-89. 4a6a uses +0x18. */
static const u8 k_struct_award[90] = {
    0x00,0x00,0x00,0x00,0x07,0x07,0x07,0x06,0x06,0x07,0x04,0x04,0x06,0x06,0x06,0x06,
    0x07,0x07,0x08,0x00,0x02,0x01,0x07,0x07,0x07,0x07,0x08,0x08,0x08,0x08,0x06,0x06,
    0x08,0x08,0x08,0x00,0x09,0x02,0x02,0x02,0x00,0x03,0x03,0x03,0x02,0x03,0x06,0x06,
    0x03,0x03,0x03,0x03,0x03,0x03,0x03,0x03,0x02,0x03,0x04,0x02,0x00,0x07,0x0F,0x0B,
    0x09,0x0A,0x0B,0x03,0x0B,0x0A,0x06,0x06,0x00,0x07,0x06,0x05,0x06,0x06,0x07,0x0A,
    0x00,0x13,0x06,0x00,0x08,0x09,0x09,0x07,0x07,0x08
};

/* 8eaf large_descender_color_table: type61 SAT (+04) + type83 +0x1d.
 * Type61: E149&7 index; if table==0x81 use 0x8F on SAT (8341). */
static const u8 k_fire83_color[8] = {
    0x81, 0x83, 0x84, 0x86, 0x87, 0x89, 0x8A, 0x8D
};

static void award_subtype(u8 t)
{
    u8 idx = 0;

    if (t < (u8)sizeof(k_struct_award))
        idx = k_struct_award[t];
    player_add_score(idx);
}

/* 880d leftover -> type 80. dest keeps +0x18 so 8e14 849c scores the source. */
static void become_husk(Slot *e, u8 orig)
{
    e->kind = KIND_HUSK;
    e->variant = 80;
    e->hp = 0;
    e->timer = 0;
    e->script = 0;
    e->ground = 1;
    e->dest = orig;
    e->vx = 0;
    e->vy = 0;
    if (e->spr)
        SPR_setAnimAndFrame(e->spr, 0, FRAME_BOX);
}

/*
 * handler_type80 8e14:
 *   first frame (bit7 clear): bfb3, ev18, SET 7, +0x0c=0, JP 849c
 *     (score + anim +0x0d/0e/0f/10 then entity_update)
 *   later: 8f45 scroll-off (Y>=0xD0 -> bfab + clear); +0x0f ? 4898 : 48d0
 */
static void husk_step(Slot *e)
{
    if (!e->script)
    {
        entity_dec_encounter_a();
        sound_play_event(SND_EV_EXPLODE);
        award_subtype((u8)e->dest);
        e->timer = 16;
        e->ground = 1;
        e->vx = 0;
        e->vy = 0;
        if (e->spr)
            SPR_setAnimAndFrame(e->spr, 0, FRAME_CIRCLE);
        return;
    }
    if (e->timer)
        e->timer--;
    if (e->spr)
        SPR_setAnimAndFrame(e->spr, 0,
            (e->timer & 2) ? FRAME_CIRCLE : FRAME_BOX);
}

/* 8a16 yellow pats 1c/20/24/20; 8a1e black same + color 81. */
static const u8 k_orb_yel_frame[4] = { FRAME_CIRCLE, FRAME_CHIP, FRAME_BOX, FRAME_CHIP };
static const u8 k_orb_blk_frame[4] = { FRAME_CIRCLE, FRAME_SHOT, FRAME_COMET, FRAME_SHOT };

/*
 * handler_type72_base_core 0x8983:
 *   first: Yvel=0xFFF8, +0x0c=5, anim 8a16 (4 frames / reload 4),
 *          +0x1e=4, +0x1f=+0x18 (70/71)
 *   each: if +0x1e: DEC +0x1b; on 0, DEC +0x1e; on 0:
 *           +0x1f==0x46 (70) -> 48d0
 *           else anim 8a1e, Yvel lo=0xF0 (0xFFF0)
 *         4898, 44b0
 *   collect (bit7 cleared): player 0x81;
 *           +0x1e ? 8a26+ev19+48d0 : E722=+0x1c/1d, SET 5 E102, 48d0
 * Port: bind/timer = Yvel 8.8; clock=+0x1b; script=+0x1e; aux=anim tick.
 *       dest kept as warp ptr (+0x1c/1d). No every-N frame Y step.
 */
static void orb_step(Slot *e)
{
    u8 idx;
    s32 ypos;

    /* 89bb: if +0x1e: DEC +0x1b; on 0 DEC +0x1e; on 0 branch. */
    if (e->script)
    {
        e->clock--;
        if (!e->clock)
        {
            e->script--;
            if (!e->script)
            {
                if (e->variant == 70)
                {
                    /* type 70 yellow expires; never turns black. */
                    spr_kill(e);
                    return;
                }
                /* 89d3: anim 8a1e, Yvel lo=0xF0 -> 0xFFF0. */
                e->bind = 0xFFF0;
            }
        }
    }

    /* 4898 Y_motion (+0c bit0): 8.8 via bind/timer.
     * Yellow 0xFFF8 = -8/256 px/f; black 0xFFF0 = -16/256 px/f. */
    ypos = ((s32)e->y << 8) | (u8)e->timer;
    ypos += (s16)e->bind;
    e->timer = (u8)ypos;
    e->y = (s16)(ypos >> 8);
    e->vx = 0;
    e->vy = 0;

    /* 8a16/8a1e: 4 pats, reload 4 (approx via aux>>2). */
    e->aux++;
    idx = (u8)((e->aux >> 2) & 3);
    if (e->spr)
    {
        SPR_setAnimAndFrame(e->spr, 0,
            e->script ? k_orb_yel_frame[idx] : k_orb_blk_frame[idx]);
        SPR_setVisibility(e->spr, VISIBLE);
    }
}

/*
 * handler_type83 8e3a black_shadow:
 *   first: +0x0c=1, Yvel=0xFFE0, type=0xD3, +0x1d=8eaf[+0x1c]
 *   each: +0x1b++, SAT 0x24/0x81 every 4th else 0x04/+0x1d, 4898, 44b0
 *   collect: player 0x81, +0x1b=0, E148-=5 sat 0, SET 7 player+5,
 *            48d0, bfc8, fire_select(+0x1c)
 * Port: bind/timer = Yvel 8.8 0xFFE0; clock=+0x1b; aux=+0x1d color;
 *       sat_col 0x81 blank (CIRCLE/0x24) vs weapon tint (CHIP/0x04).
 */
static void fireup_step(Slot *e)
{
    u8 flash;
    s32 ypos;

    if (!e->script)
    {
        /* 8e40: +0c=1, Yvel=FFE0, type=D3, +1d=8eaf[+1c]. Falls into 8e5d. */
        e->script = 1;              /* init done (Xvel unused; dest=0) */
        e->ground = 0;
        e->vx = 0;
        e->vy = 0;
        e->dest = 0;                /* Xvel 8.8 */
        e->bind = 0xFFE0;           /* Yvel 8.8: -0.125 px/frame */
        e->timer = 0;               /* Y frac */
        e->clock = 0;               /* +0x1b flash phase */
        e->aux = k_fire83_color[e->variant & 7]; /* +0x1d weapon tint */
    }

    /* 8e5d: A=+0x1b; INC +0x1b; AND 3 -> 0: pat 0x24/col 0x81 else 0x04/+0x1d */
    flash = e->clock;
    e->clock = (u8)(flash + 1);
    if ((flash & 3) == 0)
    {
        spr_place(e, FRAME_CIRCLE); /* SAT 0x24 lg_circle */
        spr_set_sat_col(e, 0x81);   /* blank/black flash */
    }
    else
    {
        spr_place(e, FRAME_CHIP);   /* pat 1; k_frame_sat is 0x00 */
        e->sat = 0x04;              /* Original SAT name for hitbox */
        spr_set_sat_col(e, e->aux); /* weapon color from 8eaf */
    }

    /* entity_update 4898 Y_motion (+0c=1): 8.8 via bind/timer */
    ypos = ((s32)e->y << 8) | (u8)e->timer;
    ypos += (s16)e->bind;
    e->timer = (u8)ypos;
    e->y = (s16)(ypos >> 8);
    e->vx = 0;
    e->vy = 0;
}

static void spawn_wide_at(Slot *e, u8 type, s16 x, s16 y, u16 dest)
{
    u8 hp;

    /* 87c7: HP from type|0x80, not Y. <0xC8 -> 6 (70/71);
     * >=0xD7 -> 3 (87-89); else 4 (81/82/84-86). Type 82 stamps digit. */
    {
        u8 t80 = (u8)(type | 0x80);
        if (t80 < 0xC8)
            hp = 6;
        else if (t80 >= 0xD7)
            hp = 3;
        else
            hp = 4;
    }

    e->kind = (type == 82) ? KIND_FIREBOX : KIND_WIDE;
    e->variant = type;
    e->hp = hp;
    e->timer = 0;
    e->script = 0;
    e->ground = 1;
    e->dest = dest;
    e->x = x;
    e->y = y;
    e->vx = 0;
    e->vy = 0;
    e->alive = 1;
    /* 8EB7: +0x1c=3 / +0x1d=0x18 then JP 87c3. +0x1d is the 0x18 reload. */
    if (type >= 84 && type <= 86)
        e->timer = 3;
    /* Idol-class + type 82 firebox: stream stamps nametable art; MSX SAT name
     * 0x24 for hitbox size only, sat_color 0 (invisible). Type 82 also stamps
     * digit 0x30+(IX+0x1c) via 87e2/8948 (script=0 until stamped). Death:
     * 84-86 -> husk+88ab; 82/89 -> fire-up places spr like idol->orb. */
    e->sat = 0x24;  /* hitbox half 0,0 => 16x16 (k_col_size[0x12]) */
    if (type == 70 || type == 71 || type == 81 || type == 82
        || (type >= 84 && type <= 86)
        || type == 87 || type == 88 || type == 89)
    {
        e->spr = NULL;
        if (type == 82)
        {
            /* Defer if still above the playfield; stamp once Y is in range. */
            e->script = 0;
            if (y >= 0 && y < 184)
            {
                map_script_stamp_82_digit(x, y, (u8)dest);
                e->script = 1;
            }
        }
    }
    else
        spr_place(e, FRAME_CIRCLE);
}

static void spawn_proto_box(void)
{
    const ModeAssets *a = mode_assets();
    s16 x;
    s16 y = -8;
    u8 i;

    /* proto_box: random X in ~0x38.., then +0x20 per child, 3 boxes. */
    x = (s16)(24 + (rnd() % (a->playfield_w - 96)));
    for (i = 0; i < 3; i++)
    {
        Slot *e = free_enemy();
        u8 t;
        if (!e)
            return;
        t = k_box_types[s_box_seq];
        s_box_seq++;
        if (s_box_seq >= (u8)sizeof(k_box_types))
            s_box_seq = 0;
        spawn_box(e, t, x, y);
        x = (s16)(x + 32);
    }
}


/* gun pair table 0x8189: flags, color, period, child type */
static const u8 k_gun[5][4] = {
    { 0x00, 0x8F, 32, 38 },
    { 0x40, 0x8D,  0, 21 },
    { 0x20, 0x8A, 80, 38 },
    { 0x00, 0x89, 32, 21 },
    { 0x20, 0x87, 46, 21 }
};

/* base_segment_table 0x8df1: sat_name, HP, y_off, x_off, motion.
 * MSX writes sat_name to +0x03 for hitbox size but never sets +0x04;
 * sat_color stays 0 (invisible). Visual is nametable tiles only. */
static const u8 k_base[7][5] = {
    { 0x20, 0x28, 0x00, 0x00, 0x7F },
    { 0x20, 0x14, 0x00, 0x00, 0x08 },
    { 0x1C, 0x0A, 0xFC, 0xFC, 0x06 },
    { 0x20, 0x14, 0xFC, 0x00, 0x0A },
    { 0x1C, 0x14, 0x00, 0xFC, 0x0A },
    { 0x20, 0x28, 0x00, 0x00, 0x0A },
    { 0x24, 0x63, 0x04, 0x04, 0x10 }
};

static const u8 k_stealth_x[4] = { 32, 208, 80, 160 };
static const u8 k_stealth_dir[4] = { 0, 6, 4, 4 }; /* [0]=0 down (was 2); E=0x80 wraps to idx0 */
/* 0x8084: player Y < entity Y. 0x8087: player Y >= entity Y. 16-dir volley. */
static const u8 k_volley_hi[3] = { 0x0C, 0x0A, 0x0E };
static const u8 k_volley_lo[3] = { 0x04, 0x02, 0x06 };
/* 0x808A type 66 bit0: five (Y,X) offsets, last pair is the 00 00 tail. */
static const s8 k_volley_66[5][2] = {
    {  24,   0 },
    {   0, -24 },
    {   0,  24 },
    { -24,   0 },
    {   0,   0 }
};

static u8 s_base_left;
static u8 s_e150;           /* base_encounter_flags */
static u8 s_desc_cycle;
static u8 s_pat_rr;         /* E717 base_attack_cursor, 0-7 */

static void spawn_frag(s16 x, s16 y, u8 dir, u8 variant);

static void spawn_child_dir(s16 x, s16 y, u8 stype, u8 dir)
{
    if (stype == 21)
    {
        /* type 21 light_bar: shared spawn_frag (speed 4 + ev0x16). */
        spawn_frag(x, y, dir, 21);
        return;
    }
    if (stype == 38)
    {
        /* type 38 burst_fragment: 8507 +0x17=3, real variant (not dir). */
        spawn_frag(x, y, dir, 38);
        return;
    }
    spawn_ebullet_dir(x, y, dir);
}

static void box_step(Slot *e)
{
    /* entity_update 4898 Y_motion (+0c=1): 8.8 via bind/timer;
     * shared pass inert. Types 4/5/6 share handler_type4_box. */
    s32 ypos = ((s32)e->y << 8) | (u8)e->timer;

    ypos += (s16)e->bind;
    e->timer = (u8)ypos;
    e->y = (s16)(ypos >> 8);
    e->vx = 0;
    e->vy = 0;
}

static void spawn_gun(Slot *e, u8 type)
{
    /* handler_type46_ground_projectiles 0x8094.
     * 8.8 packing matches type20/26-29/30: dest=Xvel, bind=Yvel,
     * script=Xfrac, timer=Yfrac. aux=ang|side(0x10)|latch(0x40);
     * clock=+0x18 fire countdown. Period/stype/flags from k_gun via
     * variant. Do not touch type41/45 aux/clock beyond this kind. */
    u8 pair = (u8)(((type - 46) & 0xFE) >> 1);
    u8 flags;
    u8 period;
    u8 right = rnd() & 1;

    if (pair > 4)
        pair = 4;
    flags = k_gun[pair][0];
    period = k_gun[pair][2];

    e->kind = KIND_GUN;
    e->variant = type;
    e->hp = 1;
    e->ground = 0;
    e->x = right ? 0xC0 : 0x30;
    e->y = -12;
    e->vx = 0;
    e->vy = 0;
    e->dest = 0;            /* Xvel 8.8 (Y-only) */
    e->bind = 0x0150;       /* Yvel 8.8: vy=1 vy_frac=0x50 */
    e->script = 0;          /* X frac */
    e->timer = 0;           /* Y frac */
    e->alive = 1;
    e->clock = period ? period : 1;
    if (flags & 0x20)
        e->aux = (u8)(12 | (right ? 0x10 : 0));
    else
        e->aux = right ? 8 : 0;
    e->sat_col = k_gun[pair][1];    /* +04 from gun pair table */
    spr_place(e, FRAME_LOGA);       /* +03=0x48 pat 18 */
    marker_place(e, FRAME_LOGA_C);  /* spawn_col_marker; fire uses 0x4C */
}

static void gun_fire(Slot *e)
{
    u8 pair = (u8)(((e->variant - 46) & 0xFE) >> 1);
    u8 stype;
    u8 dir = e->aux & 15;

    if (pair > 4)
        pair = 4;
    stype = k_gun[pair][3];
    /* 816d: +03=0x4c loga_compl while firing (black flash; no body tint) */
    spr_place(e, FRAME_LOGA_C);
    spawn_child_dir((s16)(e->x + 4), (s16)(e->y + 8), stype, dir);
}

static void gun_step(Slot *e)
{
    u8 pair = (u8)(((e->variant - 46) & 0xFE) >> 1);
    u8 flags;
    s32 ypos;

    if (pair > 4)
        pair = 4;
    flags = k_gun[pair][0];

    if (flags & 0x40)
    {
        /* Y-track: fire once when player crosses above, clear latch below. */
        u8 above = (u8)(player_y() < e->y);

        if (e->aux & 0x40)
        {
            if (!above)
                e->aux = (u8)(e->aux & 0xBF);
        }
        else if (above)
        {
            gun_fire(e);
            e->aux = (u8)(e->aux | 0x40);
        }
    }
    else
    {
        if (e->clock)
            e->clock--;
        if (!e->clock)
        {
            u8 period = k_gun[pair][2];
            u8 ang = e->aux & 15;

            if (flags & 0x20)
            {
                s8 step = (e->aux & 0x10) ? -1 : 1;
                ang = (u8)((ang + step) & 15);
                e->aux = (u8)((e->aux & 0x70) | ang);
            }
            e->clock = period ? period : 32;
            gun_fire(e);
            if (flags & 0x20)
            {
                if (ang == 4)
                {
                    /* Sweep done: reset ang=12, resume Y motion.
                     * 8155: restore +03=0x48 loga_A. */
                    e->aux = (u8)((e->aux & 0x70) | 12);
                    e->bind = 0x0150;
                    e->clock = period ? period : 32;
                    spr_place(e, FRAME_LOGA);  /* restore +04 tint */
                }
                else
                {
                    /* Mid-sweep: rapid fire, pause fall (+0c=0). */
                    e->clock = 1;
                    e->bind = 0;
                }
            }
        }
    }

    /* entity_update 4898 Y_motion: 8.8 via bind/timer; shared pass inert. */
    ypos = ((s32)e->y << 8) | (u8)e->timer;
    ypos += (s16)e->bind;
    e->timer = (u8)ypos;
    e->y = (s16)(ypos >> 8);
    e->vx = 0;
    e->vy = 0;
}

/* LAB_ram_4c91 / dir_remap_table 0x4D45. 16-dir aim; E returned as dir. */
static u8 aim_4c91(s16 x, s16 y)
{
    static const u8 k_thr[3] = { 0x32, 0x6A, 0xAB };
    static const u8 k_remap[32] = {
        0x02, 0x03, 0x03, 0x04, 0x0E, 0x0D, 0x0D, 0x0C,
        0x06, 0x05, 0x05, 0x04, 0x0A, 0x0B, 0x0B, 0x0C,
        0x02, 0x01, 0x01, 0x00, 0x0E, 0x0F, 0x0F, 0x00,
        0x06, 0x07, 0x07, 0x08, 0x0A, 0x09, 0x09, 0x08
    };
    s16 dy = (s16)(player_y() - y);
    s16 dx = (s16)(player_x() - x);
    u16 ady;
    u16 adx;
    u16 lo;
    u16 hi;
    u8 flags = 0;
    u8 b;
    u8 i;
    u8 ratio;

    if (dy < 0)
    {
        dy = (s16)-dy;
        flags |= 0x04;
    }
    if (dy == 0)
        dy = 1;
    ady = (u16)dy;
    if (dx < 0)
    {
        dx = (s16)-dx;
        flags |= 0x08;
    }
    if (dx == 0)
        dx = 1;
    adx = (u16)dx;
    if (adx >= ady)
    {
        flags |= 0x10;
        lo = ady;
        hi = adx;
    }
    else
    {
        lo = adx;
        hi = ady;
    }
    /* Z80 div_hl_e of (lo<<8)/hi; L is the low byte (256 -> 0 at 45 deg). */
    ratio = (u8)(((u16)lo << 8) / hi);
    b = 3;
    for (i = 0; i < 3; i++)
    {
        if (ratio < k_thr[i])
            break;
        b--;
    }
    return k_remap[(b | flags) & 31];
}


/* handler_type20 0x8668 Xvel: one prng_next -> H/L; dest=Xvel 8.8, script=Xfrac.
 * Packs like apply_dir_88 (dest/bind/script/timer); +0c flags are step-side only.
 * Does not touch aux/clock (type41/45) or parent type65/umber fields. */
static void type20_init_vel(Slot *e)
{
    u16 r;
    s8 xhi;

    s_rng = (u16)(s_rng * 2053 + 13849);
    r = s_rng;
    xhi = (s8)(((r >> 8) & 3) - 2);
    e->dest = (u16)(((u16)(u8)xhi << 8) | (u8)r);
    e->script = 0;          /* X position frac (IX+07) */
    e->bind = 0;            /* Yvel 8.8 (IX+08/09), start 0 */
    e->timer = 0;           /* Y position frac (IX+06) */
    e->vx = 0;
    e->vy = 0;
}

/* handler_type20_lead_homing 0x8668 first frame:
 *   +0c=0x0B (Y_motion|X_motion|Y_homing), +13=0xFF tgt, +15=0x0C accel, +17=1,
 *   Xvel.hi=(R&3)-2, Xvel.lo=L (full 8.8). Ongoing: entity_update then 44a6. */
static void spawn_lead20(s16 x, s16 y)
{
    Slot *c = free_enemy();

    if (!c)
        return;
    c->kind = KIND_EBULLET;
    c->variant = 20;
    c->hp = 1;
    c->ground = 0;
    c->x = x;
    c->y = y;
    /* 8668: +0c=0x0B, +13=0xFF, +15=0x0C, +17=1; Xvel 8.8 from one R. */
    type20_init_vel(c);
    c->alive = 1;
    spr_place(c, FRAME_LEAD);
}

/* handler_type59 @ 0x8269: dir=+0x1a&0x0F; JP 81a8 (speed 5,
 * set_velocity_from_dir, +0c=3 X|Y). Shared SAT 0x70 with type56. */
static void init_type59(Slot *c, s16 x, s16 y, u8 dir)
{
    c->kind = KIND_SIG;
    c->variant = 59;
    c->hp = 1;
    c->ground = 0;
    c->x = x;
    c->y = y;
    apply_dir_88(c, (u8)(dir & 15), 5);
    c->alive = 1;
    c->sat_col = 0x8F;              /* shared 81c3 XOR 0x09 with type56 */
    spr_place(c, FRAME_SIG);
}

static void spawn_sideways59(s16 x, s16 y, u8 dir)
{
    Slot *c = free_enemy();

    if (!c)
        return;
    init_type59(c, x, y, dir);
}

static void spawn_stealth(Slot *e, u8 type)
{
    u8 si = (u8)((rnd() & 6) >> 1);

    e->kind = KIND_STEALTH;
    e->variant = type;
    /* +0x19 = 7; type 65 (0xC1) overrides to 4. Type 34 keeps 7. */
    e->hp = (type == 65) ? 4 : 7;
    e->ground = 0;
    e->x = k_stealth_x[si];
    e->y = -12;
    /* 7f99: +17=1 set_velocity_from_dir, +0c=3 X|Y 8.8.
     * script/timer = X/Y fracs; variant==66 stands in for +05 bit0. */
    apply_dir_88(e, k_stealth_dir[si], 1);
    e->alive = 1;
    /* +0x0D/+0x1D = 0x30; type 65 overrides to 0x20. Port: clock=+1d. */
    e->clock = (type == 65) ? 32 : 48;
    spr_place(e, FRAME_STEALTH);      /* sat 0xCC pat 51 */
    marker_place(e, FRAME_STEALTH_C); /* spawn_col_marker SAT 0xD0 */
}

static void stealth_step(Slot *e)
{
    /* Volley on +1d (clock); cruise 8.8 applied in entity_update. */
    if (e->clock)
        e->clock--;
    else
    {
        u8 period = (e->variant == 65) ? 32 : 48;
        u8 i;

        e->clock = period;
        if (e->variant == 66)
        {
            /* 0x8023: ev21, 4c91 aim, table 808a (Y,X) + type 59. */
            u8 dir = aim_4c91(e->x, e->y);

            sound_play_event(SND_EV_EHIT2);
            for (i = 0; i < 5; i++)
                spawn_sideways59((s16)(e->x + k_volley_66[i][1]),
                                 (s16)(e->y + k_volley_66[i][0]),
                                 dir);
        }
        else
        {
            /* 0x8031: 8087 if playerY >= entityY else 8084. */
            const u8 *tab = (player_y() >= e->y) ? k_volley_lo : k_volley_hi;
            u8 n = (e->variant == 65) ? 1 : 3;

            for (i = 0; i < n; i++)
            {
                if (e->variant == 65)
                    spawn_lead20(e->x, e->y);
                else
                    spawn_frag(e->x, e->y, tab[i], 38);
            }
        }
    }
    if (e->spr)
        SPR_setVisibility(e->spr, (e->clock & 1) ? VISIBLE : HIDDEN);
}

static void spawn_descender(Slot *e)
{
    /* handler_type61_large_descender 0x8302: +09=02, +0c=1 Y-only 8.8.
     * Pat 62 sart + compl 63 (SAT F8/FC). clock=+1e halt.
     * +04 from 8eaf[E149&7] via sat_col (0x81->0x8F). */
    e->kind = KIND_DESCEND;
    e->variant = 61;
    e->hp = 1;
    e->clock = 32;              /* +0x1e halt frames at Y=0x60 */
    e->ground = 0;
    e->dest = 0;                /* Xvel 8.8 (Y-only) */
    e->bind = 0x0200;           /* Yvel 8.8: +09=0x02 */
    e->script = 0;              /* X frac */
    e->timer = 0;               /* Y frac */
    e->x = (player_x() >= 0x78) ? 64 : 176;
    e->y = -16;
    e->vx = 0;
    e->vy = 0;
    e->alive = 1;
    /* 8327: A=(E149); INC E149; +1d=A&7; +04=8eaf[+1d], 0x81->0x8F. */
    {
        u8 idx = (u8)(s_desc_cycle & 7);
        u8 col;

        s_desc_cycle = (u8)((s_desc_cycle + 1) & 7);
        e->aux = idx;               /* +0x1d idx -> fire# on 8394 */
        col = k_fire83_color[idx];
        if (col == 0x81)
            col = 0x8F;
        e->sat_col = col;
    }
    spr_place(e, FRAME_SART);       /* +03=0xf8 pat 62 */
    marker_place(e, FRAME_SART_C);  /* spawn_col_marker SAT 0xFC */
}

static void descender_step(Slot *e)
{
    /* 834a: at Y==0x60 clear +0c, DEC +1e; expire -> +0c=1 +09=FC.
     * Then entity_update Y-only 8.8 (bind/timer). Rise same frame. */
    if (e->y == 0x60)
    {
        /* Original: +0c=0; DEC +1e; on Z set +0c=1 +09=FC (same frame). */
        e->bind = 0;
        e->y = 0x60;
        if (e->clock)
            e->clock--;
        if (!e->clock)
            e->bind = 0xFC00;   /* Yvel 8.8: +09=0xFC */
    }
    if (e->bind)
    {
        s32 ypos = ((s32)e->y << 8) | (u8)e->timer;

        ypos += (s16)e->bind;
        e->timer = (u8)ypos;
        e->y = (s16)(ypos >> 8);
    }
    e->vx = 0;
    e->vy = 0;
}

/* handler_type62_invisible_riser 0x8709:
 * Yvel 8.8 FF80, pat 0, +0c=1; every-16f VRAM poke; ship-touch ->
 * INC E10A + ev8 + status. Spawned from type61 death when
 * (E140&0x3F)==(E103&0x3F). */
static void become_riser(Slot *e)
{
    marker_kill(e);
    if (e->spr)
    {
        SPR_releaseSprite(e->spr);
        e->spr = NULL;
    }
    e->kind = KIND_RISER;
    e->variant = 62;
    e->hp = 1;
    e->ground = 0;
    e->dest = 0;                /* Xvel 8.8 */
    e->bind = 0xFF80;           /* Yvel 8.8: -0.5 px/frame */
    e->script = 0;              /* X frac */
    e->timer = 0;               /* Y frac */
    e->clock = 0;               /* +0x0d frame counter */
    e->vx = 0;
    e->vy = 0;
    e->alive = 1;
}

static void spawn_riser(Slot *e)
{
    const ModeAssets *a = mode_assets();

    e->x = (s16)(16 + (rnd() % (a->playfield_w - 32)));
    e->y = (s16)(a->playfield_h - 32);
    become_riser(e);
}

static void riser_step(Slot *e)
{
    u8 old = e->clock;
    s32 ypos;

    /* 8728: every 16f (old&0x0f)==0 -> LDIRVM row from 876b+(old&0x10?0x20:0). */
    e->clock = (u8)(old + 1);
    if ((old & 0x0F) == 0)
        map_script_type62_poke((u8)((old & 0x10) ? 1 : 0));

    ypos = ((s32)e->y << 8) | (u8)e->timer;
    ypos += (s16)e->bind;
    e->timer = (u8)ypos;
    e->y = (s16)(ypos >> 8);
    e->vx = 0;
    e->vy = 0;
}

/* type61 post-death 836b: if type==0x23, dec_encounter_a; gate to 62 or 83. */
static int descender_on_death(Slot *e)
{
    entity_dec_encounter_a();
    if ((s_alc_shots & 0x3F) == (player_score_lo() & 0x3F))
    {
        award_subtype(61);
        become_riser(e);  /* become_riser marker_kill */
        return 1;
    }
    if (player_e148() >= 5)
    {
        award_subtype(61);
        marker_kill(e);
        /* 8394: type 0x53; +0x1c := +0x1d (color cycle / fire#). */
        e->kind = KIND_FIREUP;
        e->variant = (u8)(e->aux & 7);
        e->hp = 1;
        e->timer = 0;
        e->script = 0;
        e->ground = 0;
        e->dest = 0;
        e->bind = 0;
        e->vx = 0;
        e->vy = 0;
        if (e->spr)
            SPR_setAnimAndFrame(e->spr, 0, FRAME_CIRCLE);
        else
            spr_place(e, FRAME_CIRCLE);
        return 1;
    }
    return 0;
}

static void spawn_med_circle(Slot *e)
{
    /* 0x839f init: X=0x40+(H&0x7f) Y=0x10+(L&0x7f); +0c=3 +17=3
     * HP=+19=5; +1b=0x78 +1c=0x1e. Motion after first reaim. */
    e->kind = KIND_CIRCLE;
    e->variant = 67;
    e->hp = 5;
    e->timer = 0;
    e->script = 0;
    e->ground = 0;
    e->dest = 0;
    e->bind = 0;
    e->clock = 0x78;
    e->aux = 0x1E;
    e->x = (s16)(64 + (rnd() & 0x7F));
    e->y = (s16)(16 + (rnd() & 0x7F));
    e->vx = 0;
    e->vy = 0;
    e->alive = 1;
    spr_place(e, FRAME_MED_CIRCLE);
}

static void circle_step(Slot *e)
{
    /* 0x83d8: SAT XOR flash; DEC +0x1b; on 0: SET +05.0, DEC +0x1c,
     * if +0x1c==0 SET +05.1; else +04=0x8d, +1b=0x32+(R&0x1e),
     * aim_4c91 + set_velocity_from_dir (+17=3). Bit0 gates entity_update. */
    if (e->spr)
        SPR_setVisibility(e->spr, (e->clock & 1) ? VISIBLE : HIDDEN);

    e->clock--;
    if (!e->clock)
    {
        u8 a = (u8)(e->aux | 0x40);
        u8 phase = (u8)(a & 0x1F);

        if (phase)
            phase--;
        a = (u8)((a & 0xE0) | phase);
        if (!phase)
            a |= 0x80;

        if (!(a & 0x80))
        {
            u8 r = rnd();
            e->clock = (u8)(0x32 + (r & 0x1E));
            apply_dir_88(e, aim_4c91(e->x, e->y), 3);
        }
        e->aux = a;
    }

    if (e->aux & 0x40)
    {
        s32 xpos = ((s32)e->x << 8) | (u8)e->script;
        s32 ypos = ((s32)e->y << 8) | (u8)e->timer;

        xpos += (s16)e->dest;
        ypos += (s16)e->bind;
        e->script = (u8)xpos;
        e->timer = (u8)ypos;
        e->x = (s16)(xpos >> 8);
        e->y = (s16)(ypos >> 8);
        e->vx = 0;
        e->vy = 0;
    }
}

/* umber_burst_param_table 0x79b7 */
static const u8 k_umber_burst[7] = { 0x04, 0x05, 0x02, 0x07, 0x03, 0x06, 0x01 };

/* base_spawner_spawn_table 0x7af7: (type, count) x8 */
static const u8 k_spawner[8][2] = {
    { 10, 30 }, { 16, 8 }, { 22, 10 }, { 23, 8 },
    { 48, 6 }, { 8, 8 }, { 65, 6 }, { 36, 30 }
};

/*
 * base_attack_patterns 0x93AB: 8 descriptors of 3-byte (r0,rM,r3) records,
 * 0x00-terminated. Offsets into k_pat_blob.
 */
static const u8 k_pat_blob[] = {
    0x04,0x30,0x02,0x00,
    0x04,0x20,0x03,0x02,0x20,0x02,0x00,
    0x04,0x1C,0x02,0x04,0x30,0x04,0x00,
    0x04,0x28,0x05,0x00,
    0x05,0x40,0x0E,0x00,
    0x04,0x10,0x0A,0x03,0x20,0x05,0x00,
    0x02,0x20,0x08,0x00,
    0x03,0x20,0x08,0x00
};
static const u8 k_pat_off[8] = { 0, 4, 11, 18, 22, 26, 33, 37 };

static int spawn_from_type(u8 t);
static void spawn_frag(s16 x, s16 y, u8 dir, u8 variant);
static void entity_inc_encounter_a(void);

/* set_velocity_from_dir (+0x17 = speed) into screen-space 8.8.
 * dest=Xvel, bind=Yvel, script=Xfrac, timer=Yfrac; vx/vy cleared so the
 * shared integer pass does not double-apply. */
static void apply_dir_88(Slot *e, u8 dir, u8 speed)
{
    s16 xvel = (s16)(k_unit_x[dir & 15] * (s16)speed);
    s16 yvel = (s16)(k_unit_y[dir & 15] * (s16)speed);

    e->dest = (u16)xvel;
    e->bind = (u16)yvel;
    e->script = 0;
    e->timer = 0;
    e->vx = 0;
    e->vy = 0;
}

/* type 42/43: speed 3 then 85dd XOR R into X/Y vel low bytes. */
static void apply_dir_88_xor(Slot *e, u8 dir)
{
    u8 rx;
    u8 ry;

    apply_dir_88(e, dir, 3);
    rx = rnd();
    ry = rnd();
    e->dest = (u16)((e->dest & 0xFF00) | ((u8)e->dest ^ rx));
    e->bind = (u16)((e->bind & 0xFF00) | ((u8)e->bind ^ ry));
}

static void spawn_frag(s16 x, s16 y, u8 dir, u8 variant)
{
    Slot *e = free_enemy();
    if (!e)
        return;
    e->kind = KIND_EBULLET;
    e->variant = variant;
    e->hp = 1;
    e->timer = 0;
    e->script = 0;
    e->ground = 0;
    e->dest = 0;
    e->x = x;
    e->y = y;
    apply_dir(e, dir);
    if (variant == 20)
    {
        /* Same first-frame fields as spawn_lead20 / 0x8668 (full X 8.8). */
        type20_init_vel(e);
    }
    else if (variant == 37)
    {
        /* handler_type37 84e3: +0x17=3; player_pos_snapshot 4c8b
         * (= aim_4c91 then set_velocity_from_dir). Clean speed-3 8.8; no XOR.
         * Type 42 CALL 84e3 then XOR - keep apply_dir_88_xor below. */
        apply_dir_88(e, aim_4c91(x, y), 3);
    }
    else if (variant == 42)
    {
        /* handler_type42_proto_bullet 0x85cc:
         * CALL 84e3 (type37 init body), LD (IX+0)=0xA5, XOR R into
         * IX+0x0a / IX+0x08 (X/Y vel low bytes), RET. Runs as type 37.
         * Port: keep variant 42; 8.8 step + vel-low XOR. */
        apply_dir_88_xor(e, aim_4c91(x, y));
    }
    else if (variant == 43)
    {
        /* handler_type43_proto_fragment 0x85d6 (falls into 0x85dd XOR):
         * CALL 8507 (type38 init), LD (IX+0)=0xA6, XOR R vel lows.
         * Dir from +0x1a (spawn arg); port keeps variant 43 + 8.8 step. */
        apply_dir_88_xor(e, dir);
    }
    else if (variant == 41)
    {
        /* handler_type41_pair_fragment 0x852f / 0x857f:
         * +0x1a param (low4 base, bit4 curve sense); +0x1b heading = base +/-4;
         * init speed 2 then 4; per-frame set_velocity_from_dir(heading) @ speed 4.
         * Port: aux packs count/sense/heading; apply_dir_88(..., 4) + 8.8 step. */
        u8 base = (u8)(dir & 15);
        u8 heading = (u8)((dir & 0x10)
            ? ((base + 0xFC) & 15)
            : ((base + 4) & 15));
        e->aux = (u8)((2 << 5) | (dir & 0x10) | heading);
        apply_dir_88(e, heading, 4);
    }
    else if (variant == 38)
    {
        /* handler_type38_burst_fragment 0x8507:
         * +0x17=3; dir=+0x1a&0x0F; set_velocity_from_dir (8.8). */
        apply_dir_88(e, dir, 3);
    }
    else if (variant == 21)
    {
        /* handler_type21_light_bar 0x8635/0x863b:
         * +0x17=4; dir=+0x1a&0x0F; set_velocity_from_dir (8.8); SFX #0x16. */
        apply_dir_88(e, dir, 4);
        sound_play_event(SND_EV_DEATH); /* ev 0x16 */
    }
    else if (variant == 45)
    {
        /* handler_type45_light_bar_var 0x85ee:
         * +0x17 = (R&1)+2 speed; CALL 850b (pat/dir); +0x19=3 HP; +0x1c=0x28.
         * Same apply_dir_88 8.8 path as 21/37/38/41/42/43. Meta off fracs:
         * aux=(speed<<4)|(dir&15), clock=+0x1c re-aim (type41 keeps aux for curve). */
        u8 speed = (u8)(2 + (rnd() & 1));
        e->hp = 3;
        e->aux = (u8)((speed << 4) | (dir & 15));
        e->clock = 0x28;
        apply_dir_88(e, (u8)(dir & 15), speed);
    }
    e->alive = 1;
    /* 21/45: SAT 0x18 pat 6 light_bar (not lead 0x1C). */
    spr_place(e, (variant == 21 || variant == 45) ? FRAME_LIGHT_BAR : FRAME_LEAD);
}

static void spawn_umber(Slot *e, u8 type)
{
    /* handler_type7_umber 0x791d (shared 7/8/9 via 0x7923).
     * 8.8 packing matches type20/duster: dest=Xvel, bind=Yvel,
     * script=Xfrac, timer=Yfrac. vx/vy 0 so shared pass inert.
     * +0c=0x09 Y|Y_homing; Yvel 0x0300; +15=0x10; +17=1; +13 tgt 0.
     * Type9: clock=+0x1d spawn timer 8. */
    const ModeAssets *a = mode_assets();

    e->kind = KIND_UMBER;
    e->variant = type;
    e->hp = 1;
    e->ground = 0;
    e->dest = 0;            /* Xvel 8.8 (Y-only) */
    e->bind = 0x0300;       /* Yvel 8.8: vy=3 vy_frac=0 */
    e->script = 0;          /* X frac */
    e->timer = 0;           /* Y frac */
    e->clock = (type == 9) ? 8 : 0;  /* +0x1d type9 only */
    e->aux = 0;
    e->x = 120;             /* +0x02 = 0x78 */
    e->y = (s16)(a->playfield_h - 28);
    e->vx = 0;
    e->vy = 0;
    e->alive = 1;
    if (type == 9)
    {
        e->sat_col = 0x83;                /* cyan */
        spr_place(e, FRAME_UMBER_B);      /* pat 56 SAT 0xE0 */
        marker_place(e, FRAME_UMBER_B_C); /* pat 58 SAT 0xE8 */
    }
    else
    {
        /* type7 white 0x8F; type8 patched 0x8B @ 79c7 */
        e->sat_col = (type == 8) ? 0x8B : 0x8F;
        spr_place(e, FRAME_UMBER);        /* pat 55 SAT 0xDC */
        marker_place(e, FRAME_UMBER_C);   /* pat 57 SAT 0xE4 */
    }
}

static void umber_burst(Slot *e)
{
    u8 i;
    if (e->variant == 7)
    {
        for (i = 0; i < 7; i++)
            spawn_frag((s16)(e->x + 4), (s16)(e->y + 4), k_umber_burst[i], 38);
    }
    else if (e->variant == 8)
    {
        /* 0x79cc: +0x1a = 0x05 and 0x13 (bit4 marks curve sense). */
        spawn_frag((s16)(e->x + 4), (s16)(e->y + 4), 5, 41);
        spawn_frag((s16)(e->x + 4), (s16)(e->y + 4), 0x13, 41);
    }
}

static void umber_step(Slot *e)
{
    /* Active 0x7954: burst when Yvel word == 0 (before entity_update);
     * type9 0x7a12: DEC +0x1d, reload 8, 8ddb type20.
     * entity_update +0c=0x09: Y_homing_sub (tgt0, accel 0x10, B=1) then Y 8.8. */
    u16 yvel;
    s32 ypos;

    if (e->bind == 0 && (e->variant == 7 || e->variant == 8))
        umber_burst(e);

    if (e->variant == 9)
    {
        if (e->clock)
            e->clock--;
        else
        {
            e->clock = 8;
            spawn_frag((s16)(e->x + 4), (s16)(e->y), 0, 20);
        }
    }

    yvel = e->bind;
    if ((u8)e->y != 0)
        yvel = (u16)(yvel - 0x0010);
    e->bind = yvel;

    ypos = ((s32)e->y << 8) | (u8)e->timer;
    ypos += (s16)yvel;
    e->timer = (u8)ypos;
    e->y = (s16)(ypos >> 8);
    e->vx = 0;
    e->vy = 0;
}

static void spawn_veybar(Slot *e, u8 type)
{
    /* handler_type22_veybar 0x7d0f / type24_fast 0x7db4 -> shared 0x7d2d.
     * 8.8 packing matches type20/duster: dest=Xvel, bind=Yvel,
     * script=Xfrac, timer=Yfrac. Yvel 0x0400; +15=0x14; +17=1; +13 tgt 0.
     * 22/23: +0c=0x09 (Xvel armed, X-motion off until morph fire @0x20).
     * 24/25: +0c=0x1b + X-home (+14 tgt, +16=0x10). clock=+0x1d. */
    u8 fast = (u8)(type >= 24);
    u8 right = rnd() & 1;

    e->kind = KIND_VEYBAR;
    e->variant = type;
    e->hp = 1;
    e->ground = 0;
    e->script = 0;          /* X frac */
    e->timer = 0;           /* Y frac */
    e->bind = 0x0400;       /* Yvel 8.8: vy=4 */
    e->y = 0;
    e->vx = 0;
    e->vy = 0;
    e->alive = 1;
    if (fast)
    {
        e->x = right ? 184 : 56;
        e->dest = right ? 0xFD00 : 0x0300;  /* Xvel -3 / +3 */
        e->aux = right ? 0xFF : 0x00;       /* +0x14 X-home tgt */
        e->clock = 0x58;                    /* +0x1d = 88 */
    }
    else
    {
        e->x = right ? 200 : 40;
        e->dest = right ? 0xFF00 : 0x0100;  /* Xvel -1 / +1 (motion off) */
        e->aux = 0;                         /* bit0 phase, bit1 x_on */
        e->clock = 0x50;                    /* +0x1d = 80 */
    }
    e->sat_col = fast ? 0x89 : 0x83;        /* 24/25 light-red; 22/23 cyan */
    spr_place(e, FRAME_VEYBAR_0);
    marker_place(e, FRAME_VEYBAR_C0);  /* spawn_col_marker SAT 0x98 */
}

static void veybar_step(Slot *e)
{
    /* Active 0x7d4c (shared 22-25): countdown +0x1d / phase +0x05.0;
     * Y_homing then Y/X 8.8. Morph 0x7d64: clock<0x40 and (RRCA x2) only
     * bits 2-3 set; 7d73 SAT (IX+03)=0x94-E, marker (IY+03)=SAT+0x14
     * then 71f6 dual-SAT sibling. Fire 0x7d8c when marker==0xa0
     * (E==0x08 => clock==0x20): spawn type37. 22/23 (type>>1==0x4b):
     * 7d95 +17=4 aim+set_vel, +17=1 +15=0x0c SET +0c.1; 24/25 skip
     * re-aim/arm (already +0c=0x1b). Telegraph clocks: 0x30/0x20/0x10/0x00
     * -> SAT 0x88/0x8c/0x90/0x94 (pats 34-37). */
    u16 yvel = e->bind;
    u16 xvel = e->dest;
    s32 xpos;
    s32 ypos;
    u8 fast = (u8)(e->variant >= 24);
    u8 y_accel = 0x14;
    u8 x_on = fast ? 1 : (u8)(e->aux & 2);

    if (fast)
    {
        /* Same DEC/morph window as 22/23; aux is X-home tgt so no phase bit.
         * clock hits each value once (stops at 0) so type37 fires once @0x20. */
        if (e->clock)
            e->clock--;
        if (e->clock < 0x40)
        {
            u8 rot = (u8)((e->clock >> 2) | (e->clock << 6)); /* RRCA RRCA */
            if ((u8)(rot & 0x0c) == rot)
            {
                u8 sat = (u8)(0x94 - rot);
                u16 fi = (u16)((sat - 0x84) >> 2);
                /* 7d73 parent + marker; 71f6 emits marker SAT sibling. */
                spr_place(e, (u16)(FRAME_VEYBAR_0 + fi));
                marker_place(e, (u16)(FRAME_VEYBAR_C0 + fi));
                if ((u8)(sat + 0x14) == 0xa0)
                {
                    spawn_frag((s16)(e->x + 4), (s16)(e->y + 8),
                               aim_4c91(e->x, e->y), 37);
                }
            }
        }
    }
    else if (!(e->aux & 1))
    {
        if (e->clock)
            e->clock--;
        if (!e->clock)
            e->aux = (u8)(e->aux | 1);
        /* Morph window runs even on the frame clock hits 0 (MSX fall-through). */
        if (e->clock < 0x40)
        {
            u8 rot = (u8)((e->clock >> 2) | (e->clock << 6)); /* RRCA RRCA */
            if ((u8)(rot & 0x0c) == rot)
            {
                u8 sat = (u8)(0x94 - rot);
                u16 fi = (u16)((sat - 0x84) >> 2);
                spr_place(e, (u16)(FRAME_VEYBAR_0 + fi));
                marker_place(e, (u16)(FRAME_VEYBAR_C0 + fi));
                if ((u8)(sat + 0x14) == 0xa0)
                {
                    /* 7d95: +17=4; 4c91; set_velocity_from_dir; then +17=1 /
                     * +15=0x0c; SET +0c.1. Preserve X/Y fracs (vel words only).
                     * Same-frame motion uses the re-aimed 8.8 (not spawn +/-1). */
                    u8 xf = e->script;
                    u8 yf = e->timer;
                    apply_dir_88(e, aim_4c91(e->x, e->y), 4);
                    e->script = xf;
                    e->timer = yf;
                    xvel = e->dest;
                    yvel = e->bind;
                    e->aux = (u8)(e->aux | 2);
                    x_on = 1;
                    spawn_frag((s16)(e->x + 4), (s16)(e->y + 8),
                               aim_4c91(e->x, e->y), 37);
                }
            }
        }
    }
    if (x_on && !fast)
        y_accel = 0x0c;

    /* Y_homing_sub: tgt +13=0, accel=+15, B=+17=1. */
    if ((u8)e->y != 0)
        yvel = (u16)(yvel - (u16)y_accel);
    e->bind = yvel;

    /* X_homing_sub (fast only): tgt=aux(+14), accel=+16=0x10, B=1. */
    if (fast && (u8)e->x != e->aux)
    {
        if ((u8)e->x < e->aux)
            xvel = (u16)(xvel + 0x0010);
        else
            xvel = (u16)(xvel - 0x0010);
    }
    e->dest = xvel;

    ypos = ((s32)e->y << 8) | (u8)e->timer;
    ypos += (s16)yvel;
    e->timer = (u8)ypos;
    e->y = (s16)(ypos >> 8);

    if (x_on)
    {
        xpos = ((s32)e->x << 8) | (u8)e->script;
        xpos += (s16)xvel;
        e->script = (u8)xpos;
        e->x = (s16)(xpos >> 8);
    }

    e->vx = 0;
    e->vy = 0;
}

/* anim_sub +0d timer / +0f frame for KIND_SWOOP (period +0e=4, count +10=4). */
static u8 s_swoop_atim[ENEMY_SLOTS];
static u8 s_swoop_afi[ENEMY_SLOTS];

static void spawn_swoop(Slot *e, u8 type)
{
    /* handler_type26/27 @ 7de2 / type28/29 @ 7e78.
     * 8.8 packing matches type20/apply_dir_88: dest=Xvel, bind=Yvel,
     * script=Xfrac, timer=Yfrac. aux=+0x1d child type; clock=+0x1e fire.
     * +0x13 Y-home tgt left 0 (entity_clear); do not touch type41/45 aux/clock
     * ownership beyond this kind. */
    e->kind = KIND_SWOOP;
    e->variant = type;
    e->hp = 1;
    e->ground = 0;
    e->y = 0;               /* spawn writes type only; Y starts cleared */
    e->vx = 0;
    e->vy = 0;
    e->script = 0;          /* X frac */
    e->timer = 0;           /* Y frac */
    e->bind = 0x0280;       /* Yvel 8.8 */
    e->alive = 1;
    if (type == 26)
    {
        e->x = 0xC8;            /* H from HL=0xC825 */
        e->dest = 0xFF40;       /* Xvel 8.8 */
        e->aux = 37;            /* L = child type */
        e->clock = 0x18;        /* +0x1e */
    }
    else if (type == 27)
    {
        e->x = 0x28;            /* HL=0x2814 */
        e->dest = 0x00C0;
        e->aux = 20;
        e->clock = 0x18;
    }
    else if (type == 28)
    {
        e->x = 0xC0;            /* HL=0xC03B */
        e->dest = 0xFE00;
        e->aux = 59;
        e->clock = 0x04;        /* type28/29 set +1e=4 before join */
    }
    else
    {
        e->x = 0x30;            /* HL=0x3029 */
        e->dest = 0x0200;
        e->aux = 41;
        e->clock = 0x04;
    }
    /* anim_sub: +0d/+0e=4, +0f=0, +10=4; table pats 43-46.
     * +04 from edge_swooper_a/b_anim: 26/27=0x8E, 28/29=0x87. */
    {
        u8 si = (u8)(e - s_en);
        s_swoop_atim[si] = 4;
        s_swoop_afi[si] = 0;
    }
    e->sat_col = (type <= 27) ? 0x8E : 0x87;
    spr_place(e, FRAME_SPINNER_0);
    marker_place(e, FRAME_SPINNER_C0);  /* 71da + 7e5f: SAT+0x10 */
}

static void swoop_step(Slot *e)
{
    /* entity_update 4898 with +0c=0x0F: Y_homing (bit3) then Y/X motion + anim.
     * Y_homing_sub: B=+17=1, accel=+15=0x07, tgt=+13=0.
     * anim_sub 4912: every 4f cycle pats 43-46; 71f6 marker = sat+0x10. */
    u16 yvel = e->bind;
    s32 xpos;
    s32 ypos;
    u8 si = (u8)(e - s_en);

    if ((u8)e->y != 0)
    {
        /* tgt 0 < Y -> SBC accel (never ADD with tgt 0). */
        yvel = (u16)(yvel - 0x0007);
    }
    e->bind = yvel;

    ypos = ((s32)e->y << 8) | (u8)e->timer;
    ypos += (s16)yvel;
    e->timer = (u8)ypos;
    e->y = (s16)(ypos >> 8);

    xpos = ((s32)e->x << 8) | (u8)e->script;
    xpos += (s16)e->dest;
    e->script = (u8)xpos;
    e->x = (s16)(xpos >> 8);
    e->vx = 0;
    e->vy = 0;

    /* anim_sub 4912 (+0c bit2): DEC +0d; reload +0e=4; apply table[afi]
     * then INC (wrap +10=4). Port keeps afi = displayed frame; advance first
     * then place so marker (sat+0x10) always matches primary. spr_sync later. */
    if (s_swoop_atim[si])
        s_swoop_atim[si]--;
    if (!s_swoop_atim[si])
    {
        u8 fi = s_swoop_afi[si];
        s_swoop_atim[si] = 4;
        /* Original: write table[afi] then INC. Re-apply current then advance. */
        spr_place(e, (u16)(FRAME_SPINNER_0 + fi));
        marker_place(e, (u16)(FRAME_SPINNER_C0 + fi));
        fi++;
        if (fi >= 4)
            fi = 0;
        s_swoop_afi[si] = fi;
    }

    /* 7e3f: DEC +0x1e; on 0 reload 0x20 and 8ddb(child, C=0x04). */
    if (e->clock)
        e->clock--;
    else
    {
        u8 ct = e->aux;
        e->clock = 0x20;
        if (ct == 37)
            spawn_frag((s16)(e->x + 4), (s16)(e->y + 8),
                       aim_4c91(e->x, e->y), 37);
        else if (ct == 20)
            spawn_frag((s16)(e->x + 4), (s16)(e->y + 8), 0, 20);
        else if (ct == 59)
        {
            Slot *c = free_enemy();
            if (c)
                /* 8ddb C=0x04 -> +0x1a; type59 8269 -> apply_dir_88 speed 5. */
                init_type59(c, e->x, e->y, 4);
        }
        else
            /* type 29: LAB_ram_8ddb with C=0x04 (not coarse aim_dir). */
            spawn_frag((s16)(e->x + 4), (s16)(e->y + 8), 0x04, 41);
    }
}

static void spawn_tracker(Slot *e, u8 type)
{
    /* handler_type31_stealth_tracker @ 7f84 (run) / shared init body 7fa0.
     * Stream spawn: 807c X+dir, speed 1, sat 0xCC pat51, color 0x88,
     * +0c=1 Y-then-X (not shooter +0c=3). vy=+2 (sprint 0026); Xvel from dir
     * for flank phase. No volley. Absent-as-child path uses spawn_gswoop. */
    u8 si = (u8)((rnd() & 6) >> 1);

    e->kind = KIND_TRACKER;
    e->variant = type;
    e->hp = 7;
    e->ground = 0;
    e->x = k_stealth_x[si];
    e->y = -12;
    e->vx = 0;
    e->vy = 0;
    apply_dir_88(e, k_stealth_dir[si], 1);
    /* Y-track uses fixed +2; keep dest (Xvel) from 807c dir for flank. */
    e->bind = 0x0200;
    e->timer = 0;
    e->clock = 0x01;            /* +0c = Y_motion */
    e->aux = 0xFF;              /* no gswoop parent */
    e->alive = 1;
    e->sat_col = 0x88;            /* +04; ^=0x06 @ 7f73 */
    spr_place(e, FRAME_STEALTH);      /* sat 0xCC pat 51 */
    marker_place(e, FRAME_STEALTH_C); /* spawn_col_marker SAT 0xD0 */
}

static void tracker_step(Slot *e)
{
    /* 7f84: playerY CP entityY; BIT6 +05 -> CCF; NC keep Y, CY -> +0c=2.
     * 7f73: +04 ^= 0x06; entity_update 4898. No merge (parent 7f20 only). */
    s16 py = player_y();
    u8 mode = (u8)(e->clock & 3);
    u8 past;

    if (!(e->clock & 0x80))
    {
        if (e->clock & 0x40)
            past = ((u8)e->y <= (u8)py);
        else
            past = ((u8)e->y > (u8)py);
        if (past)
        {
            mode = 2;
            e->clock = (u8)((e->clock & (u8)~3) | 2);
        }
    }
    else
        mode = (u8)(e->clock & 3);

    if (mode & 1)
    {
        s32 ypos = ((s32)e->y << 8) | (u8)e->timer;

        ypos += (s16)e->bind;
        e->timer = (u8)ypos;
        e->y = (s16)(ypos >> 8);
        if ((u8)e->y >= 0xD0)
        {
            spr_kill(e);
            return;
        }
    }
    if (mode & 2)
    {
        s32 xpos = ((s32)e->x << 8) | (u8)e->script;

        xpos += (s16)e->dest;
        e->script = (u8)xpos;
        e->x = (s16)(xpos >> 8);
    }
    e->vx = 0;
    e->vy = 0;

    /* 7f73: +04 ^= 0x06 then 4898 (0x88<->0x8E real tint). */
    spr_set_sat_col(e, (u8)(e->sat_col ^ 0x06));
    e->clock = (u8)((e->clock & (u8)~0x04) | ((e->sat_col & 0x06) ? 0x04 : 0));
}

static void spawn_gswoop(Slot *e, u8 type)
{
    /* handler_type30_ground_swooper @ 7e9c.
     * 8.8 packing matches type20/26-29: dest=Xvel, bind=Yvel,
     * script=Xfrac, timer=Yfrac. clock low=+0c (1=Y,2=X); bit2=xor
     * phase; bit6=type32 sense; bit7=lock. aux=paired sibling (0xFF).
     * +03 SAT name 0xec (child 0xf0); +04=0x8f. */
    Slot *c;
    u8 ei;

    e->kind = KIND_GSWOOP;
    e->variant = type;
    e->hp = 1;
    e->ground = 0;
    e->script = 0;          /* X frac */
    e->timer = 0;           /* Y frac */
    e->vx = 0;
    e->vy = 0;
    e->x = 0x30;
    e->aux = 0xFF;
    e->clock = 0x01;        /* +0c = Y_motion */
    e->alive = 1;
    ei = (u8)(e - s_en);
    e->sat_col = 0x8F;      /* +04; ^=0x06 @ 7f73 */
    if (type == 30)
    {
        e->y = 0;
        e->bind = 0x0180;   /* Yvel 8.8 */
        e->dest = 0x0180;   /* Xvel 8.8 */
    }
    else
    {
        /* type32: rise from Y=0xD0, sense bit6, Xvel flip at 7f11. */
        e->y = 0xD0;
        e->bind = 0xFF00;
        e->dest = 0x0100;
        e->clock = (u8)(e->clock | 0x40);
    }

    /* spawn_col_marker + LDIR pair: child type own+1 at X=0xC0.
     * Child is KIND_TRACKER (7f84), sat 0xf0 degid_right Ã¢â‚¬â€ not stream pat51. */
    c = free_enemy();
    if (c)
    {
        u8 ci = (u8)(c - s_en);

        c->kind = KIND_TRACKER;
        c->variant = (u8)(type + 1);
        c->hp = 1;
        c->ground = 0;
        c->script = 0;
        c->timer = 0;
        c->vx = 0;
        c->vy = 0;
        c->x = 0xC0;
        c->y = e->y;
        c->bind = e->bind;
        c->clock = e->clock;
        c->dest = (type == 30) ? 0xFE80 : 0xFF00;
        c->aux = ei;
        c->alive = 1;
        c->sat_col = 0x8F;      /* +04; +03=0xf0 on MSX */
        e->aux = ci;
        spr_place(c, FRAME_DEGID_R); /* +03=0xf0 degid_right */
    }
    spr_place(e, FRAME_DEGID_L); /* +03=0xec degid_left */
}

static void gswoop_step(Slot *e)
{
    /* Active 7f20 / child 7f84 / epilogue 7f73-7f78 + entity_update 4898.
     * 7f73: +04 ^= 0x06 every frame (sat_col 0x8F<->0x89).
     * Merge 7f5b: +03=0xf4, sib type:=0x28 (type40 clear), X+5, +0c=1. */
    s16 py = player_y();
    u8 mode = (u8)(e->clock & 3);
    u8 past;
    Slot *sib = NULL;

    if (e->aux < ENEMY_SLOTS)
    {
        sib = &s_en[e->aux];
        if (!sib->alive || (sib->kind != KIND_GSWOOP && sib->kind != KIND_TRACKER))
            sib = NULL;
    }

    if (!(e->clock & 0x80))
    {
        /* CP playerY,ownY; type32 BIT6 -> CCF; CY => +0c=2. */
        if (e->clock & 0x40)
            past = ((u8)e->y <= (u8)py);
        else
            past = ((u8)e->y > (u8)py);
        if (past)
        {
            mode = 2;
            e->clock = (u8)((e->clock & (u8)~3) | 2);
            if (sib && (e->variant == 30 || e->variant == 32))
                sib->clock = (u8)((sib->clock & (u8)~3) | 2);
        }

        /* Parent: |pair.X - own.X| < 0x0B -> 7f5b reveal/merge. */
        if (sib && (e->variant == 30 || e->variant == 32))
        {
            s16 dx = (s16)(sib->x - e->x);
            if (dx < 0)
                dx = (s16)(-dx);
            if (dx < 0x0B)
            {
                /* SET lock; +03=0xf4; sib->type40; X+5; +0c=1. */
                e->clock = (u8)((e->clock & (u8)~3) | 0x81);
                /* +03=0xf4 degid_complete */
                spr_place(e, FRAME_DEGID);
                sib->variant = 40; /* type 0x28; handler = entity_clear */
                spr_kill(sib);
                e->aux = 0xFF;
                e->x = (s16)(e->x + 5);
                mode = 1;
            }
        }
    }
    else
        mode = (u8)(e->clock & 3);

    if (mode & 1)
    {
        s32 ypos = ((s32)e->y << 8) | (u8)e->timer;

        ypos += (s16)e->bind;
        e->timer = (u8)ypos;
        e->y = (s16)(ypos >> 8);
        /* Y_motion_sub: unsigned Y >= 0xD0 -> entity_clear. */
        if ((u8)e->y >= 0xD0)
        {
            spr_kill(e);
            return;
        }
    }
    if (mode & 2)
    {
        s32 xpos = ((s32)e->x << 8) | (u8)e->script;

        xpos += (s16)e->dest;
        e->script = (u8)xpos;
        e->x = (s16)(xpos >> 8);
    }
    e->vx = 0;
    e->vy = 0;

    /* 7f73: LD A,(IX+0x04); XOR 0x06; LD (IX+0x04),A â€” then 4898. */
    spr_set_sat_col(e, (u8)(e->sat_col ^ 0x06));
    e->clock = (u8)((e->clock & (u8)~0x04) | ((e->sat_col & 0x06) ? 0x04 : 0));
}
static void spawn_flash(Slot *e)
{
    /* handler_type36_flashing 0x8296/0x82b3:
     * 71c5 random_x; +0c=1 Y-only; +08=0x80 Yvel.lo (+09=0) =>
     * Yvel 8.8 0x0080; +03=0x34 +04=0x8f; +19=0x10 HP.
     * Port: dest/bind/script/timer 8.8 (like type4/61). */
    u8 r1 = rnd();
    u8 r2 = rnd();

    e->kind = KIND_FLASH;
    e->variant = 36;
    e->hp = 16;                 /* +0x19 = 0x10 */
    e->ground = 0;
    /* random_x_pos 71c5: X=(H&0x7f)+(L&0x1f)+0x28, Y=0 */
    e->x = (s16)((u8)((r1 & 0x7f) + (r2 & 0x1f) + 0x28));
    e->y = 0;
    e->vx = 0;
    e->vy = 0;
    e->dest = 0;                /* Xvel 8.8 (Y-only) */
    e->bind = 0x0080;           /* Yvel 8.8: 0.5 px/frame */
    e->script = 0;              /* X frac */
    e->timer = 0;               /* Y frac */
    e->sat_col = 0x8F;          /* +04; XOR 0x0e each frame */
    e->aux = 0;
    e->clock = 0;
    e->alive = 1;
    spr_place(e, FRAME_BOLT);   /* +03=0x34 pat 13 super_hard_bolt */
}

static void flash_step(Slot *e)
{
    /* 0x829c: attr XOR 0x0e; entity_update Y_motion (+0c=1);
     * entity_post + 7904 (shared hit path already decs HP). */
    s32 ypos = ((s32)e->y << 8) | (u8)e->timer;

    spr_set_sat_col(e, (u8)(e->sat_col ^ 0x0e)); /* 0x8F<->0x81 */
    ypos += (s16)e->bind;
    e->timer = (u8)ypos;
    e->y = (s16)(ypos >> 8);
    e->vx = 0;
    e->vy = 0;
}

static void spawn_pairdesc(Slot *e, u8 type)
{
    /* 81d1/81ac: +1f=0x20 then entity_update; port keeps Y-only descend
     * at 2 px/frame as 8.8 (was integer vy=2) before type59 convert. */
    const ModeAssets *a = mode_assets();

    e->kind = KIND_PAIRDESC;
    e->variant = type;
    e->hp = 1;
    e->clock = 32;              /* +0x1f descend frames */
    e->ground = 0;
    e->dest = 0;                /* Xvel 8.8 (Y-only) */
    e->bind = 0x0200;           /* Yvel 8.8: vy=2 */
    e->script = 0;              /* X frac */
    e->timer = 0;               /* Y frac */
    e->x = (s16)(16 + (rnd() % (a->playfield_w - 48)));
    e->y = -12;
    e->vx = 0;
    e->vy = 0;
    e->alive = 1;
    e->sat_col = 0x8F;              /* 81c3 XOR shared with 56/59 */
    /* MSX: type57 SAT 0x6C pat27 sig_double; type58 SAT 0x68 pat26 sig_triple */
    spr_place(e, (type == 58) ? FRAME_SIG_TRIPLE : FRAME_SIG_DOUBLE);
}

static void pairdesc_step(Slot *e)
{
    /* Y-only 8.8 descend (bind=0x0200); on +1f expire -> type59 @ 8269. */
    if (e->clock)
    {
        s32 ypos = ((s32)e->y << 8) | (u8)e->timer;

        e->clock--;
        ypos += (s16)e->bind;
        e->timer = (u8)ypos;
        e->y = (s16)(ypos >> 8);
        e->vx = 0;
        e->vy = 0;
        spr_set_sat_col(e, (u8)(e->sat_col ^ 0x09));
        return;
    }
    {
        /* 0x820c: LAB_ram_4c91 (not coarse aim_dir). */
        u8 dir = aim_4c91(e->x, e->y);
        u8 n = (e->variant == 58) ? 2 : 1;
        u8 k;
        /* Convert self + children to type 59; dirs stay (aim / +4 / +12).
         * Motion: 8269 set_velocity_from_dir 8.8 speed 5. */
        init_type59(e, e->x, e->y, dir);
        for (k = 0; k < n; k++)
        {
            Slot *c = free_enemy();
            if (!c)
                break;
            init_type59(c, e->x, e->y, (u8)((dir + (k ? 4 : 12)) & 15));
        }
    }
}

/* 8ddb from base_spawner_active 7ab0/7ab6: A=type, C=+0x1a (3 or 5). Parent
 * Y/X would be copied; table-wave first-frames re-roll X via 71c5 and ignore
 * +0x1a. Caller passes spawner aux (C) for side fidelity. */
static int spawn_8ddb_spawner(Slot *parent, u8 type, u8 c)
{
    (void)parent;
    (void)c;
    return spawn_from_type(type);
}
static void spawn_spawner(Slot *e)
{
    /* handler_type11 7ad4 -> base_spawner_active 7a67 first frame.
     * Table index: (E130>>3)&0x0E as byte offset -> pair (E130>>4)&7.
     * +0x03/+0x1b/+0x1c = 0x28; random_x 71c5; left X<0x78 -> drift+2 C=3
     * else drift-2 C=5. */
    u8 pair = (u8)((s_e130 >> 4) & 7);
    u8 et = k_spawner[pair][0];
    u8 cnt = k_spawner[pair][1];
    u8 r1 = rnd();
    u8 r2 = rnd();
    u8 x = (u8)((r1 & 0x7f) + (r2 & 0x1f) + 0x28);

    e->kind = KIND_SPAWNER;
    e->variant = 69;
    e->hp = 3;
    e->ground = 0;
    e->script = et;             /* +0x18 emit type */
    e->dest = cnt;              /* +0x19 remaining count */
    e->timer = 0x28;            /* +0x1b fire countdown */
    e->clock = 0x28;            /* +0x1c reload */
    e->x = (s16)x;
    e->y = 0;                   /* 71c5 Y=0 */
    e->vy = 0;
    if (x < 0x78)
    {
        e->vx = 2;              /* +0x0a drift; NOT applied every frame */
        e->aux = 3;             /* +0x1a 8ddb C */
    }
    else
    {
        e->vx = (s8)0xFE;       /* -2 */
        e->aux = 5;
    }
    e->alive = 1;
    spr_place(e, FRAME_FIRE);   /* SAT 0x1E initially transparent-ish */
}

static void spawner_step(Slot *e)
{
    /* base_spawner_active 7a9c: E12D.bit3 gate; interval; 8ddb; walk on fire;
     * bounce when u8 X >= 0xC0 (unsigned wrap supplies left edge). */
    u8 x;

    if (s_spawn_ctrl & 0x08)
        return;
    if (e->timer)
    {
        e->timer--;
        return;
    }
    e->timer = e->clock ? e->clock : 0x28;
    if (!spawn_8ddb_spawner(e, (u8)e->script, e->aux))
        return;                 /* pool full: keep count, no walk */
    if (e->dest)
        e->dest--;
    if (!e->dest)
    {
        spr_kill(e);
        return;
    }
    x = (u8)((u8)e->x + (s8)e->vx);
    e->x = (s16)x;
    if (x >= 0xC0)
        e->vx = (s8)(-(s8)e->vx);
}

static void base_fire(Slot *e)
{
    /* 0x8d14: A=type-0xC9 -> dispatch_inline_table. ROM words:
     * 73->8d2a, 74->8d51, 75->8d6c, 76->8d73, 77->8d93, 78->8d98, 79->8db8.
     * Aim (4c91) only for 8d98 (type 78). 73/74/76/77/79 share +0x13 cursor (vx). */
    u8 dir = aim_4c91(e->x, e->y);
    s16 x = (s16)(e->x + 4);
    s16 y = (s16)(e->y + 8);

    if (e->variant == 73)
    {
        /* 8d2a: ADD +0x13,3; while (a=&0x0f) in 9..13 keep adding.
         * a<9 -> type 21 dir=a; a==14 -> type 42 (C stale: port dir 0);
         * a==15 -> type 42 dir 4. Cursor stored in unused base vx. */
        u8 cur = (u8)e->vx;
        u8 a;
        for (;;)
        {
            cur = (u8)(cur + 3);
            a = (u8)(cur & 0x0F);
            if (a < 9 || a >= 14)
                break;
        }
        e->vx = (s8)cur;
        if (a >= 15)
            spawn_frag(x, y, 4, 42);
        else if (a >= 14)
            spawn_frag(x, y, 0, 42);
        else
            spawn_frag(x, y, a, 21);
        return;
    }
    if (e->variant == 74 || e->variant == 77)
    {
        /* 8d51 (74 B=4) / 8d93 (77 B=2): type 43 via 8dd9.
         * C from +0x13 (vx); if >=9 then C=0; INC C -> +0x13 each shot. */
        u8 n = (u8)((e->variant == 74) ? 4 : 2);
        u8 k;
        u8 c = (u8)e->vx;
        for (k = 0; k < n; k++)
        {
            if (c >= 9)
                c = 0;
            spawn_frag(x, y, c, 43);
            c = (u8)(c + 1);
            e->vx = (s8)c;
        }
        return;
    }
    if (e->variant == 75)
    {
        /* 8d6c: single type 42 (8dd5). */
        spawn_frag(x, y, 0, 42);
        return;
    }
    if (e->variant == 76)
    {
        /* 8d73: DEC +0x13; C=(+0x13)&7; type43 @C;
         * if C!=4 also type43 @(8-C). Cursor stays post-DEC (not &7). */
        u8 c;
        e->vx = (s8)((u8)e->vx - 1);
        c = (u8)((u8)e->vx & 7);
        spawn_frag(x, y, c, 43);
        if (c != 4)
            spawn_frag(x, y, (u8)(8 - c), 43);
        return;
    }
    if (e->variant == 78)
    {
        /* 8d98: CALL 4c91; 5-spread table 0, -1, +1, -2, +2 via type 43. */
        static const s8 sprd[5] = { 0, -1, 1, -2, 2 };
        u8 k;
        for (k = 0; k < 5; k++)
            spawn_frag(x, y, (u8)((dir + sprd[k]) & 15), 43);
        return;
    }
    if (e->variant == 79)
    {
        /* 8db8: INC +0x13; (&3)==0 -> type 42 (8d6c); else type 45 dir=R&0x0C.
         * Cursor in unused base vx (shared with 73/74/76/77). */
        u8 cur = (u8)((u8)e->vx + 1);
        e->vx = (s8)cur;
        if ((cur & 3) == 0)
            spawn_frag(x, y, 0, 42);
        else
            spawn_frag(x, y, (u8)(rnd() & 0x0C), 45);
        return;
    }
    spawn_frag(x, y, dir, 38);
}

static void base_step(Slot *e)
{
    u8 idx = (u8)(e->variant - 73);
    u8 p5;
    u8 pat;
    u8 rec;
    u8 phase;
    u8 rate;
    u8 fire_acc;
    const u8 *p;
    u16 sum;

    /* Approach (E150 bit0 only): nametable-locked, no pattern/fire.
     * SET 7 (E150 bit1): +0x10 Y + VRAM bind once (sat_col=0, no overlay), then fire. */
    if (!(s_e150 & 2))
        return;
    if (!(e->script & 0x80))
    {
        s16 y0 = e->y;
        u16 yaln = (u16)y0 & 0xF8;
        u8 col = (u8)((u8)((u8)e->x - 0x20) >> 3);

        e->y = (s16)(y0 + 0x10);
        /* SUB_ram_8948: L=Y_pre, H=X-0x20 -> 0x3800+(Y&F8)*4+col */
        e->bind = (u16)(0x3800 + (yaln << 2) + col);
        if (e->spr)
            spr_sync(e);
        e->script = (u8)(e->script | 0x80);
    }

    if (idx > 6)
        idx = 0;
    p5 = k_base[idx][4];
    if (s_e150 & 8)
        p5 <<= 1;           /* E150 bit3: SLA IX+15 */
    pat = (u8)(e->dest & 7);
    rec = (u8)((e->dest >> 3) & 0x1F);
    phase = e->script & 3;
    p = k_pat_blob + k_pat_off[pat] + rec;
    if (p[0] == 0)
    {
        rec = 0;
        p = k_pat_blob + k_pat_off[pat];
        e->dest = (u16)((e->dest & (u16)~0x00F8) | ((u16)rec << 3));
    }
    if (phase == 0)
        rate = p[0];
    else if (phase == 3)
        rate = p[2];
    else
        rate = p[1];

    sum = (u16)e->timer + rate;
    if (sum > 255)
    {
        s8 step = (e->script & 0x10) ? -1 : 1;
        s8 np = (s8)(phase + step);
        e->timer = 0;
        if (np <= 0)
        {
            rec = (u8)(rec + 3);
            e->dest = (u16)((e->dest & (u16)~0x00F8) | ((u16)(rec & 0x1F) << 3));
            e->script = (u8)((e->script & 0xF0) | 0);
            e->script = (u8)(e->script & (u8)~0x10);
        }
        else if (np >= 3)
        {
            e->script = (u8)((e->script & 0xF0) | 3 | 0x10);
        }
        else
            e->script = (u8)((e->script & 0xF0) | (u8)np | (e->script & 0x10));
    }
    else
        e->timer = (u8)sum;

    phase = e->script & 3;
    if ((phase == 3 || e->variant == 79) && e->y >= 0 && e->y < 184)
    {
        fire_acc = (u8)(e->dest >> 8);
        sum = (u16)fire_acc + p5;
        if (sum > 255)
        {
            e->dest = (u16)(e->dest & 0x00FF);
            base_fire(e);
        }
        else
            e->dest = (u16)((e->dest & 0x00FF) | (sum << 8));
    }
}

static void award_for(u8 kind)
{
    u8 idx = 3;
    if (kind == KIND_EBULLET) idx = 1;
    else if (kind == KIND_BOX) idx = 7;
    else if (kind == KIND_GUN) idx = 4;
    else if (kind == KIND_FLASH) idx = 9;
    else if (kind == KIND_BASE) idx = 9;
    else if (kind == KIND_WIDE) idx = 9;
    else if (kind == KIND_FIREBOX) idx = 6;
    else if (kind == KIND_GROUND) idx = 2;
    else if (kind == KIND_STEALTH || kind == KIND_TRACKER) idx = 6;
    else if (kind == KIND_CIRCLE) idx = 7;
    else if (kind == KIND_SPAWNER) idx = 8;
    player_add_score(idx);
}


static void spawn_base_seg(Slot *e, u8 type, s16 x, s16 y)
{
    u8 idx = (u8)(type - 73);
    s8 yo;
    s8 xo;

    if (idx > 6)
        idx = 0;
    yo = (s8)k_base[idx][2];
    xo = (s8)k_base[idx][3];
    /* k_base[][0] sat_name is MSX hitbox size only; sat_col=0 (no SAT).
     * Destroy/hit FX via scatter_expl (places type-35 sprites then). */

    e->kind = KIND_BASE;
    e->variant = type;
    e->hp = k_base[idx][1];
    e->sat = k_base[idx][0];
    e->timer = 0;
    e->script = 0;
    e->ground = 1;
    e->dest = s_pat_rr;     /* pattern index 0-7; record=0; fire_acc=0 */
    s_pat_rr++;
    if (s_pat_rr >= 8)
        s_pat_rr = 0;
    e->x = (s16)(x + xo);
    e->y = (s16)(y + yo);
    e->vx = 0;
    e->vy = 0;
    e->bind = 0;
    e->alive = 1;
    e->spr = NULL;
    e->marker = 0;
}

static int is_port_type(u8 t)
{
    if (t >= 4 && t <= 18) return 1;
    if (t == 20) return 1;          /* lead_homing 0x14 */
    if (t >= 22 && t <= 30) return 1;
    if (t == 31 || t == 32 || t == 33 || t == 34 || t == 36) return 1;
    if (t == 44) return 1;
    if (t >= 46 && t <= 55) return 1;
    if (t >= 56 && t <= 59) return 1;
    if (t == 61 || t == 62) return 1;
    if (t == 63 || t == 64) return 1;
    if (t >= 65 && t <= 69) return 1;
    if (t == 70 || t == 71) return 1;
    if (t >= 73 && t <= 79) return 1;
    if (t == 82) return 1;
    if (t == 83) return 1;
    return 0;
}

static int spawn_from_type(u8 t)
{
    Slot *e;

    if (t == 68)
    {
        spawn_proto_box();
        return 1;
    }
    if (t == 63)
    {
        const ModeAssets *a = mode_assets();
        spawn_chip_at((s16)(16 + (rnd() % (a->playfield_w - 32))), -8);
        return 1;
    }
    if (t == 64)
    {
        /* 8279: index spawn_type_list by E130/2 + R&3, clamp 0x5F. */
        u8 idx = (u8)((s_e130 >> 1) + (rnd() & 3));
        u8 nt;
        if (idx > 0x5F)
            idx = 0x5F;
        nt = spawn_type_list[idx];
        if (nt == 64 || !is_port_type(nt))
            nt = 44;
        return spawn_from_type(nt);
    }

    e = free_enemy();
    if (!e)
        return 0;
    if (t >= 4 && t <= 6)
        spawn_box(e, t, (s16)(16 + (rnd() % 180)), -8);
    else if (t == 10)
        spawn_duster(e);
    else if (t >= 12 && t <= 15)
        spawn_teruzo(e, t);
    else if (t >= 16 && t <= 18)
        spawn_luster(e, t);
    else if (t == 20)
    {
        /* handler_type20 8668 stream: random_x_pos 71c5, Y=0; first-frame
         * Xvel 8.8 via type20_init_vel. Y-home tgt/accel baked in update. */
        u8 r1 = rnd();
        u8 r2 = rnd();
        u8 x = (u8)((r1 & 0x7f) + (r2 & 0x1f) + 0x28);

        e->kind = KIND_EBULLET;
        e->variant = 20;
        e->hp = 1;
        e->ground = 0;
        e->x = (s16)x;
        e->y = 0;
        type20_init_vel(e);
        e->alive = 1;
        spr_place(e, FRAME_LEAD);
    }
    else if (t == 56)
        spawn_sig(e);
    else if (t == 83)
        spawn_fireup(e);
    else if (t == 44)
        spawn_ground_fall(e, t, (s16)(16 + (rnd() % 180)), -12, 0);
    else if (t == 70 || t == 71)
        spawn_wide_at(e, t, (s16)(16 + (rnd() % 180)), -16, 0);
    else if (t == 82)
        spawn_wide_at(e, t, (s16)(16 + (rnd() % 180)), -16, 0);
    else if (t >= 46 && t <= 55)
        spawn_gun(e, t);
    else if (t == 61)
        spawn_descender(e);
    else if (t == 62)
        spawn_riser(e);
    else if (t == 34 || t == 65 || t == 66)
        spawn_stealth(e, t);
    else if (t == 67)
        spawn_med_circle(e);
    else if (t >= 73 && t <= 79)
        spawn_base_seg(e, t, (s16)(16 + (rnd() % 180)), -16);
    else if (t >= 7 && t <= 9)
        spawn_umber(e, t);
    else if (t == 11 || t == 69)
        spawn_spawner(e);
    else if (t >= 22 && t <= 25)
        spawn_veybar(e, t);
    else if (t >= 26 && t <= 29)
        spawn_swoop(e, t);
    else if (t == 30 || t == 32)
        spawn_gswoop(e, t);
    else if (t == 31 || t == 33)
        spawn_tracker(e, t);
    else if (t == 36)
        spawn_flash(e);
    else if (t == 57 || t == 58)
        spawn_pairdesc(e, t);
    else if (t == 59)
    {
        /* Bare table spawn: +0x1a unset -> dir 4 like type56 E=4 sibling. */
        const ModeAssets *a = mode_assets();
        init_type59(e, 8, (s16)(16 + (rnd() % (a->playfield_h / 2))), 4);
    }
    else
        return 0;
    return 1;
}

static void spawn_tick(void)
{
    u8 slot;
    u8 ctr;
    u8 t;
    u16 idx;

    /* ground_struct_spawn_ctrl 0xBF2C.
     * Bit1 = stream active (E12D). Round 1 never sends cmd 0, so we
     * start with bit1 set at init - matching MSX gameplay start.
     * Bit0 = sticky update_spawn_table_ptr request (BE27 RES0).
     * E125 bit0 = BFA0 immediate type 44 (checked before bit3 block).
     * Bit3 = stream-block (SET at 8fd4, RES at 90c5 / 906f / 9325). */
    if (s_spawn_ctrl & 0x01)
    {
        s_spawn_ctrl = (u8)(s_spawn_ctrl & (u8)~0x01);
        alc_recompute();
    }
    if (s_e125 & 0x01)
    {
        /* sub_bfa0: alloc type 44, RES 0,(E125), RET. */
        s_e125 = (u8)(s_e125 & (u8)~0x01);
        spawn_from_type(44);
        return;
    }
    if (s_spawn_ctrl & 0x08)
        return;
    if (!(s_spawn_ctrl & 0x02))
        return;
    if (s_spawn_timer)
    {
        s_spawn_timer--;
        return;
    }
    s_spawn_timer = s_spawn_reload ? s_spawn_reload : 255;

    /* BF55: every-16th stream slot -> type 0x3D (61) descender.
     * Does not advance E135 / spawn_pos (BF94). */
    slot = s_stream_slot;
    s_stream_slot++;
    if ((slot & 0x0F) == 0)
    {
        spawn_from_type(61);
        return;
    }

    /* BF60-BF70: index E133 slice by E135, wrap on count (E136). */
    if (!s_e136)
        return;
    ctr = s_e135;
    s_e135++;
    if ((u8)(s_e136 - 1) == ctr)
        s_e135 = 0;
    idx = (u16)s_spawn_base + (u16)ctr;
    if (idx >= SPAWN_TYPE_LEN)
        return;
    t = spawn_type_list[idx];
    if (!t)
        return;
    if (!is_port_type(t))
        return;
    /* BF79 write type + BF7A E12F+=8 + BF8C INC E142 sat - only if slot ok. */
    if (!spawn_from_type(t))
        return;
    spawn_pos_add(8);
    s_e142++;
    if (!s_e142)
        s_e142--;
}

static void update_shots(void)
{
    u8 i;
    for (i = 0; i < SHOT_SLOTS; i++)
    {
        Slot *s = &s_shot[i];
        if (!s->alive)
            continue;
        s->y += s->vy;
        if (s->y < -16)
        {
            spr_kill(s);
            continue;
        }
        if (s->spr)
            spr_sync(s);
    }
}

static void fire_offscreen_reset(u8 fn)
{
    /* 0x749c: off-screen + E14D==0 -> fire_reset. Fire 1/4/5. */
    if ((fn == 1 || fn == 4 || fn == 5) && player_fire_ammo() == 0)
        player_fire_select(0);
}

static void update_fire(void)
{
    const ModeAssets *a = mode_assets();
    Slot *f = &s_fire;
    u8 fn;
    u8 cycle;

    if (s_f6cd)
        s_f6cd--;

    if (!f->alive)
        return;

    fn = player_fire_num();
    if (fn == 2)
    {
        /* Field Shutter 0x72F5: Y=player_Y-8, X=player_X every frame. */
        f->x = player_x();
        f->y = (s16)(player_y() - 8);
    }
    else if (fn == 3)
    {
        /* Circular 0x735D: dir++ each frame, offset += vel (speed 0xC3 = *12). */
        s16 cy;
        s16 cx;
        s16 max_x;

        s_fdir = (u8)((s_fdir + 1) & 0x0F);
        s_fvy = (s16)(k_unit_x[s_fdir] * 12);
        s_fvx = (s16)(k_unit_y[s_fdir] * 12);
        s_fyoff = (s16)(s_fyoff + s_fvy);
        s_fxoff = (s16)(s_fxoff + s_fvx);
        cy = clamp16(player_y(), 0x38, 0xA7);
        max_x = (s16)(a->playfield_w - (256 - 0xA7));
        if (max_x < 0xA7)
            max_x = 0xA7;
        cx = clamp16(player_x(), 0x48, max_x);
        f->y = (s16)(cy + (s_fyoff >> 8));
        f->x = (s16)(cx + (s_fxoff >> 8));
    }
    else if (fn == 4)
    {
        /* Vibrator 0x7439: vx += accel; if X>=anchor reverse; Y until +0x1C=0. */
        s_fvx = (s16)(s_fvx + s_faccel);
        if (f->x >= s_fanchor)
            s_fvx = (s16)(s_fvx - (s16)(s_faccel * 2));
        f->x = (s16)(f->x + (s_fvx >> 8));
        if (f->timer)
        {
            f->timer--;
            f->y = (s16)(f->y + f->vy);
        }
        if (s_fexpire)
        {
            s_fexpire--;
            if (s_fexpire == 0x1E && f->spr)
                SPR_setAnimAndFrame(f->spr, 0, FRAME_LEAD);
            if (s_fexpire == 0x0F && f->spr)
                SPR_setVisibility(f->spr, HIDDEN);
            if (!s_fexpire)
            {
                spr_kill(f);
                fire_offscreen_reset(4);
                return;
            }
        }
    }
    else if (fn == 5)
    {
        /* Rewinder 0x7464: clamp Y>=16, X=player_X, vy += 4 (8.8), die behind ship. */
        if (f->y < 0x10)
            f->y = 0x10;
        f->x = player_x();
        if ((s16)(player_y() + 0x10) < f->y)
        {
            spr_kill(f);
            fire_offscreen_reset(5);
            return;
        }
        s_fvy = (s16)(s_fvy + 4);
        f->y = (s16)(f->y + (s_fvy >> 8));
    }
    else
    {
        f->x += f->vx;
        f->y += f->vy;
    }

    f->script++;
    /* fire 0/1/2/7 run: INC sat_color AND 0x8F. 3/4/5 stay solid. */
    cycle = (u8)(fn == 0 || fn == 1 || fn == 2 || fn == 7);
    if (f->spr)
    {
        spr_sync(f);
        if (fn == 4 && s_fexpire && s_fexpire <= 0x0F)
            SPR_setVisibility(f->spr, HIDDEN);
        else if (cycle)
            SPR_setVisibility(f->spr, (f->script & 1) ? VISIBLE : HIDDEN);
        else
            SPR_setVisibility(f->spr, VISIBLE);
    }

    if (fn != 2 && fn != 3)
    {
        if (f->x < -16 || f->x > (s16)(a->playfield_w + 8)
            || f->y < -24 || f->y > (s16)(a->playfield_h + 8))
        {
            spr_kill(f);
            fire_offscreen_reset(fn);
        }
    }
}

static void luster_step(Slot *e)
{
    /* Active 7c43 (16/17) / 7cd8 (18) then entity_update via 79ae.
     * 16: +0c=1 Y 8.8 only. 17/18: +0c=0x13 X_homing then Y|X 8.8.
     * X_homing_sub: tgt=aux(+14), accel=+16, B=+17 (4 / 2). */
    u16 xvel = e->dest;
    u16 yvel = e->bind;
    s32 xpos;
    s32 ypos;
    u8 y;

    if (e->variant == 18)
    {
        /* 7ce1: DEC +0x1d; on 0 reload 0x30 and 8ddb type37. */
        e->clock--;
        if (!e->clock)
        {
            e->clock = 0x30;
            spawn_frag((s16)(e->x + 4), (s16)(e->y + 12), 0, 37);
        }
    }
    else
    {
        /* 7c43 band: ((Y+0x10)&+1e)-0x10 == Y -> type38; +1e=C0/E0. */
        u8 mask = (e->variant == 16) ? 0xC0 : 0xE0;
        y = (u8)e->y;
        if ((u8)(((u8)(y + 0x10) & mask) - 0x10) == y)
            spawn_frag((s16)(e->x + 4), (s16)(e->y + 14), e->clock, 38);
    }

    if (e->variant == 17 || e->variant == 18)
    {
        u8 accel = (e->variant == 17) ? 0x40 : 0x0e;
        u8 iters = (e->variant == 17) ? 4 : 2;
        u8 i;
        for (i = 0; i < iters; i++)
        {
            if ((u8)e->x != e->aux)
            {
                if ((u8)e->x < e->aux)
                    xvel = (u16)(xvel + accel);
                else
                    xvel = (u16)(xvel - accel);
            }
        }
        e->dest = xvel;
    }

    ypos = ((s32)e->y << 8) | (u8)e->timer;
    ypos += (s16)yvel;
    e->timer = (u8)ypos;
    e->y = (s16)(ypos >> 8);

    if (e->variant == 17 || e->variant == 18)
    {
        xpos = ((s32)e->x << 8) | (u8)e->script;
        xpos += (s16)xvel;
        e->script = (u8)xpos;
        e->x = (s16)(xpos >> 8);
    }

    e->vx = 0;
    e->vy = 0;
}

/* handler_type84_wide_variant 0x8EC7: DEC +0x1c; on 0 reload +0x1d=0x18,
 * alloc, then type 84/85/86 emit type 38 / aimed type 21 / rotating type 21. */
static void wide_variant_step(Slot *e)
{
    u8 t = e->variant;
    u8 dir;
    u8 stype;

    if (t < 84 || t > 86)
        return;
    if (e->timer)
        e->timer--;
    if (e->timer)
        return;

    /* reload +0x1c from +0x1d. Type overwrite only if a child slot exists. */
    e->timer = 0x18;
    if (!free_enemy())
        return;

    if (t == 84)
    {
        /* 8f13: +0x1c=0x0A; INC +0x1e; C=(+0x1e*2)&0x0F; A=0x26 type 38. */
        e->timer = 0x0A;
        e->script++;
        dir = (u8)((e->script << 1) & 0x0F);
        stype = 38;
    }
    else if (t == 85)
    {
        /* 8efc: player X (E302) vs own X. E710 NZ -> C, Z -> B. */
        if ((u8)player_x() >= (u8)e->x)
            dir = map_script_scroll_speed() ? 1 : 0;
        else
            dir = map_script_scroll_speed() ? 7 : 8;
        stype = 21;
    }
    else
    {
        /* 8ee3: +0x1c=8; INC +0x1e; C=((+0x1e)&3)*4+2; A=0x15 type 21. */
        e->timer = 8;
        e->script++;
        dir = (u8)(((e->script & 3) << 2) + 2);
        stype = 21;
    }
    spawn_child_dir(e->x, e->y, stype, dir);
}

static void update_enemies(void)
{
    const ModeAssets *a = mode_assets();
    u8 i;
    s16 max_x = (s16)(a->playfield_w - 16);
    s16 max_y = (s16)(a->playfield_h + 8);

    for (i = 0; i < ENEMY_SLOTS; i++)
    {
        Slot *e = &s_en[i];
        if (!e->alive)
            continue;

        if (e->kind == KIND_PDEAD)
        {
            /* handler_type60 0x869E / anim 0x86F3 tick=4, 11 frames.
             * +0F starts at 1 (empty frame 0 skipped); wrap +0F=0 -> E102.0. */
            if (!e->script)
            {
                sound_play_event(SND_EV_DEATH);
                /* 86c3-86dc: +0F=1,+10=0x0B,+0D=4,+0E=4,+0C=4. */
                e->clock = 4;
                e->aux = 1;
                e->script = 1;
                spr_place(e, k_t60_frame[1]);
                spr_set_sat_col(e, k_t60_col[1]);
            }
            if (!e->aux)
            {
                /* 86eb: SET 0,(E102); clear slot. */
                player_e102_set(0x01);
                spr_kill(e);
                continue;
            }
            if (e->clock)
                e->clock--;
            if (!e->clock)
            {
                e->clock = 4;
                e->aux++;
                if (e->aux >= 11)
                    e->aux = 0;
            }
            if (!e->aux)
            {
                player_e102_set(0x01);
                spr_kill(e);
                continue;
            }
            spr_place(e, k_t60_frame[e->aux]);
            spr_set_sat_col(e, k_t60_col[e->aux]);
            if (e->spr)
                spr_sync(e);
            continue;               /* bit2-only; no shared motion/cull */
        }
        else if (e->kind == KIND_EXPL)
        {
            /* handler_type35 0x8446: bit7 clear = first frame ALC dump +
             * ev17 + 4a6a score + 84d1 arm (+0E=4,+0F=1,+10=6). */
            if (!e->script)
            {
                u16 lo = (u16)s_spawn_pos_lo + 0x10;
                u8 a;
                u16 w;

                s_spawn_pos_lo = (u8)lo;
                if (lo > 0xFF)
                    entity_inc_encounter_a();

                /* 8457: E142 < 0x11 -> shot_rate_table[E142+1] into E131. */
                if (s_e142 < 0x11)
                {
                    a = k_shot_rate[s_e142 + 1];
                    w = (u16)s_e131 + a;
                    s_e131 = (u8)w;
                    if (w > 255)
                        entity_inc_encounter_b();
                }
                /* 8473: E141 < 8 -> 0x24-(E141*4); else 1. Into E131. */
                if (s_e141 < 8)
                    a = (u8)(0x24 - (s_e141 << 2));
                else
                    a = 1;
                w = (u16)s_e131 + a;
                s_e131 = (u8)w;
                if (w > 255)
                    entity_inc_encounter_b();
                s_e142 = 0;
                s_e141 = 0;

                /* 8495 ev17 + 849c add_score_for_subtype(+0x18). */
                sound_play_event(SND_EV_EHIT);
                award_subtype(e->variant);

                if (s_e124)
                    s_e124--;
                if (!s_e124)
                {
                    s_e124 = 0x10;
                    s_e125 = 1;
                }
                /* 84a3-84b9: +0D=1,+0E=4,+0F=1,+10=6, table 84d1. */
                e->clock = 1;
                e->aux = 1;
                e->script = 1;
                spr_place(e, k_t35_frame[1]);
                spr_set_sat_col(e, k_t35_col[1]);
            }
            /* 84c9: +0F==0 -> clear; else entity_update bit2 anim. */
            if (!e->aux)
            {
                spr_kill(e);
                continue;
            }
            if (e->clock)
                e->clock--;
            if (!e->clock)
            {
                e->clock = 4;
                e->aux++;
                if (e->aux >= 6)
                    e->aux = 0;
            }
            if (!e->aux)
            {
                spr_kill(e);
                continue;
            }
            spr_place(e, k_t35_frame[e->aux]);
            spr_set_sat_col(e, k_t35_col[e->aux]);
        }
        else if (e->kind == KIND_DUSTER)
            duster_step(e);
        else if (e->kind == KIND_TERUZO)
        {
            /* 7b07: +0c=3 X|Y 8.8; dir reload every 8f via set_vel speed 4. */
            if (e->clock)
                e->clock--;
            if (!e->clock)
            {
                e->clock = 8;
                teruzo_step(e);
            }
            {
                s32 xpos = ((s32)e->x << 8) | (u8)e->script;
                s32 ypos = ((s32)e->y << 8) | (u8)e->timer;

                xpos += (s16)e->dest;
                ypos += (s16)e->bind;
                e->script = (u8)xpos;
                e->timer = (u8)ypos;
                e->x = (s16)(xpos >> 8);
                e->y = (s16)(ypos >> 8);
                e->vx = 0;
                e->vy = 0;
            }
        }
        else if (e->kind == KIND_LUSTER)
            luster_step(e);
        else if (e->kind == KIND_SIG)
        {
            /* type56 @ 819d and type59 @ 8269 both join 81a8: +0c=3
             * X|Y 8.8 via dest/bind + script/timer (set_velocity_from_dir speed 5). */
            {
                s32 xpos = ((s32)e->x << 8) | (u8)e->script;
                s32 ypos = ((s32)e->y << 8) | (u8)e->timer;

                xpos += (s16)e->dest;
                ypos += (s16)e->bind;
                e->script = (u8)xpos;
                e->timer = (u8)ypos;
                e->x = (s16)(xpos >> 8);
                e->y = (s16)(ypos >> 8);
                e->vx = 0;
                e->vy = 0;
            }
            /* 81c3: +04 ^= 0x09 (0x8F<->0x86) */
            spr_set_sat_col(e, (u8)(e->sat_col ^ 0x09));
        }
        else if (e->kind == KIND_BOX)
            box_step(e);
        else if (e->kind == KIND_CHIP)
            box_step(e);        /* type63: inherit Y 8.8 (+0c=1) */
        else if (e->kind == KIND_GROUND)
        {
            /* type44 +0c=3: X|Y 8.8 via dest/bind + script/timer fracs. */
            s32 xpos = ((s32)e->x << 8) | (u8)e->script;
            s32 ypos = ((s32)e->y << 8) | (u8)e->timer;

            xpos += (s16)e->dest;
            ypos += (s16)e->bind;
            e->script = (u8)xpos;
            e->timer = (u8)ypos;
            e->x = (s16)(xpos >> 8);
            e->y = (s16)(ypos >> 8);
            e->vx = 0;
            e->vy = 0;
        }
        else if (e->kind == KIND_FIREUP)
            fireup_step(e);
        else if (e->kind == KIND_HUSK)
            husk_step(e);
        else if (e->kind == KIND_ORB)
        {
            orb_step(e);
            if (!e->alive)
                continue;
        }
        else if (e->kind == KIND_GUN)
            gun_step(e);
        else if (e->kind == KIND_STEALTH)
        {
            /* 7f99/8012: volley then entity_update +0c=3 X|Y 8.8
             * (set_velocity_from_dir speed 1 at spawn). */
            stealth_step(e);
            {
                s32 xpos = ((s32)e->x << 8) | (u8)e->script;
                s32 ypos = ((s32)e->y << 8) | (u8)e->timer;

                xpos += (s16)e->dest;
                ypos += (s16)e->bind;
                e->script = (u8)xpos;
                e->timer = (u8)ypos;
                e->x = (s16)(xpos >> 8);
                e->y = (s16)(ypos >> 8);
                e->vx = 0;
                e->vy = 0;
            }
        }
        else if (e->kind == KIND_DESCEND)
            descender_step(e);
        else if (e->kind == KIND_RISER)
            riser_step(e);
        else if (e->kind == KIND_CIRCLE)
            circle_step(e);
        else if (e->kind == KIND_UMBER)
            umber_step(e);
        else if (e->kind == KIND_VEYBAR)
            veybar_step(e);
        else if (e->kind == KIND_SWOOP)
            swoop_step(e);
        else if (e->kind == KIND_TRACKER)
        {
            tracker_step(e);
            if (!e->alive)
                continue;
        }
        else if (e->kind == KIND_GSWOOP)
        {
            gswoop_step(e);
            if (!e->alive)
                continue;
        }
        else if (e->kind == KIND_FLASH)
            flash_step(e);
        else if (e->kind == KIND_PAIRDESC)
            pairdesc_step(e);
        else if (e->kind == KIND_SPAWNER)
        {
            spawner_step(e);
            if (!e->alive)
                continue;
        }
        else if (e->kind == KIND_BASE)
            base_step(e);
        else if (e->kind == KIND_WIDE)
            wide_variant_step(e);
        else if (e->kind == KIND_FIREBOX)
        {
            /* 87e2 runs once on activate; port stamps when Y enters playfield. */
            if (!e->script && e->y >= 0 && e->y < 184)
            {
                map_script_stamp_82_digit(e->x, e->y, (u8)e->dest);
                e->script = 1;
            }
        }
        else if (e->kind == KIND_EBULLET && e->variant == 20)
        {
            /* +0c=0x0B: Y_homing + Y_motion + X_motion (no X_homing bit4).
             * Y_homing_sub 0x4942: tgt +13=0xFF, accel +15=0x0C, B=+17=1.
             * Y 8.8: frac=timer, vel=bind. X 8.8: frac=script, vel=dest
             * (parity with apply_dir_88 leads). vx/vy 0 -> shared pass inert. */
            u16 yvel = e->bind;
            u16 ypos;
            s32 xpos;

            if ((u8)e->y != 0xFF)
                yvel = (u16)(yvel + 0x000C);
            e->bind = yvel;
            ypos = (u16)(((u16)((u8)e->y) << 8) | (u16)e->timer);
            ypos = (u16)(ypos + yvel);
            e->timer = (u8)ypos;
            e->y = (s16)(u8)(ypos >> 8);

            xpos = ((s32)e->x << 8) | (u8)e->script;
            xpos += (s16)e->dest;
            e->script = (u8)xpos;
            e->x = (s16)(xpos >> 8);
            e->vx = 0;
            e->vy = 0;
        }
        else if (e->kind == KIND_EBULLET
            && (e->variant == 21 || e->variant == 37 || e->variant == 38
                || e->variant == 42 || e->variant == 43 || e->variant == 45))
        {
            /* 8.8 vels (37/38/21/45 clean; 42/43 XOR'd at spawn): dest=Xvel,
             * bind=Yvel, script/timer fracs. vx/vy 0; shared pass inert.
             * Type 45 (0x8608): DEC clock/+0x1c; on 0: R bit0 ?
             * dir += (R&8)-4 + apply_dir_88(speed) : reload 0x28. */
            if (e->variant == 45)
            {
                if (e->clock)
                    e->clock--;
                if (!e->clock)
                {
                    u8 r = rnd();
                    if (r & 1)
                    {
                        u8 speed = (u8)(e->aux >> 4);
                        u8 d = (u8)((e->aux & 15) + (r & 8) - 4);
                        e->aux = (u8)((speed << 4) | (d & 15));
                        apply_dir_88(e, (u8)(d & 15), speed);
                    }
                    e->clock = 0x28;
                }
            }
            {
                s32 xpos = ((s32)e->x << 8) | (u8)e->script;
                s32 ypos = ((s32)e->y << 8) | (u8)e->timer;

                xpos += (s16)e->dest;
                ypos += (s16)e->bind;
                e->script = (u8)xpos;
                e->timer = (u8)ypos;
                e->x = (s16)(xpos >> 8);
                e->y = (s16)(ypos >> 8);
                e->vx = 0;
                e->vy = 0;
            }
        }
        else if (e->kind == KIND_EBULLET && e->variant == 41)
        {
            /* 0x857f: DEC +0x15; on 0 reload 2 and INC/DEC +0x1b by bit4 of +0x1a;
             * set_velocity_from_dir(+0x1b) every frame at speed 4 (8.8). */
            u8 meta = e->aux;
            u8 heading = (u8)(meta & 15);
            u8 count = (u8)(meta >> 5);

            if (count)
                count--;
            if (!count)
            {
                count = 2;
                if (meta & 0x10)
                    heading = (u8)((heading - 1) & 15);
                else
                    heading = (u8)((heading + 1) & 15);
            }
            e->aux = (u8)((count << 5) | (meta & 0x10) | heading);
            apply_dir_88(e, heading, 4);
            {
                s32 xpos = ((s32)e->x << 8) | (u8)e->script;
                s32 ypos = ((s32)e->y << 8) | (u8)e->timer;

                xpos += (s16)e->dest;
                ypos += (s16)e->bind;
                e->script = (u8)xpos;
                e->timer = (u8)ypos;
                e->x = (s16)(xpos >> 8);
                e->y = (s16)(ypos >> 8);
                e->vx = 0;
                e->vy = 0;
            }
        }
        /* Type 69: X drifts only on successful fire (spawner_step); vx holds
         * drift delta and must not feed the shared integer pass. */
        if (e->kind != KIND_SPAWNER)
        {
            if (e->ground)
                e->y += (s16)map_script_scroll_delta();
            else
            {
                e->x += e->vx;
                e->y += e->vy;
            }
        }
        if (e->kind == KIND_HUSK)
        {
            /* 8f45 after first frame: Y>=0xD0 -> bfab + clear; +0x0f==0 -> 48d0 */
            if (e->script)
            {
                if (e->y >= 0xD0)
                {
                    entity_inc_encounter_a();
                    spr_kill(e);
                    continue;
                }
                if (!e->timer)
                {
                    spr_kill(e);
                    continue;
                }
            }
            e->script = 1;
        }
        else if (e->kind == KIND_FIREUP && e->y < 0)
        {
            /* 4898 Y_motion: unsigned Y>=0xD0 clears; rise underflow dies. */
            spr_kill(e);
            continue;
        }
        else if (e->kind == KIND_RISER && e->y < -16)
        {
            /* 874d: entity_update cleared bit7 -> RET, no life. */
            spr_kill(e);
            continue;
        }
        /* Type 69 retires on count==0 only (7abc entity_clear); u8 X wrap
         * at bounce must not trip playfield cull. */
        if (e->kind != KIND_SPAWNER
            && e->kind != KIND_HUSK
            && (e->x < -16 || e->x > max_x + 16
                || (e->kind != KIND_GSWOOP && e->y > max_y)
                || e->y < -24))
        {
            spr_kill(e);
            continue;
        }
        if (e->spr)
            spr_sync(e);
    }
}

static void box_death_drop(u8 variant, s16 sx, s16 sy)
{
    /* handler_type4_box 0x7878: +0x18 5=RET, 4=3x type 38, else type 63. */
    if (variant == 5)
        return;
    if (variant == 4)
    {
        spawn_frag(sx, sy, 3, 38);
        spawn_frag(sx, sy, 5, 38);
        spawn_frag(sx, sy, 4, 38);
        return;
    }
    if (variant == 6)
        spawn_chip_at(sx, sy);
}

static void collide_bolt_enemies(Slot *bolt, u8 persist)
{
    u8 j;
    for (j = 0; j < ENEMY_SLOTS; j++)
    {
        Slot *e = &s_en[j];
        s16 sx, sy;
        u8 drop;
        u8 kind;
        if (!e->alive)
            continue;
        /* 0x716B/entity_post: shots leg (44BA/44CA); 44A6 bullets excluded. */
        if (!enemy_takes_shots(e))
            continue;
        if (!hit_overlap(bolt->x, bolt->y, bolt->sat, e->x, e->y, e->sat))
            continue;

        if (!persist)
            spr_kill(bolt);
        else if (persist == 2)
        {
            /* fire 4 expire 0x74E2: ev24, 60-frame shrink, then clear. */
            if (!s_fexpire)
            {
                s_fexpire = 0x3C;
                sound_play_event(SND_EV_FIRE_EXPIRE);
            }
        }
        else
        {
            /* fire 2 expire 0x74C1: ev24, DEC E14D, FF -> fire_reset. */
            player_fire_dec_ammo();
            if (player_fire_ammo() == 0xFF)
            {
                spr_kill(bolt);
                player_fire_select(0);
            }
            else
                sound_play_event(SND_EV_FIRE_EXPIRE);
        }
        if (e->hp)
            e->hp--;
        if (e->hp)
        {
            /* ev17 @0x8495 / ev20 @0x8438: hit that does not kill. */
            if (e->kind == KIND_BASE)
            {
                sound_play_event(SND_EV_BASEHIT);
                scatter_expl(e->x, e->y);
            }
            else
                sound_play_event(SND_EV_EHIT);
            return;
        }
        sx = e->x;
        sy = e->y;
        drop = e->variant;
        kind = e->kind;
        {
            u16 dest = e->dest;
            u16 bind = e->bind;
            if (kind == KIND_WIDE || kind == KIND_FIREBOX)
            {
                /* 880d: A=+0x18 type. Default (IX+0)=0x48, then dispatch.
                 * 81/84-88 become type 80; 8e14 does bfb3+ev18+849c next tick.
                 * 82/89 8874 score+ev18 and become type 83 (8e3a). */
                if (drop == 82)
                {
                    /* 8874: score+ev18, 88d8, type 83 in-place. */
                    award_for(kind);
                    sound_play_explode();
                    map_script_punch_88d8(sx, sy);
                    e->kind = KIND_FIREUP;
                    e->variant = (u8)(dest & 7);
                    e->hp = 1;
                    e->timer = 0;
                    e->script = 0;
                    e->ground = 0;
                    e->dest = 0;
                    e->vx = 0;
                    e->vy = 0;
                    /* Firebox was nametable-only; fire-up needs visible pat 9. */
                    if (e->spr)
                        SPR_setAnimAndFrame(e->spr, 0, FRAME_CIRCLE);
                    else
                        spr_place(e, FRAME_CIRCLE);
                    return;
                }
                if (drop >= 87)
                {
                    /* 8892: husk; 87->88b1, 88->88cb, else R&7 then 8874. */
                    if (drop == 87)
                    {
                        become_husk(e, drop);
                        map_script_punch_88b1(sx, sy);
                        return;
                    }
                    if (drop == 88)
                    {
                        become_husk(e, drop);
                        map_script_punch_88cb(sx, sy);
                        return;
                    }
                    award_for(kind);
                    sound_play_explode();
                    map_script_punch_88d8(sx, sy);
                    e->kind = KIND_FIREUP;
                    e->variant = (u8)(rnd() & 7);
                    e->hp = 1;
                    e->timer = 0;
                    e->script = 0;
                    e->ground = 0;
                    e->dest = 0;
                    e->vx = 0;
                    e->vy = 0;
                    /* Was nametable-only; fire-up needs visible pat 9. */
                    if (e->spr)
                        SPR_setAnimAndFrame(e->spr, 0, FRAME_CIRCLE);
                    else
                        spr_place(e, FRAME_CIRCLE);
                    return;
                }
                if (drop >= 84 && drop <= 86)
                {
                    /* 8854: type 80 husk + 88ab tiles. */
                    become_husk(e, drop);
                    map_script_punch_88ab(sx, sy, drop);
                    return;
                }
                if (drop == 81)
                {
                    /* 8824: type 80 husk + 88c2, X-0x24 Y-0x10. */
                    become_husk(e, drop);
                    map_script_punch_88c2(sx, sy);
                    return;
                }
                /* 8833: 70/71. 8810 this slot := type 72; child 0xD1 HP0 -> 8824. */
                award_for(kind);
                sound_play_explode();
                e->kind = KIND_ORB;
                e->variant = drop;  /* +0x1f = +0x18 (70/71) */
                e->hp = 1;
                e->timer = 0;       /* Y frac (8.8) */
                e->clock = 0;       /* +0x1b phase byte */
                e->script = 4;      /* +0x1e yellow life */
                e->aux = 0;         /* anim tick */
                e->bind = 0xFFF8;   /* Yvel 8.8; 71 later -> 0xFFF0 */
                e->ground = 0;
                e->vx = 0;
                e->vy = 0;
                /* dest kept: +0x1c/1d warp ptr from idol table.
                 * Idol had no sprite (nametable); orb needs pat 9 lg_circle. */
                if (e->spr)
                    SPR_setAnimAndFrame(e->spr, 0, FRAME_CIRCLE);
                else
                    spr_place(e, FRAME_CIRCLE);
                if (drop == 70 || drop == 71)
                    entity_inc_encounter_b();
                {
                    Slot *c = free_enemy();
                    if (c)
                    {
                        spawn_husk_at(c, sx, sy);
                        map_script_punch_88c2(sx, sy);
                    }
                }
                return;
            }
            if (kind == KIND_BOX && drop == 6)
            {
                /* 0x7882: in-place type 63; keep Yvel 8.8 (bind/timer). */
                award_for(kind);
                sound_play_explode();
                e->kind = KIND_CHIP;
                e->variant = 0;
                e->hp = 1;
                e->ground = 0;
                e->vx = 0;
                e->vy = 0;
                /* dest/bind/script/timer kept from box (bind=0x01C0). */
                if (e->spr)
                    SPR_setAnimAndFrame(e->spr, 0, FRAME_CHIP);
                return;
            }
            if (kind == KIND_DESCEND)
            {
                /* 836b: remapped to 0x23 then gate -> type62 / type83 / explode.
                 * Gate miss: type35 init does ALC+ev17+4a6a (no pre-SFX). */
                if (descender_on_death(e))
                    return;
                become_expl(e, 61);
                return;
            }
            if (kind == KIND_BOX)
            {
                award_for(kind);
                sound_play_explode();
                spr_kill(e);
                box_death_drop(drop, sx, sy);
            }
            else if (kind == KIND_BASE)
            {
                /* 8baa: 8ca2 punch via stored 8948 bind, DEC E152.
                 * E152==0 is noticed in 8f5e hold (90a6), not here.
                 * 8b85 ev17 + 8bc1 scatter (type35 SFX/score per shard). */
                award_for(kind);
                sound_play_event(SND_EV_EHIT);
                spr_kill(e);
                scatter_expl(sx, sy);
                if (s_base_left)
                    s_base_left--;
                map_script_base_seg_down(bind, drop);
            }
            else
            {
                /* entity_post -> type 0x23: type35 first frame ALC+SFX+4a6a. */
                become_expl(e, slot_msx_type(e));
            }
        }
        return;
    }
}

static void collide_shots_enemies(void)
{
    u8 i;
    for (i = 0; i < SHOT_SLOTS; i++)
    {
        Slot *s = &s_shot[i];
        if (!s->alive)
            continue;
        collide_bolt_enemies(s, 0);
    }
    if (s_fire.alive)
    {
        u8 fn = player_fire_num();
        u8 persist = 0;

        if (fn == 2)
            persist = 1;
        else if (fn == 4)
            persist = 2;
        collide_bolt_enemies(&s_fire, persist);
    }
}

static void collide_player(void)
{
    u8 j;
    s16 px;
    s16 py;

    if (player_invincible())
        return;

    px = player_x();
    py = player_y();

    for (j = 0; j < ENEMY_SLOTS; j++)
    {
        Slot *e = &s_en[j];
        u8 et;
        u8 pf;
        u8 cls;
        if (!e->alive)
            continue;
        /* 0x453E path: only types on a ship leg (44BA/44B0/44A6) count.
         * Shots-only structures (44CA) and no-post types are ignored. */
        et = slot_msx_type(e);
        pf = post_flags(et);
        if (!(pf & POST_SHIP))
            continue;
        /* ship SAT 0x38 half 4,4 => 8x8; enemy from e->sat */
        if (!hit_overlap(px, py, SAT_PLAYER, e->x, e->y, e->sat))
            continue;
        if (pf & POST_PICK)
        {
            /* 44B0 + 453E remaps both; pickup handler restores player (0x81). */
            if (e->kind == KIND_CHIP)
            {
                player_add_shot_level();
                sound_play_event(SND_EV_PICKUP);
                spr_kill(e);
                return;
            }
            if (e->kind == KIND_RISER)
            {
                /* 8752 ship-only 44b0; on clear: INC E10A + ev8 + status. */
                player_grant_life();
                spr_kill(e);
                return;
            }
            if (e->kind == KIND_FIREUP)
            {
                /* 8e89: player type 0x81, +0x1b=0, E148-=5, SET 7 +5,
                 * 48d0, bfc8, fire_select(+0x1c). */
                player_e148_sub5();
                player_fire_select(e->variant);
                entity_inc_encounter_b();
                spr_kill(e);
                return;
            }
            if (e->kind == KIND_ORB)
            {
                u16 dest = e->dest;
                u8 yellow = e->script;
                spr_kill(e);
                if (yellow)
                {
                    /* 8a26 explode_enemies + ev19. Types >=0x46 stay. */
                    entity_explode_airborne();
                    sound_play_event(SND_EV_PLASMA);
                }
                else
                    map_script_warp(dest);
                return;
            }
            /* Unknown pickup-class type: despawn only (CLS_CLEAR). */
            spr_kill(e);
            return;
        }
        /* Hostile ship overlap: 453E maps player->60 and enemy->class;
         * 7904 then DEC HP and restores enemy from +0x18 if HP remains. */
        cls = death_class(et);
        player_hit();
        if (e->hp > 1)
        {
            e->hp--;
            sound_play_event(SND_EV_EHIT);
            return;
        }
        if (cls == CLS_EXPL)
        {
            marker_kill(e);
            e->kind = KIND_EXPL;
            e->variant = 0;
            e->hp = 0;
            e->timer = 16;
            e->script = 0;
            e->ground = 0;
            e->vx = 0;
            e->vy = 0;
            if (e->spr)
                SPR_setAnimAndFrame(e->spr, 0, FRAME_CIRCLE);
            else
                spr_place(e, FRAME_CIRCLE);
        }
        else
            spr_kill(e);  /* CLS_CLEAR bullets (20/37/38/41/42/43) */
        return;
    }
}

void entity_init(void)
{
    memset(s_shot, 0, sizeof(s_shot));
    memset(&s_fire, 0, sizeof(s_fire));
    memset(s_en, 0, sizeof(s_en));

    s_rng = 0xA351;
    s_spawn_ctrl = 0x02;          /* stream active */
    s_spawn_base = 0;
    s_e135 = 0;
    s_e136 = 0;
    s_stream_slot = 0;
    s_e124 = 6;
    s_e125 = 0;
    s_box_seq = 0;
    s_fireup_seq = 0;
    s_base_left = 0;
    s_e150 = 0;
    s_e130 = 0;
    s_e141 = 0;
    s_e142 = 0;
    s_desc_cycle = 0;
    s_pat_rr = 0;
    s_alc_shots = 0;
    s_alc_events = 0;
    s_fyoff = s_fxoff = s_fvy = s_fvx = s_faccel = s_fanchor = 0;
    s_fdir = s_fexpire = s_f6cd = 0;
    entity_alc_reset();
    /* BE27 via alc_recompute already armed E137/E138 from BE76[0]=0x38. */

    /* Objs share PAL2 with the ship so index 15 stays TMS white.
     * PAL1 index 15 remains ROUND/HUD gold (set in game/title). */
    PAL_setPalette(PAL2, spr_objs.palette->data, CPU);
}

void entity_update(void)
{
    spawn_tick();
    update_shots();
    update_fire();
    update_enemies();
    collide_shots_enemies();
    collide_player();
}

void entity_release(void)
{
    u8 i;
    for (i = 0; i < SHOT_SLOTS; i++)
        spr_kill(&s_shot[i]);
    spr_kill(&s_fire);
    for (i = 0; i < ENEMY_SLOTS; i++)
        spr_kill(&s_en[i]);
}

void entity_on_spawn_ctrl(u8 ctrl)
{
    s_spawn_ctrl = ctrl;
    /* If a later round actually enables the stream, don't stall. */
    if ((ctrl & 0x02) && s_spawn_timer > s_spawn_reload)
        s_spawn_timer = s_spawn_reload;
}

void entity_on_spawn_pace(s8 nudge)
{
    s16 v;

    /* cmd 12: E132 += nn sat; if nn<0 also E12E += nn; SET 0,(E12D). */
    v = (s16)s_e132 + (s16)nudge;
    if (v < 0)
        v = 0;
    if (v > 255)
        v = 255;
    s_e132 = (u8)v;
    if (nudge < 0)
    {
        v = (s16)s_spawn_pos_hi + (s16)nudge;
        if (v < 0)
            v = 0;
        if (v > 255)
            v = 255;
        s_spawn_pos_hi = (u8)v;
    }
    /* SET 0,(E12D) Ã¢â‚¬â€ BE27 on next ground_struct_spawn_ctrl. */
    s_spawn_ctrl = (u8)(s_spawn_ctrl | 0x01);
}

void entity_alc_reset(void)
{
    s_spawn_pos_hi = 0;
    s_spawn_pos_lo = 0;
    s_e131 = 0;
    s_e132 = 0;
    alc_recompute();
}

void entity_alc_ease(void)
{
    /* 90a6: E12E -= E12E/4; E132 -= 8, sat 0.
     * Caller (90bf) then dec_encounter_a SETs bit0 for sticky BE27. */
    s_spawn_pos_hi = (u8)(s_spawn_pos_hi - (s_spawn_pos_hi >> 2));
    if (s_e132 >= 8)
        s_e132 = (u8)(s_e132 - 8);
    else
        s_e132 = 0;
}

void entity_dec_encounter_a(void)
{
    /* BFB3 / 90bf: DEC E12E if nonzero, then SET 0,(E12D).
     * Sticky Ã¢â‚¬â€ BE27 runs in ground_struct_spawn_ctrl, not here. */
    if (s_spawn_pos_hi)
        s_spawn_pos_hi--;
    s_spawn_ctrl = (u8)(s_spawn_ctrl | 0x01);
}

static void entity_inc_encounter_a(void)
{
    /* BFAB: INC E12E sat 255 unless E150 bit1, then SET 0,(E12D).
     * Sticky Ã¢â‚¬â€ BE27 runs in ground_struct_spawn_ctrl, not here. */
    if (!(s_e150 & 2))
    {
        s_spawn_pos_hi++;
        if (!s_spawn_pos_hi)
            s_spawn_pos_hi--;
    }
    s_spawn_ctrl = (u8)(s_spawn_ctrl | 0x01);
}

void entity_dec_encounter_b(void)
{
    /* BFBF / 9329: DEC E130 if nonzero. Display tail omitted. */
    if (s_e130)
        s_e130--;
}

void entity_timeout_alc(void)
{
    /* 932c-9334 while E150 bit1 still set: E12E += 0x10, then BFAB
     * (bit1 skips INC, still SETs sticky E12D bit0 for BE27). */
    s_spawn_pos_hi = (u8)(s_spawn_pos_hi + 0x10);
    entity_inc_encounter_a();
}



void entity_spawn_res3(void)
{
    /* 90c5: RES 3,E12D immediately before LD (E150),0. */
    s_spawn_ctrl = (u8)(s_spawn_ctrl & (u8)~0x08);
}

void entity_inc_encounter_b(void)
{
    /* SUB_bfc8 0xBFC8: if E150 bit1, skip INC (HUD-only). Else E130++ sat 255. */
    if (!(s_e150 & 2))
    {
        s_e130++;
        if (!s_e130)
            s_e130--;
    }
}

u8 entity_e12e(void)
{
    return s_spawn_pos_hi;
}

u8 entity_e132(void)
{
    return s_e132;
}

u8 entity_e130(void)
{
    return s_e130;
}

void entity_on_shot_fired(u8 cadence)
{
    u8 adv;
    u16 w;
    u16 lo;

    /* player_ship_update 0x7691: cadence>=0x12 -> 1, else table[E13F-2]. */
    if (cadence >= 0x12)
        adv = 1;
    else if (cadence < 2)
        adv = k_shot_rate[0];
    else
        adv = k_shot_rate[cadence - 2];

    /* 76a7: E12F += adv; C -> inc_encounter_a (SET bit0 sticky BE27).
     * Unlike table-spawn BF7A, shot carry does not silent-INC E12E alone. */
    lo = (u16)s_spawn_pos_lo + adv;
    s_spawn_pos_lo = (u8)lo;
    if (lo > 0xFF)
        entity_inc_encounter_a();

    w = (u16)s_e131 + adv;
    s_e131 = (u8)w;
    /* 0x76b5: carry -> SUB_bfc8 (E130++, gated by E150 bit1). */
    if (w > 255)
        entity_inc_encounter_b();

    /* 0x76bc: INC E141 sat 255 (shots since last type35 ALC dump). */
    s_e141++;
    if (!s_e141)
        s_e141--;

    if (s_alc_events < 255)
        s_alc_events++;
    /* 0x76e5 E140: INC only on successful spawn â€” entity_spawn_shot. */
}

bool entity_spawn_shot(s16 x, s16 y)
{
    u8 i;
    u8 live = 0;
    u8 lvl;
    u8 cap;
    u8 frame;
    s8 vy;
    Slot *free = NULL;

    lvl = player_shot_level();
    if (lvl > 5)
        lvl = 5;
    cap = k_shot_power[lvl][1];
    vy = (s8)(-(s8)k_shot_power[lvl][0]);
    frame = k_shot_power[lvl][2];

    for (i = 0; i < SHOT_SLOTS; i++)
    {
        if (s_shot[i].alive)
            live++;
        else if (!free)
            free = &s_shot[i];
    }
    if (live >= cap || !free)
        return FALSE;

    free->alive = 1;
    free->kind = KIND_SHOT;
    free->x = x;
    free->y = y;
    free->vx = 0;
    free->vy = vy;
    free->spr = NULL;
    spr_place(free, frame);
    if (!free->spr)
    {
        free->alive = 0;
        return FALSE;
    }
    /* 0x76e5: INC E140 only after a free slot actually spawned. */
    if (s_alc_shots < 255)
        s_alc_shots++;
    return TRUE;
}

void entity_try_spawn_fire(s16 x, s16 y, u8 xvel_sel)
{
    u8 fn;
    u8 dir;
    u16 frame;

    fn = player_fire_num();
    /* Fire 6 Plasma Flash: no persistent type-3. Expire 0x7511 =
     * explode_enemies + ev19 + 0x749c ammo check. */
    if (fn == 6)
    {
        if (s_f6cd)
            return;
        s_f6cd = 20;
        player_fire_dec_ammo();
        entity_explode_airborne();
        sound_play_event(SND_EV_PLASMA);
        if (player_fire_ammo() == 0)
            player_fire_select(0);
        return;
    }

    if (s_fire.alive)
        return;

    if (xvel_sel > 8)
        xvel_sel = 8;

    s_fire.alive = 1;
    s_fire.kind = KIND_FIRE;
    s_fire.variant = fn;
    s_fire.hp = 1;
    s_fire.timer = 0;
    s_fire.script = 0;
    s_fire.x = x;
    s_fire.y = y;
    s_fire.spr = NULL;
    s_fexpire = 0;

    if (fn == 1)
    {
        /* Straight 0x72A8: fire_dec_ammo, +0x0C=1 Y-only, vy=0xFE, pat 2. */
        s_fire.vx = 0;
        s_fire.vy = -2;
        frame = FRAME_COMET;
        player_fire_dec_ammo();
    }
    else if (fn == 2)
    {
        /* Field Shutter 0x729D: +0x0C=0, pat 9, follows ship. */
        s_fire.vx = 0;
        s_fire.vy = 0;
        s_fire.y = (s16)(y - 8);
        frame = FRAME_CIRCLE;
    }
    else if (fn == 3)
    {
        /* Circular 0x7331: SAT 0x10 pat 4, +0x0C=0, off 0xC000/0xF600, dir 0xFF. */
        s_fyoff = (s16)0xC000;
        s_fxoff = (s16)0xF600;
        s_fdir = 0xFF;
        s_fire.vx = 0;
        s_fire.vy = 0;
        frame = FRAME_CIRCLE;
    }
    else if (fn == 4)
    {
        /* Vibrator 0x73CE/0x73F1: SAT 0x24, vy=-1, vx=-12, accel=+4, +0x1C=70. */
        s16 ax;
        s16 max_x;
        const ModeAssets *a = mode_assets();

        player_fire_dec_ammo();
        max_x = (s16)(a->playfield_w - (256 - 0xA0));
        if (max_x < 0xA0)
            max_x = 0xA0;
        ax = clamp16(x, 0x50, max_x);
        s_fanchor = ax;
        s_fire.x = (s16)(ax + 0x18);
        if (y < 0x50)
            s_fire.y = 0x50;
        s_fire.vx = 0;
        s_fire.vy = -1;
        s_fvx = (s16)0xF400;
        s_faccel = (s16)0x0400;
        s_fire.timer = 0x46;
        frame = FRAME_CIRCLE;
    }
    else if (fn == 5)
    {
        /* Rewinder 0x73C8: SAT 0x0C, vy=0xFE00, Y-only, then 0x7464. */
        player_fire_dec_ammo();
        s_fire.vx = 0;
        s_fire.vy = 0;
        s_fvy = (s16)0xFE00;
        frame = FRAME_FIRE;
    }
    else if (fn == 7)
    {
        /* High Speed 0x728F: SAT 0x08 comet, fire0_dir_table, speed 0xC3. */
        dir = k_fire7_dir[xvel_sel];
        apply_dir_fire7(&s_fire, dir);
        frame = FRAME_COMET;
    }
    else
    {
        /* Fire 0 All-Range 0x72B3: xvel_table[E10C] (copied to IX+0x1A). */
        dir = k_xvel_dir[xvel_sel];
        apply_dir_fast(&s_fire, dir);
        frame = FRAME_FIRE;
    }

    spr_place(&s_fire, frame);
    if (!s_fire.spr)
    {
        s_fire.alive = 0;
        return;
    }
    sound_play_event(SND_EV_FIRE);
}

void entity_kill_fire(void)
{
    spr_kill(&s_fire);
}

u8 entity_shot_count(void)
{
    u8 i, n = 0;
    for (i = 0; i < SHOT_SLOTS; i++)
        if (s_shot[i].alive)
            n++;
    return n;
}

u8 entity_enemy_count(void)
{
    u8 i, n = 0;
    for (i = 0; i < ENEMY_SLOTS; i++)
        if (s_en[i].alive)
            n++;
    return n;
}

/* check_col_clear 0x9B22.
 * MSX scans entity slots 5..25 (21 entries, stride -32 from 0xE620).
 * CF set = blocked (skip place); CF clear = ok (HL = destination slot).
 * Phase 1: any type==0 -> NC. Phase 2: type in {0x14,0x25,0x26} -> NC
 * (overwrite). Phase 3: type 0x27 or >=0x46 are blocking; any other -> NC;
 * if all blocking -> SCF.
 * MD: no type-39 sprite slots (complements folded); count each marker flag as
 * a virtual 0x27 so dual-SAT rows pressure the 21-entry window like MSX. */
u8 entity_check_col_clear(void)
{
    u8 occ[ENEMY_SLOTS * 2];
    u8 n = 0;
    u8 i;
    u8 t;

    for (i = 0; i < ENEMY_SLOTS; i++)
    {
        Slot *e = &s_en[i];
        if (!e->alive)
            continue;
        t = e->variant ? e->variant : e->kind;
        if (n < (u8)sizeof(occ))
            occ[n++] = t;
        /* type39 col-marker sibling (71f6) occupies a real MSX slot. */
        if (e->marker && n < (u8)sizeof(occ))
            occ[n++] = 0x27;
    }

    /* Phase 1: empty slot in the 21-wide window. */
    if (n < 0x15)
        return 1;

    /* Phase 2: overwriteable types 20 / 37 / 38. */
    for (i = 0; i < 0x15 && i < n; i++)
    {
        t = (u8)(occ[i] & 0x7F);
        if (t == 0x14 || t == 0x25 || t == 0x26)
            return 1;
    }

    /* Phase 3: non-blocking type can be overwritten; else SCF. */
    for (i = 0; i < 0x15 && i < n; i++)
    {
        t = (u8)(occ[i] & 0x7F);
        if (t == 0x27 || t >= 0x46)
            continue;
        return 1;
    }
    return 0;
}

u8 entity_place_ground(u8 type, s16 x, s16 y, u16 dest)
{
    Slot *e;
    const ModeAssets *a = mode_assets();

    if (x < -16)
        x = -16;
    if (x > (s16)(a->playfield_w - 8))
        x = (s16)(a->playfield_w - 8);

    /* MSX Y=0xF0 wraps on to the top; treat high Y as signed incoming. */
    if (y >= 192)
        y = (s16)(y - 256);

    e = free_enemy();
    if (!e)
        return 0;
    if (type == 80)
        spawn_husk_at(e, x, y);
    else if (type == 70 || type == 71 || type == 81
        || type == 84 || type == 85 || type == 86
        || type == 87 || type == 88 || type == 89)
        spawn_wide_at(e, type, x, y, dest);
    else if (type == 82)
        spawn_wide_at(e, 82, x, y, dest);
    else if (type >= 73 && type <= 79)
        spawn_base_seg(e, type, x, y);
    else
        spawn_ground_fall(e, type, x, y, dest);
    return 1;
}

void entity_base_open(u8 n)
{
    u16 v = (u16)s_base_left + n;
    if (v > 255)
        v = 255;
    s_base_left = (u8)v;
    /* place_tile_group 0x966F: E150 := 1 when ctrl bit7. */
    if (n)
        s_e150 = 1;
}

void entity_base_arm(void)
{
    u8 i;
    u8 pat;

    /* LAB_8fca: E150 := 2. Per-segment SET 7 (+0x10 / 8948) is in base_step. */
    s_e150 = 2;
    /*
     * 8fde / base_attack_patterns 0x93AB: reset E717 to table head, then for
     * each E780 attack-list body (port: live KIND_BASE in slot order) write
     * the next pattern descriptor (+0x0F/+0x10), clear +0x0E fire accum,
     * stamp +0x1C = sequential index, wrap every 8 patterns. Hold frames
     * jump to 9028 and skip this - one-shot at approach->hold only.
     */
    pat = 0;
    for (i = 0; i < ENEMY_SLOTS; i++)
    {
        Slot *e = &s_en[i];

        if (!e->alive || e->kind != KIND_BASE)
            continue;
        /* dest: low3=pat, mid5=rec, hi8=fire_acc (+0x14). Fresh pattern. */
        e->dest = pat;
        e->timer = 0;                   /* +0x0E phase-rate accum */
        e->clock = pat;                 /* +0x1C attack-list index */
        /* Keep SET7 if somehow already armed; clear phase / dir bits. */
        e->script = (u8)(e->script & 0x80);
        pat++;
        if (pat >= 8)
            pat = 0;
    }
    s_pat_rr = pat;
}

void entity_base_or_flags(u8 bits)
{
    s_e150 = (u8)(s_e150 | bits);
}

void entity_base_set(u8 v)
{
    s_e150 = v;
}

u8 entity_base_flags(void)
{
    return s_e150;
}

void entity_explode_airborne(void)
{
    u8 i;

    /* explode_enemies 0x8A26: type & 0x7F in [1,0x45] except 0x28 -> 0x23.
     * Keeps +0x18 so type35 4a6a scores the source type. */
    for (i = 0; i < ENEMY_SLOTS; i++)
    {
        Slot *e = &s_en[i];
        u8 score_t;

        if (!e->alive)
            continue;
        if (e->kind >= 70 || e->kind == KIND_EXPL || e->kind == KIND_PDEAD)
            continue;
        score_t = slot_msx_type(e);
        become_expl(e, score_t);
    }
}

void entity_clear_enemies(void)
{
    u8 i;
    for (i = 0; i < ENEMY_SLOTS; i++)
        spr_kill(&s_en[i]);
    s_base_left = 0;
    if (s_e150)
        map_script_resume_scroll();
    s_e150 = 0;
}

void entity_convert_clear_types(void)
{
    u8 i;

    /* 90dc: type&0x7F in {82,84,85,86} -> type 80, +0x18=0. Then 8e14. */
    for (i = 0; i < ENEMY_SLOTS; i++)
    {
        Slot *e = &s_en[i];
        u8 t;

        if (!e->alive)
            continue;
        t = (u8)(e->variant & 0x7F);
        if (t == 0x53)
            continue;
        if (t < 0x52)
            continue;
        if (t >= 0x57)
            continue;
        e->kind = KIND_HUSK;
        e->variant = 80;
        e->script = 0;
        e->hp = 0;
        e->timer = 0;
        e->vx = 0;
        e->vy = 0;
        e->ground = 1;
        e->dest = 0;
    }
}
