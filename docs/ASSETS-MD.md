# Zanac MD — asset replacement sheet

Practical list of every MSX graphic/sound the **Zanac MD** mode can swap.
Numbers are from `zanac-re` KB + SGDK 2.11 / Mega Drive VDP, not guesses.
Original mode keeps the extracted MSX skin; this sheet is the art pack you drop
under `res/md/` and later wire through `ModeAssets`.

Sources: `kb/guides/zanac-sprite-names.md`, `entity-sprite-mapping.md`,
`graphics-data.md`, `zanac-vdp-layout.md`, `vdp-tms9918a.md`, `sound-engine.md`,
`sound_track_scores.md`, subsystems F/G/H/J/L/N/O; port `res/resources.res`,
`src/mode.c`, `src/sound.c`, `src/map_script.c`, `tools/extract_map_scripts.py`;
SGDK 2.11 `inc/vdp.h`, `vdp_spr.h`, `snd/xgm.h`, `snd/xgm2.h`.

Do **not** invent pattern IDs. If a count is unknown it is marked **unknown**.

---

## How to use this

1. Draw/compose new Mega Drive assets at the sizes in tables B and C.
2. Drop files using the folder convention in table E (do not overwrite Original
   `res/sprites/` or `res/charset_tiles.bin`).
3. Add `SPRITE` / `TILESET` / `XGM` / `WAV` lines to `res/resources.res` when
   ready. `ModeAssets` currently only holds `ship` + screen size; extend it with
   pointers and swap them in `mode_init()` for `MODE_ZANAC_MD`.
4. Complements (MSX second sprite for a second color) should be **folded** into
   one 4bpp sprite. Do not allocate a second hardware sprite for a shadow.

---

## Hardware (accurate)

### MSX SCREEN2 / TMS9918A (this ROM)

| Item | Value | Source |
| --- | --- | --- |
| Playfield | 256×192, 32×24 cells | TMS SCREEN2; VDP R2 name table 0x3800 |
| Colors | 16 fixed TMS palette | `vdp-tms9918a.md` |
| BG tiles | 8×8, 1 bit + color-table byte per row (2 colors/row) | graphics-data |
| Unique charset | **256 tiles** (decompress confirmed) | `gfx_charset_bitmap` → 256×8 = 2048 B, loaded into all 3 PGT banks |
| Sprites | 16×16, 1-bit, 1 color + optional complement (EC+black 0x81) | R1 SI=1 MAG=0 |
| Unique sprite patterns | **64** (pats 0–63), 32 B each, VRAM 0x1800–0x1FFF | `gfx_sprite_patterns` 2048 B |
| Sprite slots | 32 total, **4 per line** (5th dropped) | TMS SAT 0x3B80 |
| Complement | Second SAT entry, same X/Y, color 0x81 | `zanac-sprite-names.md` |
| Audio | AY-3-8910: 3 square + 1 noise | subsystem O |
| Sound events | **27** (index 1–27; 0 = sentinel), 51 voices | `sound_track_scores.md` 100% decode 0x5236–0x5A10 |

### Mega Drive / SGDK 2.11 (this port)

| Item | Original mode | Zanac MD mode | Hardware max |
| --- | --- | --- | --- |
| Width | H32 **256×224** (`VDP_setScreenWidth256`) | H40 **320×224** (`VDP_setScreenWidth320`) | NTSC height 224 only |
| `ModeAssets` | playfield 256×224, name `"ORIGINAL"` | playfield 320×224, name `"ZANAC MD"` | `src/mode.c` — both still point `ship` at `spr_ship` |
| Tiles | 8×8, 4bpp, 32 B (`TILE_SIZE`) | same | VRAM 64 KB; tile space ends at `VDP_MAPS_START` (~1536 tiles typical) |
| Colors | 4 CRAM pals × 16 = 64 on screen from 512 (9-bit) | same | PAL0–PAL3 |
| Sprites | SGDK engine, 80 max (`SAT_MAX_SIZE`) | same | size 1×1 to 4×4 tiles (8–32 px); `SPRITE_SIZE(w,h)` |
| Sprites / line | 16 (H32) | 20 (H40) | plus 256/320 sprite pixels/line |
| Current art | `ship.png` 16×16; `objs.png` 208×16 (13 frames); charset 256 tiles @ `TILE_USER_INDEX+32` | **none yet** — this sheet | — |
| Current pals | PAL0 text, PAL1 objs/highlight, PAL2 ship, PAL3 TMS charset | keep this split unless you rewire | — |
| Audio now | PSG interpreter of the 27 MSX events, `Z80_DRIVER_NULL` | same until you swap the driver | YM2612 6 FM + MD PSG 3 square + noise |
| Audio MAY | keep PSG | XGM / XGM2 / WAV via SGDK | XGM: 4 PCM @ 14 kHz; XGM2: 3 PCM @ 13.3 or 6.65 kHz; WAV = 8-bit PCM 8–32 kHz |

SGDK VRAM layout: tiles at the bottom of VRAM, maps/SAT/HScroll at the top.
`TILE_USER_INDEX` = 16 (after 16 system tiles). `FONT_LEN` = 96.
`TILE_FONT_INDEX` = TILE_MAX_NUM − 96. Sprite engine allocates downward from there.

---

## A. Screen / palette / tile budget

| Item | MSX | Original H32 | Zanac MD H40 (MAY) | Notes |
| --- | --- | --- | --- | --- |
| Playfield px | 256×192 | 256×224 | 320×224 | mode.c |
| Visible cells | 32×24 | 32×28 | 40×28 | 8 extra columns = 64 px HUD or wider field |
| BG tile format | 8×8 1bpp + CT | 8×8 4bpp | 8×8 4bpp | 32 B/tile |
| Unique BG tiles | **256** charset | 256 loaded | **512–1024** safe (2–3 pals) | HW ~1500 including font+sprites; start at 512 |
| Colors / tile | 2 per pixel-row | 16 from 1 pal | 16 from 1 pal | color 0 = trans on sprites |
| On-screen colors | 16 TMS fixed | 64 from 512 | 64 from 512 | 4×16 CRAM |
| Suggested pals | n/a | PAL0 text, PAL1 objs, PAL2 ship, PAL3 BG | PAL0 font/HUD, PAL1 player+shots+items, PAL2 enemies, PAL3 BG | 1 pal per sprite |
| Sprite size | 16×16 1-bit | SPRITE 2×2 | 2×2 default; 3×3/4×4 large | SGDK w/h in tiles 1–4 |
| Sprite colors | 1 + complement | 15+trans | 15+trans, fold complements | Do not draw _compl as a second sprite |
| Sprite patterns | **64** unique | 1+13 extracted | replace all named visuals | pats 0–63 |
| Sprites total / line | 32 / 4 | 80 / 16 | 80 / 20 | SAT_MAX_SIZE 80 |
| Audio | AY 3+noise, 27 events | PSG interpreter | XGM loop + PCM one-shots (or keep PSG) | Cannot run XGM + current NULL driver together |

