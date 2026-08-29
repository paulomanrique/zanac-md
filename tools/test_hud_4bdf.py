#!/usr/bin/env python3
"""WINDOW HUD layout stays 0x4BD4 / 0x4BDF. No shared 0x20 opaque.

draw_hud_labels 0x4BD4: B=0x0E rows from 0x3958, inline 03 20 20 20 03.
hbars 0x4C29 at 0x3818/3878/38d8/3938/3af8 (rows 0/3/6/9/23 col 24).
Labels: TOP 0x3899, SCORE 0x38F9, ZANAC 0x3959, LEVEL 0x3999, ROUND 0x39F9.
Score 0x3918, TOP 0x38B8, lives 0x397A, level 0x39BB, round 0x3A1B.
FIRE 0x3A59. WPV=2 letterbox. Charset 0x20 keeps CT bg=0.

Usage (from zanac-md):
    python tools/test_hud_4bdf.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HUD = ROOT / "src" / "hud.c"
MODE = ROOT / "src" / "mode.c"
MAPC = ROOT / "src" / "map_script.c"


def fail(msg: str) -> int:
    print("FAIL:", msg)
    return 1


def main() -> int:
    hud = HUD.read_text(encoding="utf-8")
    mode = MODE.read_text(encoding="utf-8")
    map_c = MAPC.read_text(encoding="utf-8")

    if "03 20 20 20 03" not in hud:
        return fail("0x4BDF border bytes must stay documented")
    if 'hud_str_win(HUD_TEXT, hud_y(4), "TOP")' not in hud:
        return fail("TOP must stay 0x3899 row 4 col 25")
    if 'hud_str_win(HUD_TEXT, hud_y(7), "SCORE")' not in hud:
        return fail("SCORE must stay 0x38F9 row 7 col 25")
    if 'hud_str_win(HUD_TEXT, hud_y(10), "ZANAC")' not in hud:
        return fail("ZANAC must stay 0x3959 row 10 col 25")
    if 'hud_str_win(HUD_TEXT, hud_y(12), "LEVEL")' not in hud:
        return fail("LEVEL must stay 0x3999 row 12 col 25")
    if 'hud_str_win(HUD_TEXT, hud_y(15), "ROUND")' not in hud:
        return fail("ROUND must stay 0x39F9 row 15 col 25")
    if "hud_score6(HUD_COL, hud_y(8), player_score())" not in hud:
        return fail("SCORE digits must stay 0x3918 row 8 col 24")
    if "hud_digit2((u16)(HUD_COL + 3), hud_y(13), player_shot_level())" not in hud:
        return fail("LEVEL digits must stay 0x39BB row 13 col 27")
    if "hud_digit3((u16)(HUD_COL + 2), hud_y(11), (u8)(lives - 1))" not in hud:
        return fail("lives must stay 0x397A DEC E10A")
    if 'hud_str_win(HUD_TEXT, hud_y(18), "FIRE ")' not in hud:
        return fail("FIRE label must stay 0x3A59")
    if "hud_hbar(0)" not in hud or "hud_hbar(23)" not in hud:
        return fail("0x4C29 hbars must stay rows 0 and 23")
    if "VDP_setWindowVPos(FALSE, 2)" not in mode:
        return fail("WPV must stay 2 (rows 0-1 full-width WINDOW)")
    if "recolor_charset_tile_opaque_bg" in map_c:
        return fail("do not opaque-recolor shared 0x20")

    print("ok: 0x4BDF / labels / WPV=2 locked; 0x20 stays CT bg=0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
