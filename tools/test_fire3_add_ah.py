#!/usr/bin/env python3
"""Check fire 3 Circular SAT = clamp + offset_hi as 8-bit ADD A,H.

zanac.asm 0x7396 / 0x73be: ADD A,H then LD (IX+01/02),A.
Init 0x733d/0x7349 seeds Y/X offset 0xC000 / 0xF600.
A signed s16 (clamp + (s16)off>>8) puts 0x38+0xC0 at -8; MSX SAT Y is 0xF8.

Usage (from zanac-md):
    python tools/test_fire3_add_ah.py
"""
from __future__ import annotations

import sys


def add_a_h(clamp: int, off: int) -> int:
    """Z80 ADD A,H: A = clamp, H = offset high byte."""
    return (clamp + ((off >> 8) & 0xFF)) & 0xFF


def signed_s16(clamp: int, off: int) -> int:
    """Port bug: s16 clamp + arithmetic off>>8."""
    hi = off >> 8
    if hi >= 0x8000:
        hi -= 0x10000
    if hi >= 0x80:
        hi -= 0x100
    return clamp + hi


# (clamp_y_or_x, offset_word, msx_sat)
CASES = (
    (0x38, 0xC000, 0xF8),  # ship high; first-frame Y
    (0x3F, 0xC000, 0xFF),
    (0x40, 0xC000, 0x00),
    (0xA0, 0xC000, 0x60),  # typical ship Y
    (0xA7, 0xC000, 0x67),
    (0x48, 0xF600, 0x3E),  # first-frame X at left clamp
    (0x78, 0xF600, 0x6E),
    (0xA7, 0xF600, 0x9D),
)


def main() -> int:
    fails = 0
    for clamp, off, want in CASES:
        got = add_a_h(clamp, off)
        old = signed_s16(clamp, off)
        mark = "ok" if got == want else "FAIL"
        if got != want:
            fails += 1
        note = ""
        if old != got:
            note = f" (s16 was {old})"
        print(
            f"  clamp {clamp:02X} off {off:04X} -> SAT {got:02X} "
            f"(want {want:02X}, {mark}){note}"
        )
    # The hole this PR closes: high-ship first frame must not be signed.
    if signed_s16(0x38, 0xC000) == add_a_h(0x38, 0xC000):
        print("FAIL: 0x38+0xC0 s16 and u8 match; no hole to prove", file=sys.stderr)
        fails += 1
    if add_a_h(0x38, 0xC000) != 0xF8:
        print("FAIL: 0x38+0xC0 is not 0xF8", file=sys.stderr)
        fails += 1
    if fails:
        print(f"{fails} mismatch(es)", file=sys.stderr)
        return 1
    print("fire3 ADD A,H: 8/8 match (0x38+0xC0 = 0xF8, not -8)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
