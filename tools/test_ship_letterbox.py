#!/usr/bin/env python3
"""Ship SAT Y clamp stays 0x1E..0xB8. Letterbox clips the overlapping 8px.

player_ship_update 0x7640 CP 0xB8. SAT Y 0xB8 draws at 200; playfield
ends at 208. Do not invent 0xB0. Restamp letterbox after bg_init.

Usage (from zanac-md):
    python tools/test_ship_letterbox.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLY = ROOT / "src" / "player.c"
MAPC = ROOT / "src" / "map_script.c"
MODE = ROOT / "src" / "mode.c"


def fail(msg: str) -> int:
    print("FAIL:", msg)
    return 1


def main() -> int:
    ply = PLY.read_text(encoding="utf-8")
    map_c = MAPC.read_text(encoding="utf-8")
    mode = MODE.read_text(encoding="utf-8")

    if "max_y = 0xB8" not in ply:
        return fail("Y clamp must stay 0xB8 (0x7640)")
    if "min_y = 0x1E" not in ply:
        return fail("Y clamp must stay 0x1E (0x7636)")
    if "VDP_fillTileMapRect(BG_A, attr, 0, 26, MODE_H32_COLS, 2)" not in mode:
        return fail("bottom letterbox must be full-width high-pri BG_A")
    if "mode_draw_letterbox();" not in map_c:
        return fail("bg_init must restamp letterbox after the plane fill")

    print("ok: ship SAT 0xB8; letterbox restamp after bg_init")
    return 0


if __name__ == "__main__":
    sys.exit(main())
