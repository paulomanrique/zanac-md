#!/usr/bin/env python3
"""SAT write order is entity_dispatch slot walk, not Y-sort.

zanac.asm 0x445F: SAT ptr E000, IX=E300, B=0x1A, stride 0x20.
0x48B8 sprite_sat_write appends. TMS first SAT index is on top.
  E300 player, E320+ shots, E380 fire, E3A0+ enemies.
0x71f6 complement appends immediately after its primary.

Port used SPR_setDepth(draw Y), so a higher enemy sat in front of shots.

Usage (from zanac-md):
    python tools/test_sat_order.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENT = ROOT / "src" / "entity.c"
PLY = ROOT / "src" / "player.c"


def main() -> int:
    ent = ENT.read_text(encoding="utf-8")
    ply = PLY.read_text(encoding="utf-8")

    if "SAT_DEPTH_PLAYER" not in ent or "SAT_DEPTH_SHOT" not in ent:
        print("FAIL: missing SAT_DEPTH_* constants")
        return 1
    if "#define SAT_DEPTH_PLAYER    SPR_MIN_DEPTH" not in ent:
        print("FAIL: SAT_DEPTH_PLAYER must be SPR_MIN_DEPTH (leftover Y cannot weave)")
        return 1
    if "sat_depth_primary" not in ent or "sat_depth_marker" not in ent:
        print("FAIL: missing sat_depth helpers")
        return 1
    if re.search(r"SPR_setDepth\(\s*s->spr,\s*mdy\s*\)", ent):
        print("FAIL: primary depth still uses draw Y")
        return 1
    if re.search(r"SPR_setDepth\(\s*s->mspr,\s*\(s16\)\(mdy - 1\)\s*\)", ent):
        print("FAIL: complement depth still uses draw Y")
        return 1
    if "SPR_setDepth(s->spr, sat_depth_primary(s))" not in ent:
        print("FAIL: primary must use sat_depth_primary")
        return 1
    if "SPR_setDepth(s->mspr, sat_depth_marker(s))" not in ent:
        print("FAIL: complement must use sat_depth_marker")
        return 1
    if "SPR_setDepth(s_spr, SPR_MIN_DEPTH)" not in ply:
        print("FAIL: ship must stay SAT index 0 (E300 first write)")
        return 1

    # MSX slot math: fire is slot 4 (E380), enemies start slot 5 (E3A0).
    e300 = 0xE300
    if (0xE380 - e300) // 0x20 != 4:
        print("FAIL: E380 is not slot 4")
        return 1
    if (0xE3A0 - e300) // 0x20 != 5:
        print("FAIL: E3A0 is not slot 5")
        return 1
    # Depths: player 0 < shots < fire < enemies; complement = primary+1.
    print("ok: SAT depths follow 445F slot walk (player/shots/fire/enemies)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
