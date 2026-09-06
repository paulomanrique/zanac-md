#!/usr/bin/env python3
"""Extract Zanac MSX map-scripts + level blob from zanac.asm into the MD port.

Reads DB/DW lines (load address in the trailing comment), never copies the
asm wholesale. Operand lengths match zanac-re/tools/decode_mapscript2.py.

Usage (from zanac-md):
    python tools/extract_map_scripts.py
    python tools/extract_map_scripts.py --asm PATH --out .
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PTR_TABLE = 0x945C
SCRIPTS_LO = 0xA65C
SCRIPTS_HI = 0xB7A5  # inclusive terminal byte
BLOB_LO = 0x9B64     # tile-col region1 through region2
BLOB_HI = 0xBE26     # inclusive
CHARSET_BMP = (0x5EFC, 0x64D2)
CHARSET_COL = (0x64D3, 0x666E)  # gfx_charset_colors, 412-byte RLE -> 2048
SPRITE_RLE = (0x6976, 0x70B8)
SPAWN_TIMERS = 0xBE76
SPAWN_PAIRS = 0xBE7C
SPAWN_PAIR_LEN = 80
SPAWN_TYPES = 0xBECC
SPAWN_TYPE_LEN = 96
ROM_BASE = 0x4000
ROM_END = 0xC000  # exclusive

KNOWN_PTRS = [0xB7A5, 0xB61A, 0xB3FD, 0xB1DE, 0xAF1F, 0xAD61, 0xAAEF, 0xA751, 0xA65C]

CMD_NAME = {
    0: "spawn_ctrl", 1: "place_tiles", 2: "col_groups", 3: "tile_copy",
    4: "col_groups+", 5: "stream_slots", 6: "set_E71C",
    7: "disable_grps", 8: "idol_tbl/BANNER", 9: "SCRIPT_JUMP",
    0xA: "vram_glyph", 0xB: "wide_slot", 0xC: "spawn_pace",
}

DB_RE = re.compile(r"^\s+DB\s+(.+);\s*0x([0-9A-Fa-f]{4})", re.I)
DW_RE = re.compile(r"^\s+DW\s+(.+);\s*0x([0-9A-Fa-f]{4})", re.I)
HEX_RE = re.compile(r"0x([0-9A-Fa-f]{1,2})\b", re.I)
HEX16_RE = re.compile(r"0x([0-9A-Fa-f]{1,4})\b", re.I)

# TMS9918 palette (approx sRGB)
TMS_RGB = [
    (0x00, 0x00, 0x00), (0x00, 0x00, 0x00), (0x21, 0xC8, 0x42), (0x5E, 0xDC, 0x78),
    (0x54, 0x55, 0xED), (0x7D, 0x76, 0xFC), (0xD4, 0x52, 0x4D), (0x42, 0xEB, 0xF5),
    (0xFC, 0x55, 0x54), (0xFF, 0x79, 0x78), (0xD4, 0xC1, 0x54), (0xE6, 0xCE, 0x80),
    (0x21, 0xB0, 0x3B), (0xC9, 0x5B, 0xBA), (0xCC, 0xCC, 0xCC), (0xFF, 0xFF, 0xFF),
]


def parse_asm(path: Path) -> bytearray:
    rom = bytearray(0xC000)
    filled = bytearray(0xC000)  # 1 if a byte was written
    n_db = n_dw = 0
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = DB_RE.match(line)
            if m:
                addr = int(m.group(2), 16)
                vals = [int(h, 16) for h in HEX_RE.findall(m.group(1))]
                for i, v in enumerate(vals):
                    a = addr + i
                    if 0 <= a < 0xC000:
                        rom[a] = v & 0xFF
                        filled[a] = 1
                n_db += 1
                continue
            m = DW_RE.match(line)
            if m:
                addr = int(m.group(2), 16)
                vals = [int(h, 16) for h in HEX16_RE.findall(m.group(1))]
                for i, v in enumerate(vals):
                    a = addr + i * 2
                    if 0 <= a + 1 < 0xC000:
                        rom[a] = v & 0xFF
                        rom[a + 1] = (v >> 8) & 0xFF
                        filled[a] = filled[a + 1] = 1
                n_dw += 1
    # coverage in cart window
    hit = sum(1 for a in range(ROM_BASE, ROM_END) if filled[a])
    print("parsed DB lines=%d DW lines=%d  cart bytes filled=%d/%d" %
          (n_db, n_dw, hit, ROM_END - ROM_BASE))
    missing = [a for a in range(BLOB_LO, BLOB_HI + 1) if not filled[a]]
    if missing:
        print("WARNING: %d unfilled bytes in blob, first=0x%04X" %
              (len(missing), missing[0]))
    return rom


def at(rom, a, n=1):
    return bytes(rom[a:a + n])


def w(rom, a):
    return rom[a] | (rom[a + 1] << 8)


def cmd5_len(rom, p):
    n = rom[p]
    q = p + 1
    for _ in range(n):
        b0 = rom[q]
        q += 5 if (b0 & 0x08) else 4
    return q - p


def op_len(rom, cmd, body):
    nib = cmd & 0xF
    if nib == 0:
        op = rom[body]
        if op & 0x04:
            n = rom[body + 1]
            return 1 + 1 + 3 * n, "E12D=%02X +place N=%d" % (op, n)
        return 1, "E12D=%02X" % op
    if nib == 1:
        n = rom[body]
        return 1 + 3 * n, "N=%d" % n
    if nib == 2:
        n = rom[body]
        return 1 + 5 * n, "N=%d" % n
    if nib == 3:
        n = rom[body]
        return 1 + 2 * n, "N=%d" % n
    if nib == 4:
        n = rom[body]
        return 1 + 5 * n, "N=%d" % n
    if nib == 5:
        L = cmd5_len(rom, body)
        return L, "N=%d" % rom[body]
    if nib == 6:
        return 1, "E71C=%02X" % rom[body]
    if nib == 7:
        n = rom[body]
        return 1 + n, "N=%d" % n
    if nib == 8:
        return 2, "idol_tbl=0x%04X" % w(rom, body)
    if nib == 9:
        return 2, "-> 0x%04X" % w(rom, body)
    if nib == 0xA:
        return 1, "fill=%02X" % rom[body]
    if nib == 0xB:
        return 7, "E155..=%s" % at(rom, body, 4).hex()
    if nib == 0xC:
        v = rom[body]
        s = v - 256 if v & 0x80 else v
        return 1, "nudge=%+d" % s
    raise ValueError("bad nibble %X at body 0x%04X" % (nib, body))


def parse_script(rom, start, limit=500):
    p = start
    last_row = -1
    out = []
    for _ in range(limit):
        row = w(rom, p)
        if row >= 0x8000:
            break
        cmd = rom[p + 2]
        body = p + 3
        L, note = op_len(rom, cmd, body)
        raw = bytes(rom[body:body + L])
        out.append((p, row, cmd, note, raw))
        if (cmd & 0xF) == 9:
            break
        p = body + L
        if row < last_row:
            raise ValueError("row desync 0x%04X < 0x%04X at 0x%04X" %
                             (row, last_row, out[-1][0]))
        last_row = row
    return out


def decompress(rom, start, end_incl, max_out=8192):
    """Zanac custom RLE (decompress_block 0x5CCF)."""
    hl = start
    special = 0xFF
    mode = 0  # 0=copy, 1=repeat
    out = bytearray()

    def read_b():
        nonlocal hl
        if hl > end_incl + 64:
            raise ValueError("overread at 0x%04X" % hl)
        b = rom[hl]
        hl += 1
        return b

    def unit(val):
        nonlocal hl
        if mode == 0:
            out.append(val)
            return
        cnt = read_b()
        if cnt == 0:
            return
        out.extend([val] * cnt)

    guard = 0
    while guard < 100000 and len(out) < max_out:
        guard += 1
        b = read_b()
        if b != special:
            unit(b)
            continue
        b2 = read_b()
        if b2 != special:
            # single special: toggle mode; unread b2
            hl -= 1
            mode ^= 1
            continue
        cmd = read_b()
        if cmd == 0:
            break
        if cmd == 1:
            special = read_b()
            continue
        if cmd == 2:
            m = read_b()
            saved = hl
            for _i in range(m):
                hl = saved
                n = read_b()
                for _j in range(n):
                    val = read_b()
                    unit(val)
            continue
        raise ValueError("bad rle cmd %d at 0x%04X" % (cmd, hl))
    return bytes(out)


def screen2_to_md4(bmp: bytes, col: bytes) -> bytes:
    """256 SCREEN2 tiles -> 256 SGDK 4bpp tiles (32 bytes each)."""
    tiles = bytearray(256 * 32)
    for t in range(256):
        for row in range(8):
            bits = bmp[t * 8 + row]
            cv = col[t * 8 + row]
            fg, bg = cv >> 4, cv & 0x0F
            packed = 0
            for px in range(8):
                pix = fg if (bits & (0x80 >> px)) else bg
                packed = (packed << 4) | pix
            off = t * 32 + row * 4
            tiles[off] = (packed >> 24) & 0xFF
            tiles[off + 1] = (packed >> 16) & 0xFF
            tiles[off + 2] = (packed >> 8) & 0xFF
            tiles[off + 3] = packed & 0xFF
    return bytes(tiles)


def c_u8_array(name: str, data: bytes, per=16) -> str:
    lines = ["const u8 %s[%d] = {" % (name, len(data))]
    for i in range(0, len(data), per):
        chunk = data[i:i + per]
        lines.append("    " + ", ".join("0x%02X" % b for b in chunk) + ",")
    lines.append("};")
    return "\n".join(lines)


def c_u16_array(name: str, vals) -> str:
    body = ", ".join("0x%04X" % v for v in vals)
    return "const u16 %s[%d] = { %s };" % (name, len(vals), body)


def emit(out_root: Path, rom: bytearray, report: list):
    blob = bytes(rom[BLOB_LO:BLOB_HI + 1])
    ptrs = [w(rom, PTR_TABLE + i * 2) for i in range(9)]
    script_lens = []
    for i in range(9):
        start = ptrs[i]
        recs = parse_script(rom, start)
        if recs:
            last_p, last_row, last_cmd, last_note, last_raw = recs[-1]
            end = last_p + 3 + len(last_raw)  # exclusive
        else:
            end = start
        script_lens.append(end - start)

    res = out_root / "res"
    src_data = out_root / "src" / "data"
    inc = out_root / "inc"
    res.mkdir(parents=True, exist_ok=True)
    src_data.mkdir(parents=True, exist_ok=True)
    inc.mkdir(parents=True, exist_ok=True)

    (res / "map_blob.bin").write_bytes(blob)
    report.append("wrote %s  %d bytes  MSX 0x%04X-0x%04X" %
                  (res / "map_blob.bin", len(blob), BLOB_LO, BLOB_HI))

    charset_ok = False
    try:
        bmp = decompress(rom, CHARSET_BMP[0], CHARSET_BMP[1], max_out=4096)
        col = decompress(rom, CHARSET_COL[0], CHARSET_COL[1], max_out=4096)
        report.append("charset bitmap decompressed %d bytes (expect 2048)" % len(bmp))
        report.append("charset colors  decompressed %d bytes (expect 2048)" % len(col))
        if len(bmp) >= 2048 and len(col) >= 2048:
            tiles = screen2_to_md4(bmp[:2048], col[:2048])
            (res / "charset_tiles.bin").write_bytes(tiles)
            # One SCREEN2 bank. load_charset_sprites 0x5CA5 unpacks this
            # same stream to VRAM 0x2000, 0x2800, 0x3000 (identical).
            (res / "charset_ct.bin").write_bytes(col[:2048])
            charset_ok = True
            report.append("wrote %s  %d bytes (256 MD 4bpp tiles)" %
                          (res / "charset_tiles.bin", len(tiles)))
            report.append("wrote %s  %d bytes (one CT bank, 0x64D3 / 0x5CCF)" %
                          (res / "charset_ct.bin", 2048))
        else:
            report.append("charset size mismatch — MD will use dummy tiles")
    except Exception as e:
        report.append("charset decompress failed: %s — dummy tiles" % e)

    # metadata C
    h = []
    h.append("#ifndef MAP_SCRIPTS_H")
    h.append("#define MAP_SCRIPTS_H")
    h.append("")
    h.append("#include <genesis.h>")
    h.append("")
    h.append("/* Generated by tools/extract_map_scripts.py from zanac.asm DB lines. */")
    h.append("#define MAP_BLOB_BASE      0x%04X" % BLOB_LO)
    h.append("#define MAP_BLOB_END       0x%04X" % BLOB_HI)
    h.append("#define MAP_BLOB_LEN       %d" % len(blob))
    h.append("#define MAP_SCRIPT_COUNT   9")
    h.append("#define MAP_PTR_TABLE_MSX  0x%04X" % PTR_TABLE)
    h.append("#define MAP_DEFAULT_ROUND  1")
    h.append("#define MAP_HAS_CHARSET    %d" % (1 if charset_ok else 0))
    h.append("#define TILE_TABLES_MSX    0xA444")
    h.append("/* gfx_charset_colors 0x64D3 / decompress_block 0x5CCF, one bank. */")
    h.append("#define CHARSET_CT_MSX     0x64D3")
    h.append("#define CHARSET_CT_LEN     2048")
    h.append("")
    h.append("/* LAB_92af ending stream pointer (round 0 credits). */")
    h.append("#define MAP_ENDING_STREAM  0xA6F4")
    h.append("")
    h.append("/* ptr table @0x945C: index i is round (8-i). idx 8 = round 0 / ending. */")
    h.append("extern const u16 map_script_ptrs[MAP_SCRIPT_COUNT];")
    h.append("extern const u16 map_script_lens[MAP_SCRIPT_COUNT];")
    h.append("")
    h.append("/* The level blob lives in res/map_blob.bin (SGDK BIN map_blob). */")
    h.append("")
    h.append("#endif")
    h.append("")
    (inc / "map_scripts.h").write_text("\n".join(h), encoding="utf-8")

    c = []
    c.append('#include "map_scripts.h"')
    c.append("")
    c.append(c_u16_array("map_script_ptrs", ptrs))
    c.append("")
    c.append(c_u16_array("map_script_lens", script_lens))
    c.append("")
    (src_data / "map_scripts.c").write_text("\n".join(c), encoding="utf-8")
    report.append("wrote %s and %s" % (inc / "map_scripts.h", src_data / "map_scripts.c"))

    # spawn_table (outside the map blob)
    types = bytes(rom[SPAWN_TYPES:SPAWN_TYPES + SPAWN_TYPE_LEN])
    timers = bytes(rom[SPAWN_TIMERS:SPAWN_TIMERS + 7])
    pairs = bytes(rom[SPAWN_PAIRS:SPAWN_PAIRS + SPAWN_PAIR_LEN])
    sh = [
        "#ifndef SPAWN_TABLE_H",
        "#define SPAWN_TABLE_H",
        "",
        "#include <genesis.h>",
        "",
        "/* Generated from zanac.asm DB bytes at 0xBE76 / 0xBE7C / 0xBECC. */",
        "#define SPAWN_TYPE_LEN    %d" % SPAWN_TYPE_LEN,
        "#define SPAWN_TIMER_LEN   7",
        "#define SPAWN_PAIR_LEN    %d" % SPAWN_PAIR_LEN,
        "",
        "extern const u8 spawn_type_list[SPAWN_TYPE_LEN];",
        "extern const u8 spawn_timer_ramp[SPAWN_TIMER_LEN];",
        "extern const u8 spawn_pair_table[SPAWN_PAIR_LEN];",
        "",
        "#endif",
        "",
    ]
    (inc / "spawn_table.h").write_text("\n".join(sh), encoding="utf-8")
    sc = ['#include "spawn_table.h"', "",
          "const u8 spawn_type_list[SPAWN_TYPE_LEN] = {"]
    for i in range(0, SPAWN_TYPE_LEN, 16):
        chunk = ", ".join("0x%02X" % b for b in types[i:i+16])
        sc.append("    %s," % chunk)
    sc.append("};")
    sc.append("")
    sc.append("const u8 spawn_timer_ramp[SPAWN_TIMER_LEN] = { "
              + ", ".join("0x%02X" % b for b in timers) + " };")
    sc.append("")
    sc.append("const u8 spawn_pair_table[SPAWN_PAIR_LEN] = {")
    for i in range(0, SPAWN_PAIR_LEN, 16):
        chunk = ", ".join("0x%02X" % b for b in pairs[i:i+16])
        sc.append("    %s," % chunk)
    sc.append("};")
    sc.append("")
    (src_data / "spawn_table.c").write_text("\n".join(sc), encoding="utf-8")
    report.append("wrote spawn_table %d types + %d timers + %d pairs" %
                  (len(types), len(timers), len(pairs)))

    # MSX sprite patterns -> res/sprites/objs.png and ship.png (same decode path).
    try:
        from PIL import Image
        raw = decompress(rom, SPRITE_RLE[0], SPRITE_RLE[1], max_out=4096)
        report.append("sprites decompressed %d bytes (expect 2048)" % len(raw))
        if len(raw) >= 2048:
            def pat16(idx):
                p = raw[idx * 32:(idx + 1) * 32]
                pix = [[0] * 16 for _ in range(16)]
                for y in range(16):
                    if y < 8:
                        L, R = p[y], p[16 + y]
                    else:
                        L, R = p[8 + (y - 8)], p[24 + (y - 8)]
                    for x in range(8):
                        if L & (0x80 >> x):
                            pix[y][x] = 1
                        if R & (0x80 >> x):
                            pix[y][x + 8] = 1
                return pix

            def write_strip(dest, frames, label):
                img = Image.new("P", (16 * len(frames), 16), 0)
                pal = []
                for rgb in TMS_RGB:
                    pal.extend(rgb)
                pal.extend([0, 0, 0] * (256 - 16))
                img.putpalette(pal)
                px = img.load()
                for fi, (pat, col) in enumerate(frames):
                    bits = pat16(pat)
                    ox = fi * 16
                    for y in range(16):
                        for x in range(16):
                            px[ox + x, y] = col if bits[y][x] else 0
                dest.parent.mkdir(parents=True, exist_ok=True)
                img.save(dest)
                report.append("wrote %s  %dx%d paletted (%s)" %
                              (dest, img.size[0], img.size[1], label))

            spr_dir = res / "sprites"
            # Unfolded: primary bits only + type39 compl frames (TMS 1).
            # Colors match entity.c k_frame_color / tools/rebuild_sprites.py.
            write_strip(spr_dir / "objs.png", [
                (10, 15), (22, 9), (24, 10), (30, 14),
                (53, 15), (1, 11), (7, 15), (28, 15),
                (11, 15), (12, 15),
                (3, 15), (9, 15), (2, 15),
                (59, 15), (60, 15), (61, 15),
                (33, 7), (34, 7), (35, 7), (36, 7), (37, 7),
                (38, 1), (39, 1), (40, 1), (41, 1), (42, 1),
                (23, 1), (25, 1), (54, 1), (32, 1),
                (55, 15), (57, 1),
                (51, 8), (52, 1),
                (43, 14), (44, 14), (45, 14), (46, 14),
                (47, 1), (48, 1), (49, 1), (50, 1),
                (62, 7), (63, 1),
                (18, 15), (19, 1),
                (16, 7), (17, 1),
                (13, 15),
                (6, 4),
                (26, 15), (27, 15),
                (8, 15),
                (29, 11), (31, 1),
                (56, 7), (58, 1),
                (20, 1), (21, 1),  # loga_B SAT 0x50 / fire 0x54
                (4, 15), (5, 15),  # SNOW SAT 0x10 / SMALL_STAR SAT 0x14
            ], "61 frames, type39 unfolded from gfx_sprite_patterns 0x6976")
            # pat 14 white + pat 15 black (two 16x16 frames). Same X/Y under white.
            write_strip(spr_dir / "ship.png", [(14, 15), (15, 1)],
                        "pat 14 white + pat 15 black complement")
        else:
            report.append("sprite size mismatch — keeping existing pngs")
    except Exception as e:
        report.append("sprite extract skipped: %s" % e)


def main():
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

    ptrs = [w(rom, PTR_TABLE + i * 2) for i in range(9)]
    print("pointer table @0x945C:")
    for i, p in enumerate(ptrs):
        rnd = 8 - i
        print("  [%d] 0x%04X  round %d%s" %
              (i, p, rnd, " (ending)" if rnd == 0 else ""))
        if p != KNOWN_PTRS[i]:
            print("  ** mismatch vs KB (expected 0x%04X)" % KNOWN_PTRS[i])

    print("\n== scripts ==")
    total_recs = 0
    for idx in range(8, -1, -1):
        start = ptrs[idx]
        recs = parse_script(rom, start)
        total_recs += len(recs)
        dest = ""
        if recs and (recs[-1][2] & 0xF) == 9:
            dest = " jump->0x%04X" % w(rom, recs[-1][0] + 3)
        nbytes = 0
        if recs:
            last = recs[-1]
            nbytes = (last[0] + 3 + len(last[4])) - start
        print("  round %d idx %d @0x%04X  %d recs  %d bytes%s" %
              (8 - idx, idx, start, len(recs), nbytes, dest))
        # first 8 commands
        for rec in recs[:8]:
            a, row, cmd, note, raw = rec
            print("      0x%04X row=%-5d cmd=%02X %-15s %s" %
                  (a, row, cmd, CMD_NAME.get(cmd & 0xF, "?"), note))
        if len(recs) > 8:
            print("      ... %d more" % (len(recs) - 8))

    print("total records", total_recs)

    # round-1 cmd8 check
    r1 = parse_script(rom, ptrs[7])
    cmd8 = [r for r in r1 if (r[2] & 0xF) == 8]
    print("round 1 cmd8 count", len(cmd8),
          "first at row" , cmd8[0][1] if cmd8 else None)

    report = []
    emit(out, rom, report)
    print("\n== emit ==")
    for line in report:
        print(line)


if __name__ == "__main__":
    main()
