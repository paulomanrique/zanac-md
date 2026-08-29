#!/usr/bin/env python3
"""Pairdesc 57/58 convert dirs are aim-1 / aim+1 / aim, not 90-degree splits.

zanac.asm Japan v1 (SHA1 46e9ed7b7f6dfda8eee266476c9ebc4dd9d8fcc2):

  0x820C  CALL 0x4C91          ; E = 16-dir aim
  0x820F  LD A, E
  0x8210  LD (IX+00), 0x3B     ; self -> type 59
  0x8214  DEC E
  0x8215  LD (IX+1A), E        ; self heading = aim-1
  ... copy Y/X into child1 ...
  0x822E  INC A
  0x822F  LD (HL), A           ; child1 +0x1A = aim+1
  0x8230  LD A, (IX+03)
  0x8233  CP 0x6C / RET Z      ; type 57 SAT 0x6C: one child
  0x8236  LD A, (HL)           ; A = child1 dir = aim+1
  ... copy Y/X into child2 ...
  0x8244  DEC A
  0x8245  LD (HL), A           ; type 58 child2 +0x1A = aim

  0x8269  type 59: (IX+1A) AND 0x0F, JP 0x81A8 speed 5.

  0x4CF5  LD E,(HL) / RET      ; 4c91 returns dir in E.

The port used aim / aim+12 / aim+4 (90-degree fan vs adjacent 16-dir).

spawn_type_list 0xBECC has 0x39 (57) at 16/21/22 and 0x3A (58) at 52/68/88.

k_stealth_dir[0]=2 stays. Type 11/69 SAT color 0 stays. Cmd 0 bit2 stays.

Usage (from zanac-md):
    python tools/test_pairdesc_5758_dirs.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTITY = ROOT / "src" / "entity.c"
MAPC = ROOT / "src" / "map_script.c"
SPAWN = ROOT / "src" / "data" / "spawn_table.c"
ASM_CANDIDATES = [
    Path("/tmp/zanac-re/source/zanac.asm"),
    Path("/tmp/refs/zanac-re/source/zanac.asm"),
    Path.home() / "zanac-re" / "source" / "zanac.asm",
    ROOT.parent / "zanac-re" / "source" / "zanac.asm",
]


def fail(msg: str) -> None:
    print("FAIL:", msg, file=sys.stderr)


def find_asm() -> Path | None:
    for p in ASM_CANDIDATES:
        if p.is_file():
            return p
    return None


def main() -> int:
    fails = 0
    src = ENTITY.read_text()
    mapc = MAPC.read_text()
    spawn = SPAWN.read_text()

    asm_path = find_asm()
    if asm_path:
        asm = asm_path.read_text()
        checks = (
            (r"CALL\s+0x4c91\s*;\s*0x820c", "820c CALL 0x4C91"),
            (r"LD\s+A,\s*E\s*;\s*0x820f", "820f LD A, E (A=aim)"),
            (r"LD\s+\(IX\+0x00\),\s*0x3b\s*;\s*0x8210", "8210 self type 0x3B"),
            (r"DEC\s+E\s*;\s*0x8214", "8214 DEC E (self aim-1)"),
            (r"LD\s+\(IX\+0x1a\),\s*E\s*;\s*0x8215", "8215 self +1A = E"),
            (r"INC\s+A\s*;\s*0x822e", "822e INC A (child1 aim+1)"),
            (r"LD\s+\(HL\),\s*A\s*;\s*0x822f", "822f child1 +1A = A"),
            (r"CP\s+0x6c\s*;\s*0x8233", "8233 CP 0x6C (type 57 stop)"),
            (r"DEC\s+A\s*;\s*0x8244", "8244 DEC A (child2 aim)"),
            (r"LD\s+\(HL\),\s*A\s*;\s*0x8245", "8245 child2 +1A = A"),
            (r"AND\s+0x0f\s*;\s*0x8273", "8273 type59 AND 0x0F"),
            (r"JP\s+0x81a8\s*;\s*0x8276", "8276 JP 81a8 speed 5"),
            (r"LD\s+E,\s*\(HL\)\s*;\s*0x4cf5", "4cf5 4c91 returns dir in E"),
        )
        for pat, label in checks:
            if not re.search(pat, asm, re.I):
                fail(f"zanac.asm missing {label}")
                fails += 1
            else:
                print(f"  ASM {label}")
    else:
        print("  (zanac.asm not on this machine; C locks only)")

    step = re.search(
        r"static void pairdesc_step\(Slot \*e\)\n\{(.*?)\nstatic ",
        src,
        re.S,
    )
    if not step:
        fail("pairdesc_step not found")
        fails += 1
    else:
        body = step.group(1)
        if "dir + (k ? 4 : 12)" in body or "(k ? 4 : 12)" in body:
            fail("pairdesc_step still uses aim/+4/+12 (90-degree split)")
            fails += 1
        if re.search(r"init_type59\(\s*e,\s*e->x,\s*e->y,\s*dir\s*\)", body):
            fail("pairdesc_step self still uses raw aim (need aim-1)")
            fails += 1
        if "init_type59(e, e->x, e->y, (u8)(dir - 1))" not in body:
            fail("pairdesc_step self must be init_type59(..., dir - 1)")
            fails += 1
        else:
            print("  pairdesc_step self: aim-1")
        if "init_type59(c, e->x, e->y, (u8)(k ? dir : (dir + 1)))" not in body:
            fail("pairdesc_step children must be aim+1 then aim")
            fails += 1
        else:
            print("  pairdesc_step children: k==0 aim+1, k==1 aim")
        if "aim_4c91(e->x, e->y)" not in body:
            fail("pairdesc_step must still call aim_4c91")
            fails += 1
        else:
            print("  pairdesc_step: aim_4c91")

    init = re.search(
        r"static void init_type59\(Slot \*c, s16 x, s16 y, u8 dir\)\n\{(.*?)\n\}",
        src,
        re.S,
    )
    if not init:
        fail("init_type59 not found")
        fails += 1
    else:
        body = init.group(1)
        if "apply_dir_88(c, (u8)(dir & 15), 5)" not in body:
            fail("init_type59 must AND 0x0F and apply_dir_88 speed 5")
            fails += 1
        else:
            print("  init_type59: dir & 15, speed 5 (wraps DEC/INC)")

    # 0xBECC must still emit types 57/58 so the convert path is reachable.
    types = re.search(
        r"const u8 spawn_type_list\[SPAWN_TYPE_LEN\] = \{([^}]+)\}",
        spawn,
    )
    if not types:
        fail("spawn_type_list not found")
        fails += 1
    else:
        vals = [int(x, 16) for x in re.findall(r"0x[0-9A-Fa-f]{2}", types.group(1))]
        if vals.count(0x39) < 3 or vals.count(0x3A) < 3:
            fail(f"spawn_type_list 57/58 counts {vals.count(0x39)}/{vals.count(0x3A)}")
            fails += 1
        else:
            print(f"  spawn_type_list: 0x39 x{vals.count(0x39)}, 0x3A x{vals.count(0x3A)}")

    # PR #48 leave-alone: stealth dir[0] is 2.
    md = re.search(r"static const u8 k_stealth_dir\[4\] = \{([^}]+)\}", src)
    if not md:
        fail("k_stealth_dir not found")
        fails += 1
    else:
        ds = [int(x, 0) for x in re.findall(r"0x[0-9A-Fa-f]+|\b\d+\b", md.group(1))]
        if ds != [2, 6, 4, 4]:
            fail(f"k_stealth_dir {ds} want [2, 6, 4, 4]")
            fails += 1
        else:
            print("  k_stealth_dir: [2, 6, 4, 4] (PR #48 stays)")

    # PR #46 / #47 leave-alones.
    for name, pat in (
        ("spawn_spawner", r"static void spawn_spawner\(Slot \*e\)\n\{(.*?)\n\}"),
        (
            "spawn_spawner_cmd1",
            r"static void spawn_spawner_cmd1\(Slot \*e, u8 emit, u8 count, u8 interval\)\n\{(.*?)\n\}",
        ),
    ):
        m = re.search(pat, src, re.S)
        if not m:
            fail(f"{name} not found")
            fails += 1
            continue
        if re.search(r"spr_place\s*\(\s*e\s*,\s*FRAME_FIRE\s*\)", m.group(1)):
            fail(f"{name} spr_place(FRAME_FIRE) was restored")
            fails += 1
        elif "e->sat_col = 0;" not in m.group(1):
            fail(f"{name} sat_col=0 was removed")
            fails += 1
        else:
            print(f"  {name}: sat_col 0, no FRAME_FIRE")

    fn = re.search(
        r"static void cmd_spawn_ctrl\(u8 cmd, const u8 \*ops\)\n\{(.*?)\n\}",
        mapc,
        re.S,
    )
    if not fn or "cmd_place_tiles" not in fn.group(1):
        fail("cmd_spawn_ctrl bit2 -> cmd_place_tiles was reverted")
        fails += 1
    else:
        print("  cmd_spawn_ctrl: bit2 still falls into cmd_place_tiles")

    if fails:
        print(f"{fails} FAIL(s)", file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
