#!/usr/bin/env python3
"""0x96c2 ROUND/STAGE banner uses charset 0x20 spaces on BG_A, not WINDOW.

zanac-re 0x96bc SETWRT 0x3948 (row 10 col 8), bytes 20 52 4f 55 4e 44 20
then E701+'0' then 20. Port stamps that on BG_A. Tile 0x20 CT 70 bg=0
must stay transparent so the spaces are not opaque black blocks.

Usage (from zanac-md):
    python tools/test_stage_round_banner.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPC = ROOT / "src" / "map_script.c"
HUD = ROOT / "src" / "hud.c"
CT = ROOT / "res" / "charset_ct.bin"


def fail(msg: str) -> int:
    print("FAIL:", msg)
    return 1


def main() -> int:
    map_c = MAPC.read_text(encoding="utf-8")
    hud = HUD.read_text(encoding="utf-8")

    if 's_ms.banner[0] = \' \'' not in map_c:
        return fail("banner must start with space 0x20")
    if '" ROUND n "' not in map_c and "0x3948" not in map_c:
        return fail("banner must stay 0x3948 / ROUND n")
    if "hud_draw_str(BG_A, 8, mode_text_row(10), s_ms.banner)" not in map_c:
        return fail("ROUND banner must stay BG_A col 8 row 10 (not WINDOW)")
    if "recolor_charset_tile_opaque_bg" in map_c:
        return fail("opaque_bg on 0x20 poisons ROUND/STAGE banner spaces")
    if "hud_fill_tile(BG_A, 8, mode_text_row(10), 0, 9)" not in map_c:
        return fail("banner clear must stay BG_A tile 0 (transparent)")
    if HUD_COL_BACKING_OK(hud):
        pass
    else:
        return fail("HUD stripe must still back BG_B cols 24-31")

    ct = CT.read_bytes()
    space = ct[0x20 * 8:0x20 * 8 + 8]
    if space != bytes([0x70] * 8):
        return fail("charset 0x20 CT must stay 70 (bg nibble 0), got %s" % space.hex())

    print("ok: ROUND banner on BG_A col 8; space 0x20 CT bg=0; no opaque_bg")
    return 0


def HUD_COL_BACKING_OK(hud: str) -> bool:
    return "VDP_fillTileMapRect(BG_B, blank, HUD_COL, 0, MODE_BAR_W, 32)" in hud


if __name__ == "__main__":
    sys.exit(main())
