#!/usr/bin/env python3
"""Type 72 8a16 mid-pulse is SAT 0x20 with colors 0x83/0x8B, not baked TMS 6.

base_core_anim 0x8a16:
  1C 8F / 20 83 / 24 8A / 20 8B   then 8a1e blacks 81.
Pat 8 (SAT 0x20) baked as TMS 6 (type 67 +04=0x86) showed a red frame
on white totem orbs when sat_col remap missed.

Usage (from zanac-md):
    python tools/test_orb_med_white.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENT = ROOT / "src" / "entity.c"
PNG = ROOT / "res" / "sprites" / "objs.png"
REBUILD = ROOT / "tools" / "rebuild_sprites.py"

# 8a16 yellow pairs then 8a1e black pairs
K_ORB_SAT = [0x1C, 0x20, 0x24, 0x20]
K_ORB_YEL = [0x8F, 0x83, 0x8A, 0x8B]
K_ORB_BLK = [0x81, 0x81, 0x81, 0x81]


def png_frame52_hist() -> dict[int, int]:
    from PIL import Image

    im = Image.open(PNG)
    fr = im.crop((52 * 16, 0, 53 * 16, 16))
    hist: dict[int, int] = {}
    for p in fr.getdata():
        hist[p] = hist.get(p, 0) + 1
    return hist


def main() -> int:
    ent = ENT.read_text(encoding="utf-8")
    reb = REBUILD.read_text(encoding="utf-8")

    if "0x1C, 0x20, 0x24, 0x20" not in ent:
        print("FAIL: 8a16 SAT names must stay 1C/20/24/20")
        return 1
    if "0x8F, 0x83, 0x8A, 0x8B" not in ent:
        print("FAIL: 8a16 yellow colors must stay 8F/83/8A/8B")
        return 1

    # k_frame_color[52] is the last value on the 42-52 line (11 numbers).
    m = re.search(
        r"7, 1, 15, 1, 7, 1, 15, 4, 15, 15, (\d+)", ent
    )
    if not m or int(m.group(1)) != 15:
        print("FAIL: k_frame_color[FRAME_MED_CIRCLE] must be 15, got",
              m.group(1) if m else None)
        return 1
    if "(8, 15, False)" not in reb and "(8, 15, False)," not in reb:
        print("FAIL: rebuild_sprites MED_CIRCLE bake must be TMS 15")
        return 1

    hist = png_frame52_hist()
    if hist.get(6, 0):
        print("FAIL: objs.png FRAME_MED_CIRCLE still has TMS 6 pixels", hist)
        return 1
    if hist.get(15, 0) != 96 or hist.get(0, 0) != 160:
        print("FAIL: objs.png FRAME_MED_CIRCLE pattern bits changed", hist)
        return 1

    # Remap source is now 15; 8a16 mid nibbles are 3 and 11, not 6.
    if (K_ORB_YEL[1] & 0x0F) == 6 or (K_ORB_YEL[3] & 0x0F) == 6:
        print("FAIL: 8a16 mid color is not 0x86")
        return 1
    if K_ORB_SAT[1] != 0x20 or K_ORB_SAT[3] != 0x20:
        print("FAIL: mid-pulse SAT name is 0x20")
        return 1
    print("ok: 8a16 names/colors; FRAME_MED_CIRCLE bake 15 (96 body px)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
