#!/usr/bin/env python3
"""Warp / level-complete LAB_414d does E132 += 0x20 after alc_reset.

zanac.asm Japan v1 (SHA1 46e9ed7b7f6dfda8eee266476c9ebc4dd9d8fcc2):

  reset_entities 0x40D6: LD (E132),A   (A=0)
  level_complete_handler 0x40DA: CALL 0x40BA; E722==0 JP 414d; else load;
                                 fall through to LAB_414d
  LAB_414d 0x4152:
    LD HL,E132 / LD A,(HL) / ADD A,0x20 / LD (HL),A
    JR NC,415d / LD (HL),0xFF
  Main loop 0x4088 BIT 5,E102 JP NZ,40DA.
  SET 5 writers: type72 black orb 0x8A11, award 0x0F 0x91FA, LAB_92af 0x92B8.

  First boot (title 4065 / LAB_4074) never enters 40DA, so E132 stays 0.
  entity_alc_reset must not bake +0x20. Cmd 9 still must not reset.

Usage (from zanac-md):
    python tools/test_warp_e132_plus20.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPC = ROOT / "src" / "map_script.c"
ENTITY = ROOT / "src" / "entity.c"
ENTITY_H = ROOT / "inc" / "entity.h"
ASM_CANDIDATES = [
    Path("/tmp/zanac-re/source/zanac.asm"),
    Path("/tmp/refs/zanac-re/source/zanac.asm"),
    Path.home() / "zanac-re" / "source/zanac.asm",
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


def main() -> int:
    fails = 0
    mapc = MAPC.read_text(encoding="utf-8")
    ent = ENTITY.read_text(encoding="utf-8")
    hdr = ENTITY_H.read_text(encoding="utf-8")

    asm = load_asm()
    if asm:
        if not re.search(r"LD\s+\(0xe132\),\s*A\s*;\s*0x40d6", asm, re.I):
            fail("reset_entities 40d6 must zero E132")
            fails += 1
        else:
            print("  ASM 40d6: reset_entities zeros E132")
        if not re.search(r"ADD\s+A,\s*0x20\s*;\s*0x4156", asm, re.I):
            fail("LAB_414d 4156 must ADD A,0x20")
            fails += 1
        else:
            print("  ASM 4156: LAB_414d E132 += 0x20")
        if not re.search(r"LD\s+\(HL\),\s*0xFF\s*;\s*0x415b", asm, re.I):
            fail("LAB_414d 415b must sat 0xFF")
            fails += 1
        else:
            print("  ASM 415b: E132 sat 0xFF")
        if not re.search(r"JP\s+NZ,\s*0x40da\s*;\s*0x408a", asm, re.I):
            fail("main loop 408a must JP NZ 40da on E102 bit5")
            fails += 1
        else:
            print("  ASM 408a: BIT 5 -> level_complete")
        if not re.search(r"SET\s+5,\s*\(HL\)\s*;\s*0x8a11", asm, re.I):
            fail("type72 8a11 must SET 5,E102")
            fails += 1
        else:
            print("  ASM 8a11: black orb SET 5")
        if not re.search(r"SET\s+5,\s*\(HL\)\s*;\s*0x91fa", asm, re.I):
            fail("award 0x0F 91fa must SET 5,E102")
            fails += 1
        else:
            print("  ASM 91fa: award 0x0F SET 5")
        if not re.search(r"SET\s+5,\s*\(HL\)\s*;\s*0x92b8", asm, re.I):
            fail("LAB_92af 92b8 must SET 5,E102")
            fails += 1
        else:
            print("  ASM 92b8: ending SET 5")
    else:
        print("  (zanac.asm not on this machine; C locks only)")

    reset = fn_span(ent, "void entity_alc_reset(void)")
    if not reset:
        fail("entity_alc_reset not found")
        return 1
    if "0x20" in reset:
        fail("entity_alc_reset must not bake LAB_414d +0x20 (first boot stays 0)")
        fails += 1
    else:
        print("  entity_alc_reset: no +0x20")
    if "s_e132 = 0" not in reset:
        fail("entity_alc_reset must still zero s_e132")
        fails += 1
    else:
        print("  entity_alc_reset: still zeros s_e132")

    complete = fn_span(ent, "void entity_alc_complete(void)")
    if not complete:
        fail("entity_alc_complete not found")
        fails += 1
    else:
        if "0x20" not in complete:
            fail("entity_alc_complete must ADD 0x20")
            fails += 1
        else:
            print("  entity_alc_complete: E132 += 0x20")
        if "0xFF" not in complete and "255" not in complete:
            fail("entity_alc_complete must sat 0xFF")
            fails += 1
        else:
            print("  entity_alc_complete: sat 0xFF")

    if "void entity_alc_complete(void);" not in hdr:
        fail("entity.h must declare entity_alc_complete")
        fails += 1
    else:
        print("  entity.h: entity_alc_complete declared")

    boot = fn_span(mapc, "static void script_boot(u8 round, u16 pc)")
    if not boot or "entity_alc_reset" not in boot:
        fail("script_boot must still entity_alc_reset (first boot / warp)")
        fails += 1
    else:
        print("  script_boot: still entity_alc_reset")
    if boot and "entity_alc_complete" in boot:
        fail("script_boot must not entity_alc_complete (first boot E132 stays 0)")
        fails += 1
    else:
        print("  script_boot: no entity_alc_complete")

    ending = fn_span(mapc, "static void arm_ending_stream(void)")
    if not ending or "entity_alc_reset" not in ending:
        fail("arm_ending_stream must still entity_alc_reset")
        fails += 1
    else:
        print("  arm_ending_stream: still entity_alc_reset")
    if ending and "entity_alc_complete" in ending:
        fail("arm_ending_stream must not bake +0x20 (cmd 9 ending is not 40DA)")
        fails += 1
    else:
        print("  arm_ending_stream: no entity_alc_complete")

    jump = fn_span(mapc, "static void cmd_script_jump(u8 cmd, const u8 *ops)")
    if not jump:
        fail("cmd_script_jump not found")
        return 1
    if "entity_alc_reset" in jump or "entity_alc_complete" in jump:
        fail("cmd_script_jump must not touch ALC (96e2/9433/941b)")
        fails += 1
    else:
        print("  cmd_script_jump: no alc_reset / alc_complete")

    warp = fn_span(mapc, "void map_script_warp(u16 dest)")
    if not warp or warp.count("entity_alc_complete") < 3:
        fail("map_script_warp must entity_alc_complete on every 40DA exit")
        fails += 1
    else:
        print("  map_script_warp: entity_alc_complete on all exits")

    finish = fn_span(mapc, "static void base_clear_finish(void)")
    if not finish:
        fail("base_clear_finish not found")
        return 1
    if "entity_alc_complete" not in finish:
        fail("base_clear_finish 0x0F / 92af must entity_alc_complete")
        fails += 1
    else:
        print("  base_clear_finish: entity_alc_complete after 0x0F / 92af")
    # 91FD / 9251 do not SET 5.
    m10 = re.search(
        r"if \(mode == 0x10\)\s*\{(.*?)\}", finish, re.S
    )
    m11 = re.search(
        r"if \(mode == 0x11\)\s*\{(.*?)\}", finish, re.S
    )
    if m10 and "entity_alc_complete" in m10.group(1):
        fail("mode 0x10 91FD must not entity_alc_complete")
        fails += 1
    else:
        print("  base_clear_finish 0x10: no +0x20 (91FD CALL 9433)")
    if m11 and "entity_alc_complete" in m11.group(1):
        fail("mode 0x11 9251 must not entity_alc_complete")
        fails += 1
    else:
        print("  base_clear_finish 0x11: no +0x20 (9251 letters)")

    # KEEP: SAT +04 from PR #51; type 21 init still no +04.
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
    elif re.search(r"if\s*\(\s*variant\s*==\s*21\s*\)\s*\n\s*e->sat_col", t21):
        fail("type 21 init must not invent +04")
        fails += 1
    else:
        print("  KEEP: type 21 init still no +04")

    if fails:
        print(f"{fails} FAIL(s)", file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
