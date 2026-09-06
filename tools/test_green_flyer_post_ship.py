#!/usr/bin/env python3
"""Green flyer (veybar 22/23 sat_col 0x83) must collide and kill.

collide_player skips dead/over, hidden box, type67 idle 83ee, and
KIND_GROUND (44CA) only. Veybar/umber/duster/teruzo stay 44BA POST_SHIP.
Do not close !(KIND_EBULLET) early.

Usage (from zanac-md):
    python tools/test_green_flyer_post_ship.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENT = ROOT / "src" / "entity.c"


def fail(msg: str) -> int:
    print("FAIL:", msg)
    return 1


def main() -> int:
    ent = ENT.read_text(encoding="utf-8")

    col = re.search(r"static void collide_player\(void\)\s*\{(.*?)^\}", ent, re.S | re.M)
    if not col:
        return fail("collide_player not found")
    body = col.group(1)
    if "player_dead() || player_is_over()" not in body:
        return fail("collide_player must skip dead/over")
    if "KIND_GROUND" not in body:
        return fail("ship AABB must still skip KIND_GROUND (44CA)")
    if "KIND_VEYBAR" in body:
        return fail("collide_player must not skip KIND_VEYBAR")
    if "KIND_UMBER" in body:
        return fail("collide_player must not skip KIND_UMBER")
    if "KIND_DUSTER" in body or "KIND_TERUZO" in body:
        return fail("collide_player must not skip duster/teruzo")

    if "e->sat_col = fast ? 0x89 : 0x83" not in ent:
        return fail("veybar 22/23 stay sat_col 0x83 (TMS 3 green)")
    if "return (u8)(POST_SHOT | POST_SHIP);" not in ent:
        return fail("default post_flags must stay 44BA (shot+ship)")

    # ebullet grouping must not close !(KIND_EBULLET) early
    if "KIND_TRACKER" not in ent or "KIND_VEYBAR" not in ent:
        return fail("keep ebullet grouping kinds")

    print("ok: veybar 0x83 POST_SHIP; collide_player does not skip flyers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
