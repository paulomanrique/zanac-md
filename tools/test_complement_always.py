#!/usr/bin/env python3
"""71f6 always writes the complement SAT. Do not drop EC sprites.

TMS spawn_col_marker 0x71f6 writes Y=parentY-0x11, color 0x81 after the
primary. Port hid mspr when a line-budget (>=10 primaries on a 16px band)
or the primary (not the complement) overlapped the HUD. EC complement
sits 32px left and can still be on the playfield -- that left colored
halves.

Clip only the complement's own draw box via spr_vis_playfield.
marker_place may still withhold at hw_sprite_count() >= 70.

Usage (from zanac-md):
    python tools/test_complement_always.py
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

    if "line_budget_full" in ent or "band_overlap" in ent:
        return fail("do not drop complements on an invented MD line-budget")

    sync = re.search(r"static void spr_sync\(Slot \*s\)\s*\{(.*?)^\}", ent, re.S | re.M)
    if not sync:
        return fail("spr_sync not found")
    body = sync.group(1)
    if "spr_vis_playfield(s->mspr, mdx, mdy, 1)" not in body:
        return fail("spr_sync must clip the complement's own box only")
    if re.search(r"spr_vis_playfield\(\s*s->mspr,\s*dx,\s*dy", body):
        return fail("complement vis must not use the primary draw box")

    place = re.search(r"static void marker_place\(Slot \*s, u16 frame\)\s*\{(.*?)^\}",
                      ent, re.S | re.M)
    if not place:
        return fail("marker_place not found")
    pbody = place.group(1)
    if "line_budget" in pbody:
        return fail("marker_place must not refuse on a line-budget")
    if "hw_sprite_count() >= 70" not in pbody:
        return fail("marker_place may still withhold at 70 hardware sprites")

    print("ok: complement SAT stays; clip is own box; no line-budget drop")
    return 0


if __name__ == "__main__":
    sys.exit(main())
