#!/usr/bin/env python3
"""Prove anim_sub 0x4912 writes table[index] then increments.

zanac.asm 0x4912: DEC +0D; NZ keep SAT. Else +0D=+0E, write
(sat_name,sat_color) at table[+0F], INC +0F, wrap +0F>=+10 to 0.

Type 35/80 0x84D1 (6 pairs). 849c sets +0D=1 +0E=4 +0F=1 +10=6,
then 84c9 JP 4898 same frame. Frame 0 is JP 0x48D0 bytes (0xD0,0x48)
and is never written: wrap sets +0F=0 and the next 84c9/8e30 clears.

The port incremented BEFORE the write, so the first visible SAT was
84d1[2] (med 0x20) and 84d1[1] lead 0x1C/0x8A was skipped.

Usage (from zanac-md):
    python tools/test_anim_4912.py
"""
from __future__ import annotations

import sys

# 0x84D1 bytes from zanac.asm (INC E / ADC / JR NZ decoded as data).
T35_SAT = (0xD0, 0x1C, 0x20, 0x24, 0x20, 0x1C)
T35_COL = (0x48, 0x8A, 0x8E, 0x8F, 0x8D, 0x89)

# 0x86F3 type 60. +0D=4 +0F=1 +10=0x0B.
T60_SAT = (0x00, 0x1C, 0x1C, 0x20, 0x20, 0x24, 0x24, 0x20, 0x20, 0x1C, 0x1C)
T60_COL = (0xC9, 0x86, 0x8F, 0x88, 0x8F, 0x89, 0x8F, 0x88, 0x89, 0x86, 0x8F)


def anim_sub(clock: int, idx: int, sats, cols, n: int, reload: int):
    """Return (clock, idx, sat_or_None, col_or_None). None = no SAT write."""
    if clock:
        clock -= 1
    if clock:
        return clock, idx, None, None
    clock = reload
    sat = sats[idx] if idx < n else None
    col = cols[idx] if idx < n else None
    idx += 1
    if idx >= n:
        idx = 0
    return clock, idx, sat, col


def old_port(clock: int, idx: int, sats, cols, n: int, reload: int):
    """Increment-then-display (the bug). Pre-place was table[idx] then this."""
    if clock:
        clock -= 1
    if not clock:
        clock = reload
        idx += 1
        if idx >= n:
            idx = 0
    sat = sats[idx] if idx < n else None
    col = cols[idx] if idx < n else None
    return clock, idx, sat, col


def run_until_wrap(clock0: int, idx0: int, sats, cols, n: int, reload: int,
                   fn, max_frames: int = 64):
    clock, idx = clock0, idx0
    seq = []
    for _ in range(max_frames):
        if idx == 0 and seq:
            break
        clock, idx, sat, col = fn(clock, idx, sats, cols, n, reload)
        seq.append((sat, col))
    return seq


def main() -> int:
    fails = 0

    msx = run_until_wrap(1, 1, T35_SAT, T35_COL, 6, 4, anim_sub)
    # Visible SAT while +0F != 0. Last write is table[5]; wrap idx=0.
    writes = [(s, c) for s, c in msx if s is not None]
    want_writes = [
        (0x1C, 0x8A),
        (0x20, 0x8E),
        (0x24, 0x8F),
        (0x20, 0x8D),
        (0x1C, 0x89),
    ]
    if writes != want_writes:
        print("FAIL 84d1 writes", writes, "want", want_writes, file=sys.stderr)
        fails += 1

    # First visible (including keep-SAT ticks) must be lead 0x1C/0x8A.
    first_vis = next((s, c) for s, c in msx if s is not None)
    if first_vis != (0x1C, 0x8A):
        print("FAIL 84d1 first write", first_vis, file=sys.stderr)
        fails += 1

    # Hold 4 frames on table[1] (write + 3 keep).
    lead_hold = 0
    for s, c in msx:
        if (s, c) == (0x1C, 0x8A) or (s is None and lead_hold):
            if s == 0x20:
                break
            lead_hold += 1
        elif s is not None:
            break
    if lead_hold != 4:
        print("FAIL 84d1 lead hold", lead_hold, "want 4", file=sys.stderr)
        fails += 1

    # Old port: clock=1 idx=1 then increment-before-write -> table[2].
    old = run_until_wrap(1, 1, T35_SAT, T35_COL, 6, 4, old_port)
    old_first = next((s, c) for s, c in old if s is not None)
    if old_first != (0x20, 0x8E):
        print("FAIL old-port probe", old_first, "expected med skip", file=sys.stderr)
        fails += 1
    if old_first == first_vis:
        print("FAIL old and 4912 first SAT match; bug not isolated", file=sys.stderr)
        fails += 1

    # Type 60: +0D=4, first three ticks write nothing.
    t60 = []
    clock, idx = 4, 1
    for _ in range(4):
        clock, idx, sat, col = anim_sub(clock, idx, T60_SAT, T60_COL, 11, 4)
        t60.append((sat, col))
    if t60[0] != (None, None) or t60[1] != (None, None) or t60[2] != (None, None):
        print("FAIL 86f3 early writes", t60[:3], file=sys.stderr)
        fails += 1
    if t60[3] != (0x1C, 0x86):
        print("FAIL 86f3 first write", t60[3], file=sys.stderr)
        fails += 1

    # Frame 0 SAT names must not be shot (0x28) or chip-as-0.
    if T35_SAT[0] != 0xD0 or T35_COL[0] != 0x48:
        print("FAIL 84d1[0]", T35_SAT[0], T35_COL[0], file=sys.stderr)
        fails += 1
    if T60_SAT[0] != 0x00:
        print("FAIL 86f3[0]", T60_SAT[0], file=sys.stderr)
        fails += 1

    if fails:
        print("%d FAIL" % fails, file=sys.stderr)
        return 1
    print("ok 84d1/86f3 anim_sub 0x4912 write-then-inc")
    return 0


if __name__ == "__main__":
    sys.exit(main())
