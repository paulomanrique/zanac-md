#!/usr/bin/env python3
"""8a16 discs are gfx pats 7/8/9. Body bits only; no TMS 4/5 specks.

SAT 0x1C/0x20/0x24 = lead / med_circle / lg_circle. rebuild_sprites
primary_only paints those bits TMS 15. objs.png FRAME_LEAD / CIRCLE /
MED_CIRCLE must stay {0,15}. Do not invent a new disc.

Usage (from zanac-md):
    python tools/test_orb_disc_pixels.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENT = ROOT / "src" / "entity.c"
PNG = ROOT / "res" / "sprites" / "objs.png"
REBUILD = ROOT / "tools" / "rebuild_sprites.py"

# FRAME_* indices in entity.c / rebuild_sprites FRAMES
FRAMES = (
    (6, "LEAD", 7),
    (11, "CIRCLE", 9),
    (52, "MED_CIRCLE", 8),
)


def fail(msg: str) -> int:
    print("FAIL:", msg)
    return 1


def main() -> int:
    ent = ENT.read_text(encoding="utf-8")
    reb = REBUILD.read_text(encoding="utf-8")

    if "FRAME_LEAD, FRAME_MED_CIRCLE, FRAME_CIRCLE, FRAME_MED_CIRCLE" not in ent:
        return fail("k_orb_frame must stay lead / med / lg / med")
    if "(7, 15, False)" not in reb:
        return fail("rebuild LEAD bake must be pat 7 TMS 15")
    if "(9, 15, False)" not in reb:
        return fail("rebuild CIRCLE bake must be pat 9 TMS 15")
    if "(8, 15, False)" not in reb:
        return fail("rebuild MED_CIRCLE bake must be pat 8 TMS 15")

    try:
        from PIL import Image
    except ImportError:
        print("ok: 8a16 frames locked (PIL missing; skip objs.png hist)")
        return 0

    im = Image.open(PNG)
    for fi, name, _pat in FRAMES:
        fr = im.crop((fi * 16, 0, fi * 16 + 16, 16))
        pix = list(fr.getdata())
        stray = [p for p in pix if p not in (0, 15)]
        if stray:
            return fail("objs.png FRAME_%s has non-0/non-15 pixels %s" % (
                name, sorted(set(stray))))
        ul = [pix[y * 16 + x] for y in range(4) for x in range(4)]
        if any(p in (4, 5) for p in ul):
            return fail("objs.png FRAME_%s UL 4x4 has TMS 4/5" % name)

    print("ok: 8a16 discs are body bits only (0/15); no TMS 4/5 specks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
