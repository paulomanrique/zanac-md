#!/usr/bin/env python3
"""Extract the MSX late-stage background tiles from zanac.asm into the MD port.

Reads DB lines (load address in the trailing comment), never copies the asm
wholesale. Same parser as tools/extract_map_scripts.py / tools/extract_sound.py.

`load_bg_tiles` (0x5C60) overwrites part of the charset once the round number is
a multiple of 8, so round 8 does not look like round 1. It decompresses four
RLE blocks (kb/data/gfx_bg_late_*.md, sprint 0007) through decompress_block
(0x5CCF), each one written to all three SCREEN2 thirds:

  0x666F gfx_bg_late_bitmap_a -> PGT 0x00B8 / 0x08B8 / 0x10B8   20 tiles @ 23
  0x68A9 gfx_bg_late_colors_a -> CT  0x20B8 / 0x28B8 / 0x30B8   20 tiles @ 23
  0x6705 gfx_bg_late_bitmap_b -> PGT 0x02D8 / 0x0AD8 / 0x12D8   67 tiles @ 91
  0x68DD gfx_bg_late_colors_b -> CT  0x22D8 / 0x2AD8 / 0x32D8   69 tiles @ 91

Byte offset 0x00B8 = 184 = tile 23 and 0x02D8 = 728 = tile 91.  Block B carries
two more colour tiles than pattern tiles, so tiles 158 and 159 keep their
charset pattern and only change colour -- that is what the hardware does, and it
is reproduced here.

The Mega Drive has no colour table: a 4bpp tile bakes its colours in.  So each
output tile is (late bitmap or charset bitmap) x (late colour), one CT byte per
pixel row, high nibble foreground and low nibble background -- exactly what
res/charset_tiles.bin already is for the base charset.

Output: res/bg_late.bin, 89 tiles x 32 bytes, block A then block B.

Usage (from zanac-md):
    python tools/extract_bg_late.py --asm ../zanac-re/source/zanac.asm
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROM_END = 0xC000

BITMAP_A = 0x666F
COLORS_A = 0x68A9
BITMAP_B = 0x6705
COLORS_B = 0x68DD
CHARSET_BITMAP = 0x5EFC

TILE_A = 23        # PGT/CT byte offset 0x00B8 / 8
TILE_B = 91        # PGT/CT byte offset 0x02D8 / 8

DB_RE = re.compile(r"^\s+DB\s+(.+);\s*0x([0-9A-Fa-f]{4})", re.I)
HEX_RE = re.compile(r"0x([0-9A-Fa-f]{1,2})\b", re.I)


def parse_asm(path: Path) -> bytearray:
    rom = bytearray(ROM_END)
    n_db = 0
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = DB_RE.match(line)
            if not m:
                continue
            addr = int(m.group(2), 16)
            for i, h in enumerate(HEX_RE.findall(m.group(1))):
                a = addr + i
                if 0 <= a < ROM_END:
                    rom[a] = int(h, 16) & 0xFF
            n_db += 1
    print("parsed DB=%d" % n_db)
    return rom


def decompress(rom: bytearray, src: int) -> bytes:
    """decompress_block 0x5CCF.

    D is the escape byte (0xFF at entry), E bit 0 selects the unit encoding.
      <b>            b != D            one unit
      unit           E bit0 clear      write the byte once
      unit           E bit0 set        the byte is followed by a repeat count
      D <b>          b != D            toggle E bit 0, re-read b (0x5CEC DEC HL)
      D D 00         end of block                            (0x5CFE)
      D D 01 <n>     D := n                                  (0x5D02)
      D D 02 <c> ..  repeat a [count][units] group c times    (0x5D06)
    """
    hl = src
    out = bytearray()
    e = 0
    d = 0xFF

    def unit(a: int) -> None:
        nonlocal hl
        if e & 1:
            n = rom[hl]
            hl += 1
        else:
            n = 1
        out.extend([a] * n)

    while True:
        a = rom[hl]
        hl += 1
        if a != d:
            unit(a)
            continue
        a = rom[hl]
        hl += 1
        if a != d:
            hl -= 1
            e ^= 1
            continue
        sel = rom[hl]
        hl += 1
        if sel == 0x00:
            return bytes(out)
        if sel == 0x01:
            d = rom[hl]
            hl += 1
            continue
        if sel != 0x02:
            sys.exit("unknown dispatch %#04x at %#06x" % (sel, hl - 1))
        c = rom[hl]
        hl += 1
        start = hl
        for _ in range(c):
            hl = start
            b = rom[hl]
            hl += 1
            for _ in range(b):
                a2 = rom[hl]
                hl += 1
                unit(a2)


def to_md4(bitmap: bytes, colors: bytes) -> bytes:
    """SCREEN2 1bpp pattern + one CT byte per pixel row -> MD 4bpp."""
    out = bytearray()
    for r in range(8):
        bits = bitmap[r]
        ct = colors[r]
        fg, bg = ct >> 4, ct & 0x0F
        for p in range(0, 8, 2):
            hi = fg if (bits >> (7 - p)) & 1 else bg
            lo = fg if (bits >> (6 - p)) & 1 else bg
            out.append((hi << 4) | lo)
    return bytes(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asm", default=r"C:\Users\Filipe\GameMakerProjects\Zanac\zanac-re\source\zanac.asm")
    ap.add_argument("--out", default=r"C:\Users\Filipe\GitRepos\zanac-md")
    args = ap.parse_args()
    asm = Path(args.asm)
    out = Path(args.out)
    if not asm.is_file():
        sys.exit("asm not found: %s" % asm)

    print("ASM", asm, "size", asm.stat().st_size)
    rom = parse_asm(asm)

    charset = decompress(rom, CHARSET_BITMAP)
    if len(charset) != 2048:
        sys.exit("charset bitmap decompressed to %d bytes, expected 2048" % len(charset))

    blob = bytearray()
    for name, bm_src, ct_src, first in (
        ("a", BITMAP_A, COLORS_A, TILE_A),
        ("b", BITMAP_B, COLORS_B, TILE_B),
    ):
        bm = decompress(rom, bm_src)
        ct = decompress(rom, ct_src)
        n_bm, n_ct = len(bm) // 8, len(ct) // 8
        print("block %s: bitmap %d tiles, colors %d tiles, first tile %d"
              % (name, n_bm, n_ct, first))
        for i in range(n_ct):
            tid = first + i
            # Beyond the pattern block the CT keeps going: those tiles stay on
            # their charset pattern and only change colour (0x5C9A onward
            # writes 552 colour bytes against 536 pattern bytes).
            pat = bm[i * 8:i * 8 + 8] if i < n_bm else charset[tid * 8:tid * 8 + 8]
            blob += to_md4(pat, ct[i * 8:i * 8 + 8])

    dst = out / "res" / "bg_late.bin"
    dst.write_bytes(bytes(blob))
    print("wrote %s: %d bytes (%d tiles)" % (dst, len(blob), len(blob) // 32))


if __name__ == "__main__":
    main()
