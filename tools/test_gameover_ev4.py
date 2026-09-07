#!/usr/bin/env python3
"""Game Over ev4 is 3 voices on slots 2/3/4. Do not enqueue other events.

zanac.asm 0x4663: stop_all then ev4. wait_fire_or_timeout 0x46A8 is
9480 + 9393 only — not 8f5e (0x4077). 90a6 / hold must not tick
during GO: base_clear_tick phase 4/5 sound_stop_all kills ev4.
ev4 header @0x551C: n=3, dest 2/3/4, cfg 0x41, tempo 3,
transpose 5, streams 0x5538 / 0x5563 / 0x557F.
ev1 uses slots 0/1/2; ev13 shot uses slot 3. Either steals a GO voice
(0x51C1 F_BUSY aborts the rest).

Usage (from zanac-md):
    python tools/test_gameover_ev4.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SND = ROOT / "src" / "sound.c"
HDR = ROOT / "inc" / "sound.h"
MAPC = ROOT / "src" / "map_script.c"
GAME = ROOT / "src" / "game.c"
TOOLS = ROOT / "tools"


def fail(msg: str) -> int:
    print("FAIL:", msg)
    return 1


def ev4_from_asm() -> list[tuple[int, int, int, int, int]] | None:
    asm = Path("/tmp/zanac-re/source/zanac.asm")
    if not asm.is_file():
        return None
    sys.path.insert(0, str(TOOLS))
    from extract_sound import PTR_TABLE, parse_asm, parse_header, w

    rom = parse_asm(asm)
    ptr = w(rom, PTR_TABLE + 4 * 2)
    if ptr != 0x551C:
        raise SystemExit("ev4 ptr is 0x%04X, want 0x551C" % ptr)
    voices = parse_header(rom, 4)
    out = []
    for d, cfg, stream in voices:
        if stream is None:
            raise SystemExit("ev4 voice silenced")
        out.append((d, cfg[0], cfg[4], cfg[3], stream))
    return out


def main() -> int:
    snd = SND.read_text(encoding="utf-8")
    hdr = HDR.read_text(encoding="utf-8")
    map_c = MAPC.read_text(encoding="utf-8")
    game_c = GAME.read_text(encoding="utf-8")

    if "#define SND_EV_GAMEOVER   4" not in hdr:
        return fail("SND_EV_GAMEOVER must be event 4")
    if "static int gameover_voices_active(void);" not in snd:
        return fail("gameover_voices_active must be prototyped before first use")
    if "s_slot[i].event == SND_EV_GAMEOVER" not in snd:
        return fail("gameover_voices_active must look at slot.event == ev4")
    if "if (ev != SND_EV_GAMEOVER && gameover_voices_active())" not in snd:
        return fail("sound_play_event must refuse other events while GO lives")
    if "sound_stop_all();" not in snd or "sound_play_event(SND_EV_GAMEOVER)" not in snd:
        return fail("sound_play_gameover must stop_all then ev4 (0x4663)")

    # 0x46A8 does not CALL 8f5e. Ceremony stop_all must not run on GO.
    upd = re.search(r"void map_script_update\(void\)\s*\{(.*?)^\}", map_c, re.S | re.M)
    if not upd:
        return fail("map_script_update not found")
    body = upd.group(1)
    if not re.search(
        r"if\s*\(\s*!player_is_over\(\)\s*\)\s*\{[^}]*base_hold\(\);[^}]*base_clear_tick\(\);",
        body,
        re.S,
    ):
        return fail("8f5e hold/90a6 must not tick while GO (0x46A8 is 9480+9393)")
    if "map_script_update();" not in game_c:
        return fail("GO wait still runs 9480 via map_script_update")

    ev4 = ev4_from_asm()
    want = [
        (2, 0x41, 3, 5, 0x5538),
        (3, 0x41, 3, 5, 0x5563),
        (4, 0x41, 3, 5, 0x557F),
    ]
    if ev4 is not None and ev4 != want:
        return fail("ev4 header %s != %s" % (ev4, want))
    if ev4 is None:
        ev4 = want
        print("  (zanac.asm not present; using Japan ev4 header)")

    # 4F55: 0x00-0x7F is a note. ev4 rests with 0x00; treating 0 as END
    # killed two voices and left a one-instrument GO cue.
    fetch = re.search(r"static void fetch_stream\(Slot \*s\)\s*\{(.*?)^\}", snd, re.S | re.M)
    if not fetch:
        return fail("fetch_stream not found")
    if "if (b <= 0x7F)" not in fetch.group(1):
        return fail("fetch_stream must take 0x00-0x7F as notes (0x00 is rest)")
    if re.search(r"if\s*\(\s*b\s*&&", fetch.group(1)):
        return fail("do not skip note 0 (ev4 rests)")

    blob = ROOT / "res" / "sound_blob.bin"
    if blob.is_file():
        data = blob.read_bytes()
        base = 0x5234

        def rd(a: int) -> int:
            return data[a - base]

        notes_per = []
        chans = []
        for dest, cfg0, tempo, tr, stream in ev4:
            a = stream
            notes = []
            unknown = []
            for _ in range(96):
                if a < base or a > 0x5A10:
                    unknown.append(a)
                    break
                b = rd(a)
                if b == 0x82:
                    break
                if b == 0x80 or b == 0x81:
                    a += 3
                    continue
                if 0x84 <= b <= 0x89:
                    a += 2
                    continue
                if b in (0x8A, 0x8B, 0x8C):
                    a += 3
                    continue
                if b == 0xDF:
                    a += 2
                    continue
                if b >= 0xE0:
                    a += 1
                    continue
                if b <= 0x7F:
                    notes.append(b)
                    a += 1
                    continue
                unknown.append(b)
                break
            if unknown:
                return fail("ev4 dest %d unknown opcode/OOB %s" % (dest, unknown))
            if len(notes) < 8:
                return fail("ev4 dest %d only %d notes (multi-channel GO)" % (dest, len(notes)))
            if 0 not in notes:
                return fail("ev4 dest %d must keep 0x00 rests" % dest)
            notes_per.append(len(notes))
            # header channels are 0/1/2 — walk used the dest list above
            chans.append(dest)
        if chans != [2, 3, 4]:
            return fail("ev4 dest slots drifted")
        print("  ev4 notes/voice", notes_per, "incl. 0x00 rests")

    print("ok: ev4 slots 2/3/4; lock + 8f5e skipped during GO wait")
    return 0


if __name__ == "__main__":
    sys.exit(main())