### Current port numbers (do not guess)

| File | Size | Meaning |
| --- | --- | --- |
| `res/sprites/ship.png` | **16×16** | MSX pat 14, TMS color 15 |
| `res/sprites/objs.png` | **208×16** | 13 frames × 16 px: pats **10, 22, 24, 30, 53, 1, 7, 28, 11, 12, 3, 9, 2** |
| `res/charset_tiles.bin` | **8192 B** | 256 × 32 B MD 4bpp |
| `res/sound_blob.bin` | **2013 B** | MSX 0x5234–0x5A10 |
| `res/map_blob.bin` | **8899 B** | tile columns + scripts 0x9B64–0xBE26 |
| `res/resources.res` | SPRITE 2 2 | both sprites declared `2 2 NONE 0` |

`objs.png` frames in `entity.c`: 0 shot, 1 duster, 2 teruzo, 3 luster, 4 box, 5 chip, 6 lead, 7 sig, 8 shot_d, 9 shot_t, 10 fire/target, 11 lg_circle, 12 comet.

---

## B. Sprite slots — named MSX patterns

64 patterns. Pattern index = SAT_NAME >> 2 (16×16 mode, low 2 bits ignored).
Each MSX sprite is 16×16 1-bit. **MD default is 2×2 tiles (16×16 4bpp)** so
Original and Zanac MD can share hit-boxes; larger sizes are allowed in Zanac MD
only. `max colors` = 15 visible + transparent index 0.

Complement rows (`*_compl`) are **not** separate MD assets — fold their pixels
into the primary.

