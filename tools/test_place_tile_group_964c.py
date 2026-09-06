#!/usr/bin/env python3
"""Ground-base SAT X is 0x964C. Do not invent stacking offsets.

place_tile_group / place_ctrl_at:
  SAT X = (u8)(ybase*8 + blob_X - 0x20)   /* Japan 964C 8-bit wrap */
proto_box 77a1: X=(H&0x3F)+0x38, +0x20 per child, Y leftover 0.
k_base xo/yo apply at arm (8ac7), not at place.

0xBCB2 (ctrl 0x8B, ybase 8) and 0xBBF3 (3x type 79) place at distinct
SAT X/Y in the ROM. No proven port stack on one tile -- leftover.

Usage (from zanac-md):
    python tools/test_place_tile_group_964c.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPC = ROOT / "src" / "map_script.c"
ENT = ROOT / "src" / "entity.c"


def fail(msg: str) -> int:
    print("FAIL:", msg)
    return 1


def main() -> int:
    map_c = MAPC.read_text(encoding="utf-8")
    ent = ENT.read_text(encoding="utf-8")

    if "sat_x_964c(st->ybase, r[2])" not in map_c:
        return fail("place_tile_group SAT X must be sat_x_964c (8-bit 964C)")
    if "sat_x_964c(st.ybase, r[2])" not in map_c:
        return fail("place_ctrl_at SAT X must be sat_x_964c (8-bit 964C)")
    if "(s16)st->ybase * 8 + (s16)r[2] - 0x20" in map_c:
        return fail("16-bit 964C rejects the R1 left eye (SAT 368→248)")

    proto = re.search(r"static void spawn_proto_box\(void\)\s*\{(.*?)^\}", ent, re.S | re.M)
    if not proto:
        return fail("spawn_proto_box not found")
    body = proto.group(1)
    if "x + 0x20" not in body:
        return fail("proto_box children must stay +0x20 apart (77a1)")
    if re.search(r"y\s*\+=\s*|e->y\s*=\s*\(.*\+\s*0x", body):
        return fail("proto_box Y must stay leftover 0; do not invent a stack")

    if "e->y = (s16)(u8)((u8)e->y + k_base[idx][2])" not in ent:
        return fail("k_base yo applies at arm (8ac7), not at place")
    if "e->x = (s16)(u8)((u8)e->x + k_base[idx][3])" not in ent:
        return fail("k_base xo applies at arm (8ac7), not at place")

    print("ok: 964C SAT X; proto_box +0x20; k_base xo/yo at arm (no invented stack)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
