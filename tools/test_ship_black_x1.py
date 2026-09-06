#!/usr/bin/env python3
"""Ship black complement is SAT-drawn 1 MSX pixel right of white.

Japan v1 gfx_sprite_patterns pats 14/15: black covers more white hull
at X+1 (overlap 48 vs same-X 29). player.c draws frame 1 at white X+1.
Collision stays SAT 0x38. Do not invent SAT 0x3C.

Usage (from zanac-md):
    python tools/test_ship_black_x1.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLY = ROOT / "src" / "player.c"
SHIP = ROOT / "res" / "sprites" / "ship.png"
EX = ROOT / "tools" / "extract_map_scripts.py"


def fail(msg: str) -> int:
    print("FAIL:", msg)
    return 1


def main() -> int:
    ply = PLY.read_text(encoding="utf-8")
    ex = EX.read_text(encoding="utf-8")

    if "ship_compl_draw_x" not in ply:
        return fail("player.c must draw black complement at white X+1")
    if "mode_draw_x(s_x, 0x81) + 1" not in ply:
        return fail("complement draw X must be mode_draw_x(x, 0x81)+1")
    if "SPR_setAnimAndFrame(s_cspr, 0, 1)" not in ply:
        return fail("s_cspr must be ship.png frame 1 (pat 15)")
    if "SPR_setAnimAndFrame(s_spr, 0, 0)" not in ply:
        return fail("s_spr must be ship.png frame 0 (pat 14)")
    if "SAT 0x3C" in ply:
        return fail("do not invent SAT 0x3C; ship SAT stays 0x38")

    if '[(14, 15), (15, 1)]' not in ex:
        return fail("extract must emit pat 14 white + pat 15 black frames")

    try:
        from PIL import Image
    except ImportError:
        return fail("Pillow required to prove ship.png frames")

    im = Image.open(SHIP)
    if im.size != (32, 16):
        return fail("ship.png must be 32x16 (two 16x16 frames), got %s" % (im.size,))

    white = list(im.crop((0, 0, 16, 16)).getdata())
    black = list(im.crop((16, 0, 32, 16)).getdata())
    if 1 in white:
        return fail("frame 0 must be white-only (no folded black)")
    if 15 not in white:
        return fail("frame 0 must contain TMS 15 hull")
    if 15 in black:
        return fail("frame 1 must be black-only (no white hull)")
    if 1 not in black:
        return fail("frame 1 must contain index-1 complement bits")

    print("ok: ship black SAT draw at X+1; 32x16 two-frame; no SAT 0x3C")
    return 0


if __name__ == "__main__":
    sys.exit(main())
