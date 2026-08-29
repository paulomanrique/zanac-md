#!/usr/bin/env python3
"""8A26 / 90fe white backdrop must flash PAL0[1], not only the backdrop index.

explode_enemies 0x8A26: WRTVDP BC=0x0F07, wait_frames 5, convert, 0x0107.
90fe: WRTVDP 0x0F07, gameplay_frame_loop B=3, then sweep, then 8A26.
MD color 0 is always transparent; visible black is PAL0[1].

Usage (from zanac-md):
    python tools/test_flash_8a26.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODE = ROOT / "src" / "mode.c"
ENT = ROOT / "src" / "entity.c"
MAPC = ROOT / "src" / "map_script.c"


def fail(msg: str) -> int:
    print("FAIL:", msg)
    return 1


def main() -> int:
    mode = MODE.read_text(encoding="utf-8")
    ent = ENT.read_text(encoding="utf-8")
    map_c = MAPC.read_text(encoding="utf-8")

    if "s_flash_left = 5" not in ent:
        return fail("8A26 wait_frames B=5")
    if "mode_backdrop_flash(1)" not in ent:
        return fail("flash_begin must call mode_backdrop_flash(1)")
    if "PAL_setColor(1, RGB24_TO_VDPCOLOR(on ? 0xFFFFFF : 0x000000))" not in mode:
        return fail("flash must set PAL0[1] (letterbox / HUD backing)")
    if "VDP_setBackgroundColor(on ? 15 : 0)" not in mode:
        return fail("flash must still set the backdrop register")
    if "mode_backdrop_flash(1)" not in map_c:
        return fail("90fe phase 1 must WRTVDP-white the 3-frame wait")
    if "s_clr_wait = 3" not in map_c:
        return fail("90fe gameplay_frame_loop B=3 must stay")

    print("ok: 8A26 5-frame + 90fe 3-frame flash PAL0[1] and backdrop")
    return 0


if __name__ == "__main__":
    sys.exit(main())
