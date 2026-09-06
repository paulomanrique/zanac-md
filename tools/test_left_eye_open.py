#!/usr/bin/env python3
"""R1 diamond left eye must open: 964C is 8-bit wrap, not 16-bit SAT X.

Playtest on main 14c3b3b (PR #87): top/right/bottom 8c15 open; LEFT stays
the closed map swirl. PR #85/#87 unsigned SUB 0x20 + 8c15 1x1 did not
open it — do not re-ship that claim.

Japan v1 (SHA1 46e9ed7b7f6dfda8eee266476c9ebc4dd9d8fcc2):

  964C  ADD A,A*3 (ybase*8) + blob_X; SUB 0x20; 8-bit store to +02
  8a92  SUB 0x20 unsigned → 8948 H (still required; not this bug)
  8c15  type 75 B=1 D=0  1x1 0xBF+phase
        type 76 B=1 D=1  1x2 same tile
        type 77 B=2 D=0  2x1 same tile
        type 78 B=2 D=1  2x2 same tile
        type 79 → 8c80

R1 cmd B @0xA82F: ybase=0x15, ptr=0x9EB8 → extra 0, then 07 84 + four
type-75 records (N/E/S/W are the same variant; side is blob X/Y):

  S  y=F0 x=00   SAT (0x15*8+0x00-0x20)&255 = 136   8948 col 13
  W  y=D8 x=E8   SAT (0x15*8+0xE8-0x20)&255 = 112   8948 col 10
  E  y=D8 x=18   SAT (0x15*8+0x18-0x20)&255 = 160   8948 col 16
  N  y=C0 x=00   SAT 136                           8948 col 13

16-bit ybase*8+blob-0x20 for west is 368. entity_place_ground clamps
to playfield_w-8=248. 8948 H=216 → col 27 >= PF_COLS 24 → bind fail.
8c15 never paints the left cell. That is the playtest.

This file must FAIL on that 16-bit formula.

Usage (from zanac-md):
    python tools/test_left_eye_open.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "src" / "map_script.c"
ENT = ROOT / "src" / "entity.c"
HDR = ROOT / "inc" / "map_script.h"

# R1 first diamond (cmd B 0xA82F / stream 0x9EB8).
R1_YBASE = 0x15
R1_PODS = (
    ("S", 75, 0xF0, 0x00),
    ("W", 75, 0xD8, 0xE8),
    ("E", 75, 0xD8, 0x18),
    ("N", 75, 0xC0, 0x00),
)
PF_COLS = 24


def fail(msg: str) -> int:
    print("FAIL:", msg)
    return 1


def sat_x_8bit(ybase: int, blob_x: int) -> int:
    return (ybase * 8 + blob_x - 0x20) & 0xFF


def sat_x_16bit(ybase: int, blob_x: int) -> int:
    return ybase * 8 + blob_x - 0x20


def clamp_playfield(x: int, playfield_w: int = 256) -> int:
    if x < -16:
        return -16
    if x > playfield_w - 8:
        return playfield_w - 8
    return x


def bind_col(sat_x: int) -> int | None:
    """8948 H = unsigned SAT_X-0x20; sat_to_nt rejects col>=24."""
    hx = (sat_x - 0x20) & 0xFF
    col = hx >> 3
    if col >= PF_COLS:
        return None
    return col


def main() -> int:
    mp = MAP.read_text(encoding="utf-8")
    ent = ENT.read_text(encoding="utf-8")
    hdr = HDR.read_text(encoding="utf-8")

    # --- numbers that FAIL on current main (16-bit 964C) ---
    west_8 = sat_x_8bit(R1_YBASE, 0xE8)
    west_16 = sat_x_16bit(R1_YBASE, 0xE8)
    west_clamped = clamp_playfield(west_16)
    if west_8 != 112:
        return fail("Japan west SAT must be 112, got %d" % west_8)
    if west_16 != 368:
        return fail("16-bit west SAT must be 368 (the main bug), got %d" % west_16)
    if west_clamped != 248:
        return fail("16-bit+clamp west SAT must be 248, got %d" % west_clamped)
    if bind_col(west_8) != 10:
        return fail("Japan west 8948 col must be 10, got %s" % bind_col(west_8))
    if bind_col(west_clamped) is not None:
        return fail("clamped west SAT 248 must fail sat_to_nt (col>=24)")

    for name, typ, _y, xb in R1_PODS:
        if typ != 75:
            return fail("R1 diamond %s must be type 75, got %d" % (name, typ))
        sat = sat_x_8bit(R1_YBASE, xb)
        col = bind_col(sat)
        if col is None:
            return fail("R1 %s SAT %d must bind (8-bit 964C)" % (name, sat))

    # 16-bit formula still in tree = this test fails (current main).
    old = [
        "x = (s16)st->ybase * 8 + (s16)r[2] - 0x20",
        "x = (s16)st.ybase * 8 + (s16)r[2] - 0x20",
    ]
    for s in old:
        if s in mp:
            return fail("16-bit 964C still present (%s) — left eye stays closed" % s)

    if "sat_x_964c" not in mp:
        return fail("964C must be a shared 8-bit helper")
    fn = re.search(
        r"static s16 sat_x_964c\(u8 ybase, u8 blob_x\)\s*\{(.*?)^\}",
        mp,
        re.S | re.M,
    )
    if not fn:
        return fail("sat_x_964c not found")
    body = fn.group(1)
    if "(u8)" not in body or "- 0x20" not in body:
        return fail("sat_x_964c must wrap ybase*8 + blob_X - 0x20 as u8")
    if "s16)ybase * 8" in body or "s16)blob" in body:
        return fail("sat_x_964c must not 16-bit add")

    if "sat_x_964c(st->ybase, r[2])" not in mp:
        return fail("place_tile_group must use sat_x_964c")
    if "sat_x_964c(st.ybase, r[2])" not in mp:
        return fail("place_ctrl_at must use sat_x_964c")

    # 8948 unsigned SUB stays (Japan 8a92). Not sufficient alone.
    if "u8 hx = (u8)((u8)sat_x - 0x20)" not in mp:
        return fail("8948 H must stay unsigned SUB 0x20")
    if "map_script_8948_cell" not in hdr:
        return fail("8948 cell bind must stay declared")

    # 8c15 1x1 for 75-78 stays (R1 is all type 75; Japan 75 is 1x1).
    fn15 = re.search(
        r"void map_script_base_8c15_at\(u8 col, u8 row, u8 variant, u8 phase\)\s*\{(.*?)^\}",
        mp,
        re.S | re.M,
    )
    if not fn15:
        return fail("map_script_base_8c15_at not found")
    tail = fn15.group(1).split("0xBF + p", 1)[-1]
    if "rows = 1" not in tail or "cols = 1" not in tail:
        return fail("75-78 stay 1x1 0xBF+phase (R1 type 75)")
    if "rows = 2" in tail or "cols = 2" in tail:
        return fail("do not restore Japan 76/77/78 repeat (double lens)")

    if "k_base[idx][3]" not in ent:
        return fail("k_base xo still after 8948 bind")
    if "map_script_8948_cell(e->x, (s16)ypre, &col, &row)" not in ent:
        return fail("arm still 8948-binds SAT X / Y-pre-+0x10")

    print("ok: 964C 8-bit; R1 west SAT 112 col 10; 16-bit 368/248 rejected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