| Pat | Name | Group | Suggested MD size | Pal | Colors | Frames in set | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | empty | empty | — | — | — | 1 | All-zero pattern. SAT terminator / invisible slots. Do not draw. |
| 1 | power_chip | item | 2×2 tiles (16×16px) | PAL1 | 15+trans | 1 | Weapon-upgrade pickup. Type 83 also uses SAT 0x04 = pat 1 (black/EC). Type 63 handler does not LD a SAT name (likely inherits pat 1; not confirmed in handler). |
| 2 | comet | fx | 2×2 tiles (16×16px) | PAL2 | 15+trans | 1 | Named in sprite-names. No entity type in entity-sprite-mapping uses this pattern. Port extracts it as objs.png frame 12. Entity use: unknown. |
| 3 | target | fire | 2×2 tiles (16×16px) | PAL1 | 15+trans | 1 | Fire weapon 0 All-Range Cannon. Type 3, +0x0C=0x03. Color cycles 0x80-0x8F (all 16 TMS colors). |
| 4 | snowflake | fire | 2×2 tiles (16×16px) | PAL1 | 15+trans | 1 | Fire 3 Circular and fire 4 Vibrator. Type 3. |
| 5 | small_star | fx | 1×1 tiles (8×8px) | PAL1 | 15+trans | 1 | Named in sprite-names. No confirmed entity type. Entity use: unknown. |
| 6 | light_bar | projectile | 2×1 tiles (16×8px) | PAL2 | 15+trans | 1 | Types 21 (color 0x84/0x85) and 45 (white 0x8F). Ground-guns 48/49/52-55 spawn type 21. |
| 7 | lead | projectile | 1×1 tiles (8×8px) | PAL2 | 15+trans | 1 | Small bullet. Types 20, 37, 38, 41, 42/43 (init), 69, 75. Death/orb anims also use it as frame 0 of a pulse. |
| 8 | medium_circle | projectile | 2×2 tiles (16×16px) | PAL2 | 15+trans | 1 | Type 67. Type 35/60/72 anim mid-frame. Type 73 probe uses pat 8 transparent. |
| 9 | large_circle | projectile | 2×2 tiles (16×16px) | PAL1 | 15+trans | 1 | Fire expire / type 19 first frame. Type 72 orb. Types 82/87 likely. Peak of pulse anims. |
| 10 | shot_single | shot | 2×2 tiles (16×16px) | PAL1 | 15+trans | 1 | Player shot levels 0-1. SAT_NAME 0x28 from shot_power_table. Type 2. Type 11 init also writes 0x28. |
| 11 | shot_double | shot | 2×2 tiles (16×16px) | PAL1 | 15+trans | 1 | Player shot levels 2-3. SAT_NAME 0x2C. |
| 12 | shot_triple | shot | 2×2 tiles (16×16px) | PAL1 | 15+trans | 1 | Player shot levels 4-5. SAT_NAME 0x30. |
| 13 | super_hard_bolt | enemy | 2×2 tiles (16×16px) | PAL2 | 15+trans | 1 | Type 36 flashing: SAT 0x34, color XOR 0x0E each frame, slow descent. |
| 14 | player_ship | player | 2×2 tiles (16×16px) | PAL2 | 15+trans | 1 | Type 1, SAT 0x38, color 0x8F normal / 0x81 invincible flash (~64 frames). Port: res/sprites/ship.png 16x16. Zanac MD MAY use 3x3 or 4x4. |
| 15 | player_ship_compl | player | fold into pat 14 | — | — | 1 | Complement of pat 14. Extract script: unused. Fold into player_ship on MD (4bpp). Do not ship a second sprite. |
| 16 | plane | enemy | 2×2 tiles (16×16px) | PAL2 | 15+trans | 1 | Type 44 ground structure sprite + type 64 proto. Type 35 pool can pick pat 16. |
| 17 | plane_compl | enemy | fold into pat 16 | — | — | 1 | Complement of plane. Type 39 col-marker. Fold into plane. |
| 18 | loga_A | loga | 2×2 tiles (16×16px) | PAL2 | 15+trans | 2 | Opener enemy, 2-frame set in pattern table (18/20). Types 46-55 ground-guns use SAT 0x48 = pat 18. Runtime animation: unknown (handler does not document bit2 anim). |
| 19 | loga_A_compl | loga | fold into pat 18 | — | — | 2 | Complement of loga_A. Fold into loga. |
| 20 | loga_B | loga | 2×2 tiles (16×16px) | PAL2 | 15+trans | 2 | Second loga frame in pattern table. Runtime use: unknown. |
| 21 | loga_B_compl | loga | fold into pat 20 | — | — | 2 | Complement of loga_B. Fold into loga. |
| 22 | duster | duster | 2×2 tiles (16×16px) | PAL2 | 15+trans | 1 | Type 10. SAT 0x58, color 0x89. Meteor-like. |
| 23 | duster_compl | duster | fold into pat 22 | — | — | 1 | Complement. Type 39. Fold into duster. |
| 24 | teruzo | teruzo | 2×2 tiles (16×16px) | PAL2 | 15+trans | 1 | Types 12-15. SAT 0x60 hardcoded. Colors 0x8A (lower) / 0x89 (upper). Type 35 pool can pick pat 24. |
| 25 | teruzo_compl | teruzo | fold into pat 24 | — | — | 1 | Complement SAT 0x64. Fold into teruzo. |
| 26 | sig_triple | sig | 2×2 tiles (16×16px) | PAL2 | 15+trans | 1 | Sprite-names: sig triple. Type 58 paired descender B uses SAT 0x68 = pat 26. |
| 27 | sig_double | sig | 2×2 tiles (16×16px) | PAL2 | 15+trans | 1 | Sprite-names: sig double. Type 57 paired descender A uses SAT 0x6C = pat 27. |
| 28 | sig_single | sig | 2×2 tiles (16×16px) | PAL1 | 15+trans | 1 | Type 56 falling pickup/missile, color XOR 0x09 (0x86↔0x8F). Type 59 sideways also SAT 0x70 = pat 28. |
| 29 | luster_A | luster | 2×2 tiles (16×16px) | PAL2 | 15+trans | 2 | Type 18. SAT 0x74, color 0x8B. 2-frame set exists (29/30); types pick one variant, bit2 anim not documented. |
| 30 | luster_B | luster | 2×2 tiles (16×16px) | PAL2 | 15+trans | 2 | Types 16/17. SAT 0x78, color 0x8E. Tank-like. |
| 31 | luster_A_compl | luster | fold into pat 29 | — | — | 2 | Complement of luster_A. Fold into luster. |
| 32 | luster_B_compl | luster | fold into pat 30 | — | — | 2 | Complement of luster_B. Fold into luster. |
| 33 | veybar_0 | veybar | 3×3 tiles (24×24px) | PAL2 | 15+trans | 5 | Glider. Types 22-25 use SAT 0x84 = pat 33 only. 5 primary frames exist (33-37); runtime cycle: unknown. |
| 34 | veybar_1 | veybar | 3×3 tiles (24×24px) | PAL2 | 15+trans | 5 | Frame 1 of 5 in pattern table. Handler use: unknown. |
| 35 | veybar_2 | veybar | 3×3 tiles (24×24px) | PAL2 | 15+trans | 5 | Frame 2 of 5. Handler use: unknown. |
| 36 | veybar_3 | veybar | 3×3 tiles (24×24px) | PAL2 | 15+trans | 5 | Frame 3 of 5. Handler use: unknown. |
| 37 | veybar_4 | veybar | 3×3 tiles (24×24px) | PAL2 | 15+trans | 5 | Frame 4 of 5. Handler use: unknown. |
| 38 | veybar_0_compl | veybar | fold into pat 33 | — | — | 5 | Complement of veybar_0 (SAT 0x98). Fold into veybar. |
| 39 | veybar_1_compl | veybar | fold into pat 34 | — | — | 5 | Fold into veybar. |
| 40 | veybar_2_compl | veybar | fold into pat 35 | — | — | 5 | Fold into veybar. |
| 41 | veybar_3_compl | veybar | fold into pat 36 | — | — | 5 | Fold into veybar. |
| 42 | veybar_4_compl | veybar | fold into pat 37 | — | — | 5 | Fold into veybar. |
| 43 | spinner_0 | spinner | 2×2 tiles (16×16px) | PAL2 | 15+trans | 4 | Edge-swooper / spinner. Types 26-29. Anim table CONFIRMED 4 frames pats 43,44,45,46 (edge_swooper_a_anim 0x7E68 / b 0x7E70). Color 0x8E (A) or 0x87 (B). |
| 44 | spinner_1 | spinner | 2×2 tiles (16×16px) | PAL2 | 15+trans | 4 | Frame 1. Confirmed in anim tables. |
| 45 | spinner_2 | spinner | 2×2 tiles (16×16px) | PAL2 | 15+trans | 4 | Frame 2. Confirmed in anim tables (entity-sprite-mapping once listed 46 as frame 2 — tables are 43,44,45,46). |
| 46 | spinner_3 | spinner | 2×2 tiles (16×16px) | PAL2 | 15+trans | 4 | Frame 3. Confirmed. |
| 47 | spinner_0_compl | spinner | fold into pat 43 | — | — | 4 | Complement = sat_name+0x10 (pat 47). Fold into spinner. |
| 48 | spinner_1_compl | spinner | fold into pat 44 | — | — | 4 | Fold into spinner. |
| 49 | spinner_2_compl | spinner | fold into pat 45 | — | — | 4 | Fold into spinner. |
| 50 | spinner_3_compl | spinner | fold into pat 46 | — | — | 4 | Fold into spinner. |
| 51 | stealth | stealth | 2×2 tiles (16×16px) | PAL2 | 15+trans | 1 | Types 31/33 tracker and 34/65/66 stationary. SAT 0xCC, color 0x88 (type 65 override 0x85). |
| 52 | stealth_compl | stealth | fold into pat 51 | — | — | 1 | Complement SAT 0xD0. Fold into stealth. Also appears as skipped frame 0 of type-35 anim table (never shown). |
| 53 | box | box | 2×2 tiles (16×16px) | PAL1 | 15+trans | 1 | Types 4-6. SAT 0xD4 after countdown. Type 4 drops 3× type-38; 5 drops nothing; 6 drops type 63. |
| 54 | box_compl | box | fold into pat 53 | — | — | 1 | Complement SAT 0xD8. Fold into box. |
| 55 | umber_A | umber | 3×3 tiles (24×24px) | PAL2 | 15+trans | 2 | Types 7/8. SAT 0xDC. Type 7 white 0x8F bursts 7× type-38; type 8 light-red 0x8B bursts 2× type-41. Squid-like. 2-frame set exists; handler uses A or B as variants, not a confirmed cycle. |
| 56 | umber_B | umber | 3×3 tiles (24×24px) | PAL2 | 15+trans | 2 | Type 9. SAT 0xE0, cyan 0x83. Timer spawns type 20. |
| 57 | umber_A_compl | umber | fold into pat 55 | — | — | 2 | Complement SAT 0xE4. Fold into umber. |
| 58 | umber_B_compl | umber | fold into pat 56 | — | — | 2 | Complement SAT 0xE8. Fold into umber. |
| 59 | degid_left | degid | 2×2 tiles (16×16px) | PAL2 | 15+trans | 1 | Sprite-names: degid left. Types 30/32 ground swooper SAT 0xEC = pat 59. |
| 60 | degid_right | degid | 2×2 tiles (16×16px) | PAL2 | 15+trans | 1 | Sprite-names: degid right. Entity type that uses pat 60: unknown. |
| 61 | degid_complete | degid | 2×2 tiles (16×16px) | PAL2 | 15+trans | 1 | Sprite-names: degid complete. Entity type that uses pat 61: unknown. |
| 62 | sart | sart | 4×4 tiles (32×32px) | PAL2 | 15+trans | 1 | Type 61 large descender. SAT 0xF8, color from large_descender_color_table (8 TMS colors cycling). Largest named pattern index. |
| 63 | sart_compl | sart | fold into pat 62 | — | — | 1 | Complement of sart. Fold into sart. |

