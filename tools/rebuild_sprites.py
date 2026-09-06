#!/usr/bin/env python3
"""Rebuild zanac-md objs.png from zanac.asm gfx_sprite_patterns 0x6976.

Unfolds body vs complement into separate frames so entity.c can draw a
second MD sprite (type39 / 71f6) without overlaying black on a fold.
Does not write ship.png (player.c draws pat 14 + pat 15 at the same X, Y+2).

Usage (from zanac-md):
    python tools/rebuild_sprites.py --asm PATH --out res/sprites/objs.png
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

TMS_RGB = [
    (0, 0, 0), (0, 0, 0), (33, 200, 66), (94, 220, 120),
    (84, 85, 237), (125, 118, 252), (212, 82, 77), (66, 235, 245),
    (252, 85, 84), (255, 121, 120), (212, 193, 84), (230, 206, 128),
    (33, 176, 59), (201, 91, 186), (204, 204, 204), (255, 255, 255),
]

SPRITE_RLE = (0x6976, 0x70B8)


def load_extract(root: Path):
    spec = importlib.util.spec_from_file_location(
        "extract_map_scripts", root / "tools" / "extract_map_scripts.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.parse_asm, mod.decompress


def pat_bits(pat: bytes):
    bits = [[0] * 16 for _ in range(16)]
    for y in range(16):
        left, right = pat[y], pat[16 + y]
        for x in range(8):
            if left & (0x80 >> x):
                bits[y][x] = 1
            if right & (0x80 >> x):
                bits[y][8 + x] = 1
    return bits


def primary_only(primary, color: int):
    pb = pat_bits(primary)
    return [color if pb[y][x] else 0 for y in range(16) for x in range(16)]


def compl_only(compl):
    cb = pat_bits(compl)
    return [1 if cb[y][x] else 0 for y in range(16) for x in range(16)]


# FRAME index -> (pat, tms_color, is_complement)
# Matches entity.c FRAME_* 0..60. Primaries are body bits only.
FRAMES = [
    (10, 15, False),   # SHOT
    (22, 9, False),    # DUSTER
    (24, 10, False),   # TERUZO
    (30, 14, False),   # LUSTER_B
    (53, 15, False),   # BOX
    (1, 11, False),    # CHIP
    (7, 15, False),    # LEAD
    (28, 15, False),   # SIG
    (11, 15, False),   # SHOT_D
    (12, 15, False),   # SHOT_T
    (3, 15, False),    # FIRE
    (9, 15, False),    # CIRCLE
    (2, 15, False),    # COMET
    (59, 15, False),   # DEGID_L
    (60, 15, False),   # DEGID_R
    (61, 15, False),   # DEGID
    (33, 7, False),    # VEYBAR 0-4
    (34, 7, False),
    (35, 7, False),
    (36, 7, False),
    (37, 7, False),
    (38, 1, True),     # VEYBAR_C 0-4
    (39, 1, True),
    (40, 1, True),
    (41, 1, True),
    (42, 1, True),
    (23, 1, True),     # DUSTER_C
    (25, 1, True),     # TERUZO_C
    (54, 1, True),     # BOX_C
    (32, 1, True),     # LUSTER_C
    (55, 15, False),   # UMBER_A
    (57, 1, True),     # UMBER_C
    (51, 8, False),    # STEALTH
    (52, 1, True),     # STEALTH_C
    (43, 14, False),   # SPINNER 0-3
    (44, 14, False),
    (45, 14, False),
    (46, 14, False),
    (47, 1, True),
    (48, 1, True),
    (49, 1, True),
    (50, 1, True),
    (62, 7, False),    # SART
    (63, 1, True),     # SART_C
    (18, 15, False),   # LOGA_A
    (19, 1, True),     # LOGA_A_C
    (16, 7, False),    # PLANE
    (17, 1, True),     # PLANE_C
    (13, 15, False),   # BOLT
    (6, 4, False),     # LIGHT_BAR
    (26, 15, False),   # SIG_TRIPLE
    (27, 15, False),   # SIG_DOUBLE
    (8, 15, False),    # MED_CIRCLE (pat 8; SAT color from 8a16 / +04, not type67 0x86)
    (29, 11, False),   # LUSTER_A
    (31, 1, True),     # LUSTER_A_C
    (56, 7, False),    # UMBER_B
    (58, 1, True),     # UMBER_B_C
    (20, 1, True),     # LOGA_B SAT 0x50
    (21, 1, True),     # LOGA_D SAT 0x54
    (4, 15, False),    # SNOW pat 4 SAT 0x10 fire 3
    (5, 15, False),    # SMALL_STAR pat 5 SAT 0x14 type 67 83d8 XOR
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asm", required=True, help="zanac-re source/zanac.asm")
    ap.add_argument("--out", required=True, help="objs.png destination")
    args = ap.parse_args()
    asm = Path(args.asm)
    out = Path(args.out)
    root = Path(__file__).resolve().parents[1]
    if not asm.is_file():
        sys.exit("asm not found: %s" % asm)

    from PIL import Image

    parse_asm, decompress = load_extract(root)
    rom = parse_asm(asm)
    raw = decompress(rom, SPRITE_RLE[0], SPRITE_RLE[1], max_out=4096)
    if len(raw) < 2048:
        sys.exit("sprite decompress got %d bytes, need 2048" % len(raw))
    P = [raw[i * 32:(i + 1) * 32] for i in range(64)]

    n = len(FRAMES)
    strip = Image.new("P", (n * 16, 16))
    pal = []
    for rgb in TMS_RGB:
        pal.extend(rgb)
    pal.extend([0] * (768 - len(pal)))
    strip.putpalette(pal)

    for fi, (pat, color, is_c) in enumerate(FRAMES):
        if is_c:
            pix = compl_only(P[pat])
        else:
            pix = primary_only(P[pat], color)
        # LEAD (6, pat 7) and MED_CIRCLE (52, pat 8): zanac-re UL 4x4
        # is 0 bits. Force 0 so a neighbor 8x8 cannot bake TMS 4/5 into
        # the displayed corner. CIRCLE (11, pat 9) UL 4x4 is the disc.
        if fi in (6, 52):
            for y in range(4):
                for x in range(4):
                    pix[y * 16 + x] = 0
        fr = Image.new("P", (16, 16))
        fr.putpalette(pal)
        fr.putdata(pix)
        strip.paste(fr, (fi * 16, 0))

    out.parent.mkdir(parents=True, exist_ok=True)
    strip.save(out, optimize=False)
    duster = list(strip.crop((16, 0, 32, 16)).getdata())
    duster_c = list(strip.crop((26 * 16, 0, 27 * 16, 16)).getdata())
    print("wrote %s %s frames=%d" % (out, strip.size, n))
    print("duster body", sorted(set(duster)), "on", duster.count(9),
          "blk", duster.count(1))
    print("duster_c", sorted(set(duster_c)), "blk", duster_c.count(1))
    if duster.count(1) != 0:
        sys.exit("unfold failed: primary still has black complement bits")
    if duster.count(9) == 0 or duster_c.count(1) == 0:
        sys.exit("unfold failed: empty duster body or complement")


if __name__ == "__main__":
    main()
