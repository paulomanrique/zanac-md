#!/usr/bin/env python3
"""Type 63 chip pickup does 78d0 i-frames + 78d4 bfc8.

zanac.asm Japan v1 (SHA1 46e9ed7b7f6dfda8eee266476c9ebc4dd9d8fcc2):

  handler_type63_power_chip 0x78AF:
    78BF  LD A,0x17 / CALL 0x5189          ; pickup SFX
    78C4  IY=E300 / (IY+0)=0x81
    78CC  SET 7,(IY+0x05)                  ; invuln latch
    78D0  LD (IY+0x1B),0x40                ; 64-frame timer
    78D4  CALL 0xBFC8                      ; E130++ unless E150 bit1
    78D7  INC E10B / CP 6 ...              ; shot_level (already ported)

  handler_type60 0x869E first frame:
    86A4  BIT 7,(IX+0x05) / JR Z,86B1      ; no latch -> real death
    86AA  LD (IX+0x00),0x81 / JP 0x7612    ; latch set -> cancel death

  player_ship_update 0x7710: BIT 7 +05, XOR +04 0x0E, DEC +1B, clear at 0.

  Type 62 875A restores 0x81 + INC E10A only (no 78d0 / no bfc8).
  Type 83 8E89 writes +1B=0 then SET 7 +05 (not 0x40).

Port collide_player KIND_CHIP used to stop at add_shot_level + SFX.

Usage (from zanac-md):
    python tools/test_chip_pickup_78d0.py
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
    ent = ENTITY.read_text(encoding="utf-8")
    ply = PLAYER.read_text(encoding="utf-8")
    hdr = PLAYER_H.read_text(encoding="utf-8")

    asm = load_asm()
    if asm:
        if not re.search(r"SET\s+7,\s*\(IY\+0x05\)\s*;\s*0x78cc", asm, re.I):
            fail("type63 78cc must SET 7,(IY+0x05)")
            fails += 1
        else:
            print("  ASM 78cc: SET 7 player +05")
        if not re.search(
            r"LD\s+\(IY\+0x1b\),\s*0x40\s*;\s*0x78d0", asm, re.I
        ):
            fail("type63 78d0 must LD (IY+0x1B),0x40")
            fails += 1
        else:
            print("  ASM 78d0: +1B = 0x40")
        if not re.search(r"CALL\s+0xbfc8\s*;\s*0x78d4", asm, re.I):
            fail("type63 78d4 must CALL 0xBFC8")
            fails += 1
        else:
            print("  ASM 78d4: CALL bfc8")
        if not re.search(
            r"BIT\s+7,\s*\(IX\+0x05\)\s*;\s*0x86a4", asm, re.I
        ):
            fail("type60 86a4 must BIT 7 +05 (cancel death)")
            fails += 1
        else:
            print("  ASM 86a4: type60 cancel if +05 bit7")
        if not re.search(
            r"LD\s+\(IX\+0x00\),\s*0x81\s*;\s*0x86aa", asm, re.I
        ):
            fail("type60 86aa must restore type 0x81")
            fails += 1
        else:
            print("  ASM 86aa: restore 0x81")
        if re.search(r"LD\s+\(IY\+0x1b\),\s*0x40\s*;\s*0x875", asm, re.I):
            fail("type62 must not write +1B=0x40")
            fails += 1
        else:
            print("  ASM 875a: type62 no 78d0")
        if not re.search(
            r"LD\s+\(IY\+0x1b\),\s*A\s*;\s*0x8e92", asm, re.I
        ):
            fail("type83 8e92 must LD (IY+0x1B),A (A=0)")
            fails += 1
        else:
            print("  ASM 8e92: fireup +1B = 0, not 0x40")
    else:
        print("  (zanac.asm not on this machine; C locks only)")

    if "void player_grant_iframes(void);" not in hdr:
        fail("player.h must declare player_grant_iframes")
        fails += 1
    else:
        print("  player.h: player_grant_iframes declared")

    grant = fn_span(ply, "void player_grant_iframes(void)")
    if not grant:
        fail("player_grant_iframes not found")
        return 1
    if "s_invuln = PLAYER_IFRAMES" not in grant:
        fail("player_grant_iframes must assign s_invuln = PLAYER_IFRAMES (78d0)")
        fails += 1
    else:
        print("  player_grant_iframes: s_invuln = 0x40")
    if "s_invuln +" in grant or "s_invuln++" in grant:
        fail("player_grant_iframes must assign 0x40, not add")
        fails += 1
    else:
        print("  player_grant_iframes: assign, not add")

    shot = fn_span(ply, "void player_add_shot_level(void)")
    if not shot:
        fail("player_add_shot_level not found")
        return 1
    if "s_invuln" in shot or "entity_inc_encounter_b" in shot:
        fail("player_add_shot_level is 78d7+ only (no 78d0 / 78d4)")
        fails += 1
    else:
        print("  player_add_shot_level: still 78d7+ only")

    collide = fn_span(ent, "static void collide_player(void)")
    if not collide:
        fail("collide_player not found")
        return 1

    chip = kind_block(collide, "KIND_CHIP")
    if not chip:
        fail("collide_player KIND_CHIP block not found")
        return 1
    if "player_grant_iframes" not in chip:
        fail("KIND_CHIP must player_grant_iframes (78d0)")
        fails += 1
    else:
        print("  KIND_CHIP: player_grant_iframes")
    if "entity_inc_encounter_b" not in chip:
        fail("KIND_CHIP must entity_inc_encounter_b (78d4)")
        fails += 1
    else:
        print("  KIND_CHIP: entity_inc_encounter_b")
    if "player_add_shot_level" not in chip:
        fail("KIND_CHIP must still player_add_shot_level (78d7)")
        fails += 1
    else:
        print("  KIND_CHIP: still player_add_shot_level")

    fireup = kind_block(collide, "KIND_FIREUP")
    if not fireup or "entity_inc_encounter_b" not in fireup:
        fail("KIND_FIREUP must still entity_inc_encounter_b (8ea6)")
        fails += 1
    else:
        print("  KIND_FIREUP: still bfc8")
    if fireup and "player_grant_iframes" in fireup:
        fail("KIND_FIREUP 8e92 writes +1B=0, not 0x40")
        fails += 1
    else:
        print("  KIND_FIREUP: no player_grant_iframes")

    riser = kind_block(collide, "KIND_RISER")
    if not riser:
        fail("KIND_RISER block not found")
        return 1
    if "player_grant_iframes" in riser or "entity_inc_encounter_b" in riser:
        fail("KIND_RISER 875a has no 78d0 / 78d4")
        fails += 1
    else:
        print("  KIND_RISER: no 78d0 / 78d4")

    # KEEP: PR #51 SAT +04; type 21 init still no +04; PR #53 alc_complete.
    if "e->sat_col = 0x89" not in ent:
        fail("type 10 sat_col 0x89 was reverted")
        fails += 1
    else:
        print("  KEEP: type 10 sat_col 0x89")
    if ent.count("sat_col = 0x8F") < 3:
        fail("types 20/37/38/41 sat_col 0x8F was reverted")
        fails += 1
    else:
        print("  KEEP: type 20/37/38/41 sat_col 0x8F")
    t21 = fn_span(ent, "static void init_frag(Slot *e, s16 x, s16 y, u8 dir, u8 variant)")
    if not t21 or "variant != 21" not in t21:
        fail("type 21 init must still skip +04 (863b)")
        fails += 1
    else:
        print("  KEEP: type 21 init still no +04")

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
