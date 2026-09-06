#!/usr/bin/env python3
"""Boot peek must DMA into NT 31 (first 8px reveal), not NT 0.

hidden_wrap is SAT Y 0 / screen Y 16. At scroll_px=0 that is NT 0
(the flushed playfield top). Peeking there would overwrite the live
row. +8 is NT 31 -- the row VSCROLL reveals in the first 1-8px.

Usage (from zanac-md):
    python tools/test_boot_peek_nt31.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPC = ROOT / "src" / "map_script.c"


def hidden_wrap_nt_at(scroll_px: int, y_off: int = 16) -> int:
    off = (scroll_px + y_off) & 0xFF
    py = (16 - off) & 0xFF
    return py >> 3


def main() -> int:
    src = MAPC.read_text(encoding="utf-8")
    if "peek_next_row_at((u16)(s_ms.row + 1), (u16)(s_scroll_px + 8))" not in src:
        print("FAIL: boot peek must target hidden_wrap_nt_at(scroll_px+8) = NT 31")
        return 1
    if not re.search(
        r"peek_next_row_at\(map_row,\s*\(u16\)\(s_scroll_px \+ 8\)\)", src
    ):
        print("FAIL: in-game peek must keep +8 so it does not overwrite 97e3")
        return 1

    if hidden_wrap_nt_at(0) != 0:
        print("FAIL: playfield top at scroll_px=0 must be NT 0, got",
              hidden_wrap_nt_at(0))
        return 1
    if hidden_wrap_nt_at(8) != 31:
        print("FAIL: +8 playfield top is NT 31, got", hidden_wrap_nt_at(8))
        return 1
    for px in range(1, 9):
        # first 1-8px reveal NT 31 (pixel 255..248)
        pix = (-px) & 0xFF
        row = pix >> 3
        if row != 31:
            print("FAIL: scroll_px", px, "top NT row", row, "want 31")
            return 1
    print("ok: boot peek NT 31 via +8; wrap is SAT Y 0 (NT 0 at scroll 0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
