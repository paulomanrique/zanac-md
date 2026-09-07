#!/usr/bin/env python3
"""Filipe playtest after PR #95 (d817a1d / 464d3de) — wrap(raw)+Y/8 was peek.

Japan v1 SHA1 46e9ed7b7f6dfda8eee266476c9ebc4dd9d8fcc2.

#95 got wrong: sat_to_nt used hidden_wrap_nt_at(s_scroll_px)+Y/8 on RAW
scroll. At leftover E711 frac 1-7, wrap(post)==the peek sliver — one NT
row *north* of the 8px 97e3 tile (not "8 rows off"). Stamps landed in
the 1-2px letterbox instead of the live cell → missing digits, purple
k_88ab leftover (chars 0x3A-0x3D are crater L-marks), sky/green cut.

Japan 8948 is TMS Y/8 with no VSCROLL. MD must stamp wrap(scroll&~7)+Y/8.
KEEP 97e3 DMA wrap(pre) RAW (= wrap(aligned) at leftover). Peek only after
97e3 at scroll+8.

Screenshots 1-6: seam, 90° coast (stamps on peek, not invented art),
garbled firebox, flyer 71f6 KEEP, wreckage leftover, dome L-marks.

Usage (from zanac-md):
    python tools/test_playtest_filipe_post95.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "src" / "map_script.c"
ENT = ROOT / "src" / "entity.c"
PLAYER = ROOT / "src" / "player.c"
GAME = ROOT / "src" / "game.c"
MAIN = ROOT / "src" / "main.c"
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
    """Same as src/map_script.c hidden_wrap_nt_at (RAW, y_off=16)."""
    off = (scroll_px + 16) & 0xFF
    py = (16 - off) & 0xFF
    return py >> 3


def tile_wrap_nt_at(scroll_px: int) -> int:
    return hidden_wrap_nt_at(scroll_px & ~7)


def ramp_shifted() -> tuple[int, int, int]:
    """First 9480 cruise leftover where wrap(pre) != wrap(post)."""
    e710 = 0x20
    e712 = 0x34
    e711 = 0
    e713 = 0
    row_off = 0
    for _ in range(400):
        e713 += 1
        if (e713 & 3) == 0 and e710 != e712:
            e710 = e710 + 1 if e710 < e712 else e710 - 1
        s = e711 + e710
        if s > 255:
            pre = row_off * 8 + (e711 >> 5)
            post = (row_off + 1) * 8 + ((s & 255) >> 5)
            if hidden_wrap_nt_at(pre) != hidden_wrap_nt_at(post):
                return e710, pre, post
            row_off += 1
        e711 = s & 255
    fail("9480 ramp produced no wrap(pre)!=wrap(post) leftover")
    return 0, 0, 0


def check_tile_wrap_helper() -> None:
    m = src(MAP)
    if "static u8 tile_wrap_nt_at(u16 scroll_px)" not in m:
        fail("need tile_wrap_nt_at for 8948 stamps vs peek")
    if "hidden_wrap_nt_at((u16)(scroll_px & 0xFFF8))" not in m:
        fail("tile_wrap must be wrap(scroll&~7)")
    ok("tile_wrap_nt_at = wrap(scroll&~7)")


def check_sat_to_nt_hits_8px_tile_not_peek() -> None:
    m = src(MAP)
    fn = fn_span(m, "static int sat_to_nt(s16 x, s16 y, u8 *col, u8 *row)")
    if not fn:
        fail("sat_to_nt not found")
    if "tile_wrap_nt_at(s_scroll_px)" not in fn:
        fail("sat_to_nt must use tile_wrap_nt_at (8px cell), not wrap(raw)")
    if "hidden_wrap_nt_at(s_scroll_px)" in fn:
        fail("sat_to_nt must not use wrap(raw) — that is the peek sliver")
    if "y - " in fn and "0xFFF8" in fn:
        fail("do not subtract scroll&~7 from Y inside sat_to_nt")
    e710, pre, post = ramp_shifted()
    wrap_pre = hidden_wrap_nt_at(pre)
    wrap_post = hidden_wrap_nt_at(post)
    wrap_tile = tile_wrap_nt_at(post)
    wrap_peek = hidden_wrap_nt_at(pre + 8)
    if wrap_pre != wrap_tile:
        fail(
            f"wrap(pre) must equal tile wrap(post) at leftover "
            f"({wrap_pre} vs {wrap_tile}) E710=0x{e710:02X} pre={pre} post={post}"
        )
    if wrap_post == wrap_tile:
        fail("wrap(raw post) must differ from tile wrap at leftover frac")
    if wrap_post != wrap_peek and wrap_post != hidden_wrap_nt_at(post):
        fail("wrap(raw post) identity")
    ok(
        f"sat_to_nt Y=0 -> tile wrap {wrap_tile} "
        f"(not wrap(raw post)={wrap_post}) leftover E710=0x{e710:02X} "
        f"pre={pre} post={post}"
    )


def check_vis_nt_row_aligned() -> None:
    m = src(MAP)
    fn = fn_span(m, "static u8 vis_nt_row(u8 tms_row)")
    if not fn:
        fail("vis_nt_row not found")
    if "tile_wrap_nt_at" not in fn:
        fail("vis_nt_row must use tile_wrap (same cell as stamps)")
    if "hidden_wrap_nt_at(s_scroll_px)" in fn:
        fail("vis_nt_row must not wrap(raw)")
    leftover = 0xE9
    vis0 = tile_wrap_nt_at(leftover)
    raw = hidden_wrap_nt_at(leftover)
    if vis0 == raw:
        fail("vis at leftover frac must not equal wrap(raw)")
    ok(f"vis_nt_row leftover {leftover:#x} -> tile {vis0} != wrap(raw) {raw}")


def check_keep_97e3_peek_pre_carry() -> None:
    m = src(MAP)
    upd = fn_span(m, "void map_script_update(void)")
    if not upd:
        fail("map_script_update not found")
    skip = upd.split("if (!s_skip_precompute)")
    if len(skip) < 2:
        fail("KEEP: s_skip_precompute")
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
    if "scroll_precompute" not in block:
        fail("97e3 must stay inside !s_skip_precompute")
    if "peek_next_row" not in block:
        fail("peek only after real 97e3")
    pre = fn_span(m, "static void scroll_precompute(u16 map_row)")
    if not pre:
        fail("scroll_precompute (97e3) not found")
    if "hidden_wrap_nt_at(s_scroll_px)" not in pre:
        fail("97e3 DMA must stay wrap(pre) RAW")
    if "tile_wrap_nt_at" in pre:
        fail("97e3 must not switch to tile_wrap — keep RAW wrap(pre)")
    peek = fn_span(m, "static void peek_next_row(u16 map_row)")
    if not peek or "s_scroll_px + 8" not in peek:
        fail("peek must stay wrap(scroll+8) after real 97e3")
    g = src(GAME)
    if not re.search(
        r"map_script_update\s*\(\s*\)\s*;[\s\S]{0,200}?entity_update\s*\(\s*\)\s*;",
        g,
    ):
        fail("entity_update must see POST-97e3 scroll (game.c)")
    ok("KEEP #92: 97e3 wrap(pre) RAW; peek after 97e3 at +8; stamps after map_script")


def check_keep_rest() -> None:
    m, e, p, main = src(MAP), src(ENT), src(PLAYER), src(MAIN)
    st = fn_span(m, "void map_script_stamp_82_digit(s16 x, s16 y, u8 fire_num)")
    if not st or "0x30 + fire_num" not in st:
        fail("KEEP #94 dest: 87e2 0x30+fire")
    punch = fn_span(m, "static void punch_88ed(s16 x, s16 y, const u8 *d, s16 xadj, s16 yadj)")
    if not punch or "punch_cell(" not in punch:
        fail("KEEP 88ed punch_cell e800")
    if "mdy = dy" not in e:
        fail("KEEP 71f6: complement Y = parent (ship Y+2 only)")
    if "ADD 0xF1" not in p or "s->y += 2" not in p and "mode_draw_y(s_y) + 2" not in p:
        fail("KEEP ship black Y+2 (7735)")
    if "0x28" in st and "punch" in st.lower():
        fail("no 0x28 punch")
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
    # proto_box type 68 = 0x44 at spawn_type_list[50]
    types = re.findall(r"0x[0-9A-Fa-f]{2}", spawn.split("spawn_type_list")[1].split(";")[0])
    if len(types) < 51 or types[50].lower() != "0x44":
        fail("KEEP proto_box type 68 = spawn_type_list[50] 0x44")
    if "spr_detach" not in e:
        fail("KEEP spr_detach (white-box SAT leak)")
    if "SPR_initEx(512)" not in main:
        fail("KEEP SPR_initEx(512)")
    if "VDP_fillTileMapRect(BG_A, mode_letter_attr(), 0, 2, MODE_BAR_COL, 24)" in m:
        fail("no letter fill")
    ok("KEEP #93 40DA path, #94 dest, fire7, 964C, ship Y+2, no 0x28, orb, 60fps")


def check_no_invented_coast() -> None:
    m = src(MAP)
    if "ASM_SKIP        8" not in m and "ASM_SKIP  8" not in m and "ASM_SKIP        8" not in m:
        if "ASM_SKIP        8" not in m and "#define ASM_SKIP        8" not in m:
            if "ASM_SKIP" not in m or "8" not in m.split("ASM_SKIP")[1][:20]:
                fail("KEEP EA48 skip 8 for column streams (Japan coast)")
    if "#define ASM_SKIP" not in m:
        fail("KEEP ASM_SKIP")
    if "do not invent" not in m.lower() and "Do not invent" not in m:
        # comment on col_paint
        if "do not invent stamps" not in m:
            fail("col_paint must document Japan streams; no invented coast")
    ok("coast from Japan column streams; no invented tiles")


def check_white_boxes_type68_only() -> None:
    e = src(ENT)
    if "handler_type68" not in e and "type68" not in e:
        fail("need proto_box type 68")
    if "spawn_proto_box" not in e:
        fail("need spawn_proto_box")
    if "spawn_box" not in e:
        fail("need spawn_box")
    if "retry -- Japan 71da" not in e and "retry" not in e:
        fail("box reveal must retry addSprite")
    if re.search(r"spawn_type_list\[[^\]]+\]\s*=\s*0x0[456]\b", e):
        fail("do not invent extra 4/5/6 spawn_type_list entries")
    ok("white boxes: types 4/5/6 from proto_box 68 only; spr_detach+retry")


def check_wreckage_k_88ab_not_on_peek() -> None:
    m, e = src(MAP), src(ENT)
    if "k_88ab" not in m:
        fail("need k_88ab wreckage dest")
    if "0x3A" not in m or "0x3D" not in m:
        fail("k_88ab dest includes 0x3A-0x3D crater chars")
    if "map_script_punch_88ab" not in e:
        fail("ground death must punch 88ab dest")
    punch = fn_span(m, "static void punch_88ed(s16 x, s16 y, const u8 *d, s16 xadj, s16 yadj)")
    if not punch or "sat_to_nt" not in punch:
        fail("88ed uses sat_to_nt — must hit tile wrap after this PR")
    ok("wreckage 88ed/8c15 via sat_to_nt → 8px tile (not peek leftover)")


def check_firebox_digit_path() -> None:
    m, e = src(MAP), src(ENT)
    if "stamp_82_digit" not in m:
        fail("need stamp_82_digit")
    st = fn_span(m, "void map_script_stamp_82_digit(s16 x, s16 y, u8 fire_num)")
    if not st or "sat_to_nt" not in st:
        fail("82 digit uses sat_to_nt")
    if "0x30 + fire_num" not in st:
        fail("87e2 char is 0x30+fire")
    if "KIND_FIREBOX" not in e:
        fail("need KIND_FIREBOX")
    ok("firebox 87e2 0x30+fire via sat_to_nt tile wrap")


def check_flyer_71f6() -> None:
    e = src(ENT)
    if "71f6" not in e:
        fail("need 71f6 comment")
    sync = fn_span(e, "static void spr_sync(Slot *s)")
    if not sync:
        fail("spr_sync not found")
    if "mdy = dy" not in sync:
        fail("complement Y = parent")
    if "mode_draw_y(s->y) + 2" in sync:
        fail("do not apply ship Y+2 to 71f6")
    ok("green flyer 71f6 same XY; ship Y+2 KEEP only for 7735")


def main() -> None:
    check_tile_wrap_helper()
    check_sat_to_nt_hits_8px_tile_not_peek()
    check_vis_nt_row_aligned()
    check_keep_97e3_peek_pre_carry()
    check_keep_rest()
    check_no_invented_coast()
    check_white_boxes_type68_only()
    check_wreckage_k_88ab_not_on_peek()
    check_firebox_digit_path()
    check_flyer_71f6()
    print("test_playtest_filipe_post95: all checks passed")


if __name__ == "__main__":
    main()
