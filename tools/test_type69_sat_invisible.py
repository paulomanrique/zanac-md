#!/usr/bin/env python3
"""Type 11/69 spawners are SAT occupancy only: color 0, no FRAME_FIRE.

zanac.asm Japan v1 (SHA1 46e9ed7b7f6dfda8eee266476c9ebc4dd9d8fcc2):

  handler_type11 0x7ad4:
    LD (IX+0x00), 0x45          ; become type 69
    LD (IX+0x03), 0x28          ; SAT name = interval 0x28
    JP 0x7a67

  base_spawner_active 0x7a67 first frame:
    copies +01/+02/+03 -> +18/+19/+1c/+1b
    CALL 0x71c5                 ; X random, Y=0; no SAT/color write
    never LD (IX+0x04), ...

  97bc / 97ca:
    LD (HL), 0x45
    LDIR 3 bytes                ; emit, count, interval -> +01/+02/+03
    +04 leftover 0

TMS SAT color 0 is transparent. Old port spr_place(FRAME_FIRE) (SAT 0x0C,
baked nibble 15) drew a white target at SAT Y 0 / draw Y 16.

Usage (from zanac-md):
    python tools/test_type69_sat_invisible.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTITY = ROOT / "src" / "entity.c"
ASM_CANDIDATES = [
    Path("/tmp/refs/zanac-re/source/zanac.asm"),
    Path.home() / "zanac-re" / "source" / "zanac.asm",
    ROOT.parent / "zanac-re" / "source" / "zanac.asm",
]


def fail(msg: str) -> int:
    print("FAIL:", msg, file=sys.stderr)
    return 1


def find_asm() -> Path | None:
    for p in ASM_CANDIDATES:
        if p.is_file():
            return p
    return None


def main() -> int:
    fails = 0
    src = ENTITY.read_text()

    asm_path = find_asm()
    if asm_path:
        asm = asm_path.read_text()
        if not re.search(r"LD\s+\(IX\+0x03\),\s*0x28\s*;\s*0x7af0", asm):
            print("FAIL: zanac.asm 7af0 is not LD (IX+0x03), 0x28", file=sys.stderr)
            fails += 1
        else:
            print("  ASM 7af0: SAT 0x28 (type 11 interval)")
        # 7a67..7a9b first-frame body: no +04 write before SET 7.
        m = re.search(
            r"base_spawner_active:.*?SET\s+7,\s*\(IX\+0x00\)\s*;\s*0x7a98",
            asm,
            re.S,
        )
        if not m:
            print("FAIL: 7a67 first-frame span not found", file=sys.stderr)
            fails += 1
        elif re.search(r"\(IX\+0x04\)", m.group(0)):
            print("FAIL: 7a67 first frame writes +04 (color)", file=sys.stderr)
            fails += 1
        else:
            print("  ASM 7a67: no +04 write (color leftover 0)")
        if not re.search(r"LD\s+\(HL\),\s*0x45\s*;\s*0x97ca", asm):
            print("FAIL: 97ca is not LD (HL), 0x45", file=sys.stderr)
            fails += 1
        else:
            print("  ASM 97ca: type 69 + LDIR emit/count/interval")
    else:
        print("  (zanac.asm not on this machine; C locks only)")

    fn11 = re.search(
        r"static void spawn_spawner\(Slot \*e\)\n\{(.*?)\n\}",
        src,
        re.S,
    )
    fn69 = re.search(
        r"static void spawn_spawner_cmd1\(Slot \*e, u8 emit, u8 count, u8 interval\)\n\{(.*?)\n\}",
        src,
        re.S,
    )
    if not fn11 or not fn69:
        return fail("spawn_spawner / spawn_spawner_cmd1 not found")

    for name, body in (("spawn_spawner", fn11.group(1)),
                       ("spawn_spawner_cmd1", fn69.group(1))):
        if re.search(r"spr_place\s*\(\s*e\s*,\s*FRAME_FIRE\s*\)", body):
            print(f"FAIL: {name} still spr_place(FRAME_FIRE)", file=sys.stderr)
            fails += 1
        else:
            print(f"  {name}: no FRAME_FIRE sprite")
        if not re.search(r"e->sat_col\s*=\s*0\s*;", body):
            print(f"FAIL: {name} must set sat_col = 0", file=sys.stderr)
            fails += 1
        else:
            print(f"  {name}: sat_col = 0")
        if re.search(r"e->spr\s*=\s*NULL\s*;", body):
            print(f"  {name}: spr = NULL")
        elif "spr_detach(e)" in body:
            print(f"  {name}: spr_detach (spr NULL after release)")
        else:
            print(f"FAIL: {name} must leave spr NULL (spr_detach)", file=sys.stderr)
            fails += 1

    if not re.search(r"e->sat\s*=\s*0x28\s*;", fn11.group(1)):
        print("FAIL: type 11 SAT must stay 0x28 (7af0)", file=sys.stderr)
        fails += 1
    else:
        print("  spawn_spawner: sat = 0x28")

    if not re.search(r"e->sat\s*=\s*interval\s*;", fn69.group(1)):
        print("FAIL: cmd1/97bc SAT must stay the interval leftover", file=sys.stderr)
        fails += 1
    else:
        print("  spawn_spawner_cmd1: sat = interval")

    # Occupancy fallback 0x40 must stay leave-alone (not this SAT).
    if "e->sat ? e->sat : (u8)0x40" not in src:
        print("FAIL: sat==0 fallback 0x40 was changed (leave-alone)", file=sys.stderr)
        fails += 1
    else:
        print("  sat==0 occupancy fallback 0x40 unchanged")

    return fails


if __name__ == "__main__":
    sys.exit(main())