### B2. Entity type → pattern → MD sprite

One row per handler family. Pattern IDs only where the KB writes them.

| Type(s) | Name | MSX pat | MD size | Pal | Colors | Anim | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | player_ship | 14 | 2x2 (MD MAY 3x3/4x4) | PAL2 | 15+trans | 1 + i-frame color flash | Slot 0. SAT 0x38. Color 0x8F / 0x81 invuln 64 frames. Complement pat 15 unused. Port: spr_ship PAL2. |
| 2 | shot | 10/11/12 | 2x2 | PAL1 | 15+trans | 3 power looks (not frames) | SAT from E10F via shot_power_table: 0x28/0x2C/0x30. Cap 2 or 3 on screen. SFX event = 3+(E10F>>2) → 13/14/15. |
| 3 | fire_weapon | 3 / 4 / 9 / varies | 2x2 | PAL1 | 15+trans | see fire 0-7 | All 8 fire types in slot 4. Fire 0: pat 3 color-cycle. Fire 3/4: pat 4. Fire 6: no persistent entity. Fire 1/5/7 exact pattern: unknown (KB: color cycle / varies). |
| 4-6 | box | 53 | 2x2 | PAL1 | 15+trans | countdown then reveal | SAT_NAME countdown then 0xD4. Complement 54. Drop by type: 4→3× type38, 5→none, 6→type63. |
| 7-8 | umber_A | 55 | 3x3 | PAL2 | 15+trans | 2 variants in set; not confirmed cycle | SAT 0xDC. Type 7 color 0x8F burst 7×38; type 8 color 0x8B burst 2×41. Complement 57. |
| 9 | umber_B | 56 | 3x3 | PAL2 | 15+trans | variant B | SAT 0xE0 color 0x83. Spawns type 20 on timer. Complement 58. |
| 10 | duster | 22 | 2x2 | PAL2 | 15+trans | 1 | SAT 0x58 color 0x89. Complement 23. |
| 11 | base_spawner | 10 then type→69 | — | — | — | transient | Init writes shot_single then becomes type 69. No unique art. |
| 12-15 | teruzo | 24 | 2x2 | PAL2 | 15+trans | 1 | SAT 0x60 hardcoded. 12/13 lower Y=112 color 0x8A; 14/15 upper Y=32 color 0x89. Complement 25. |
| 16-17 | luster_B | 30 | 2x2 | PAL2 | 15+trans | variant B | SAT 0x78 color 0x8E. 16 = Y-fall; 17 = homing. |
| 18 | luster_A | 29 | 2x2 | PAL2 | 15+trans | variant A | SAT 0x74 color 0x8B. |
| 19 | fire_expire | 9 then type→3 | 2x2 | PAL1 | 15+trans | transient | First frame pat 9 color 0x80, then type 0x83 (dispatches as type 3). Not an enemy. |
| 20 | lead_homing | 7 | 1x1 or 2x2 | PAL2 | 15+trans | 1 | SAT 0x1C. Spawned by type 9. |
| 21 | light_bar | 6 | 2x1 or 2x2 | PAL2 | 15+trans | 1 | SAT 0x18 color 0x84/0x85. |
| 22-23 | veybar | 33 | 3x3 | PAL2 | 15+trans | 5 exist; handler uses 33 only | SAT 0x84 color 0x83. Complement 38. Y-homing. |
| 24-25 | veybar_fast | 33 | 3x3 | PAL2 | 15+trans | same as 22-23 | SAT 0x84 color 0x89. Full homing. |
| 26-27 | edge_swooper_A | 43-46 | 2x2 | PAL2 | 15+trans | 4 CONFIRMED | Table 0x7E68 color 0x8E. Complement sat_name+0x10. |
| 28-29 | edge_swooper_B | 43-46 | 2x2 | PAL2 | 15+trans | 4 CONFIRMED | Table 0x7E70 color 0x87. |
| 30/32 | ground_swooper | 59 | 2x2 | PAL2 | 15+trans | 1 | SAT 0xEC = degid_left. Sprite-names degid right/complete (60/61) unused by this handler. |
| 31/33 | stealth_tracker | 51 | 2x2 | PAL2 | 15+trans | 1 | SAT 0xCC color 0x88. Complement 52. Tracks player Y then X. |
| 34/65/66 | stealth_stationary | 51 | 2x2 | PAL2 | 15+trans | 1 | Same sprite; 3-shot bursts. Type 65 color override 0x85. |
| 35 | enemy_projectile | 7/8/9/16/24 | 2x2 | PAL2 | 15+trans | 6-frame pulse CONFIRMED | Init pattern from E141. Then table 0x84D1 tick_rate=4: (skip) lead→med→lg→med→lead. NOT a base-eye. |
| 36 | flashing_bolt | 13 | 2x2 | PAL2 | 15+trans | color XOR flicker | SAT 0x34. Color XOR 0x0E/frame. 16 hp in port. |
| 37 | lead_bullet | 7 | 1x1 or 2x2 | PAL2 | 15+trans | 1 | SAT 0x1C color 0x8F. Upward. Type 42 converts into this. |
| 38 | burst_fragment | 7 | 1x1 or 2x2 | PAL2 | 15+trans | 1 | SAT 0x1C. Umber-7 burst; box-4 drop. Type 43 converts into this. |
| 39 | col_marker_or_compl | 17/23/25 / parent+offset | — | — | — | follows parent | Type 39 is the complement/column-marker slot. On MD fold into parent sprite; no extra hardware sprite required. |
| 40 | instant_despawn | — | — | — | — | none | Handler = entity_clear. No art. |
| 41 | pair_fragment | 7 | 1x1 or 2x2 | PAL2 | 15+trans | 1 | SAT 0x1C. Spawned by type 8. |
| 42 | proto_bullet | 7 then type→37 | — | — | — | transient | No unique art. |
| 43 | proto_fragment | 7 then type→38 | — | — | — | transient | No unique art. |
| 44 | ground_structure | 16 + nametable tiles | 2x2 overlay + BG tiles | PAL2/PAL3 | 15+trans / 16 | 1 | Sprite plane + complement 17. Also stamps tiles (place_tile_group). Draw both a sprite and BG greeble. |
| 45 | light_bar_var | 6 | 2x1 or 2x2 | PAL2 | 15+trans | 1 | SAT 0x18 color 0x8F. |
| 46-55 | ground_gun | 18 | 2x2 | PAL2 | 15+trans | loga 2-frame set exists; handler uses 18 | SAT 0x48 = loga_A. 5 pair behaviours spawn type 38 or 21. Nametable-locked fallers. |
| 56 | sig_single | 28 | 2x2 | PAL1 | 15+trans | color flash XOR 0x09 | SAT 0x70. Falling pickup/missile. |
| 57 | paired_descender_A | 27 | 2x2 | PAL2 | 15+trans | 1 | SAT 0x6C. Sprite-names call pat 27 sig_double — same pixels, different role. |
| 58 | paired_descender_B | 26 | 2x2 | PAL2 | 15+trans | 1 | SAT 0x68. Sprite-names: sig_triple. |
| 59 | sideways | 28 | 2x2 | PAL2 | 15+trans | 1 | SAT 0x70 same as sig_single. Moves right. |
| 60 | player_death_fx | 7/8/9 | 2x2 or 3x3 | PAL1 | 15+trans | 11 CONFIRMED | Table 0x86F3 tick_rate=4. Invisible→lead→med→lg→med→lead. Slot 0. No motion. |
| 61 | large_descender | 62 | 4x4 | PAL2 | 15+trans | 1 + 8-color cycle | SAT 0xF8. Colors from 0x8EAF table (0x81/83/84/86/87/89/8A/8D). Sprite-names: sart. |
| 62 | invisible_riser | 0 | — | — | — | none | No sprite. Trigger/effect entity. |
| 63 | power_chip | 1 (likely) | 2x2 | PAL1 | 15+trans | 1 | Handler 0x78AF does not LD SAT name. Sprite-names + port objs frame 5 use pat 1. Pickup SFX event 0x17 = 23. |
| 64 | proto_structure | 16 then type→44 | — | — | — | transient | Cyan plane, becomes type 44. |
| 67 | med_circle | 8 | 2x2 | PAL2 | 15+trans | 1 | SAT 0x20 color 0x86. 5 hp in port. |
| 68 | proto_box | 53 then type→4 | — | — | — | transient | Spawns 3-box cluster via proto_box_type_table. |
| 69 | base_projectile | 7 | 1x1 or 2x2 | PAL2 | 15+trans | 1 | SAT 0x1E (pat 7, lower bits ignored). Initially transparent. From type 11. |
| 70-71 | idol_totem | nametable (SAT invisible) | BG ~3x2 tiles | PAL3 | 16 | - | Stream stamps face tiles (plain 0x13/14 vs smile 0x15/16). MSX SAT 0x24 color 0. Port: no sprite; destroy -> type 72 orb. |
| 72 | orb_core | 9 (anim 7/8/9) | 2x2 | PAL1 | 15+trans | 4+4 CONFIRMED | base_core_anim 0x8A16 phase1 (colors 0x8F/83/8A/8B) then 0x8A1E all 0x81 black. Yellow touch=kill-all, black=warp. |
| 73-79 | base_segment | nametable only (sat_col=0) | BG tiles | PAL3 | 16 | none | Nametable-locked; MSX sat_name for hitbox size only, +04 stays 0. HP from base_segment_table. Fire tables REAL. Hit/kill FX via scatter_expl. |
| 80 | base_damage | unknown | — | — | — | unknown | Handler calls base-encounter decrement. No SAT write documented. |
| 81/87-89 | wide_structure | 9 likely / nametable | BG tiles + optional 2x2 | PAL3 | 16 | unknown | Same handler group as 70/82. Type 82 is the fire-box (confirmed). Others are wide totems/structures. |
| 82 | fire_box | nametable 4x4 + digit | BG 4x4 tiles | PAL3 | 16 | 1 | Blue 4×4, digit = fire#. 4 hp → type 83. Not a warp totem. |
| 83 | fire_upgrade | 1 | 2x2 | PAL1 | 15+trans | 1 | SAT 0x04 color 0x81 black. Touch → fire_select(+0x1c). Same pattern as power chip, different color/role. |
| 84-86 | wide_variant | unknown (joins 0x87AB) | BG tiles | PAL3 | 16 | unknown | wide_struct_init then same as 70-group. Distinct pixels: unknown. |

