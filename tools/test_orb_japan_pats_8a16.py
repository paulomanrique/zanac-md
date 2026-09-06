#!/usr/bin/env python3
"""Type 72 pulse tiles must be Japan v1 pats 7/8/9, not SGDK FRAME_LEAD.

objs.png FRAME_LEAD/MED/CIRCLE already match zanac-re gfx pats 7/8/9
(SAT 0x1C/0x20/0x24). Playtest still failed: SGDK BALANCED cuts
FRAME_LEAD to an 8x8 that displays only the UL tile (4 px shard /
garbage) while Japan shows a clean centered disc.

This test fails on main c66c196 (sheet-match + orb_paint only):
  - entity.c must embed Japan pat bytes and encode them to 4 tiles
  - orb_step must use the 16x16 FRAME_CIRCLE vehicle
  - every 8a16/8a1e frame's body bits must equal the Japan pat

Do not invent SAT names or colours. Mid 0x83 -> PAL2[7] stays.

Usage (from zanac-md):
    python tools/test_orb_japan_pats_8a16.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENT = ROOT / "src" / "entity.c"
PNG = ROOT / "res" / "sprites" / "objs.png"
RES = ROOT / "res" / "resources.res"

# zanac-re gfx_sprite_patterns pats 7/8/9 (32 bytes, left then right).
JAPAN = {
    7: bytes.fromhex(
        "00000000000001030203010000000000"
        "00000000000080c040c0800000000000"
    ),
    8: bytes.fromhex(
        "000001070f1f1f3f3f1f1f0f07010000"
        "000080e0f0f8f8fcfcf8f8f0e0800000"
    ),
    9: bytes.fromhex(
        "030f3f3f7f7fffffffff7f7f3f3f0f03"
        "c0f0fcfcfefefffffffffefefcfcf0c0"
    ),
}

K_ORB_SAT = (0x1C, 0x20, 0x24, 0x20)
K_ORB_YEL = (0x8F, 0x83, 0x8A, 0x8B)
K_ORB_BLK = (0x81, 0x81, 0x81, 0x81)
SAT_PAT = {0x1C: 7, 0x20: 8, 0x24: 9}

# objs.png FRAME_* indices
PNG_FRAMES = ((6, "LEAD", 7), (11, "CIRCLE", 9), (52, "MED_CIRCLE", 8))


def fail(msg: str) -> int:
    print("FAIL:", msg)
    return 1


def pat_bits(pat: bytes) -> list[list[int]]:
    bits = [[0] * 16 for _ in range(16)]
    for y in range(16):
        left, right = pat[y], pat[16 + y]
        for x in range(8):
            if left & (0x80 >> x):
                bits[y][x] = 1
            if right & (0x80 >> x):
                bits[y][8 + x] = 1
    return bits


def encode_japan_tiles(pat: bytes, want: int) -> bytes:
    """Mirror orb_encode_japan_tiles: 4 tiles column-major TL,BL,TR,BR."""
    out = bytearray()
    for t in range(4):
        tx = 8 if (t & 2) else 0
        ty = 8 if (t & 1) else 0
        for row in range(8):
            y = ty + row
            left, right = pat[y], pat[16 + y]
            for col in range(0, 8, 2):
                x0, x1 = tx + col, tx + col + 1
                b0 = (left if x0 < 8 else right) & (0x80 >> (x0 if x0 < 8 else x0 - 8))
                b1 = (left if x1 < 8 else right) & (0x80 >> (x1 if x1 < 8 else x1 - 8))
                out.append(((want if b0 else 0) << 4) | (want if b1 else 0))
    return bytes(out)


def decode_tiles_bits(tiles: bytes) -> list[list[int]]:
    bits = [[0] * 16 for _ in range(16)]
    for t in range(4):
        tx = 8 if (t & 2) else 0
        ty = 8 if (t & 1) else 0
        off = t * 32
        for row in range(8):
            for col in range(0, 8, 2):
                b = tiles[off + row * 4 + col // 2]
                hi, lo = b >> 4, b & 0x0F
                bits[ty + row][tx + col] = 1 if hi else 0
                bits[ty + row][tx + col + 1] = 1 if lo else 0
    return bits


def parse_c_bytes(ent: str, name: str) -> bytes | None:
    m = re.search(
        r"static const u8 %s\[32\] = \{([^}]+)\}" % name, ent, flags=re.S
    )
    if not m:
        return None
    nums = [int(x, 0) for x in re.findall(r"0x[0-9A-Fa-f]+", m.group(1))]
    if len(nums) != 32:
        return None
    return bytes(nums)


def png_frame_bits(fi: int) -> list[list[int]] | None:
    try:
        from PIL import Image
    except ImportError:
        return None
    im = Image.open(PNG)
    fr = im.crop((fi * 16, 0, fi * 16 + 16, 16))
    pix = list(fr.getdata())
    return [[1 if pix[y * 16 + x] else 0 for x in range(16)] for y in range(16)]


def main() -> int:
    ent = ENT.read_text(encoding="utf-8")
    res = RES.read_text(encoding="utf-8")

    if "0x1C, 0x20, 0x24, 0x20" not in ent:
        return fail("k_orb_sat must stay 1C/20/24/20")
    if "0x8F, 0x83, 0x8A, 0x8B" not in ent:
        return fail("8a16 yellow colours 8F/83/8A/8B")
    if "0x81, 0x81, 0x81, 0x81" not in ent:
        return fail("8a1e black colours must stay 81")
    if "FRAME_LEAD, FRAME_MED_CIRCLE, FRAME_CIRCLE, FRAME_MED_CIRCLE" not in ent:
        return fail("k_orb_frame SAT map must stay lead/med/lg/med")
    if "k_orb_mid_pal = 7" not in ent:
        return fail("mid 0x83 -> PAL2[7] stays")
    if "PAL_setColor((u16)((PAL2 * 16) + 2), k_flyer_green_dim[0])" not in ent:
        return fail("PAL2[2] half-green must stay")
    if "PAL_setColor((u16)((PAL2 * 16) + 3), k_flyer_green_dim[1])" not in ent:
        return fail("PAL2[3] half-green must stay")
    if "u16 out = 128" in ent:
        return fail("do not re-ship 4-tile pad as the flyer overflow")

    # Current main spr_places k_orb_frame[idx] (LEAD shard). Must not.
    if "spr_place(e, k_orb_frame[idx])" in ent:
        return fail("orb_step must not spr_place FRAME_LEAD (8x8 UL shard)")
    if "spr_place(e, FRAME_CIRCLE)" not in ent:
        return fail("orb must use 16x16 FRAME_CIRCLE vehicle")
    if "orb_encode_japan_tiles" not in ent or "orb_upload_japan" not in ent:
        return fail("type 72 must encode Japan pats 7/8/9, not SGDK tileset")
    if "k_japan_pat7" not in ent or "k_japan_pat8" not in ent or "k_japan_pat9" not in ent:
        return fail("entity.c must embed Japan pats 7/8/9")

    objs_line = [ln for ln in res.splitlines() if "spr_objs" in ln]
    if not objs_line or not re.search(r"NONE\s+0\s+NONE\s+NONE", objs_line[0]):
        return fail("spr_objs must set opt_type NONE (full 16x16, not BALANCED)")

    for name, pati in (("k_japan_pat7", 7), ("k_japan_pat8", 8), ("k_japan_pat9", 9)):
        got = parse_c_bytes(ent, name)
        if got != JAPAN[pati]:
            return fail("%s must match Japan v1 pat %d" % (name, pati))

    for fi, name, pati in PNG_FRAMES:
        pb = png_frame_bits(fi)
        if pb is None:
            break
        jb = pat_bits(JAPAN[pati])
        if pb != jb:
            return fail("objs.png FRAME_%s bits != Japan pat %d" % (name, pati))
        stray_ok = True
        try:
            from PIL import Image
            im = Image.open(PNG)
            pix = list(im.crop((fi * 16, 0, fi * 16 + 16, 16)).getdata())
            if any(p not in (0, 15) for p in pix):
                stray_ok = False
        except ImportError:
            pass
        if not stray_ok:
            return fail("objs.png FRAME_%s has non-0/non-15 pixels" % name)

    # Every pulse frame (yellow + black) is a clean disc: body bits == Japan.
    for sat, col in list(zip(K_ORB_SAT, K_ORB_YEL)) + list(zip(K_ORB_SAT, K_ORB_BLK)):
        pati = SAT_PAT[sat]
        want = 7 if (col & 0x0F) == 3 else (col & 0x0F)
        tiles = encode_japan_tiles(JAPAN[pati], want)
        if len(tiles) != 128:
            return fail("encode must be 4 tiles (128 bytes), got %d" % len(tiles))
        body = decode_tiles_bits(tiles)
        if body != pat_bits(JAPAN[pati]):
            return fail("encoded SAT 0x%02X col 0x%02X shape != Japan pat %d"
                        % (sat, col, pati))
        # No junk nibbles: every nonzero nibble is `want`.
        junk = [b for b in tiles if ((b >> 4) not in (0, want)) or ((b & 0x0F) not in (0, want))]
        if junk:
            return fail("SAT 0x%02X encode has non-body nibbles" % sat)
        on = sum(sum(r) for r in body)
        if on not in (14, 96, 192):
            return fail("SAT 0x%02X on-bits %d not a Japan disc" % (sat, on))

    # First yellow frame is the small disc (pat 7, 14 bits), not a shard.
    first = encode_japan_tiles(JAPAN[7], 15)
    if sum(sum(r) for r in decode_tiles_bits(first)) != 14:
        return fail("first 8a16 frame must be Japan pat 7 (14-bit disc)")
    # UL 4x4 of pat 7 is empty; a shard upload would light those pixels.
    ul = [decode_tiles_bits(first)[y][x] for y in range(4) for x in range(4)]
    if any(ul):
        return fail("first frame UL 4x4 must stay empty (not FRAME_LEAD shard)")

    print("ok: 8a16 frames are Japan pats 7/8/9 in a 16x16 vehicle; no LEAD shard")
    return 0


if __name__ == "__main__":
    sys.exit(main())
