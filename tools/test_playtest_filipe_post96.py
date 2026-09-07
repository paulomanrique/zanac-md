#!/usr/bin/env python3
"""Filipe playtest after PR #96 (2a7a9ce) — leftover tear + gone wreckage.

Japan v1 SHA1 46e9ed7b7f6dfda8eee266476c9ebc4dd9d8fcc2.

#96 sat_to_nt is wrap(scroll&~7)+Y/8 (KEEP). 87e2/88ed then hit the 8px
97e3 cell. DMA_QUEUE still snapshotted s_dma_row *inside* 97e3, before
entity_update. Japan 9a79 is vblank after 87e2/88ed write E800 — the
wrap DMA must read the punched row.

game.c: entity_update then map_script_commit_wrap. 97e3 latches
hidden_wrap(pre) RAW (KEEP #92); does not DMA_QUEUE the assemble yet.

Type 44 82d0 death stays type 35 (no 88ed). Wreckage is 880d / k_88ab
for 81/82/84-89. 87e2 uses punch_cell (E800 then VRAM).

KEEP: tile_wrap stamps; peek only after real 97e3; #93 40DA; #94 dest;
fire7; 964C; ship Y+2; no 0x28 punch; orb; 4898; ebullet; 4BDF; 60fps;
no letter fill; no opaque 0x20; no BFD6. Ignore complement offset / horns.

Usage (from zanac-md):
    python tools/test_playtest_filipe_post96.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "src" / "map_script.c"
ENT = ROOT / "src" / "entity.c"
GAME = ROOT / "src" / "game.c"
HDR = ROOT / "inc" / "map_script.h"
MAIN = ROOT / "src" / "main.c"
PLY = ROOT / "src" / "player.c"
SPAWN = ROOT / "src" / "data" / "spawn_table.c"


def src(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def ok(msg: str) -> None:
    print(f"ok: {msg}")


def fn_span(text: str, sig: str) -> str | None:
    m = re.search(rf"{re.escape(sig)}\s*\{{", text)
    if not m:
        return None
    i = m.end() - 1
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[i : j + 1]
    return None


def hidden_wrap_nt_at(scroll_px: int) -> int:
    off = (scroll_px + 16) & 0xFF
    py = (16 - off) & 0xFF
    return py >> 3


def tile_wrap_nt_at(scroll_px: int) -> int:
    return hidden_wrap_nt_at(scroll_px & ~7)


def check_97e3_latches_pre_no_queue_dma() -> None:
    m = src(MAP)
    pre = fn_span(m, "static void scroll_precompute(u16 map_row)")
    if not pre:
        fail("scroll_precompute (97e3) not found")
    if "hidden_wrap_nt_at(s_scroll_px)" not in pre:
        fail("97e3 must latch wrap(pre) RAW")
    if "tile_wrap_nt_at" in pre:
        fail("97e3 must not switch to tile_wrap — KEEP wrap(pre) RAW")
    if "s_wrap_nt = hidden_wrap_nt_at(s_scroll_px)" not in pre:
        fail("97e3 must store wrap(pre) for post-punch DMA")
    if "s_wrap_pending = 1" not in pre:
        fail("97e3 DMA_QUEUE path must defer to commit_wrap")
    if re.search(r"dma_nt_row\(hidden_wrap_nt_at\(s_scroll_px\)", pre):
        fail("97e3 must not DMA_QUEUE the wrap row before 87e2/88ed")
    ok("97e3 latches wrap(pre) RAW; DMA_QUEUE deferred")


def check_commit_after_entity() -> None:
    m, g, h = src(MAP), src(GAME), src(HDR)
    if "void map_script_commit_wrap(void)" not in h:
        fail("need map_script_commit_wrap in header")
    commit = fn_span(m, "void map_script_commit_wrap(void)")
    if not commit:
        fail("map_script_commit_wrap not found")
    if "dma_nt_row(s_wrap_nt, s_e800[s_e714]" not in commit:
        fail("commit must DMA e800[e714] at latched wrap(pre)")
    if not re.search(
        r"entity_update\s*\(\s*\)\s*;[\s\S]{0,80}?map_script_commit_wrap\s*\(\s*\)\s*;",
        g,
    ):
        fail("entity_update must punch before commit_wrap (Japan 9a79 after 87e2)")
    if g.find("map_script_commit_wrap();") < 0:
        fail("need commit_wrap on gameplay paths")
    # GO / credits / warp still flush a pending 97e3 (no entity punches).
    if g.count("map_script_commit_wrap();") < 4:
        fail("GO / credits / warp / play must all commit_wrap")
    ok("commit_wrap after entity; e800[e714] -> wrap(pre)")


def check_87e2_punch_cell() -> None:
    m = src(MAP)
    st = fn_span(m, "void map_script_stamp_82_digit(s16 x, s16 y, u8 fire_num)")
    if not st:
        fail("stamp_82_digit not found")
    if "punch_cell(" not in st:
        fail("87e2 must punch_cell (E800 then VRAM) like Japan 8948")
    if "0x30 + fire_num" not in st:
        fail("KEEP 87e2 0x30+fire")
    if "sat_to_nt" not in st:
        fail("87e2 still binds via sat_to_nt tile_wrap")
    ok("87e2 punch_cell e800 + 0x30+fire")


def check_88ed_type44() -> None:
    m, e = src(MAP), src(ENT)
    punch = fn_span(m, "static void punch_88ed(s16 x, s16 y, const u8 *d, s16 xadj, s16 yadj)")
    if not punch or "punch_cell(" not in punch:
        fail("88ed punch_cell e800 KEEP")
    if "k_88ab_84[] = { 2, 2, 0x3B, 0x3C, 2, 0x3A, 0x3D }" not in m:
        fail("k_88ab dest is Japan 88b1")
    if "map_script_punch_88ab" not in e:
        fail("84-86 still punch 88ab")
    ground = e.split("if (kind == KIND_GROUND)", 1)
    if len(ground) < 2:
        fail("type 44 death path missing")
    death = ground[1][:400]
    if "become_expl" not in death:
        fail("type 44 82d0 death stays type 35")
    if "map_script_punch_88" in death:
        fail("type 44 must not 88ed (Japan 82d0 -> 44ba / 0x23)")
    ok("88ed/k_88ab for 81/82/84-89; type 44 stays type 35")


def check_keep_tile_wrap_and_peek() -> None:
    m = src(MAP)
    sat = fn_span(m, "static int sat_to_nt(s16 x, s16 y, u8 *col, u8 *row)")
    if not sat or "tile_wrap_nt_at(s_scroll_px)" not in sat:
        fail("KEEP #96 sat_to_nt tile_wrap")
    if "hidden_wrap_nt_at(s_scroll_px)" in sat:
        fail("KEEP #96: sat_to_nt must not wrap(raw)")
    leftover = 0xE9
    if tile_wrap_nt_at(leftover) == hidden_wrap_nt_at(leftover):
        fail("leftover tile wrap must differ from wrap(raw) peek")
    upd = fn_span(m, "void map_script_update(void)")
    if not upd:
        fail("map_script_update not found")
    skip = upd.split("if (!s_skip_precompute)")
    if len(skip) < 2:
        fail("KEEP s_skip_precompute")
    body = skip[1]
    i = body.find("{")
    depth = 0
    end = i
    for j, ch in enumerate(body[i:], i):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = j
                break
    block = body[i : end + 1]
    if "s_scroll_px =" in block:
        fail("must not write s_scroll_px before 97e3")
    if "peek_next_row" not in block:
        fail("peek only after real 97e3")
    peek = fn_span(m, "static void peek_next_row(u16 map_row)")
    if not peek or "s_scroll_px + 8" not in peek:
        fail("peek must stay wrap(scroll+8)")
    ok("KEEP tile_wrap stamps; 97e3 pre-carry; peek after 97e3 +8")


def check_keep_rest() -> None:
    m, e, p, main = src(MAP), src(ENT), src(PLY), src(MAIN)
    if "mdy = dy" not in e:
        fail("KEEP 71f6 complement Y = parent (ignore horns)")
    if "ADD 0xF1" not in p:
        fail("KEEP ship black Y+2")
    if "k_orb_sat" not in e:
        fail("KEEP orb")
    if re.search(r"VDP_setTileMapXY\([^,]+,\s*0x20\s*,", m):
        fail("no 0x20 opaque")
    if "recolor_charset_tile_opaque_bg" in m:
        fail("no 0x20 opaque")
    if "BFD6" in m or "0xBFD6" in e or "0xbfd6" in e:
        fail("no BFD6")
    if "SYS_doVBlankProcess" not in main:
        fail("KEEP 60fps")
    spawn = src(SPAWN)
    types = re.findall(r"0x[0-9A-Fa-f]{2}", spawn.split("spawn_type_list")[1].split(";")[0])
    if len(types) < 51 or types[50].lower() != "0x44":
        fail("KEEP proto_box type 68")
    if "VDP_fillTileMapRect(BG_A, mode_letter_attr(), 0, 2, MODE_BAR_COL, 24)" in m:
        fail("no letter fill")
    if "ASM_SKIP" not in m or "8" not in m.split("ASM_SKIP")[1][:24]:
        fail("KEEP EA48 skip 8")
    if "do not invent stamps" not in m:
        fail("coast from Japan streams; no invented art")
    ok("KEEP fire7/964C/orb/4898/60fps/no 0x28/no BFD6/coast streams")


def main() -> None:
    check_97e3_latches_pre_no_queue_dma()
    check_commit_after_entity()
    check_87e2_punch_cell()
    check_88ed_type44()
    check_keep_tile_wrap_and_peek()
    check_keep_rest()
    print("test_playtest_filipe_post96: all checks passed")


if __name__ == "__main__":
    main()
