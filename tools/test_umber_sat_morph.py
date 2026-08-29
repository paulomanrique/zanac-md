#!/usr/bin/env python3
"""Types 7/8 umber remaps SAT 0xDC/0xE4 <-> 0xE0/0xE8 on Yvel.hi.

zanac.asm Japan v1 (SHA1 46e9ed7b7f6dfda8eee266476c9ebc4dd9d8fcc2):

  handler_type7_umber 0x791D; shared active 0x7954 (types 7 and 8).
  0x795D  LD A,(IX+09)          ; Yvel high
  0x7960  OR A / JR Z, 0x7971   ; yh==0 -> SAT 0xE0 / IY+03 0xE8
  0x7963  CP 0xFF / JR NZ, 0x79AE
  0x7967  LD (IX+03), 0xDC      ; rising: pat 55 / complement 0xE4
  0x796B  LD (IY+03), 0xE4
  0x7971  LD (IX+03), 0xE0      ; stopped: pat 56 / complement 0xE8
  0x7975  LD (IY+03), 0xE8
  0x7979  CP (IX+08)            ; burst only when the Yvel word is 0

  Type 9 active is 0x7A12 (no 795d morph). Spawn already writes 0xE0/0xE8.

  collision_size_table 0x45C9: sat>>1. 0xDC -> 12x14, 0xE0 -> 14x16.

PR #49 pairdesc dirs stay. k_stealth_dir[0]=2 stays.
Type 11/69 SAT color 0 stays. Cmd 0 bit2 place stays.

Usage (from zanac-md):
    python tools/test_umber_sat_morph.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTITY = ROOT / "src" / "entity.c"
MAPC = ROOT / "src" / "map_script.c"
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


def main() -> int:
    fails = 0
    src = ENTITY.read_text(encoding="utf-8")
    mapc = MAPC.read_text(encoding="utf-8")

    step = re.search(r"static void umber_step\(Slot \*e\)\n\{(.*?)\n\}", src, re.S)
    if not step:
        fail("umber_step not found")
        return 1
    body = step.group(1)

    if "e->variant == 9" in body.split("if (e->variant == 7 || e->variant == 8)")[0]:
        fail("umber_step morph must not run on type 9")
        fails += 1

    if "FRAME_UMBER_B" not in body or "FRAME_UMBER_B_C" not in body:
        fail("umber_step yh==0 must spr_place FRAME_UMBER_B / _C (SAT 0xE0/0xE8)")
        fails += 1
    else:
        print("  umber_step yh==0: FRAME_UMBER_B / FRAME_UMBER_B_C")

    if "FRAME_UMBER);" not in body.replace(" ", "") and "FRAME_UMBER)" not in body:
        # Accept spr_place(e, FRAME_UMBER) but not only FRAME_UMBER_B
        fail("umber_step yh==0xFF must spr_place FRAME_UMBER / _C (SAT 0xDC/0xE4)")
        fails += 1
    elif "yh == 0xFF" not in body and "yh == 0xff" not in body.lower():
        fail("umber_step must test Yvel.hi == 0xFF")
        fails += 1
    else:
        if "spr_place(e, FRAME_UMBER)" not in body or "FRAME_UMBER_C" not in body:
            fail("umber_step yh==0xFF must spr_place FRAME_UMBER / FRAME_UMBER_C")
            fails += 1
        else:
            print("  umber_step yh==0xFF: FRAME_UMBER / FRAME_UMBER_C")

    if "e->bind == 0" not in body or "umber_burst" not in body:
        fail("umber_step must still burst when Yvel word == 0")
        fails += 1
    else:
        print("  umber_step: burst still at bind==0")

    type9 = re.search(r"if \(e->variant == 9\)\n    \{.*?FRAME_UMBER", body, re.S)
    if type9:
        fail("type 9 active must not rematch FRAME_UMBER (7a12 has no morph)")
        fails += 1

    spawn = re.search(r"static void spawn_umber\(Slot \*e, u8 type\)\n\{(.*?)\n\}", src, re.S)
    if not spawn:
        fail("spawn_umber not found")
        fails += 1
    else:
        sb = spawn.group(1)
        if "FRAME_UMBER_B" not in sb or "FRAME_UMBER);" not in sb.replace(" ", ""):
            if "spr_place(e, FRAME_UMBER)" not in sb:
                fail("spawn_umber must still place FRAME_UMBER for types 7/8")
                fails += 1
            else:
                print("  spawn_umber: type 7/8 FRAME_UMBER, type 9 FRAME_UMBER_B")
        else:
            print("  spawn_umber: type 7/8 FRAME_UMBER, type 9 FRAME_UMBER_B")

    m = re.search(r"static const u8 k_frame_sat\[FRAME_N\] = \{([^}]+)\}", src, re.S)
    if not m:
        fail("k_frame_sat not found")
        fails += 1
    else:
        raw = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.S)
        vals = [int(x, 16) for x in re.findall(r"0x[0-9A-Fa-f]+", raw)]
        want = {30: 0xDC, 31: 0xE4, 55: 0xE0, 56: 0xE8}
        for idx, sat in want.items():
            if idx >= len(vals) or vals[idx] != sat:
                fail(f"k_frame_sat[{idx}] want 0x{sat:02X} got {vals[idx] if idx < len(vals) else 'missing'}")
                fails += 1
        else:
            print("  k_frame_sat: UMBER 0xDC/0xE4, UMBER_B 0xE0/0xE8")

    # Hitbox sizes from collision_size_table 0x45C9 (full 128-byte port table).
    col = re.search(r"static const u8 k_col_size\[128\] = \{([^}]+)\}", src, re.S)
    if not col:
        fail("k_col_size not found")
        fails += 1
    else:
        raw = re.sub(r"/\*.*?\*/", "", col.group(1), flags=re.S)
        ks = [int(x, 16) for x in re.findall(r"0x[0-9A-Fa-f]+", raw)]

        def box(sat: int) -> tuple[int, int]:
            idx = sat >> 1
            hy, hx = ks[idx], ks[idx + 1]
            return (16 - 2 * hx, 16 - 2 * hy)

        if box(0xDC) == box(0xE0):
            fail("SAT 0xDC and 0xE0 must differ in k_col_size (morph is hitbox)")
            fails += 1
        else:
            print(f"  hitbox 0xDC={box(0xDC)} 0xE0={box(0xE0)}")

    asm = load_asm()
    if asm:
        for addr, needle in (
            ("0x7967", "0xdc"),
            ("0x796b", "0xe4"),
            ("0x7971", "0xe0"),
            ("0x7975", "0xe8"),
        ):
            if not re.search(rf"{needle}\s*;\s*{addr}", asm, re.I):
                fail(f"zanac.asm {addr} is not {needle}")
                fails += 1
        else:
            print("  zanac.asm 795d: DC/E4 <-> E0/E8")

    # PR #49 leave-alone: pairdesc convert dirs.
    pd = re.search(r"static void pairdesc_step\(Slot \*e\)\n\{(.*?)\n\}", src, re.S)
    if not pd:
        fail("pairdesc_step not found")
        fails += 1
    else:
        pb = pd.group(1)
        if "dir - 1" not in pb or "dir + 1" not in pb:
            fail("pairdesc 57/58 convert dirs were reverted")
            fails += 1
        else:
            print("  pairdesc_step: aim-1 / aim+1 / aim (PR #49 stays)")

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
