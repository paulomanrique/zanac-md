#!/usr/bin/env python3
"""Type 72 8a16 mid-pulse is SAT 0x20 / 0x83, uploaded off dim PAL2[3].

base_core_anim 0x8a16:
  1C 8F / 20 83 / 24 8A / 20 8B   then 8a1e blacks 81.
SAT 0x20 is gfx pat 8 (96-bit disc), bake TMS 15. 0x83 is TMS 3.
PAL2[3] is half flyer green (leave-alone). Type 72 only remaps that
SAT upload to PAL2[7] TMS cyan. Flyer 0x83 stays nibble 3.

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

    try:
        hist = png_frame52_hist()
    except ImportError:
        hist = None
    if hist is not None:
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

    # Type 72 0x83 must not paint PAL2[3] (dim flyer green).
    pal = re.search(r"static const u8 k_orb_mid_pal\s*=\s*(\d+)", ent)
    if not pal or int(pal.group(1)) != 7:
        print("FAIL: k_orb_mid_pal must be 7 (TMS cyan / light-cyan)")
        return 1
    if "s->kind == KIND_ORB && (s->sat_col & 0x0F) == 3" not in ent:
        print("FAIL: type-72 0x83 upload must gate on KIND_ORB nibble 3")
        return 1
    if "want = k_orb_mid_pal" not in ent:
        print("FAIL: type-72 0x83 must upload k_orb_mid_pal, not nibble 3")
        return 1
    if "PAL_setColor((u16)((PAL2 * 16) + 3), k_flyer_green_dim[1])" not in ent:
        print("FAIL: PAL2[3] half-green override must stay")
        return 1
    if "PAL_setColor((u16)((PAL2 * 16) + 2), k_flyer_green_dim[0])" not in ent:
        print("FAIL: PAL2[2] half-green override must stay")
        return 1
    if "e->sat_col = 0x86" not in ent:
        print("FAIL: type 67 +04=0x86 must stay (nibble 6, not orb remap)")
        return 1

    print("ok: 8a16 names/colors; FRAME_MED_CIRCLE bake 15; type72 0x83 -> PAL2[7]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
