#!/usr/bin/env python3
"""Check res/charset_ct.bin HUD rows against the decoded Zanac v1 CT.

CT source: gfx_charset_colors 0x64D3, decompress_block 0x5CCF, one 2048-byte
bank (load_charset_sprites 0x5CA5 copies it to VRAM 0x2000/0x2800/0x3000).
Does not need a ROM or zanac.asm.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CT_PATH = ROOT / "res" / "charset_ct.bin"
TILES_PATH = ROOT / "res" / "charset_tiles.bin"

# TMS (FG<<4)|BG, 0 = transparent. Verified from v1 ROM SHA1
# 46e9ed7b7f6dfda8eee266476c9ebc4dd9d8fcc2.
HUD_CT = {
    0x01: bytes([0xF0, 0xF0, 0xE0, 0xE0, 0xE0, 0xE0, 0xE0, 0xE0]),
    0x02: bytes([0xF0, 0xF0, 0xE0, 0xE0, 0xE0, 0xE0, 0xE0, 0xE0]),
    0x03: bytes([0xE0] * 8),
    0x20: bytes([0x70] * 8),
}
HUD_CT.update({t: bytes([0x90] * 8) for t in range(0x30, 0x3A)})
HUD_CT.update({t: bytes([0x70] * 8) for t in range(0x41, 0x5B)})


def row_nibs(tiles: bytes, tid: int, row: int) -> list[int]:
    off = tid * 32 + row * 4
    packed = int.from_bytes(tiles[off:off + 4], "big")
    return [(packed >> ((7 - px) * 4)) & 0xF for px in range(8)]


def main() -> int:
    ct = CT_PATH.read_bytes()
    tiles = TILES_PATH.read_bytes()
    if len(ct) != 2048:
        print("charset_ct.bin size %d, expected 2048" % len(ct), file=sys.stderr)
        return 1
    if len(tiles) != 8192:
        print("charset_tiles.bin size %d, expected 8192" % len(tiles), file=sys.stderr)
        return 1

    bad = 0
    for tid, expect in sorted(HUD_CT.items()):
        got = ct[tid * 8:tid * 8 + 8]
        if got != expect:
            print("CT tile 0x%02X: %s != %s" %
                  (tid, got.hex(), expect.hex()), file=sys.stderr)
            bad += 1
            continue
        for row in range(8):
            fg, bg = expect[row] >> 4, expect[row] & 0x0F
            for n in row_nibs(tiles, tid, row):
                if n != fg and n != bg:
                    print("tile 0x%02X row %d nibble %X not FG %X / BG %X" %
                          (tid, row, n, fg, bg), file=sys.stderr)
                    bad += 1
                    break
    if bad:
        print("%d HUD CT / bake mismatches" % bad, file=sys.stderr)
        return 1
    print("HUD CT ok: bars 01/02 F then E, 03 gray, space/A-Z cyan, digits lt-red")
    return 0


if __name__ == "__main__":
    sys.exit(main())
