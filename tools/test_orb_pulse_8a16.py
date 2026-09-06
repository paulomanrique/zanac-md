#!/usr/bin/env python3
"""Totem white bomb (type 72) is 8a16 cyan/yellow pulse, four SAT names.

1C/20/24/20 lead/med/lg/med. Mid 0x83 -> PAL2[7] cyan. Disc pixels are
repainted from every nonzero nibble (SGDK may pack baked 15 off 15).
spr_place cadence is not the fix. Half-greens PAL2[2]/[3] stay.

Usage (from zanac-md):
    python tools/test_orb_pulse_8a16.py
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

    if "0x1C, 0x20, 0x24, 0x20" not in ent:
        return fail("k_orb_sat must stay 1C/20/24/20")
    if "FRAME_LEAD, FRAME_MED_CIRCLE, FRAME_CIRCLE, FRAME_MED_CIRCLE" not in ent:
        return fail("k_orb_frame must stay lead/med/lg/med")
    if "0x8F, 0x83, 0x8A, 0x8B" not in ent:
        return fail("8a16 yellow colours 8F/83/8A/8B")
    if "k_orb_mid_pal = 7" not in ent:
        return fail("mid pulse 0x83 uses PAL2[7] cyan")
    if "orb_paint_body_nibbles" not in ent:
        return fail("type 72 must paint every nonzero nibble to sat_col")
    if "if (hi)\n            hi = want" not in ent and "if (hi)\n                hi = want" not in ent:
        return fail("orb_paint_body_nibbles must not require from==15")
    if "u16 out = 128" in ent:
        return fail("do not re-ship 4-tile pad as the orb fix")
    if "orb_keep_body_nibbles" not in ent:
        return fail("orb sanitize stays")

    print("ok: 8a16 pulse locked; disc remap is all-nonzero, not spr_place cadence")
    return 0


if __name__ == "__main__":
    sys.exit(main())
