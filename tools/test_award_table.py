#!/usr/bin/env python3
"""Check score_award_table 0x4AEA against src/player.c k_award.

The 21 little-endian BCD triplets are copied from zanac.asm (Zanac v1
SHA1 46e9ed7b7f6dfda8eee266476c9ebc4dd9d8fcc2). idx 20 is 00 00 20 =
200000; a u16 table stored 2000.

Usage (from zanac-md):
    python tools/test_award_table.py
"""
from __future__ import annotations

import sys

# 0x4AEA..0x4B28 inclusive (21 * 3). Last triplet is idx 20.
SCORE_AWARD_TABLE = bytes((
    0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x06, 0x00, 0x00, 0x10, 0x00, 0x00,
    0x17, 0x00, 0x00, 0x20, 0x00, 0x00, 0x30, 0x00, 0x00, 0x50, 0x00, 0x00,
    0x80, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x02, 0x00, 0x00, 0x04, 0x00,
    0x00, 0x08, 0x00, 0x00, 0x10, 0x00, 0x00, 0x15, 0x00, 0x00, 0x20, 0x00,
    0x00, 0x30, 0x00, 0x00, 0x40, 0x00, 0x00, 0x50, 0x00, 0x00, 0x00, 0x01,
    0x00, 0x00, 0x20,
))

# src/player.c k_award after the u32 fix.
K_AWARD = (
    0, 1, 6, 10, 17, 20, 30, 50, 80, 100,
    200, 400, 800, 1000, 1500, 2000, 3000, 4000, 5000, 10000, 200000,
)


def bcd_byte(x: int) -> int:
    return ((x >> 4) * 10) + (x & 0x0F)


def decode_triplet(lo: int, mid: int, hi: int) -> int:
    return bcd_byte(lo) + bcd_byte(mid) * 100 + bcd_byte(hi) * 10000


def main() -> int:
    assert len(SCORE_AWARD_TABLE) == 63
    fails = 0
    for i in range(21):
        lo, mid, hi = SCORE_AWARD_TABLE[i * 3 : i * 3 + 3]
        got = decode_triplet(lo, mid, hi)
        want = K_AWARD[i]
        mark = "ok" if got == want else "FAIL"
        if got != want:
            fails += 1
        print(f"  idx {i:2d}: {lo:02X} {mid:02X} {hi:02X} -> {got} ({mark}, k_award={want})")
    if K_AWARD[20] <= 0xFFFF:
        print("FAIL: idx 20 still fits in u16; expected 200000", file=sys.stderr)
        fails += 1
    if fails:
        print(f"{fails} mismatch(es)", file=sys.stderr)
        return 1
    print("score_award_table: 21/21 match (idx 20 = 200000)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
