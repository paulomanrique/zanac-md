#!/usr/bin/env python3
"""Type 83 fire-up collect does 8e9f SET 7 +05 with +1B=0.

zanac.asm Japan v1 (SHA1 46e9ed7b7f6dfda8eee266476c9ebc4dd9d8fcc2):

  handler_type83 0x8E3A collect (after 44B0 clear):
    8E89  IY=E300 / (IY+0)=0x81
    8E91  SUB A / LD (IY+0x1B),A           ; +1B := 0 (not 0x40)
    8E95  E148 -= 5 (floor 0)
    8E9F  SET 7,(IY+0x05)                  ; 86a4 cancel latch
    8EA3  CALL 0x48D0 / 0xBFC8 / JP 0x7548

  handler_type60 0x869E first frame:
    86A4  BIT 7,(IX+0x05) / JR Z,86B1      ; no latch -> real death
    86AA  LD (IX+0x00),0x81 / JP 0x7612    ; latch set -> cancel death

  player_ship_update 0x7710:
    BIT 7,(IX+0x05) / JP Z,772C
    XOR (IX+0x04),0x0E
    DEC (IX+0x1B)
    JR NZ,772C
    RES 7,(IX+0x05) / LD (IX+0x04),0x8F

  +1B=0 + SET 7: next 7710 DEC wraps 0→255 (256-frame blink), then RES 7.

Port KIND_FIREUP used to skip the latch, so player_hit() ran on the next
hostile (s_invuln==0). Must NOT call player_grant_iframes (that assigns 0x40).

Usage (from zanac-md):
    python tools/test_type83_8e9f_latch.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTITY = ROOT / "src" / "entity.c"
PLAYER = ROOT / "src" / "player.c"
PLAYER_H = ROOT / "inc" / "player.h"
ASM_CANDIDATES = [
    Path("/tmp/zanac-re/source/zanac.asm"),
    Path("/tmp/refs/zanac-re/source/zanac.asm"),
    Path.home() / "zanac-re" / "source" / "zanac.asm",
    ROOT.parent / "zanac-re" / "source" / "zanac.asm",
]


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)


def load_asm() -> str | None:
    for p in ASM_CANDIDATES:
        if p.is_file():
            return p.read_text(encoding="utf-8", errors="replace")
    return None


def fn_span(src: str, sig: str) -> str | None:
    m = re.search(rf"{re.escape(sig)}\s*\{{", src)
    if not m:
        return None
    i = m.end() - 1
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i : j + 1]
    return None


def kind_block(src: str, kind: str) -> str | None:
    m = re.search(
        rf"if \(e->kind == {re.escape(kind)}\)\s*\{{",
        src,
    )
    if not m:
        return None
    i = m.end() - 1
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i : j + 1]
    return None


def main() -> int:
    fails = 0
    ent = ENTITY.read_text(encoding="utf-8", errors="replace")
    ply = PLAYER.read_text(encoding="utf-8", errors="replace")
    hdr = PLAYER_H.read_text(encoding="utf-8", errors="replace")
    asm = load_asm()

    if asm:
        if not re.search(
            r"SET\s+7,\s*\(IY\+0x05\)\s*;\s*0x8e9f", asm, re.I
        ):
            fail("type83 8e9f must SET 7,(IY+0x05)")
            fails += 1
        else:
            print("  ASM 8e9f: SET 7,(IY+0x05) cancel latch")
        if not re.search(
            r"LD\s+\(IY\+0x1b\),\s*A\s*;\s*0x8e92", asm, re.I
        ):
            fail("type83 8e92 must LD (IY+0x1B),A (A=0)")
            fails += 1
        else:
            print("  ASM 8e92: fireup +1B = 0, not 0x40")
        if not re.search(
            r"BIT\s+7,\s*\(IX\+0x05\)\s*;\s*0x86a4", asm, re.I
        ):
            fail("type60 86a4 must BIT 7,(IX+0x05)")
            fails += 1
        else:
            print("  ASM 86a4: type60 cancel if +05 bit7")
        if not re.search(
            r"DEC\s+\(IX\+0x1b\)\s*;\s*0x771f", asm, re.I
        ):
            fail("7710 must DEC (IX+0x1B)")
            fails += 1
        else:
            print("  ASM 771f: DEC +1B (wrap 0→255 when latch set)")
    else:
        print("  (zanac.asm not on this machine; C locks only)")

    if "void player_fireup_latch(void);" not in hdr:
        fail("player.h must declare player_fireup_latch")
        fails += 1
    else:
        print("  player.h: player_fireup_latch declared")

    fire = fn_span(ply, "void player_fireup_latch(void)")
    if not fire:
        fail("player_fireup_latch not found")
        return 1
    if "s_invuln = 0" not in fire:
        fail("player_fireup_latch must assign s_invuln = 0 (8e92)")
        fails += 1
    else:
        print("  player_fireup_latch: s_invuln = 0")
    if "s_if_latch = 1" not in fire:
        fail("player_fireup_latch must SET s_if_latch (8e9f)")
        fails += 1
    else:
        print("  player_fireup_latch: s_if_latch = 1")
    if "PLAYER_IFRAMES" in fire:
        fail("player_fireup_latch must not assign 0x40")
        fails += 1
    else:
        print("  player_fireup_latch: not 0x40")

    grant = fn_span(ply, "void player_grant_iframes(void)")
    if not grant or "s_invuln = PLAYER_IFRAMES" not in grant:
        fail("player_grant_iframes must still assign 0x40 (PR #54)")
        fails += 1
    else:
        print("  KEEP: player_grant_iframes assign 0x40")
    if grant and "s_if_latch = 1" not in grant:
        fail("player_grant_iframes must still SET 7 (78cc)")
        fails += 1
    else:
        print("  KEEP: player_grant_iframes SET latch")

    hit = fn_span(ply, "void player_hit(void)")
    if not hit:
        fail("player_hit not found")
        return 1
    if "s_invuln" not in hit:
        fail("player_hit must still no-op on s_invuln (86a4)")
        fails += 1
    else:
        print("  player_hit: still no-op on s_invuln")
    if "s_if_latch" not in hit:
        fail("player_hit must no-op on s_if_latch (86a4 BIT 7 +05)")
        fails += 1
    else:
        print("  player_hit: no-op on s_if_latch (8e9f / 86a4)")

    upd = fn_span(ply, "void player_update(void)")
    if not upd:
        fail("player_update not found")
        return 1
    if "s_if_latch" not in upd or "s_invuln--" not in upd:
        fail("7710 must tick on latch (DEC +1B wraps 0→255)")
        fails += 1
    else:
        print("  player_update: 7710 ticks latch / DEC +1B")

    collide = fn_span(ent, "static void collide_player(void)")
    if not collide:
        fail("collide_player not found")
        return 1
    if re.search(r"if\s*\(\s*player_invincible\s*\(\s*\)\s*\)", collide):
        fail("collide_player must not early-out on player_invincible()")
        fails += 1
    else:
        print("  KEEP: collide_player no player_invincible() early-out")

    fireup = kind_block(collide, "KIND_FIREUP")
    if not fireup:
        fail("KIND_FIREUP block not found")
        return 1
    if "player_fireup_latch" not in fireup:
        fail("KIND_FIREUP must player_fireup_latch (8e9f)")
        fails += 1
    else:
        print("  KIND_FIREUP: player_fireup_latch")
    if "player_grant_iframes" in fireup:
        fail("KIND_FIREUP 8e92 writes +1B=0, not 0x40")
        fails += 1
    else:
        print("  KEEP: KIND_FIREUP no player_grant_iframes")
    if "entity_inc_encounter_b" not in fireup:
        fail("KIND_FIREUP must still entity_inc_encounter_b (8ea6)")
        fails += 1
    else:
        print("  KEEP: KIND_FIREUP bfc8")

    chip = kind_block(collide, "KIND_CHIP")
    if not chip or "player_grant_iframes" not in chip:
        fail("KIND_CHIP must still player_grant_iframes (78d0)")
        fails += 1
    else:
        print("  KEEP: KIND_CHIP player_grant_iframes")

    riser = kind_block(collide, "KIND_RISER")
    if riser and (
        "player_grant_iframes" in riser
        or "player_fireup_latch" in riser
        or "entity_inc_encounter_b" in riser
    ):
        fail("KIND_RISER 875a has no 78d0 / 8e9f / 78d4")
        fails += 1
    else:
        print("  KEEP: KIND_RISER lives-only")

    if "e->sat_col = 0x89" not in ent:
        fail("type 10 sat_col 0x89 was reverted")
        fails += 1
    else:
        print("  KEEP: type 10 sat_col 0x89")

    complete = fn_span(ent, "void entity_alc_complete(void)")
    if not complete or "0x20" not in complete:
        fail("entity_alc_complete must stay (PR #53)")
        fails += 1
    else:
        print("  KEEP: entity_alc_complete")
    reset = fn_span(ent, "void entity_alc_reset(void)")
    if not reset or "0x20" in reset:
        fail("entity_alc_reset must not bake +0x20")
        fails += 1
    else:
        print("  KEEP: entity_alc_reset no +0x20")

    if fails:
        print(f"{fails} FAIL(s)", file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
