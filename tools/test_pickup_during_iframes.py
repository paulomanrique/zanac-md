#!/usr/bin/env python3
"""44ea ship collide is CP 0x81, not s_invuln.

zanac.asm Japan v1 (SHA1 46e9ed7b7f6dfda8eee266476c9ebc4dd9d8fcc2):

  LAB_ram_44ea 0x44EA (used by 44B0 pickups and 44D4 ship leg):
    44EA  LD A,(0xE300)
    44ED  CP 0x81
    44EF  JR NZ,0x453C          ; NC — no ship collide
    44F1  IY=E300 / CALL 0x4560

  44B0 callers (no +1B / +05 bit7 test before 44ea):
    78B7  type63 chip
    8752  type62 riser
    89E7  type72 orb
    8E81  type83 fireup

  player_ship_handler spawn:
    75D5  type 1 -> SET 7 -> 0x81
    75F7  +1B=0x40 / 75FB SET 7 +05

  player_ship_update 0x7710:
    BIT 7 +05, XOR +04 0x0E, DEC +1B, RES 7 at 0.
    Type stays 0x81 for the whole countdown.

  handler_type60 0x869E first frame:
    86A4  BIT 7 +05 / JR Z,86B1   ; no latch -> real death
    86AA  LD (IX+0x00),0x81 / JP 0x7612

  collision_response 0x453E remaps both sides; 7904 then DEC HP.

Port collide_player used to `if (player_invincible()) return;` which
blocked 44B0 pickups and 453E enemy remap for the whole 64-count
(spawn blink and chip 78d0). Death (type 60) must still skip.

Usage (from zanac-md):
    python tools/test_pickup_during_iframes.py
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
        if not re.search(
            r"LD\s+A,\s*\(0xe300\)\s*;\s*0x44ea", asm, re.I
        ):
            fail("44ea must LD A,(E300)")
            fails += 1
        else:
            print("  ASM 44ea: LD A,(E300)")
        if not re.search(r"CP\s+0x81\s*;\s*0x44ed", asm, re.I):
            fail("44ed must CP 0x81")
            fails += 1
        else:
            print("  ASM 44ed: CP 0x81")
        # 44ea body must not test +1B or +05 bit7
        m44 = re.search(
            r"LD\s+A,\s*\(0xe300\)\s*;\s*0x44ea.*?"
            r"CALL\s+0x4560\s*;\s*0x44f5",
            asm,
            re.I | re.S,
        )
        if not m44:
            fail("44ea..44f5 span not found")
            fails += 1
        else:
            span = m44.group(0)
            if re.search(r"0x1[Bb]|0x05", span):
                fail("44ea must not test +1B or +05")
                fails += 1
            else:
                print("  ASM 44ea: no +1B / +05 test")
        if not re.search(r"CALL\s+0x44b0\s*;\s*0x78b7", asm, re.I):
            fail("type63 must CALL 0x44B0")
            fails += 1
        else:
            print("  ASM 78b7: chip 44B0")
        if not re.search(r"CALL\s+0x44b0\s*;\s*0x8752", asm, re.I):
            fail("type62 must CALL 0x44B0")
            fails += 1
        else:
            print("  ASM 8752: riser 44B0")
        if not re.search(r"CALL\s+0x44b0\s*;\s*0x89e7", asm, re.I):
            fail("type72 must CALL 0x44B0")
            fails += 1
        else:
            print("  ASM 89e7: orb 44B0")
        if not re.search(r"CALL\s+0x44b0\s*;\s*0x8e81", asm, re.I):
            fail("type83 must CALL 0x44B0")
            fails += 1
        else:
            print("  ASM 8e81: fireup 44B0")
        if not re.search(
            r"LD\s+\(IX\+0x1b\),\s*0x40\s*;\s*0x75f7", asm, re.I
        ):
            fail("ship spawn 75f7 must +1B=0x40")
            fails += 1
        else:
            print("  ASM 75f7: spawn +1B=0x40")
        if not re.search(
            r"BIT\s+7,\s*\(IX\+0x05\)\s*;\s*0x7710", asm, re.I
        ):
            fail("7710 must BIT 7 +05 (blink, type stays 0x81)")
            fails += 1
        else:
            print("  ASM 7710: blink only, type stays 0x81")
        if not re.search(
            r"BIT\s+7,\s*\(IX\+0x05\)\s*;\s*0x86a4", asm, re.I
        ):
            fail("type60 86a4 must BIT 7 +05 (cancel death)")
            fails += 1
        else:
            print("  ASM 86a4: type60 cancel if +05 bit7")
    else:
        print("  (zanac.asm not on this machine; C locks only)")

    collide = fn_span(ent, "static void collide_player(void)")
    if not collide:
        fail("collide_player not found")
        return 1

    if re.search(r"if\s*\(\s*player_invincible\s*\(\s*\)\s*\)", collide):
        fail("collide_player must not early-out on player_invincible()")
        fails += 1
    else:
        print("  collide_player: no player_invincible() early-out")

    if "player_dead()" not in collide or "player_is_over()" not in collide:
        fail("collide_player must still skip when dead/over (type != 0x81)")
        fails += 1
    else:
        print("  collide_player: dead/over still skip (type 60)")

    # 44B0 pickups must still be in the loop (reachable during i-frames).
    for kind, label in (
        ("KIND_CHIP", "chip"),
        ("KIND_RISER", "riser"),
        ("KIND_FIREUP", "fireup"),
        ("KIND_ORB", "orb"),
    ):
        blk = kind_block(collide, kind)
        if not blk:
            fail(f"collide_player {kind} block not found")
            fails += 1
        else:
            print(f"  collide_player: {label} 44B0 still in loop")

    # Hostile remap still runs; player_hit no-ops on s_invuln.
    if "player_hit()" not in collide:
        fail("collide_player must still player_hit() on hostile (453E)")
        fails += 1
    else:
        print("  collide_player: hostile still player_hit (453E)")

    hit = fn_span(ply, "void player_hit(void)")
    if not hit:
        fail("player_hit not found")
        return 1
    if "s_invuln" not in hit:
        fail("player_hit must still no-op on s_invuln (86a4)")
        fails += 1
    else:
        print("  player_hit: still no-op on s_invuln")

    grant = fn_span(ply, "void player_grant_iframes(void)")
    if not grant or "s_invuln = PLAYER_IFRAMES" not in grant:
        fail("player_grant_iframes must still assign 0x40 (PR #54)")
        fails += 1
    else:
        print("  KEEP: player_grant_iframes assign 0x40")

    chip = kind_block(collide, "KIND_CHIP")
    if not chip or "player_grant_iframes" not in chip:
        fail("KIND_CHIP must still player_grant_iframes (78d0)")
        fails += 1
    else:
        print("  KEEP: KIND_CHIP player_grant_iframes")
    if not chip or "entity_inc_encounter_b" not in chip:
        fail("KIND_CHIP must still entity_inc_encounter_b (78d4)")
        fails += 1
    else:
        print("  KEEP: KIND_CHIP bfc8")

    fireup = kind_block(collide, "KIND_FIREUP")
    if fireup and "player_grant_iframes" in fireup:
        fail("KIND_FIREUP 8e92 writes +1B=0, not 0x40")
        fails += 1
    else:
        print("  KEEP: KIND_FIREUP no player_grant_iframes")

    riser = kind_block(collide, "KIND_RISER")
    if riser and (
        "player_grant_iframes" in riser or "entity_inc_encounter_b" in riser
    ):
        fail("KIND_RISER 875a has no 78d0 / 78d4")
        fails += 1
    else:
        print("  KEEP: KIND_RISER lives-only")

    if "void player_grant_iframes(void);" not in hdr:
        fail("player.h must still declare player_grant_iframes")
        fails += 1
    else:
        print("  KEEP: player.h player_grant_iframes")

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
    t21 = fn_span(
        ent, "static void init_frag(Slot *e, s16 x, s16 y, u8 dir, u8 variant)"
    )
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
