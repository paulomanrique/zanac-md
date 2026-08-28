#!/usr/bin/env python3
"""Extract MSX title logo from zanac.asm.

Writes:
  res/logo_tiles.bin       — MD4 patterns (legacy / game)
  res/title_logo.png       — pre-composed 144×40 title bitmap
  src/data/title_logo.c    — row tables (legacy)
  inc/title_logo.h
"""
from __future__ import annotations

import argparse
import importlib.util
import struct
import sys
import zlib
from pathlib import Path

LOGO_BMP = (0x5D2C, 0x5EEF)
LOGO_COL = (0x5EF0, 0x5EFB)
LOGO_ROWS_ADDR = 0x4827
LOGO_SWIRL_ADDR = 0x5B59
LOGO_TILE_FIRST = 176
LOGO_TILE_COUNT = 61
LOGO_COLOR_TILES = 29
LOGO_HOME_ROW = 7
LOGO_HOME_COL = 5
LOGO_DRAW_ROWS = 5
LOGO_DRAW_COLS = 18
LOGO_ROW_OFFSET = 19  # draw_logo_row: table index = row * 19, not row * 25
TITLE_BAND0 = 2

TMS_RGB = [
    (0x00, 0x00, 0x00), (0x00, 0x00, 0x00), (0x21, 0xC8, 0x42), (0x5E, 0xDC, 0x78),
    (0x54, 0x55, 0xED), (0x7D, 0x76, 0xFC), (0xD4, 0x52, 0x4D), (0x42, 0xEB, 0xF5),
    (0xFC, 0x55, 0x54), (0xFF, 0x79, 0x78), (0xD4, 0xC1, 0x54), (0xE6, 0xCE, 0x80),
    (0x21, 0xB0, 0x3B), (0xC9, 0x5B, 0xBA), (0xCC, 0xCC, 0xCC), (0xFF, 0xFF, 0xFF),
]


