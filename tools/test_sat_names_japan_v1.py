#!/usr/bin/env python3
"""Lock k_frame_sat to Japan v1 SAT names (pat << 2). Do not invent ids.

zanac-re zanac-sprite-names.md + handler LD (IX+0x03),imm.
objs.png must stay 61 frames (rebuild_sprites FRAMES / extract).

Usage (from zanac-md):
    python tools/test_sat_names_japan_v1.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENT = ROOT / "src" / "entity.c"
REB = ROOT / "tools" / "rebuild_sprites.py"
OBJS = ROOT / "res" / "sprites" / "objs.png"

# FRAME index -> SAT name. Pattern index = SAT >> 2.
JAPAN_V1 = {
    0: 0x28,   # SHOT pat 10
    1: 0x58,   # DUSTER pat 22
    2: 0x60,   # TERUZO pat 24
    3: 0x78,   # LUSTER_B pat 30
    5: 0x04,   # CHIP pat 1
    6: 0x1C,   # LEAD pat 7
    9: 0x30,   # SHOT_T pat 12
    12: 0x08,  # COMET pat 2
    16: 0x84,  # VEYBAR_0 pat 33
    21: 0x98,  # VEYBAR_C0 pat 38
    26: 0x5C,  # DUSTER_C pat 23
    29: 0x80,  # LUSTER_C pat 32
    44: 0x48,  # LOGA pat 18
    46: 0x40,  # PLANE pat 16
    52: 0x20,  # MED_CIRCLE pat 8
    53: 0x74,  # LUSTER_A pat 29
    54: 0x7C,  # LUSTER_A_C pat 31
    59: 0x10,  # SNOW pat 4
    60: 0x14,  # SMALL_STAR pat 5
}


def fail(msg: str) -> int:
    print("FAIL:", msg)
    return 1


def main() -> int:
    ent = ENT.read_text(encoding="utf-8")
    reb = REB.read_text(encoding="utf-8")
    # Comments in k_frame_sat contain '}' (e.g. "7882 / 8e5d SAT 0x04")
    # — strip them before taking the initializer list.
    ent_nc = re.sub(r"/\*.*?\*/", "", ent, flags=re.S)

    m = re.search(r"static const u8 k_frame_sat\[FRAME_N\] = \{([^}]+)\}", ent_nc)
    if not m:
        return fail("k_frame_sat not found")
    nums = [int(x, 0) for x in re.findall(r"0x[0-9A-Fa-f]+|\d+", m.group(1))]
    if len(nums) < 61:
        return fail("k_frame_sat must have 61 entries, got %d" % len(nums))
    for idx, sat in JAPAN_V1.items():
        if nums[idx] != sat:
            return fail("k_frame_sat[%d] must be 0x%02X (Japan v1), got 0x%02X"
                        % (idx, sat, nums[idx]))

    if "u16 out = 128" not in ent:
        return fail("spr_upload_color must 4-tile zero-pad (no interlaced leftover)")
    if "frame == FRAME_SHOT || frame == FRAME_CHIP" not in ent:
        return fail("complement_frame_ok must reject SHOT/CHIP")

    if "SNOW pat 4 SAT 0x10" not in reb:
        return fail("rebuild_sprites must keep FRAME_SNOW")
    if "(8, 15, False)" not in reb:
        return fail("MED_CIRCLE bake must stay TMS 15")

    try:
        from PIL import Image
        im = Image.open(OBJS)
    except Exception as e:
        return fail("objs.png: %s" % e)
    if im.size[0] // 16 != 61:
        return fail("objs.png must stay 61 frames, got %d" % (im.size[0] // 16))

    print("ok: k_frame_sat matches Japan v1 SAT names; 61-frame sheet; 4-tile pad")
    return 0


if __name__ == "__main__":
    sys.exit(main())
