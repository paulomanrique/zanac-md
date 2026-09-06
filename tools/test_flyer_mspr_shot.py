#!/usr/bin/env python3
"""Flyer dual-SAT is body + FRAME_*_C, never leftover SHOT/CHIP mspr.

Japan v1 spawn_col_marker 0x71f6 writes complement SAT after the primary.
SGDK addSprite defaults to objs frame 0 (SHOT). A reused slot whose
type39 mspr stayed at that frame drew the flyer interlaced with a shot.

Representative pairs (SAT name = pat<<2):
  veybar 0x84/0x98  swoop 0xAC/0xBC  stealth 0xCC/0xD0
  umber  0xDC/0xE4  plane 0x40/0x44

Usage (from zanac-md):
    python tools/test_flyer_mspr_shot.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENT = ROOT / "src" / "entity.c"


def fail(msg: str) -> int:
    print("FAIL:", msg)
    return 1


def main() -> int:
    ent = ENT.read_text(encoding="utf-8")

    pairs = (
        ("FRAME_VEYBAR_0", "FRAME_VEYBAR_C0"),
        ("FRAME_SPINNER_0", "FRAME_SPINNER_C0"),
        ("FRAME_STEALTH", "FRAME_STEALTH_C"),
        ("FRAME_UMBER", "FRAME_UMBER_C"),
        ("FRAME_PLANE", "FRAME_PLANE_C"),
    )
    for body, compl in pairs:
        if "marker_place(e, %s)" % compl not in ent and \
           "marker_place(e, (u16)(%s" % compl not in ent:
            return fail("%s complement must stay %s" % (body, compl))

    if "0x84" not in ent or "0x98" not in ent:
        return fail("veybar SAT 0x84 / marker 0x98")
    if "0xCC" not in ent or "0xD0" not in ent:
        return fail("stealth SAT 0xCC / marker 0xD0")
    if "0x40" not in ent or "0x44" not in ent:
        return fail("plane SAT 0x40 / marker 0x44")

    if "marker_kill(&s_en[i])" not in ent:
        return fail("free_enemy must drop leftover type39 before reuse")
    if "complement_frame_ok(s->mframe)" not in ent:
        return fail("spr_place must kill SHOT/CHIP leftover mspr")
    if "mspr_frame_cb" not in ent:
        return fail("mspr must disable AUTO_TILE_UPLOAD (frame 0 is SHOT)")
    if "u16 out = 128" in ent:
        return fail("do not re-ship 4-tile pad as the interlacing fix")

    print("ok: flyer complements are SAT-name pairs; leftover SHOT mspr killed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
