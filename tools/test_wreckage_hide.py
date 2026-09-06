#!/usr/bin/env python3
"""Destroyed ground / gun sprites hide immediately; 88ed punches stay.

Flyer type-35 leftover SAT/velocity is leave-alone (item 1). Ground, gun,
wide, firebox, base hide the original body so it cannot scroll with the map.

Usage (from zanac-md):
    python tools/test_wreckage_hide.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENT = ROOT / "src" / "entity.c"
MAP = ROOT / "src" / "map_script.c"


def fail(msg: str) -> int:
    print("FAIL:", msg)
    return 1


def main() -> int:
    ent = ENT.read_text(encoding="utf-8")
    mp = MAP.read_text(encoding="utf-8")

    if "KIND_GROUND || e->kind == KIND_GUN" not in ent:
        return fail("become_expl must hide ground/gun leftover body")
    if "if (hide && e->spr)" not in ent:
        return fail("become_expl must SPR_setVisibility HIDDEN for ground leftovers")
    if "e->vx = 0" not in ent:
        return fail("become_expl still zeros vel (do not invent flyer leftover vel)")
    if "Flyers keep leftover SAT until 8446" not in ent:
        return fail("flyer leftover SAT comment must stay (item 1)")
    if "if (e->spr)" not in ent or "become_husk" not in ent:
        return fail("become_husk must hide leftover body")
    if "map_script_punch_88ab" not in ent:
        return fail("84-86 still punch 88ab wreckage")
    if "k_88ab_84" not in mp:
        return fail("88ed wreckage tables stay")

    print("ok: ground leftover hidden; 88ed punches stay; flyer vel leave-alone")
    return 0


if __name__ == "__main__":
    sys.exit(main())
