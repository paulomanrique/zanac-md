#!/usr/bin/env python3
"""Boot peek must DMA into NT 31 (letterbox at scroll_px=0), not NT 30.

MD VSCROLL = -(scroll_px + 16). Top of the 192 is screen Y 16:
  NT pixel = 16 - scroll_px - 16 = -scroll_px
scroll_px 1..8 reveals NT row 31 (pixels 255..248). fill_letterbox_b
paints NT 24-31 black. peek_next_row used hidden_wrap_nt_at(scroll_px+8)
= NT 30 at boot, so NT 31 stayed black and travelled the playfield.

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
    py = (8 - off) & 0xFF
    return py >> 3


def main() -> int:
    src = MAPC.read_text(encoding="utf-8")
    if "peek_next_row_at((u16)(s_ms.row + 1), s_scroll_px)" not in src:
        print("FAIL: boot peek must target hidden_wrap_nt_at(s_scroll_px)")
        return 1
    if not re.search(
        r"peek_next_row_at\(map_row,\s*\(u16\)\(s_scroll_px \+ 8\)\)", src
    ):
        print("FAIL: in-game peek must keep +8 so it does not overwrite 97e3")
        return 1

    boot = hidden_wrap_nt_at(0)
    old_peek = hidden_wrap_nt_at(8)
    if boot != 31:
        print("FAIL: letterbox at scroll_px=0 must be NT 31, got", boot)
        return 1
    if old_peek != 30:
        print("FAIL: +8 letterbox is NT 30 (the old wrong boot target), got",
              old_peek)
        return 1
    # First 8px of VSCROLL show NT 31, then NT 30 after the first carry.
    for px in range(1, 9):
        top = (-px) & 0xFF
        row = top >> 3
        if row != 31:
            print("FAIL: scroll_px", px, "top NT row", row, "want 31")
            return 1
    print("ok: boot peek NT 31; in-game peek stays +8 (NT 30 after carry)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
