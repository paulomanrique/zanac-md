#!/usr/bin/env python3
"""Pyramid (loga 46-55) shots spawn from the peak, not the SAT vertex.

Japan v1 pats 18|20 first set row is y=0, xs mid = 8. 8ddb copies SAT
X/Y; SAT origin is the top-left vertex. Port adds +8 so the child leaves
the diamond tip.

Usage (from zanac-md):
    python tools/test_loga_peak_shots.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENT = ROOT / "src" / "entity.c"


def fail(msg: str) -> int:
    print("FAIL:", msg)
    return 1


def main() -> int:
    ent = ENT.read_text(encoding="utf-8")

    if "spawn_child_dir((s16)(e->x + 8), e->y, stype, dir)" not in ent:
        return fail("gun_fire must spawn at parent X+8 (loga peak), not SAT vertex")
    if "FRAME_LOGA" not in ent or "0x48" not in ent:
        return fail("guns stay SAT 0x48 pat 18")
    if "FRAME_LOGA_B" not in ent:
        return fail("marker stays SAT 0x50 pat 20 (MSX 80f2)")

    print("ok: loga shots from peak X+8 (Japan v1 pat 18|20 mid 8)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