### Fire weapons (type 3) — sprite detail

| fire_num | Manual name (KB) | MSX sprite | MD note |
| --- | --- | --- | --- |
| 0 | All-Range Cannon | pat **3** target, 16-color cycle | 2×2, PAL1; cycle hues inside the 16-color pal or use a 4-frame flash |
| 1 | Straight Crasher | color cycle; exact pat unknown | unknown pat — reuse pat 3 until dumped |
| 2 | Field Shutter | follows player (Y−8,X); exact pat unknown | shield/field — 2×2 or 4×2 overlay |
| 3 | Circular | pat **4** snowflake | 2×2, several orbs = several sprites |
| 4 | Vibrator | pat **4** snowflake | 2×2 |
| 5 | Rewinder | similar to Straight; exact pat unknown | unknown |
| 6 | Plasma Flash | **no persistent entity** | SFX + optional full-screen flash (plane, not sprite) |
| 7 | High Speed | +0x0C varies; exact pat unknown | unknown |

Shot power looks (not animation): levels 0–1 pat 10, 2–3 pat 11, 4–5 pat 12.

Confirmed animation tables (do draw these frame counts):

| Who | Frames | Table | Sequence |
| --- | --- | --- | --- |
| Types 26–29 spinner | **4** | 0x7E68 / 0x7E70 | pats 43,44,45,46 |
| Type 35 projectile | **6** (frame 0 skipped) | 0x84D1 tick=4 | lead→med→lg→med→lead |
| Type 60 death | **11** | 0x86F3 tick=4 | empty→lead→med→lg→med→lead |
| Type 72 orb | **4 + 4** | 0x8A16 / 0x8A1E | lead/med/lg pulse, then black |

