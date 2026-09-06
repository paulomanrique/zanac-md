#!/usr/bin/env python3
"""88ed wreckage must persist into E800 so wrap DMA cannot restore live tiles.

PR #85 SPR_setVisibility(HIDDEN) left the nametable cells. Japan v1 8948
writes E800[(E714+Y/8) mod 24]. A wrap-row punch that skipped e800 left
HALF the original stream tiles scrolling with the map.

Type 70/71 8833 has no dest; stream face 0x13-0x16 is cleared to 0x28.
Flyer type-35 leftover SAT/velocity is leave-alone (item 1).

Usage (from zanac-md):
    python tools/test_wreckage_hide.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENT = ROOT / "src" / "entity.c"
MAP = ROOT / "src" / "map_script.c"
HDR = ROOT / "inc" / "map_script.h"


def fail(msg: str) -> int:
    print("FAIL:", msg)
    return 1


def main() -> int:
    ent = ENT.read_text(encoding="utf-8")
    mp = MAP.read_text(encoding="utf-8")
    hdr = HDR.read_text(encoding="utf-8")

    if "punch_cell" not in mp:
        return fail("88ed must punch_cell (e800 first, then displayed NT)")
    if "s_e800[(u8)((s_e714 + screen_row) % BOOT_ROWS)][col] = tid" not in mp:
        return fail("8948 E800[(E714+Y/8) mod 24] must be written for every dest cell")
    if "hidden_wrap_nt_at(s_scroll_px)" not in mp or "s_e800[s_e714][col] = tid" not in mp:
        return fail("nt_put must persist wrap/letterbox NT into e800[e714]")
    if "map_script_clear_totem_face" not in hdr or "map_script_clear_totem_face" not in ent:
        return fail("type 70/71 must clear stream face 0x13-0x16 (8833 has no 88ed)")
    if "tid >= 0x13 && tid <= 0x16" not in mp:
        return fail("totem clear must only replace face tiles 0x13-0x16")
    if "punch_cell(col, srow, 0x28)" not in mp:
        return fail("cleared face cells must become 0x28 (empty playfield)")
    if "k_88ab_84" not in mp:
        return fail("88ed wreckage tables stay")
    if "map_script_punch_88ab" not in ent:
        return fail("84-86 still punch 88ab wreckage")
    if "e->vx = 0" not in ent:
        return fail("become_expl still zeros vel (do not invent flyer leftover vel)")
    if "Flyers keep leftover SAT until 8446" not in ent:
        return fail("flyer leftover SAT comment must stay (item 1)")

    print("ok: 88ed persists e800; wrap NT updated; totem face 0x13-16 -> 0x28")
    return 0


if __name__ == "__main__":
    sys.exit(main())