def load_decompress():
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location("ems", here / "extract_map_scripts.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.parse_asm, mod.decompress, mod.screen2_to_md4


def md4_to_indices(data: bytes) -> list:
    out = []
    for row in range(8):
        v = (data[row * 4] << 24) | (data[row * 4 + 1] << 16) | (data[row * 4 + 2] << 8) | data[row * 4 + 3]
        for px in range(8):
            out.append((v >> ((7 - px) * 4)) & 0x0F)
    return out


def write_png(path: Path, width: int, height: int, indices: list):
    """Minimal 8-bit indexed PNG writer."""
    pal = []
    for rgb in TMS_RGB:
        pal.extend(rgb)
    pal.extend([0] * (256 - len(TMS_RGB)) * 3)

    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw.extend(indices[y * width:(y + 1) * width])

    def chunk(tag: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(tag + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 3, 0, 0, 0)
    idat = zlib.compress(bytes(raw), 9)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"PLTE", bytes(pal[:256 * 3]))
    png += chunk(b"IDAT", idat)
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


def c_u8_array(name: str, data, per=16) -> str:
    lines = ["const u8 %s[%d] = {" % (name, len(data))]
    for i in range(0, len(data), per):
        chunk = data[i:i + per]
        lines.append("    " + ", ".join("0x%02X" % b for b in chunk) + ",")
    lines.append("};")
    return "\n".join(lines)


def compose_logo_png(rows: bytes, charset_md: bytes, logo_md: bytes, out_png: Path):
    w = LOGO_DRAW_COLS * 8
    h = LOGO_DRAW_ROWS * 8
    canvas = [0] * (w * h)

    def blit(tid: int, dx: int, dy: int):
        if tid in (0x00, 0x20):
            return
        if tid >= LOGO_TILE_FIRST:
            off = (tid - LOGO_TILE_FIRST) * 32
            src = logo_md[off:off + 32]
        else:
            off = tid * 32
            src = charset_md[off:off + 32]
        if len(src) < 32:
            return
        px = md4_to_indices(src)
        for ty in range(8):
            for tx in range(8):
                x = dx + tx
                y = dy + ty
                if 0 <= x < w and 0 <= y < h:
                    canvas[y * w + x] = px[ty * 8 + tx]

    for ri in range(LOGO_DRAW_ROWS):
        off = ri * LOGO_ROW_OFFSET
        strip = rows[off:off + LOGO_DRAW_COLS]
        for ci, tid in enumerate(strip):
            blit(tid, ci * 8, ri * 8)

    write_png(out_png, w, h, canvas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asm", default=str(Path(__file__).resolve().parents[1].parent / "zanac-re" / "source" / "zanac.asm"))
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1]))
    args = ap.parse_args()
    asm = Path(args.asm)
    out = Path(args.out)
    if not asm.is_file():
        alt = Path(__file__).resolve().parents[1] / ".." / "zanac-re" / "source" / "zanac.asm"
        if alt.is_file():
            asm = alt.resolve()
        else:
            sys.exit("asm not found: %s" % args.asm)

    parse_asm, decompress, screen2_to_md4 = load_decompress()
    rom = parse_asm(asm)
    bmp = decompress(rom, LOGO_BMP[0], LOGO_BMP[1])
    col = decompress(rom, LOGO_COL[0], LOGO_COL[1])
    print("logo bitmap %d bytes, colors %d bytes" % (len(bmp), len(col)))

    full_bmp = bytearray(256 * 8)
    full_col = bytearray(256 * 8)
    for i in range(LOGO_TILE_COUNT):
        ti = LOGO_TILE_FIRST + i
        full_bmp[ti * 8:(ti + 1) * 8] = bmp[i * 8:(i + 1) * 8]
        ci = (i % LOGO_COLOR_TILES) * 8
        full_col[ti * 8:(ti + 1) * 8] = col[ci:ci + 8]

    all_tiles = screen2_to_md4(bytes(full_bmp), bytes(full_col))
    logo_md = all_tiles[LOGO_TILE_FIRST * 32:(LOGO_TILE_FIRST + LOGO_TILE_COUNT) * 32]

    rows = bytes(rom[LOGO_ROWS_ADDR:LOGO_ROWS_ADDR + 125])
    swirl = bytes(rom[LOGO_SWIRL_ADDR:LOGO_SWIRL_ADDR + 56])

    res = out / "res"
    src_data = out / "src" / "data"
    inc = out / "inc"
    res.mkdir(parents=True, exist_ok=True)
    src_data.mkdir(parents=True, exist_ok=True)
    inc.mkdir(parents=True, exist_ok=True)

    (res / "logo_tiles.bin").write_bytes(logo_md)

    charset_path = res / "charset_tiles.bin"
    if charset_path.is_file():
        charset_md = charset_path.read_bytes()
    else:
        charset_md = b"\x00" * (256 * 32)

    compose_logo_png(rows, charset_md, logo_md, res / "title_logo.png")

    hdr = [
        "#ifndef TITLE_LOGO_H",
        "#define TITLE_LOGO_H",
        "",
        "#include <genesis.h>",
        "",
        "/* Generated by tools/extract_logo.py from zanac.asm. */",
        "#define LOGO_TILE_MSX_FIRST  0x%02X" % LOGO_TILE_FIRST,
        "#define LOGO_TILE_COUNT      %d" % LOGO_TILE_COUNT,
        "#define LOGO_ROW_STRIDE      25",
        "#define LOGO_ROW_COUNT       5",
        "#define LOGO_DRAW_COLS       %d" % LOGO_DRAW_COLS,
        "#define LOGO_DRAW_ROWS       %d" % LOGO_DRAW_ROWS,
        "#define LOGO_PX_X            %d" % (LOGO_HOME_COL * 8),
        "#define LOGO_PX_Y            %d" % ((TITLE_BAND0 + LOGO_HOME_ROW) * 8),
        "",
        "extern const u8 logo_tile_rows[LOGO_ROW_COUNT * LOGO_ROW_STRIDE];",
        "extern const u8 logo_swirl_path[56];",
        "",
        "#endif",
        "",
    ]
    (inc / "title_logo.h").write_text("\n".join(hdr), encoding="utf-8")

    c = [
        '#include "title_logo.h"',
        "",
        c_u8_array("logo_tile_rows", rows),
        "",
        c_u8_array("logo_swirl_path", swirl),
        "",
    ]
    (src_data / "title_logo.c").write_text("\n".join(c), encoding="utf-8")

    print("wrote %s (%d bytes)" % (res / "logo_tiles.bin", len(logo_md)))
    print("wrote %s" % (res / "title_logo.png"))
    print("wrote %s, %s" % (inc / "title_logo.h", src_data / "title_logo.c"))


if __name__ == "__main__":
    main()