Pattern-table frame *sets* that exist but are **not** confirmed as runtime cycles:
loga 2, luster 2, veybar 5, umber 2. Draw the extra frames if you want; the
current handlers may only show frame 0.

---

## C. Background — charset, columns, title, HUD, credits

MSX has **one** 256-tile charset for letters, HUD, starfield and greeble.
Late stages and the title **overwrite** slices of that 256. On MD you can
(and should) keep those as separate tilesets.

Safe Zanac MD BG budget: **512 tiles / 2 palettes** first pass, **1024 / 3** if
the title + late-stage sets are resident together. Leave ~300 tiles for sprites
and 96 for the SGDK font (or replace the font and reclaim them).

| Asset | MSX count | MD you MAY use | Tile budget | Pal | Notes |
| --- | --- | --- | --- | --- | --- |
| charset | 256 tiles × 8 bytes = 2048 B bitmap + 256 × 8 color | 256 MD 4bpp tiles (charset_tiles.bin = 8192 B = 256×32) | 512-768 | PAL3 (2nd pal allowed) | Alphabet, digits, HUD labels, main terrain. Loaded into all 3 SCREEN2 banks identically. Port: VDP_loadTileData 256 tiles at TILE_USER_INDEX+32. |
| logo | 61 tiles (indices 176-236). 5 nametable rows, stride 25, up to 18 names/row. Color block decompresses to 29 entries. | Replace with a title tileset or a sprite logo | 64-128 | PAL0 or PAL3 | Overwrites charset tiles 176-236 on MSX title. MD can keep logo in its own VRAM range. Title currently SGDK font only. |
| late_bg_a | 20 tiles into indices 23-42 | Dedicated late-stage tileset, do not overwrite font | 32-64 | PAL3 | MSX overwrites charset slots 23-42 for last stages. |
| late_bg_b | 67 tiles into indices 90-156 | Dedicated late-stage tileset | 64-128 | PAL3 | MSX overwrites charset slots 90-156. Color block B decompresses to 69 tiles. |
| tile_tables | 22 columns × 24 rows of charset IDs (4+8+8+1+1) | Reuse new BG tiles; columns still 24 tiles tall (plus 4 extra rows on 224px) | included in charset budget | PAL3 | Primary 4 entries (stage&3), variant A/B 8 each (stage&7), two fixed columns. Fill IDs cluster 0x28/0x29 and 0x17-0x19 / 0x24-0x27. |
| column_greeble | variable-length columns of charset IDs, max 24 tiles | Same IDs into the new tileset, or a 2nd tileset if you exceed 256 | 256-512 extra if split | PAL3 (or PAL0 for a 2nd pal) | Cmd 2/4/5/B streams. place_tile_group stamps idols/fire-boxes onto the nametable. |
| hud_font | No separate HUD glyph table. Labels: ALC TOP SCORE ZANAC LEVEL ROUND FIRE. PAUSE 5 bytes @0x4E40. | SGDK FONT_LEN=96 now; MAY replace with a 1bpp/4bpp HUD font (~64-96 tiles) | 96 | PAL0 | MSX HUD is in the nametable (right-panel border 14 rows from VRAM 0x3958). H40 has 8 extra tile-columns (64px) for a side HUD. |
| credits | Length-prefixed ASCII: GAME DESIGN, PROGRAM, GRAPHICS, SOUND, DIRECTOR, JANUS, JEMINI, COMPILE, WAO, MOO, MIYAMOTO, YORIKI, THANKS, PAL, MUSIC, LUNARIAN | Same font as HUD or a credits tileset | 0 extra if font reused | PAL0 | Centered pages, fire-to-cycle, ESC-to-title. Continues over scrolling BG. |
| title_text | GAME DESIGNED BY COMPILE / PRODUCED BY AII / PRESENTED BY PONY INC. / COPYRIGHT 1986 PONY INC. + A.I. row | Font or title tiles | 0-32 | PAL0 | Currently replaced by the Original / Zanac MD menu (SGDK font). |

### Charset overwrite map (MSX) — so you do not pack overlapping MD tiles

| Tiles | Content | When |
| --- | --- | --- |
| 0–255 | Full charset (font + terrain) | always, all 3 SCREEN2 banks |
| 23–42 | Late-stage BG A (20 tiles) | last stages, `load_bg_tiles` |
| 90–156 | Late-stage BG B (67 tiles) | last stages |
| 176–236 | Logo (61 tiles) | title, `load_logo_tiles` |

HUD labels (charset letters, not a separate atlas): **ALC, TOP, SCORE, ZANAC,
LEVEL, ROUND, FIRE**. Digits = tile `0x30 + n`. `PAUSE` is 5 ASCII bytes at
0x4E40. Score is 7-digit BCD (3 bytes). Lives / round / fire-num / shot-level
are 1–2 digits.

