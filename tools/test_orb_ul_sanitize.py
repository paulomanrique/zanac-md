#!/usr/bin/env python3
"""Type 72 orb upload must drop leftover PAL2 blues in empty UL tiles.

zanac-re gfx pats 7/8 UL 4x4 = 0 bits; pat 9 UL 4x4 is the lg disc.
k_orb_frame stays lead/med/lg/med. k_orb_mid_pal=7 stays. SAT 1C/20/24.
Do not invent a disc. Sanitizer keeps 0 and the SAT nibble only.

Usage (from zanac-md):
    python tools/test_orb_ul_sanitize.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENT = ROOT / "src" / "entity.c"
REBUILD = ROOT / "tools" / "rebuild_sprites.py"


def fail(msg: str) -> int:
    print("FAIL:", msg)
    return 1


def main() -> int:
    ent = ENT.read_text(encoding="utf-8")
    reb = REBUILD.read_text(encoding="utf-8")

    if "FRAME_LEAD, FRAME_MED_CIRCLE, FRAME_CIRCLE, FRAME_MED_CIRCLE" not in ent:
        return fail("k_orb_frame must stay lead / med / lg / med")
    if "static const u8 k_orb_mid_pal = 7" not in ent:
        return fail("k_orb_mid_pal must stay 7")
    if "0x1C, 0x20, 0x24, 0x20" not in ent:
        return fail("k_orb_sat must stay 1C/20/24/20")
    if "orb_keep_body_nibbles" not in ent:
        return fail("orb upload must sanitize leftover PAL2 nibbles")
    if "s->kind == KIND_ORB" not in ent:
        return fail("sanitize must run on type 72 uploads")
    if "u16 out = 128" not in ent:
        return fail("orb upload must zero-pad to 4 tiles (leftover UL VRAM)")
    if "if (hi && hi != keep)" not in ent:
        return fail("sanitizer must drop any nibble that is not 0 or SAT color")
    if "PAL_setColor((u16)((PAL2 * 16) + 2), k_flyer_green_dim[0])" not in ent:
        return fail("PAL2[2] half-green must stay")
    if "PAL_setColor((u16)((PAL2 * 16) + 3), k_flyer_green_dim[1])" not in ent:
        return fail("PAL2[3] half-green must stay")
    if "if fi in (6, 52):" not in reb:
        return fail("rebuild must force-zero LEAD/MED UL 4x4 (pat 7/8 empty)")

    print("ok: orb sanitize drops non-body nibbles; 4-tile pad; mid pal 7")
    return 0


if __name__ == "__main__":
    sys.exit(main())
