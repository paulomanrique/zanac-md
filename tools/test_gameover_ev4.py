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
    if ev4 is None:
        print("ok: GO lock in sound.c (zanac.asm not present; header check skipped)")
        return 0
    want = [
        (2, 0x41, 3, 5, 0x5538),
        (3, 0x41, 3, 5, 0x5563),
        (4, 0x41, 3, 5, 0x557F),
    ]
    if ev4 != want:
        return fail("ev4 header %s != %s" % (ev4, want))
    print("ok: ev4 slots 2/3/4; lock + 8f5e skipped during GO wait")
    return 0


if __name__ == "__main__":
    sys.exit(main())
