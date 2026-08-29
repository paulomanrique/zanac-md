#!/usr/bin/env python3
"""BG_A playfield must not keep leftover SGDK tile 0.

VDP_clearPlane writes tile 0. SCREEN2 CT bg nibble 0 is transparent to
R7 black. On MD that punches through BG_B to BG_A. HUD already fills
BG_B cols 24-31. Playfield cols 0-23 rows 2-25 need the same PAL0[1]
letter tile so mid-screen holes are black, not leftover white.

Do not opaque-recolor shared charset 0x20 (ROUND banner spaces).
Do not fill HUD cols here (hud_fill_bar_backing). hidden_wrap Y 8 stays.

Usage (from zanac-md):
    python tools/test_playfield_tile0.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPC = ROOT / "src" / "map_script.c"
HUD = ROOT / "src" / "hud.c"


def fail(msg: str) -> int:
    print("FAIL:", msg)
    return 1


def main() -> int:
    map_c = MAPC.read_text(encoding="utf-8")
    hud = HUD.read_text(encoding="utf-8")

    fill = "VDP_fillTileMapRect(BG_A, mode_letter_attr(), 0, 2, MODE_BAR_COL, 24)"
    if fill not in map_c:
        return fail("bg_init must fill BG_A playfield cols 0-23 rows 2-25")
    if map_c.find(fill) > map_c.find("bg_fill_plane();"):
        return fail("playfield fill must run before bg_fill_plane (0x3948 banner)")
    if "recolor_charset_tile_opaque_bg" in map_c:
        return fail("do not opaque-recolor shared charset 0x20")
    if "recolor_charset_tile(0x20, charset_ct + 0x20 * 8)" not in map_c:
        return fail("space 0x20 must keep ROM CT (bg nibble 0)")
    if "VDP_fillTileMapRect(BG_B, blank, HUD_COL, 0, MODE_BAR_W, 32)" not in hud:
        return fail("HUD stripe must stay BG_B cols 24-31 only")
    if "8 - off" not in map_c:
        return fail("hidden_wrap_nt_at must stay screen Y 8")

    print("ok: BG_A playfield letter-tile; no 0x20 opaque; wrap Y 8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
