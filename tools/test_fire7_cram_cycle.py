#!/usr/bin/env python3
"""Fire 7 72de colour cycle is CRAM, not per-frame tile remap.

MSX writes one SAT colour byte. MD tile remap every frame + wrap/peek NT
DMA produced a full-width blue tear. Bind comet to PAL2[13] once; cycle
that index. Keep dma_nt_row HUD cols 24-31 restore. No playfield letter
fill. No opaque-recolor 0x20.

Usage (from zanac-md):
    python tools/test_fire7_cram_cycle.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENT = ROOT / "src" / "entity.c"
MAP = ROOT / "src" / "map_script.c"
MAIN = ROOT / "src" / "main.c"


def fail(msg: str) -> int:
    print("FAIL:", msg)
    return 1


def main() -> int:
    ent = ENT.read_text(encoding="utf-8")
    mp = MAP.read_text(encoding="utf-8")
    main_c = MAIN.read_text(encoding="utf-8")

    if "FIRE7_CRAM_NIB" not in ent:
        return fail("fire 7 must bind a dedicated PAL2 nibble")
    if "FIRE7_CRAM_NIB  13" not in ent and "FIRE7_CRAM_NIB 13" not in ent:
        return fail("fire 7 CRAM nibble must stay 13 (not half-green 2/3)")
    if "fire7_cycle_cram" not in ent:
        return fail("72de INC for fire 7 must be CRAM, not spr_set_sat_col")
    if "fire7_bind_cram" not in ent:
        return fail("spawn fire 7 must upload comet to the CRAM nibble once")
    if "fire7_cycle_cram(f)" not in ent:
        return fail("update_fire cycle path must CRAM-cycle fire 7")
    if "VDP_setTileMapDataRow(BG_B, dst + MODE_BAR_COL" not in mp:
        return fail("dma_nt_row must restore HUD cols 24-31")
    if "mode_draw_letterbox" in mp.split("static void dma_nt_row")[1][:800]:
        return fail("dma_nt_row must not playfield-wide letter fill")
    if "0x20" in ent and "opaque" in ent.lower() and "recolor 0x20" in ent:
        return fail("do not opaque-recolor charset 0x20")
    if "DMA_setAutoFlush(FALSE)" not in main_c:
        return fail("60Hz: autoflush stays off")

    print("ok: fire 7 CRAM cycle; HUD restore; no letter fill")
    return 0


if __name__ == "__main__":
    sys.exit(main())
