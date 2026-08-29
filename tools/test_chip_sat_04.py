#!/usr/bin/env python3
"""Type 63 chip SAT name is 0x04 (pat 1), not 0x00.

zanac.asm 7882 (box type 6 -> type 63):
  LD (IX+0x03), 0x04
  LD (IX+0x04), 0x8F
  LD (IX+0x00), 0xBF

8e5d (type 83 non-blank frames) writes the same SAT 0x04.
gfx pat 1 = power chip; SAT name = pat*4 = 0x04.

collision_size_table 0x45C9, index SAT>>1:
  SAT 0x04 -> half Y=3 X=3 -> box [pos+3, pos+10] (10x10)
Old port: k_frame_sat[FRAME_CHIP]=0x00; spr_place clobbered 7882;
hit_overlap_slot then used sat==0 -> 0x40 (half Y=2 X=1 => 14x12).

Usage (from zanac-md):
    python tools/test_chip_sat_04.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTITY = ROOT / "src" / "entity.c"

# collision_size_table 0x45C9 (first 64 bytes cover SAT 0x00..0x7E)
K_COL = [
    0x00, 0x00, 0x03, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x03, 0x03, 0x05, 0x00, 0x06, 0x06,
    0x01, 0x01, 0x00, 0x00, 0x00, 0x06, 0x00, 0x03, 0x00, 0x00, 0x02, 0x02, 0x04, 0x04, 0x04, 0x04,
    0x02, 0x01, 0x02, 0x01, 0x00, 0x03, 0x00, 0x03, 0x00, 0x02, 0x00, 0x02, 0x00, 0x03, 0x00, 0x00,
    0x02, 0x02, 0x00, 0x00, 0x00, 0x01, 0x02, 0x01, 0x02, 0x06, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00,
]


def hitbox(sat: int) -> tuple[int, int]:
    idx = sat >> 1
    hy = K_COL[idx]
    hx = K_COL[idx + 1]
    return (16 - 2 * hx, 16 - 2 * hy)


def old_port_sat(written: int) -> int:
    """spr_place(FRAME_CHIP) used to write 0x00; sat==0 then became 0x40."""
    _ = written
    return 0x40


def main() -> int:
    fails = 0
    src = ENTITY.read_text()

    # k_frame_sat FRAME_CHIP (index 5) must be 0x04.
    m = re.search(
        r"static const u8 k_frame_sat\[FRAME_N\] = \{([^}]+)\}",
        src,
        re.S,
    )
    if not m:
        print("FAIL: k_frame_sat not found", file=sys.stderr)
        return 1
    vals = re.findall(r"0x[0-9A-Fa-f]+", m.group(1))
    if len(vals) < 6 or int(vals[5], 16) != 0x04:
        print(f"FAIL: k_frame_sat[5] want 0x04 got {vals[5] if len(vals) > 5 else '?'}",
              file=sys.stderr)
        fails += 1
    else:
        print("  k_frame_sat[FRAME_CHIP] = 0x04 (pat 1)")

    w04, h04 = hitbox(0x04)
    w40, h40 = hitbox(0x40)
    w00, h00 = hitbox(0x00)
    if (w04, h04) != (10, 10):
        print(f"FAIL: SAT 0x04 hitbox {w04}x{h04}, want 10x10", file=sys.stderr)
        fails += 1
    else:
        print("  SAT 0x04: 10x10 (7882 / 4560 half 3,3)")
    if (w40, h40) != (14, 12):
        print(f"FAIL: SAT 0x40 hitbox {w40}x{h40}, want 14x12", file=sys.stderr)
        fails += 1
    else:
        print("  SAT 0x40 (old sat==0 fallback): 14x12")
    if (w00, h00) != (16, 16):
        print(f"FAIL: SAT 0x00 hitbox {w00}x{h00}, want 16x16", file=sys.stderr)
        fails += 1
    else:
        print("  SAT 0x00 (empty leftover, no fallback): 16x16")

    if old_port_sat(0x04) != 0x40:
        print("FAIL: old_port_sat model", file=sys.stderr)
        fails += 1
    else:
        print("  old port: 7882 0x04 -> spr_place 0x00 -> fallback 0x40")

    # become_chip / spawn_chip_at must write +03 after spr_place.
    for name in ("become_chip", "spawn_chip_at"):
        fm = re.search(rf"static void {name}\(.*?^}}", src, re.S | re.M)
        if not fm:
            print(f"FAIL: {name} not found", file=sys.stderr)
            fails += 1
            continue
        body = fm.group(0)
        place = body.find("spr_place(e, FRAME_CHIP)")
        sat = body.find("e->sat = 0x04")
        if place < 0 or sat < 0 or sat < place:
            print(f"FAIL: {name} must set sat=0x04 after spr_place", file=sys.stderr)
            fails += 1
        else:
            print(f"  {name}: SAT 0x04 after spr_place")

    if fails:
        print(f"{fails} FAIL(s)", file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
