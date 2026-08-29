#!/usr/bin/env python3
"""Fire 4 +1b is type19 expire DEC per hit, not a 60-frame tick.

zanac.asm:
  7435  LD (IX+0x1b), 0x3C          ; init
  74a4  type := 0x83 then expire dispatch
  74ae  fire 4 -> 74e2
  74e2  ev24; DEC +1b; Z -> 7507
        +1b==0x1E -> SAT 0x20; ==0x0F -> color 0x81; else JP 7439

74e2 runs when 453E remaps type 3 -> 19, i.e. once per hit. 7439
(update) never touches +1b.

Usage (from zanac-md):
    python tools/test_fire4_74e2.py
"""
from __future__ import annotations

import sys


def rom_expire(hits: int, frames_after_first: int = 0) -> tuple[int, int | None, int | None, bool]:
    """Return (+1b, sat_at, col_at, dead) after `hits` expire calls.

    frames_after_first is ignored by ROM (update 7439 does not DEC +1b).
    sat_at / col_at are the SAT name / color written on the last DEC, else None.
    """
    n = 0x3C
    sat = None
    col = None
    dead = False
    for _ in range(hits):
        n -= 1
        if n == 0:
            dead = True
            break
        if n == 0x1E:
            sat = 0x20
        if n == 0x0F:
            col = 0x81
    _ = frames_after_first
    return n, sat, col, dead


def old_port(hits: int, frames_after_first: int) -> tuple[int, bool]:
    """Old port: first hit arms 0x3C; 7439-equivalent then DECs every frame."""
    if hits <= 0:
        return 0x3C, False
    n = 0x3C
    for _ in range(frames_after_first):
        n -= 1
        if n <= 0:
            return 0, True
    return n, False


def new_port(hits: int, frames_after_first: int = 0) -> tuple[int, int | None, int | None, bool]:
    """New port: spawn +1b=0x3C, DEC only on persist==2 hits."""
    return rom_expire(hits, frames_after_first)


def main() -> int:
    fails = 0

    n, sat, col, dead = rom_expire(1)
    if n != 0x3B or dead or sat is not None or col is not None:
        print(f"FAIL: 1 hit -> +1b {n:02X} sat={sat} col={col} dead={dead}", file=sys.stderr)
        fails += 1
    else:
        print("  1 hit: +1b=3B, SAT/col unchanged, alive")

    n, sat, col, dead = rom_expire(1, frames_after_first=60)
    if n != 0x3B or dead:
        print(f"FAIL: 1 hit + 60 frames must stay 3B, got {n:02X} dead={dead}", file=sys.stderr)
        fails += 1
    else:
        print("  1 hit + 60 idle frames: still 3B (7439 does not DEC)")

    old_n, old_dead = old_port(1, 60)
    if old_n != 0 or not old_dead:
        print(f"FAIL: old port 1 hit + 60 frames should die, got {old_n} dead={old_dead}", file=sys.stderr)
        fails += 1
    else:
        print("  old port 1 hit + 60 frames: dead (the hole)")

    n, sat, col, dead = rom_expire(0x3C - 0x1E)
    if n != 0x1E or sat != 0x20 or dead:
        print(f"FAIL: hits to 1E -> +1b {n:02X} sat={sat} dead={dead}", file=sys.stderr)
        fails += 1
    else:
        print("  30 hits: +1b=1E SAT 0x20")

    n, sat, col, dead = rom_expire(0x3C - 0x0F)
    if n != 0x0F or col != 0x81 or dead:
        print(f"FAIL: hits to 0F -> +1b {n:02X} col={col} dead={dead}", file=sys.stderr)
        fails += 1
    else:
        print("  45 hits: +1b=0F color 0x81")

    n, sat, col, dead = rom_expire(0x3C)
    if not dead or n != 0:
        print(f"FAIL: 60 hits must clear, +1b={n} dead={dead}", file=sys.stderr)
        fails += 1
    else:
        print("  60 hits: +1b=0 clear (7507)")

    n, sat, col, dead = new_port(1, 60)
    if n != 0x3B or dead:
        print(f"FAIL: new port 1 hit + 60 frames -> {n:02X} dead={dead}", file=sys.stderr)
        fails += 1
    else:
        print("  new port 1 hit + 60 frames: 3B (matches ROM)")

    if old_port(1, 60)[1] == new_port(1, 60)[3]:
        print("FAIL: old and new port agree on 1-hit+60f; no hole", file=sys.stderr)
        fails += 1

    if fails:
        print(f"{fails} mismatch(es)", file=sys.stderr)
        return 1
    print("fire4 74e2: +1b DEC per hit, not per frame")
    return 0


if __name__ == "__main__":
    sys.exit(main())
