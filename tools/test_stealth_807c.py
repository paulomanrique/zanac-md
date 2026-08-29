#!/usr/bin/env python3
"""0x807C stealth/tracker dir[0] is 2 (down-right), not 0 (right).

zanac.asm Japan v1 (SHA1 46e9ed7b7f6dfda8eee266476c9ebc4dd9d8fcc2):

  0x7FAC  LD HL, 0x807C
  0x7FA7  R AND 0x06 / ADD HL, DE
  0x7FB0  LD A,(HL) -> IX+02 X
  0x7FB9  LD E,(HL) / CALL 0x4CF7

  0x807C is data, listed as code. Bytes:

    20 02 D0 06 50 04 A0 04

  (X,dir) = (0x20,2) (0xD0,6) (0x50,4) (0xA0,4)

  vel_dir_table 0x4D65 dir 0: word0=0 word1=0x80  -> right
                 dir 2: word0=0x5A word1=0x5A -> down-right
                 dir 4: word0=0x80 word1=0    -> down

The port apply_dir_88 uses the same 4cf7 index. k_stealth_dir[0] was
rewritten to 0 under the wrong label "down". Types 34/65/66 (+0c=3)
at X=32 then cruise east along Y=0 instead of descending diagonally.
Types 31/33 keep dest Xvel for the flank: 128 vs 90.

Type 11/69 SAT color 0 / no FRAME_FIRE stays. Cmd 0 bit2 -> cmd 1 stays.

Usage (from zanac-md):
    python tools/test_stealth_807c.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTITY = ROOT / "src" / "entity.c"
MAPC = ROOT / "src" / "map_script.c"
VEL = ROOT / "src" / "data" / "vel_dir.c"
ASM_CANDIDATES = [
    Path("/tmp/refs/zanac-re/source/zanac.asm"),
    Path.home() / "zanac-re" / "source" / "zanac.asm",
    ROOT.parent / "zanac-re" / "source" / "zanac.asm",
]

# 0x807C listed as JR NZ / RET NC / LD B / INC B / AND B / INC B
ROM_807C = bytes((0x20, 0x02, 0xD0, 0x06, 0x50, 0x04, 0xA0, 0x04))
WANT_X = (32, 208, 80, 160)
WANT_DIR = (2, 6, 4, 4)


def fail(msg: str) -> None:
    print("FAIL:", msg, file=sys.stderr)


def find_asm() -> Path | None:
    for p in ASM_CANDIDATES:
        if p.is_file():
            return p
    return None


def ints_in(src: str) -> list[int]:
    return [int(x, 0) for x in re.findall(r"0x[0-9A-Fa-f]+|\b\d+\b", src)]


def main() -> int:
    fails = 0
    src = ENTITY.read_text()
    mapc = MAPC.read_text()
    vel = VEL.read_text() if VEL.is_file() else ""

    asm_path = find_asm()
    if asm_path:
        asm = asm_path.read_text()
        if not re.search(r"LD\s+HL,\s*0x807c\s*;\s*0x7fac", asm, re.I):
            fail("zanac.asm 7fac is not LD HL, 0x807C")
            fails += 1
        else:
            print("  ASM 7fac: LD HL, 0x807C")
        if not re.search(r"AND\s+0x06\s*;\s*0x7fa7", asm, re.I):
            fail("zanac.asm 7fa7 is not AND 0x06")
            fails += 1
        else:
            print("  ASM 7fa7: R AND 0x06 (pair index)")
        if not re.search(r"CALL\s+0x4cf7\s*;\s*0x7fba", asm, re.I):
            fail("zanac.asm 7fba is not CALL 0x4CF7")
            fails += 1
        else:
            print("  ASM 7fba: CALL 0x4CF7 (dir from table)")
        # Data-as-code listing of 0x807C..0x8083.
        if not re.search(r"JR\s+NZ,\s*0x8080\s*;\s*0x807c", asm, re.I):
            fail("zanac.asm 807c listing is not JR NZ, 0x8080 (20 02)")
            fails += 1
        else:
            print("  ASM 807c: JR NZ, 0x8080 -> bytes 20 02")
        if not re.search(r"RET\s+NC\s*;\s*0x807e", asm, re.I):
            fail("zanac.asm 807e listing is not RET NC (D0)")
            fails += 1
        else:
            print("  ASM 807e: RET NC -> byte D0")
        if not re.search(r"LD\s+B,\s*0x50\s*;\s*0x807f", asm, re.I):
            fail("zanac.asm 807f listing is not LD B, 0x50 (06 50)")
            fails += 1
        else:
            print("  ASM 807f: LD B, 0x50 -> bytes 06 50")
        db = re.search(
            r"DB\s+((?:0x[0-9A-Fa-f]{2},\s*){15}0x[0-9A-Fa-f]{2})\s*;\s*0x4d65",
            asm,
            re.I,
        )
        if not db:
            fail("vel_dir_table 0x4D65 DB not found")
            fails += 1
        else:
            b = [int(x, 16) for x in re.findall(r"0x[0-9A-Fa-f]{2}", db.group(1))]
            d0 = (b[0] | (b[1] << 8), b[2] | (b[3] << 8))
            d2 = (b[8] | (b[9] << 8), b[10] | (b[11] << 8))
            if d0 != (0, 0x80) or d2 != (0x5A, 0x5A):
                fail(f"0x4D65 dir0={d0} dir2={d2}, want (0,128) (90,90)")
                fails += 1
            else:
                print("  ASM 4d65: dir 0 = (Y0,X128) right; dir 2 = (Y90,X90)")
    else:
        print("  (zanac.asm not on this machine; C locks only)")

    pairs = list(zip(ROM_807C[0::2], ROM_807C[1::2]))
    if [p[0] for p in pairs] != list(WANT_X) or [p[1] for p in pairs] != list(WANT_DIR):
        fail(f"ROM_807C decode {pairs} != {list(zip(WANT_X, WANT_DIR))}")
        fails += 1
    else:
        print(f"  0x807C pairs: {pairs}")

    mx = re.search(
        r"static const u8 k_stealth_x\[4\] = \{([^}]+)\}",
        src,
    )
    md = re.search(
        r"static const u8 k_stealth_dir\[4\] = \{([^}]+)\}",
        src,
    )
    if not mx or not md:
        fail("k_stealth_x / k_stealth_dir not found")
        fails += 1
    else:
        xs = ints_in(mx.group(1))
        ds = ints_in(md.group(1))
        if tuple(xs) != WANT_X:
            fail(f"k_stealth_x {xs} want {list(WANT_X)}")
            fails += 1
        else:
            print(f"  k_stealth_x: {xs}")
        if tuple(ds) != WANT_DIR:
            fail(f"k_stealth_dir {ds} want {list(WANT_DIR)} (dir[0] must be 2)")
            fails += 1
        else:
            print(f"  k_stealth_dir: {ds}")

    # apply_dir_88: dest=word1 (X)=k_unit_y[dir], bind=word0 (Y)=k_unit_x[dir]
    ux = re.search(r"static const s16 k_unit_x\[16\] = \{([^}]+)\}", src)
    uy = re.search(r"static const s16 k_unit_y\[16\] = \{([^}]+)\}", src)
    if not ux or not uy:
        fail("k_unit_x / k_unit_y not found")
        fails += 1
    else:
        word0 = ints_in(ux.group(1))
        word1 = ints_in(uy.group(1))
        if word0[0] != 0 or word1[0] != 128:
            fail(f"dir 0 units Y={word0[0]} X={word1[0]}, want Y=0 X=128 (right)")
            fails += 1
        else:
            print("  apply_dir_88 dir 0: X=128 Y=0 (right)")
        if word0[2] != 90 or word1[2] != 90:
            fail(f"dir 2 units Y={word0[2]} X={word1[2]}, want 90,90 (down-right)")
            fails += 1
        else:
            print("  apply_dir_88 dir 2: X=90 Y=90 (down-right)")
        if word0[4] != 128 or word1[4] != 0:
            fail(f"dir 4 units Y={word0[4]} X={word1[4]}, want Y=128 X=0 (down)")
            fails += 1
        else:
            print("  apply_dir_88 dir 4: X=0 Y=128 (down)")

    if vel and "dir 0 = right, 4 = down" not in vel:
        fail("vel_dir.c must keep dir 0 = right, 4 = down")
        fails += 1
    elif vel:
        print("  vel_dir.c: dir 0 = right, 4 = down")

    for name, pat in (
        ("spawn_stealth", r"static void spawn_stealth\(Slot \*e, u8 type\)\n\{(.*?)\n\}"),
        ("spawn_tracker", r"static void spawn_tracker\(Slot \*e, u8 type\)\n\{(.*?)\n\}"),
    ):
        m = re.search(pat, src, re.S)
        if not m:
            fail(f"{name} not found")
            fails += 1
            continue
        if "apply_dir_88(e, k_stealth_dir[si], 1)" not in m.group(1):
            fail(f"{name} must apply 807C dir via apply_dir_88 speed 1")
            fails += 1
        else:
            print(f"  {name}: apply_dir_88(k_stealth_dir, 1)")

    # PR #46 / #47 leave-alones this hunt must not revert.
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
