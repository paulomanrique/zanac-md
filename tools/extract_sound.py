#!/usr/bin/env python3
"""Extract Zanac MSX sound-track bytes from zanac.asm into the MD port.

Reads DB/DW lines (load address in the trailing comment), never copies the
asm wholesale. Same parser as tools/extract_map_scripts.py.

Region (kb/data/sound_track_scores.md, sprint 0064):
  0x51F0-0x5207  12-semitone period base
  0x5234-0x5A10  event pointer table + duration + curves + 27 event streams

Usage (from zanac-md):
    python tools/extract_sound.py
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PTR_TABLE = 0x5234
REGION_LO = 0x5234
REGION_HI = 0x5A10  # inclusive
PERIOD_LO = 0x51F0
PERIOD_HI = 0x5207
ROM_END = 0xC000

DB_RE = re.compile(r"^\s+DB\s+(.+);\s*0x([0-9A-Fa-f]{4})", re.I)
DW_RE = re.compile(r"^\s+DW\s+(.+);\s*0x([0-9A-Fa-f]{4})", re.I)
HEX_RE = re.compile(r"0x([0-9A-Fa-f]{1,2})\b", re.I)
HEX16_RE = re.compile(r"0x([0-9A-Fa-f]{1,4})\b", re.I)

KIND = {
    1: "main theme", 2: "round\equiv0 BGM", 3: "title", 4: "game over",
    5: "jingle <-ev12", 6: "weapon SFX", 7: "stage intro -> ev1",
    8: "state jingle", 9: "state jingle", 10: "round-variant BGM",
    11: "init jingle", 12: "round/boss -> ev5", 13: "shot SFX",
    18: "explosion", 25: "round fanfare", 26: "round-clear",
    27: "round-clear var",
}


def parse_asm(path: Path) -> bytearray:
    rom = bytearray(ROM_END)
    filled = bytearray(ROM_END)
    n_db = n_dw = 0
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = DB_RE.match(line)
            if m:
                addr = int(m.group(2), 16)
                vals = [int(h, 16) for h in HEX_RE.findall(m.group(1))]
                for i, v in enumerate(vals):
                    a = addr + i
                    if 0 <= a < ROM_END:
                        rom[a] = v & 0xFF
                        filled[a] = 1
                n_db += 1
                continue
            m = DW_RE.match(line)
            if m:
                addr = int(m.group(2), 16)
                vals = [int(h, 16) for h in HEX16_RE.findall(m.group(1))]
                for i, v in enumerate(vals):
                    a = addr + i * 2
                    if 0 <= a + 1 < ROM_END:
                        rom[a] = v & 0xFF
                        rom[a + 1] = (v >> 8) & 0xFF
                        filled[a] = filled[a + 1] = 1
                n_dw += 1
    miss = [a for a in range(REGION_LO, REGION_HI + 1) if not filled[a]]
    pmiss = [a for a in range(PERIOD_LO, PERIOD_HI + 1) if not filled[a]]
    print("parsed DB=%d DW=%d  track filled=%d/%d  period filled=%d/%d" %
          (n_db, n_dw,
           (REGION_HI - REGION_LO + 1) - len(miss), REGION_HI - REGION_LO + 1,
           (PERIOD_HI - PERIOD_LO + 1) - len(pmiss), PERIOD_HI - PERIOD_LO + 1))
    if miss:
        print("WARNING: %d unfilled track bytes, first=0x%04X" % (len(miss), miss[0]))
    if pmiss:
        print("WARNING: unfilled period bytes", [hex(a) for a in pmiss])
    return rom


def w(rom, a):
    return rom[a] | (rom[a + 1] << 8)


def parse_header(rom, ev):
    p = w(rom, PTR_TABLE + ev * 2)
    n = rom[p]
    p += 1
    voices = []
    for _ in range(n):
        D = rom[p]
        p += 1
        cfg0 = rom[p]
        if cfg0 == 0:
            voices.append((D, bytes([0]), None))
            p += 1
        else:
            cfg = bytes(rom[p:p + 8])
            stream = cfg[6] | (cfg[7] << 8)
            voices.append((D, cfg, stream))
            p += 8
    return voices


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asm", default=r"C:\Users\Filipe\GameMakerProjects\Zanac\zanac-re\source\zanac.asm")
    ap.add_argument("--out", default=r"C:\Users\Filipe\GitRepos\zanac-md")
    args = ap.parse_args()
    asm = Path(args.asm)
    out = Path(args.out)
    if not asm.is_file():
        sys.exit("asm not found: %s" % asm)

    print("ASM", asm, "size", asm.stat().st_size)
    rom = parse_asm(asm)

    period = bytes(rom[PERIOD_LO:PERIOD_HI + 1])
    blob = bytes(rom[REGION_LO:REGION_HI + 1])
    print("period", period.hex())
    print("blob  0x%04X-0x%04X  %d bytes" % (REGION_LO, REGION_HI, len(blob)))

    print("\n== event headers ==")
    for ev in range(1, 28):
        ptr = w(rom, PTR_TABLE + ev * 2)
        voices = parse_header(rom, ev)
        print(" ev%2d @0x%04X  %d voices  %s" %
              (ev, ptr, len(voices), KIND.get(ev, "SFX" if 13 <= ev <= 24 else "jingle")))
        for i, (D, cfg, stream) in enumerate(voices):
            if stream is None:
                print("   v%d D=%d silenced" % (i, D))
            else:
                print("   v%d D=%d cfg=%s ch=%d amp=%d curve=%d tr=%d tempo=%d stream=0x%04X" %
                      (i, D, cfg.hex(), cfg[5], cfg[1], cfg[2], cfg[3], cfg[4], stream))

    res = out / "res"
    inc = out / "inc"
    res.mkdir(parents=True, exist_ok=True)
    inc.mkdir(parents=True, exist_ok=True)
    (res / "sound_blob.bin").write_bytes(blob)
    print("\nwrote", res / "sound_blob.bin", len(blob), "bytes")

    h = []
    h.append("#ifndef SOUND_DATA_H")
    h.append("#define SOUND_DATA_H")
    h.append("")
    h.append("#include <genesis.h>")
    h.append("")
    h.append("/* Generated by tools/extract_sound.py from zanac.asm DB lines. */")
    h.append("#define SOUND_BLOB_BASE    0x%04X" % REGION_LO)
    h.append("#define SOUND_BLOB_END     0x%04X" % REGION_HI)
    h.append("#define SOUND_BLOB_LEN     %d" % len(blob))
    h.append("#define SOUND_PTR_TABLE    0x%04X" % PTR_TABLE)
    h.append("#define SOUND_DUR_TABLE    0x526C")
    h.append("#define SOUND_CURVE_TABLE  0x527D")
    h.append("#define SOUND_EVENT_MAX    27")
    h.append("")
    h.append("/* 12-semitone AY period base @0x51F0 (init_psg_freq_table). */")
    words = [period[i] | (period[i + 1] << 8) for i in range(0, 24, 2)]
    h.append("static const u16 k_psg_period_base[12] = {")
    h.append("    " + ", ".join("0x%04X" % w for w in words))
    h.append("};")
    h.append("")
    h.append("#endif")
    h.append("")
    (inc / "sound_data.h").write_text("\n".join(h), encoding="utf-8")
    print("wrote", inc / "sound_data.h")


if __name__ == "__main__":
    main()
