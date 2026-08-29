#!/usr/bin/env python3
"""Cmd 0 bit2 falls into cmd 1 (0x97B3) and places type-69 spawners.

zanac.asm Japan v1 (SHA1 46e9ed7b7f6dfda8eee266476c9ebc4dd9d8fcc2):

  0x97A8  LD A,(HL) / LD (E12D),A / INC HL
  0x97AD  BIT 2,A
  0x97AF  JR NZ, 0x97B3          ; same body as cmd 1
  0x97B1  JR 0x97D5
  0x97B3  LD B,(HL) / INC HL / CALL 0x97BC / DJNZ

  0x97CA  LD (HL), 0x45 + LDIR 3  ; emit/count/interval

op_len already consumed 1+1+3N so the stream stayed in sync. The handler
only stored E12D and dropped the placement records.

Live blob records (cmd 0x80, bit2 set):

  0xA67F row 100  E12D=07 N=1  (30,20,60)          script 0xA65C
  0xAE29 row 1000 E12D=05 N=2  (17,8,200)(18,8,100) script 0xAD61
  0xAED6 row 2300 E12D=06 N=3  (54,3,200)...        script 0xAD61
  0xB737 row 1200 E12D=07 N=2  (14,10,60)(15,10,60) script 0xB61A

Type 11/69 SAT color 0 / no FRAME_FIRE stays. Peek 97e3 / 4BDF / HUD
BG_B / GO skip / disc sanitizer / wrap Y 8 / boot peek NT 31 stay.

Usage (from zanac-md):
    python tools/test_cmd0_bit2_place.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPC = ROOT / "src" / "map_script.c"
ENTITY = ROOT / "src" / "entity.c"
BLOB = ROOT / "res" / "map_blob.bin"
BLOB_BASE = 0x9B64
ASM_CANDIDATES = [
    Path("/tmp/refs/zanac-re/source/zanac.asm"),
    Path.home() / "zanac-re" / "source" / "zanac.asm",
    ROOT.parent / "zanac-re" / "source" / "zanac.asm",
]

LIVE = (
    (0xA67F, 100, 0x07, ((30, 20, 60),)),
    (0xAE29, 1000, 0x05, ((17, 8, 200), (18, 8, 100))),
    (0xAED6, 2300, 0x06, ((54, 3, 200), (58, 10, 120), (53, 8, 240))),
    (0xB737, 1200, 0x07, ((14, 10, 60), (15, 10, 60))),
)


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
    src = MAPC.read_text()
    ent = ENTITY.read_text()

    asm_path = find_asm()
    if asm_path:
        asm = asm_path.read_text()
        if not re.search(r"BIT\s+2,\s*A\s*;\s*0x97ad", asm, re.I):
            print("FAIL: zanac.asm 97ad is not BIT 2,A", file=sys.stderr)
            fails += 1
        else:
            print("  ASM 97ad: BIT 2,A")
        if not re.search(r"JR\s+NZ,\s*0x97b3\s*;\s*0x97af", asm, re.I):
            print("FAIL: zanac.asm 97af is not JR NZ,0x97b3", file=sys.stderr)
            fails += 1
        else:
            print("  ASM 97af: JR NZ, 0x97B3 (cmd 1 body)")
        if not re.search(r"LD\s+\(HL\),\s*0x45\s*;\s*0x97ca", asm):
            print("FAIL: 97ca is not LD (HL), 0x45", file=sys.stderr)
            fails += 1
        else:
            print("  ASM 97ca: type 69 + LDIR emit/count/interval")
    else:
        print("  (zanac.asm not on this machine; C/blob locks only)")

    fn = re.search(
        r"static void cmd_spawn_ctrl\(u8 cmd, const u8 \*ops\)\n\{(.*?)\n\}",
        src,
        re.S,
    )
    if not fn:
        return fail("cmd_spawn_ctrl not found")
    body = fn.group(1)
    if "ops[0] & 0x04" not in body and "ops[0]&0x04" not in body:
        print("FAIL: cmd_spawn_ctrl must test operand bit2", file=sys.stderr)
        fails += 1
    else:
        print("  cmd_spawn_ctrl: tests bit2")
    if "cmd_place_tiles" not in body:
        print("FAIL: cmd_spawn_ctrl bit2 must fall into cmd_place_tiles", file=sys.stderr)
        fails += 1
    else:
        print("  cmd_spawn_ctrl: bit2 -> cmd_place_tiles")

    oplen = re.search(
        r"case MAPCMD_SPAWN_CTRL:\s*if \(ops\[0\] & 0x04\)\s*\{\s*n = ops\[1\];"
        r"\s*return \(u16\)\(1 \+ 1 \+ 3 \* n\);",
        src,
        re.S,
    )
    if not oplen:
        print("FAIL: op_len cmd 0 bit2 must stay 1+1+3N", file=sys.stderr)
        fails += 1
    else:
        print("  op_len: cmd 0 bit2 is 1+1+3N")

    if not BLOB.is_file():
        print("FAIL: res/map_blob.bin missing", file=sys.stderr)
        fails += 1
    else:
        blob = BLOB.read_bytes()

        def at(addr: int, n: int = 1) -> bytes:
            off = addr - BLOB_BASE
            return blob[off : off + n]

        for pc, row, e12d, recs in LIVE:
            rec_row = at(pc, 2)[0] | (at(pc, 2)[1] << 8)
            cmd = at(pc + 2)[0]
            op = at(pc + 3)[0]
            n = at(pc + 4)[0]
            got = []
            q = pc + 5
            for _ in recs:
                got.append((at(q)[0], at(q + 1)[0], at(q + 2)[0]))
                q += 3
            if rec_row != row or (cmd & 0x0F) != 0 or op != e12d or n != len(recs) or tuple(got) != recs:
                print(
                    f"FAIL: blob {pc:#x} is not cmd0 bit2 row {row} E12D={e12d:02X} {recs}",
                    file=sys.stderr,
                )
                fails += 1
            else:
                print(f"  blob {pc:#x}: row {row} E12D={e12d:02X} N={n} {recs}")

    # PR #46: type 11/69 stay SAT color 0, no FRAME_FIRE.
    for name, pat in (
        ("spawn_spawner", r"static void spawn_spawner\(Slot \*e\)\n\{(.*?)\n\}"),
        (
            "spawn_spawner_cmd1",
            r"static void spawn_spawner_cmd1\(Slot \*e, u8 emit, u8 count, u8 interval\)\n\{(.*?)\n\}",
        ),
    ):
        m = re.search(pat, ent, re.S)
        if not m:
            print(f"FAIL: {name} not found", file=sys.stderr)
            fails += 1
            continue
        if re.search(r"spr_place\s*\(\s*e\s*,\s*FRAME_FIRE\s*\)", m.group(1)):
            print(f"FAIL: {name} spr_place(FRAME_FIRE) was restored", file=sys.stderr)
            fails += 1
        elif "e->sat_col = 0;" not in m.group(1):
            print(f"FAIL: {name} sat_col=0 was removed", file=sys.stderr)
            fails += 1
        else:
            print(f"  {name}: sat_col 0, no FRAME_FIRE")

    return fails


if __name__ == "__main__":
    sys.exit(main())