H40 leftover width: 320−256 = **64 px = 8 tiles**. That is exactly enough for
the MSX right-side HUD column if you keep a 256 px playfield; `mode.c` currently
sets Zanac MD `playfield_w = 320`, so a bottom bar also works.

---

## D. Sound events 1–27

Original mode plays these through the PSG interpreter (`src/sound.c`,
`SOUND_EVENT_MAX 27`). Zanac MD can replace each with XGM (looping BGM) or
one-shot PCM/WAV. Map by **event number**, not by guessed song titles.

Port currently wires: ev3 title, ev7/ev2 round-start, ev13 shot, ev18 explode,
ev4 game-over.

| Ev | Name | MSX kind | When it fires | MD replacement |
| --- | --- | --- | --- | --- |
| 1 | main_stage_theme | BGM | After ev7 chain (0x87 01). Longest, 3 voices ch 0/2/1. | XGM loop (or XGM2) |
| 2 | round_mod8_theme | BGM | Round start when round≡0 mod 8 (0x4065 else-path). 2 voices. | XGM loop |
| 3 | title_music | BGM | Title intro (0x5A16, live-confirmed). 3 voices. Port: sound_play_title(). | XGM loop |
| 4 | game_over | BGM | Game-over / attract (0x467B). 3 voices. Port: sound_play_gameover(). | XGM one-shot (no loop) or short XGM |
| 5 | jingle_from_ev12 | jingle | Chained from event 12 (0x87 05 @0x5804). 2 voices. | XGM one-shot |
| 6 | weapon_fire_sfx | SFX | Weapon/fire (0x7260). 1 voice ch 1. | one-shot PCM (XGM PCM ch) or PSG |
| 7 | stage_intro | BGM | Round-start when round&7≠0 (0x4065). 3 voices. Chains → ev1. Port: sound_play_round(). | XGM intro then loop ev1 (or one XGM with intro) |
| 8 | state_jingle_a | jingle | E102 bit2 clear (0x4A61); also enemy (0x8763). 2 voices. | XGM one-shot |
| 9 | state_jingle_b | jingle | E102 bit2 clear (0x4A20). 2 voices. | XGM one-shot |
| 10 | round_variant_bgm | BGM | Round-variant BGM (0x4133 init). 3 voices. | XGM loop |
| 11 | init_jingle | jingle | Init jingle (0x40EA). 3 voices, 2 share stream 0x57B5 (chorus). | XGM one-shot |
| 12 | round_boss_jingle | jingle | Round/boss (0x924B). 3 voices. Chains → ev5. | XGM one-shot then ev5 |
| 13 | shot_sfx_lv0 | SFX | Shot fire. 0x7234 plays event=3+(E10F>>2). Levels 0-1 E10F=0x28 → ev13. Live-confirmed. 1 voice ch 2. | one-shot PCM |
| 14 | shot_sfx_lv2 | SFX | Same formula: E10F=0x2C (shot levels 2-3) → ev14. Catalogue lists 'SFX ch C' with no extra call site. | one-shot PCM (higher pitch/layer) |
| 15 | shot_sfx_lv4 | SFX | Same formula: E10F=0x30 (shot levels 4-5) → ev15. Catalogue lists 'SFX ch C' with no extra call site. | one-shot PCM |
| 16 | sfx_enemy_16 | SFX | ch C noise — enemy (0x86C0). 1 voice. Exact gameplay beat beyond 'enemy': unknown. | one-shot PCM (noise) |
| 17 | sfx_enemy_hit | SFX | ch C noise — enemy hit (0x8495, 0x8B87). | one-shot PCM |
| 18 | explosion | SFX | ch C noise — explosion (base damage/death 0x8879, 0x8E1F). Port: sound_play_explode(). | one-shot PCM |
| 19 | sfx_fire_or_enemy | SFX | ch C — fire (0x7516) / enemy (0x89FF). | one-shot PCM |
| 20 | sfx_player_or_base | SFX | ch C — player (0x7911) / base (0x8438). | one-shot PCM |
| 21 | sfx_enemy_hit_21 | SFX | ch C — enemy hit (0x8025, 0x8209). | one-shot PCM |
| 22 | sfx_noise_22 | SFX | ch C noise. Call site not listed in the 0057 catalogue. Purpose: unknown. | one-shot PCM (noise) or keep PSG |
| 23 | sfx_pickup | SFX | ch C — player (0x78C1). Power-chip handler 0x78BF is LD A,0x17 / CALL play_sound_event — 0x17=23. | one-shot PCM |
| 24 | sfx_weapon_expire | SFX | ch B — weapon (0x74C1, 0x74E2). Those addresses are fire 2 / fire 4 expire handlers. | one-shot PCM or PSG |
| 25 | round_fanfare | jingle | Round fanfare, conditional (0x9044). 3 voices. | XGM one-shot |
| 26 | round_clear_a | jingle | Round-clear fanfare C=0x1A (0x917A). 3 voices. | XGM one-shot |
| 27 | round_clear_b | jingle | Round-clear variant C=0x1B (0x917A). 3 voices. | XGM one-shot |

Chains (confirmed): **ev7 → ev1**, **ev12 → ev5**. Round-start is ev7 except
when `round & 7 == 0` then ev2. Shot event is computed `3 + (E10F >> 2)` so
power-ups walk ev13 → ev14 → ev15.

SGDK note: loading XGM/XGM2 **replaces** the Z80 driver. The current
`Z80_DRIVER_NULL` + 68k PSG tick cannot coexist with XGM. Keep Original on the
interpreter; switch driver only in Zanac MD (or gate `sound_tick`).

---

## E. Folder convention

Drop new files here so a later change can point `ModeAssets` at them without
touching Original.

```
res/
  sprites/           Original (do not overwrite)
    ship.png         16x16 pat 14
    objs.png         208x16 13 frames
  charset_tiles.bin  Original 256 tiles
  sound_blob.bin     Original 27 events
  md/                Zanac MD pack (create)
    sprites/         PNG, SGDK SPRITE w/h in tiles
    bg/              tilesets / maps
    vgm/             XGM / XGM2 / VGM / WAV
```

