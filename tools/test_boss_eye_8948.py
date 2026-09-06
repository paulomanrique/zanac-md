#!/usr/bin/env python3
"""Boss eyes bind 8948 NT cell at arm; 8c15 paints that cell (not live Y+16).

Japan v1 8a7d Y+=0x10 then 8948 uses L (pre-+0x10). Stored +06/+07 is the
VRAM cell. Re-binding against live VSCROLL put eyes one eye-height south
(letterbox 16px) and skipped the 4th eye when C>=0x18.

Usage (from zanac-md):
    python tools/test_boss_eye_8948.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENT = ROOT / "src" / "entity.c"
MAP = ROOT / "src" / "map_script.c"
HDR = ROOT / "inc" / "map_script.h"


def fail(msg: str) -> int:
    print("FAIL:", msg)
    return 1


def main() -> int:
    ent = ENT.read_text(encoding="utf-8")
    mp = MAP.read_text(encoding="utf-8")
    hdr = HDR.read_text(encoding="utf-8")

    if "map_script_8948_cell" not in hdr or "map_script_base_8c15_at" not in hdr:
        return fail("8948 cell bind + 8c15_at must be declared")
    if "map_script_8948_cell(e->x, (s16)ypre, &col, &row)" not in ent:
        return fail("arm must 8948-bind SAT X / Y-pre-+0x10")
    if "0x8000 | ((u16)col << 8) | row" not in ent:
        return fail("bind must store NT col/row with valid bit")
    if "map_script_base_8c15_at" not in ent:
        return fail("8c15 must paint the stored NT cell")
    if "base_8c15(e);" not in ent:
        return fail("arm must paint phase 0 so all four eyes exist")
    if "variant == 79" not in mp:
        return fail("type 79 still skips 8c15 (8c80)")
    if "0xBF + p" not in mp:
        return fail("types 75-78 stay tile 0xBF+phase")

    print("ok: 8948 NT cell stored at arm; 8c15_at; phase 0 paint")
    return 0


if __name__ == "__main__":
    sys.exit(main())
