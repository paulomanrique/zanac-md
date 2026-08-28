#!/usr/bin/env python3
"""Check the ship movement model against the MSX velocity table.

Re-reads vel_dir_table straight from zanac.asm (same parser as
extract_vel_dir.py) and replays the arithmetic that src/player.c performs, so a
mistake in the 8.8 accumulation, the selector mapping or the clamps shows up as
a failing assertion rather than needing a run in an emulator.

Usage (from zanac-md):
    python tools/test_ship_speed.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_vel_dir import (  # noqa: E402
    SHIP_SPEED, VEL_DIR_TABLE, XVEL_LEN, XVEL_TABLE, parse_db_bytes, s16le,
)

FRAMES = 600
OLD_SPEED = 2          # the integer model this replaces

# inc/mode.h
SHIP_W = SHIP_H = 16
MODE_BAR_COL = 24
ORIGINAL = dict(name="ORIGINAL", min_x=0x28, min_y=0x1E,
                max_x=MODE_BAR_COL * 8 - SHIP_W, max_y=0xB8)
ZANAC_MD = dict(name="ZANAC_MD", min_x=0, min_y=0,
                max_x=320 - SHIP_W, max_y=224 - SHIP_H)

DIR_NAME = {7: "right", 1: "left", 3: "down", 5: "up",
            6: "down-right", 0: "down-left", 8: "up-right", 2: "up-left"}
CARDINALS = (7, 1, 3, 5)
DIAGONALS = (6, 0, 8, 2)


def step_axis(pos: int, frac: int, vel: int, lo: int, hi: int) -> tuple[int, int]:
    """src/player.c step_axis()."""
    acc = (pos << 8) | frac
    acc += vel
    pos = acc >> 8
    if pos < lo:
        return lo, 0
    if pos > hi:
        return hi, 0
    return pos, acc & 0xFF


def selector(up: bool, down: bool, left: bool, right: bool) -> int:
    """src/player.c E10C: base 4, UP +1, DOWN -1, LEFT -3, RIGHT +3."""
    s = 4 + (1 if up else 0) - (1 if down else 0) \
          - (3 if left else 0) + (3 if right else 0)
    return max(0, min(8, s))


def main() -> int:
    asm = Path("../zanac-re/source/zanac.asm")
    if not asm.is_file():
        print(f"error: no asm at {asm}", file=sys.stderr)
        return 2
    rom, _, _ = parse_db_bytes(asm)
    vy = [s16le(rom, VEL_DIR_TABLE + d * 4 + 0) for d in range(16)]
    vx = [s16le(rom, VEL_DIR_TABLE + d * 4 + 2) for d in range(16)]
    sel_dir = [rom[XVEL_TABLE + i] for i in range(XVEL_LEN)]

    fails = []

    # 1. Selector mapping: each of the 8 held-direction combinations must move
    #    the ship the way the joystick points.
    print("selector -> direction")
    combos = {
        7: (False, False, False, True), 1: (False, False, True, False),
        3: (False, True, False, False), 5: (True, False, False, False),
        6: (False, True, False, True), 0: (False, True, True, False),
        8: (True, False, False, True), 2: (True, False, True, False),
    }
    want_sign = {
        "right": (1, 0), "left": (-1, 0), "down": (0, 1), "up": (0, -1),
        "down-right": (1, 1), "down-left": (-1, 1),
        "up-right": (1, -1), "up-left": (-1, -1),
    }
    for sel, (u, d, l, r) in combos.items():
        assert selector(u, d, l, r) == sel, f"selector math: expected {sel}"
        dirx = sel_dir[sel]
        gx, gy = (1 if vx[dirx] > 0 else -1 if vx[dirx] < 0 else 0,
                  1 if vy[dirx] > 0 else -1 if vy[dirx] < 0 else 0)
        name = DIR_NAME[sel]
        ok = (gx, gy) == want_sign[name]
        print(f"  sel {sel} ({name:10s}) -> dir {dirx:2d} "
              f"vx={vx[dirx]:5d} vy={vy[dirx]:5d}  {'ok' if ok else 'MISMATCH'}")
        if not ok:
            fails.append(f"selector {sel} ({name}) moves the wrong way")

    # 2. Travelled distance over FRAMES frames in an unbounded field: every
    #    direction must cover the same ground, so diagonals stop being faster.
    print(f"\ndisplacement over {FRAMES} frames (no clamping)")
    big = 10 ** 6
    dist = {}
    for sel in CARDINALS + DIAGONALS:
        dirx = sel_dir[sel]
        x = y = 0
        fx = fy = 0
        for _ in range(FRAMES):
            y, fy = step_axis(y, fy, vy[dirx] * SHIP_SPEED, -big, big)
            x, fx = step_axis(x, fx, vx[dirx] * SHIP_SPEED, -big, big)
        dist[sel] = math.hypot(x, y)
        print(f"  sel {sel} ({DIR_NAME[sel]:10s}) dx={x:6d} dy={y:6d} "
              f"|d|={dist[sel]:9.2f}  {dist[sel] / FRAMES:.4f} px/frame")

    lo, hi = min(dist.values()), max(dist.values())
    spread = (hi - lo) / hi * 100.0
    print(f"\n  spread across 8 directions: {spread:.2f}% "
          f"({lo / FRAMES:.4f}..{hi / FRAMES:.4f} px/frame)")
    if spread > 1.0:
        fails.append(f"speed varies by {spread:.2f}% across directions")

    card = max(dist[s] for s in CARDINALS)
    diag = max(dist[s] for s in DIAGONALS)
    print(f"  fastest cardinal {card / FRAMES:.4f} px/frame, "
          f"fastest diagonal {diag / FRAMES:.4f} px/frame "
          f"({(diag / card - 1) * 100:+.2f}%)")
    if diag > card * 1.01:
        fails.append(f"diagonal is still {(diag / card - 1) * 100:.1f}% faster")
    old_ratio = math.hypot(OLD_SPEED, OLD_SPEED) / OLD_SPEED
    print(f"  previous integer model was {(old_ratio - 1) * 100:+.1f}% "
          f"on the diagonal ({OLD_SPEED} vs {OLD_SPEED * old_ratio:.3f} px/frame)")

    # 3. Clamps: hold each direction long enough to pin the ship to every edge
    #    of both playfields and confirm it stays inside.
    print("\nplayfield limits")
    for mode in (ORIGINAL, ZANAC_MD):
        for sel in combos:
            dirx = sel_dir[sel]
            x, y = 120, 100
            fx = fy = 0
            for _ in range(FRAMES):
                y, fy = step_axis(y, fy, vy[dirx] * SHIP_SPEED,
                                  mode["min_y"], mode["max_y"])
                x, fx = step_axis(x, fx, vx[dirx] * SHIP_SPEED,
                                  mode["min_x"], mode["max_x"])
            inside = (mode["min_x"] <= x <= mode["max_x"]
                      and mode["min_y"] <= y <= mode["max_y"])
            if not inside:
                fails.append(f"{mode['name']} sel {sel} left the field at "
                             f"({x},{y})")
        print(f"  {mode['name']:8s} x {mode['min_x']}..{mode['max_x']}, "
              f"y {mode['min_y']}..{mode['max_y']}: all 8 directions stay inside")

    print()
    if fails:
        for f in fails:
            print(f"FAIL: {f}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
