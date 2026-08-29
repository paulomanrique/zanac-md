#!/usr/bin/env python3
"""Cmd 9 does not wipe E12E/E12F/E131/E132.

zanac.asm Japan v1 (SHA1 46e9ed7b7f6dfda8eee266476c9ebc4dd9d8fcc2):

  0x96DE  LD E,(HL) / INC HL / LD D,(HL) / EX DE,HL
  0x96E2  JP 0x9433                 ; init_credits_stream

  init_credits_stream 0x9433:
    OR A / RET Z
    CALL 0x9444                     ; resolve_round_from_ptr
    LD (E701),A
    CALL 0x4C68                     ; render_round_digit
    JP 0x941B                       ; LAB_ram_941b

  LAB_ram_941b:
    load E706/E702/E704 from HL
    RES 0,(E700)
    RET

  Neither 0x96DE-0x96E2 nor 0x9433/0x941B writes E12E/E12F/E131/E132.
  E132 writers are reset_entities 0x40D6, LAB_414d +=0x20, type60 SRL,
  90a6 -=8, and cmd 12 +=nn.

  Port cmd_script_jump invented entity_alc_reset() on every in-map jump.
  First boot / warp / credits still reset via script_boot / arm_ending.

Live blob (cmd 0x89, 2-byte dest):

  0xAD2C row 3000 dest 0xAD61   (round 2 -> round 3)
  0xAD5E         dest 0xAAEF   (warp stub -> round 2 start)

Type 10/20/37/38/41 SAT +04 stays. Types 7/8 umber morph stays.
Pairdesc dirs / stealth dir[0]=2 / type 11/69 SAT 0 / cmd 0 bit2 stay.

Usage (from zanac-md):
    python tools/test_cmd9_no_alc_reset.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPC = ROOT / "src" / "map_script.c"
ENTITY_H = ROOT / "inc" / "entity.h"
BLOB = ROOT / "res" / "map_blob.bin"
BLOB_BASE = 0x9B64
ASM_CANDIDATES = [
    Path("/tmp/zanac-re/source/zanac.asm"),
    Path("/tmp/refs/zanac-re/source/zanac.asm"),
    Path.home() / "zanac-re" / "source" / "zanac.asm",
    ROOT.parent / "zanac-re" / "source" / "zanac.asm",
]

LIVE = (
    (0xAD2C, 3000, 0xAD61),
)


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)


def load_asm() -> str | None:
    for p in ASM_CANDIDATES:
        if p.is_file():
            return p.read_text(encoding="utf-8", errors="replace")
    return None


def fn_span(src: str, sig: str) -> str | None:
    """Body of a top-level C function starting at sig, brace-balanced."""
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
    src = MAPC.read_text(encoding="utf-8")
    hdr = ENTITY_H.read_text(encoding="utf-8")

    asm = load_asm()
    if asm:
        if not re.search(r"JP\s+0x9433\s*;\s*0x96e2", asm, re.I):
            fail("zanac.asm 96e2 is not JP 0x9433")
            fails += 1
        else:
            print("  ASM 96e2: JP 0x9433 (init_credits_stream)")
        if not re.search(r"JP\s+0x941b\s*;\s*0x9441", asm, re.I):
            fail("zanac.asm 9441 is not JP 0x941b")
            fails += 1
        else:
            print("  ASM 9441: JP 0x941b (reload trigger/row/PC)")
        # 9433..9432-RET / 941b..9432 must not store E12E/E132.
        for label, start, end in (
            ("init_credits_stream", 0x9433, 0x9443),
            ("LAB_ram_941b", 0x941B, 0x9432),
            ("cmd9", 0x96DE, 0x96E4),
        ):
            hits = re.findall(
                rf"LD\s+\(0xe12[ef]\),\s*A\s*;\s*0x([0-9a-f]+)"
                rf"|LD\s+\(0xe131\),\s*A\s*;\s*0x([0-9a-f]+)"
                rf"|LD\s+\(0xe132\),\s*A\s*;\s*0x([0-9a-f]+)"
                rf"|LD\s+HL,\s*0xe132\s*;\s*0x([0-9a-f]+)",
                asm,
                re.I,
            )
            for groups in hits:
                addr = int(next(g for g in groups if g), 16)
                if start <= addr <= end:
                    fail(f"{label} writes ALC at {addr:#x}")
                    fails += 1
                    break
            else:
                print(f"  ASM {label}: no E12E/E131/E132 store")
        if not re.search(r"LD\s+\(0xe132\),\s*A\s*;\s*0x40d6", asm, re.I):
            fail("reset_entities 40d6 must still zero E132")
            fails += 1
        else:
            print("  ASM 40d6: reset_entities zeros E132 (boot/warp, not cmd 9)")
    else:
        print("  (zanac.asm not on this machine; C/blob locks only)")

    jump = fn_span(src, "static void cmd_script_jump(u8 cmd, const u8 *ops)")
    if not jump:
        fail("cmd_script_jump not found")
        return 1
    if "entity_alc_reset" in jump:
        fail("cmd_script_jump must not call entity_alc_reset (96e2/9433/941b)")
        fails += 1
    else:
        print("  cmd_script_jump: no entity_alc_reset")
    if "load_trigger_from_pc" not in jump:
        fail("cmd_script_jump must still load_trigger_from_pc (941b)")
        fails += 1
    else:
        print("  cmd_script_jump: still load_trigger_from_pc")

    boot = fn_span(src, "static void script_boot(u8 round, u16 pc)")
    if not boot or "entity_alc_reset" not in boot:
        fail("script_boot must still entity_alc_reset (first boot / warp)")
        fails += 1
    else:
        print("  script_boot: still entity_alc_reset")

    if "Cmd 8/9 round transition" in hdr:
        fail("entity.h still claims cmd 8/9 reset ALC")
        fails += 1
    else:
        print("  entity.h: cmd 9 no longer documented as ALC reset")

    if not BLOB.is_file():
        fail("res/map_blob.bin missing")
        fails += 1
    else:
        blob = BLOB.read_bytes()

        def at(addr: int, n: int = 1) -> bytes:
            off = addr - BLOB_BASE
            return blob[off : off + n]

        for pc, row, dest in LIVE:
            rec_row = at(pc, 2)[0] | (at(pc, 2)[1] << 8)
            cmd = at(pc + 2)[0]
            got = at(pc + 3, 2)[0] | (at(pc + 3, 2)[1] << 8)
            if rec_row != row or (cmd & 0x0F) != 9 or got != dest:
                fail(
                    f"blob {pc:#x} is not cmd9 row {row} dest {dest:#x} "
                    f"(row={rec_row} cmd={cmd:#x} dest={got:#x})"
                )
                fails += 1
            else:
                print(f"  blob {pc:#x}: row {row} cmd9 dest {dest:#x}")

        stub = at(0xAD5E, 3)
        dest = stub[1] | (stub[2] << 8)
        if stub[0] != 0x89 or dest != 0xAAEF:
            fail(f"blob 0xAD5E is not cmd9 dest 0xAAEF (got {stub[0]:#x} {dest:#x})")
            fails += 1
        else:
            print("  blob 0xAD5E: warp-stub cmd9 dest 0xAAEF")

    # KEEP: cmd 0 bit2 still places type 69.
    fn = re.search(
        r"static void cmd_spawn_ctrl\(u8 cmd, const u8 \*ops\)\n\{(.*?)\n\}",
        src,
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