| Path | What to put | resources.res line | Rules |
| --- | --- | --- | --- |
| res/md/sprites/ | PNG (indexed or 4bpp-friendly), one file per visual or a strip | SPRITE name "md/sprites/foo.png" W H NONE 0 | W,H are tiles 1-4. Color 0 = transparent. 16 colors from one CRAM pal. Frame strips are horizontal (see current objs.png 208x16 = 13×16px). |
| res/md/sprites/ship.png | Player ship (replace 16x16 MSX) | SPRITE spr_md_ship ... 2 2 (or 3 3 / 4 4) | Point ModeAssets.ship here in Zanac MD. Original keeps res/sprites/ship.png. |
| res/md/sprites/enemies.png or per-enemy | Folded complement, anim frames as strip | SPRITE spr_md_* W H | Suggested groups: player, shots, fire, items, duster, teruzo, luster, veybar, spinner, stealth, box, umber, degid, sart, projectiles. |
| res/md/bg/ | 8x8 4bpp tilesets + optional maps | TILESET / MAP in resources.res | Keep Original charset_tiles.bin. Zanac MD can load a 512-1024 tile set split across 2 palettes. |
| res/md/bg/terrain.png | Main scrolling greeble / starfield | TILESET md_terrain | Covers charset + tile_tables + column streams. 2nd palette OK. |
| res/md/bg/logo.png | Title logo (was 61 MSX tiles) | TILESET or SPRITE | Do not overwrite HUD font. Title currently has no logo art. |
| res/md/bg/hud.png | Optional HUD panel / digits | TILESET md_hud | H40 extra 64px is a natural right-side HUD like MSX ALC/TOP/SCORE/LEVEL/ROUND/FIRE. |
| res/md/bg/credits.png | Optional credits decorations | TILESET or font | Strings can stay as text; this is ornament. |
| res/md/vgm/ | XGM / XGM2 / VGM / WAV | XGM / WAV in resources.res | SGDK 2.11: XGM = 4 PCM @14 kHz; XGM2 = 3 PCM @13.3/6.65 kHz; WAV = PCM sample. Original mode keeps sound_blob.bin + PSG interpreter. Zanac MD: Z80_loadDriver(XGM or XGM2) and map events 1-27 to tracks/SFX ids. |
| res/md/vgm/bgm_*.xgm | Looping stage / title / game-over | XGM bgm_title, bgm_stage, ... | Events 1,2,3,4,7,10. Ev7 may be the intro of the ev1 file. |
| res/md/vgm/sfx_*.wav | One-shot PCM | WAV sfx_shot, sfx_explode, ... | Events 6,13-24. Keep filenames = event id so ModeAssets can be a table of pointers. |

### Suggested `resources.res` additions (when files exist)

```
SPRITE spr_md_ship "md/sprites/ship.png" 3 3 NONE 0
SPRITE spr_md_objs "md/sprites/objs.png" 2 2 NONE 0
TILESET bg_md_terrain "md/bg/terrain.png"
XGM bgm_md_title "md/vgm/ev03_title_music.xgm"
WAV sfx_md_shot "md/vgm/ev13_shot.wav"
WAV sfx_md_explode "md/vgm/ev18_explosion.wav"
```

`ModeAssets` today (`inc/mode.h`):

```
const SpriteDefinition *ship;
u16 screen_width, playfield_w, playfield_h;
const char *name;
```

Add later (do not invent the C yet unless you are wiring it): `objs`, `palette`,
`tileset`, `bgm[]`, `sfx[]`. `mode_init()` already has a separate `s_md` struct
— that is the swap point.

PNG / SPRITE rules (rescomp):

- Width = frames × (w_tiles×8), height = h_tiles×8. Current objs strip is
  horizontal.
- Indexed PNG, ≤16 colors, index 0 transparent.
- One CRAM palette per SPRITE (the `palette->data` loaded like PAL2 for the ship).
- Animation frames = columns of the strip; `SPR_setAnimAndFrame(spr, 0, frame)`.

---

## Gaps (unknown — not invented)

- **Type 63** SAT pattern is not written in `handler_type63`; likely pat 1
  (sprite-names + port extract) but unconfirmed in the handler.
- **Pats 2 (comet) and 5 (small star):** named, no entity type in the mapping.
  Port extracts comet as objs frame 12; nothing uses it in `entity.c` spawn
  beyond the #define.
- **Pats 60 and 61** (degid right / complete): named; no handler SAT write found.
- **Fire 1 / 2 / 5 / 7** exact pattern indices: unknown (KB describes behaviour,
  not a SAT LD).
- **Types 80, 84–86** distinct pixels: unknown.
- **Types 70–71, 73–79, 81, 87–89:** primarily nametable; overlay sprite pats
  not fully documented (70-group shares handler with 82; 82 is the fire-box).
- **Veybar / loga / luster / umber** extra pattern-table frames: runtime cycle
  unknown (handlers pin one SAT).
- **Events 16, 19, 20, 21, 22:** SFX with call-site addresses but no designer
  name. Ev14/15 are explained by the shot formula; ev22 has **no** catalogue
  call site.
- **Player complement pat 15:** extract script marks unused.
- Title screen in the port is a text menu — MSX logo swirl / credit lines are
  not drawn yet (61 logo tiles still need an MD replacement if you want them).

---

## Palette cheat-sheet (Zanac MD target)

| Pal | Use | Colors |
| --- | --- | --- |
| PAL0 | SGDK font + HUD text (keep index 15 light) | 16, mostly greys + 1 accent |
| PAL1 | Player shots, fire weapons, chips, box, sig, orb, death FX | 16 |
| PAL2 | Ship + all enemies (or split ship into PAL1 if enemy pal is tight) | 16 — ship currently uses PAL2 |
| PAL3 | Scrolling BG / greeble / logo | 16; a 2nd BG pal means stealing PAL0 or PAL1 on title-only screens |

Sprite palettes cannot mix: one sprite = one pal. If an enemy needs ship colors,
either share PAL2 or accept a remap.

MSX sprite colors you will be replacing (SAT low nibble, EC usually set):
0x8F white, 0x83 cyan, 0x89 light-blue, 0x8B light-red, 0x8E light-green,
0x8A dark-yellow, 0x88 medium-red, 0x87 cyan-ish dark green, 0x86 dark red,
0x84 dark blue, 0x81 black/complement. These are TMS indices, not MD CRAM.
