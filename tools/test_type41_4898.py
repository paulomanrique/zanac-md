#!/usr/bin/env python3
"""Prove type 41 pair_fragment 0x857f is 4898 + speed-2 LDIR bias.

zanac.asm 0x852f: 4cf7 speed 2, LDIR +08..+0b -> +1c..+1f, +17=4, RET.
0x857f: heading tick, 4cf7 speed 4, ADD HL,(+1c/+1e), CALL 0x4898.

The port used s32 8.8 (no wrap) and invented screen cull, and dropped the
speed-2 bias. apply_dir_88 also zeroed the position frac every frame.

Usage (from zanac-md):
    python tools/test_type41_4898.py
"""
from __future__ import annotations

import sys

# entity.c k_unit_x = ROM word0 (Y), k_unit_y = ROM word1 (X).
UNIT_Y = (
    0, 48, 90, 118, 128, 118, 90, 48,
    0, -48, -90, -118, -128, -118, -90, -48,
)
UNIT_X = (
    128, 118, 90, 48, 0, -48, -90, -118,
    -128, -118, -90, -48, 0, 48, 90, 118,
)


def vel(dir_: int, speed: int) -> tuple[int, int]:
    d = dir_ & 15
    return UNIT_X[d] * speed, UNIT_Y[d] * speed


def add16(a: int, b: int) -> int:
    return (a + b) & 0xFFFF


def to_s16(u: int) -> int:
    return u - 0x10000 if u >= 0x8000 else u


def step_4898(x: int, y: int, xf: int, yf: int, vx: int, vy: int):
    """u8 8.8 ADD then unsigned Y>=0xD0 / X>=0xD1."""
    xpos = add16(((x & 0xFF) << 8) | (xf & 0xFF), vx & 0xFFFF)
    ypos = add16(((y & 0xFF) << 8) | (yf & 0xFF), vy & 0xFFFF)
    x = (xpos >> 8) & 0xFF
    y = (ypos >> 8) & 0xFF
    culled = y >= 0xD0 or x >= 0xD1
    return x, y, xpos & 0xFF, ypos & 0xFF, culled


def step_s32(x: int, y: int, xf: int, yf: int, vx: int, vy: int):
    """Old port: signed 32-bit 8.8, no wrap, no 4898 cull."""
    xpos = ((x << 8) | (xf & 0xFF)) + to_s16(vx & 0xFFFF)
    ypos = ((y << 8) | (yf & 0xFF)) + to_s16(vy & 0xFFFF)
    return xpos >> 8, ypos >> 8, xpos & 0xFF, ypos & 0xFF, False


def heading_init(param: int) -> int:
    base = param & 15
    return ((base + 0xFC) & 15) if (param & 0x10) else ((base + 4) & 15)


def main() -> int:
    fails = 0

    # Umber-8 children: +0x1a = 0x05 / 0x13. Swoop-29: 0x04.
    for param, name in ((0x05, "umber-8 a"), (0x13, "umber-8 b"), (0x04, "swoop-29")):
        ih = heading_init(param)
        bx, by = vel(ih, 2)
        sx, sy = vel(ih, 4)
        tx, ty = add16(sx, bx), add16(sy, by)
        # First update frame heading == init heading: speed4 + speed2 = *6.
        want_x, want_y = vel(ih, 6)
        if to_s16(tx) != want_x or to_s16(ty) != want_y:
            print(
                f"FAIL {name}: bias {ih:X} vx={to_s16(tx)} vy={to_s16(ty)} "
                f"want {want_x},{want_y}",
                file=sys.stderr,
            )
            fails += 1
        else:
            print(f"  {name} param {param:02X} ih {ih} first-frame vel *6 ok")

    # apply_dir_88 zeroed frac: diagonal speed 4 loses 0x6C/frame.
    vx4, _ = vel(2, 4)
    if (vx4 & 0xFF) == 0:
        print("FAIL: dir2 speed4 has no frac; cannot prove frac hole", file=sys.stderr)
        fails += 1
    x = y = xf = yf = 0x40
    # One 4898 step keeps frac; next add uses it.
    x1, y1, xf1, yf1, _ = step_4898(x, y, xf, yf, vx4 & 0xFFFF, 0)
    x2, _, xf2, _, _ = step_4898(x1, y1, xf1, yf1, vx4 & 0xFFFF, 0)
    x_zero, _, _, _, _ = step_4898(x1, y1, 0, 0, vx4 & 0xFFFF, 0)
    if x2 == x_zero:
        print("FAIL: keeping frac did not change X vs zeroed frac", file=sys.stderr)
        fails += 1
    else:
        print(f"  frac keep X {x2:02X} vs zeroed {x_zero:02X} (dir2 *4)")

    # s32 signed vs 4898: rise through Y=0 with vy = 0xFF00 (-1.0).
    # 4898: Y wraps to 0xFF and culls (>=0xD0). s32: Y=-1, invented cull
    # at y < -24 keeps it live.
    x, y, xf, yf, culled = step_4898(0x80, 0x00, 0, 0, 0, 0xFF00)
    sx, sy, _, _, _ = step_s32(0x80, 0x00, 0, 0, 0, 0xFF00)
    if not culled or y != 0xFF:
        print(f"FAIL: 4898 Y rise wrap want Y=FF cull, got Y={y:02X} cull={culled}",
              file=sys.stderr)
        fails += 1
    if sy != -1:
        print(f"FAIL: s32 rise from 0 + FF00 should be -1, got {sy}", file=sys.stderr)
        fails += 1
    if culled and sy == -1:
        print("  4898 Y=00+FF00 -> FF cull; s32 stays at -1 (old hole)")

    # X>=0xD1: 4898 clears; s32 at 0xD1 lives (invented cull was playfield+16).
    x, y, _, _, culled = step_4898(0xD0, 0x40, 0, 0, 0x0100, 0)
    sx, _, _, _, _ = step_s32(0xD0, 0x40, 0, 0, 0x0100, 0)
    if not culled or x != 0xD1:
        print(f"FAIL: 4898 X 0xD0+1 want D1 cull, got {x:02X} cull={culled}",
              file=sys.stderr)
        fails += 1
    if sx != 0xD1:
        print(f"FAIL: s32 X should be 0xD1, got {sx}", file=sys.stderr)
        fails += 1
    if culled and sx == 0xD1:
        print("  4898 X>=0xD1 culls; s32 keeps 0xD1 (old hole)")

    if fails:
        print(f"{fails} mismatch(es)", file=sys.stderr)
        return 1
    print("type41: 4898 wrap-cull + speed-2 bias; not s32 / zeroed frac")
    return 0


if __name__ == "__main__":
    sys.exit(main())
