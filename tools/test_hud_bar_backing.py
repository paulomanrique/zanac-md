#!/usr/bin/env python3
"""HUD bar spaces must not punch WINDOW color 0 through to leftover white.

0x4BDF border is 03 20 20 20 03. Tile 0x20 CT is 0x70 (bg nibble 0).
WINDOW replaces BG_A; punch-through is BG_B. Fill BG_B cols 24-31.

Do NOT opaque-recolor shared charset 01/02/03/20: 0x20 is also the
0x96c2 " ROUND n " space at 0x3948 (BG_A col 8). Mapping CT bg=0 to
PAL3[1] painted black blocks on that banner (PR #40 regression).

Usage (from zanac-md):
    python tools/test_hud_bar_backing.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HUD = ROOT / "src" / "hud.c"
MAPC = ROOT / "src" / "map_script.c"


def fail(msg: str) -> int:
    print("FAIL:", msg)
    return 1


def main() -> int:
    hud = HUD.read_text(encoding="utf-8")
    map_c = MAPC.read_text(encoding="utf-8")

    if "VDP_fillTileMapRect(BG_B, blank, HUD_COL, 0, MODE_BAR_W, 32)" not in hud:
        return fail("hud backing must fill BG_B cols 24-31 (WINDOW punch-through)")
    if "recolor_charset_tile_opaque_bg" in map_c:
        return fail("do not opaque-recolor shared charset (ROUND/STAGE spaces)")
    if "recolor_charset_tile(0x20, charset_ct + 0x20 * 8)" not in map_c:
        return fail("space 0x20 must keep ROM CT (bg nibble 0)")
    if "recolor_charset_tile(0x01, charset_ct + 0x01 * 8)" not in map_c:
        return fail("HUD 0x01 must keep ROM CT")
    if "03 20 20 20 03" not in hud:
        return fail("0x4BDF border bytes must stay documented")

    print("ok: HUD BG_B backing; shared 01/02/03/20 keep CT bg=0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
