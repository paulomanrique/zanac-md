"""Rebuild the title layers straight from the assembled resource data.

This checks the whole chain -- PNG palette indices surviving rescomp, tileset
packing, tilemap order -- rather than trusting the intermediate PNGs.
"""

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("b", ROOT / "tools" / "build_title_md.py")
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)

ASM = (ROOT / "out" / "release" / "res" / "resources.s").read_text()


def data_bytes(label: str) -> bytes:
    m = re.search(rf"^{label}:\s*\n((?:\s*dc\.\w+\s+.*\n)+)", ASM, re.M)
    out = bytearray()
    for line in m.group(1).splitlines():
        kind, rest = line.split(None, 1)
        size = {"dc.b": 1, "dc.w": 2, "dc.l": 4}[kind]
        for tok in rest.split(","):
            out.extend(int(tok.strip(), 0).to_bytes(size, "big"))
    return bytes(out)


def layer(name: str, tw: int, th: int):
    tiles = data_bytes(f"{name}_tileset_data")
    tmap = data_bytes(f"{name}_tilemap_data")
    w, h = tw * 8, th * 8
    px = [0] * (w * h)
    for ty in range(th):
        for tx in range(tw):
            idx = int.from_bytes(tmap[(ty * tw + tx) * 2:][:2], "big") & 0x7FF
            base = idx * 32
            for r in range(8):
                for c in range(8):
                    byte = tiles[base + r * 4 + c // 2]
                    px[(ty * 8 + r) * w + tx * 8 + c] = (byte >> 4) if c % 2 == 0 else (byte & 0xF)
    return w, h, px


def consts() -> dict:
    text = (ROOT / "inc" / "title_md.h").read_text()
    out = {}
    for name, expr in re.findall(r"#define\s+(TITLE_\w+)\s+(.+)", text):
        try:
            out[name] = eval(expr, {}, dict(out))
        except Exception:
            pass
    return out


SCREEN_W, SCREEN_H = 256, 176


def compose(C, zanac, mark, offset):
    zw, zh, zpx = zanac
    mw, mh, mpx = mark
    scr = [0] * (SCREEN_W * SCREEN_H)
    groove_y = C["TITLE_GROOVE_ROW"] * 8

    for y in range(groove_y, SCREEN_H):
        for x in range(SCREEN_W):
            scr[y * SCREEN_W + x] = B.OPAQUE_BLACK

    zy0 = C["TITLE_ZANAC_TILE_Y"] * 8 + offset
    zx0 = C["TITLE_ZANAC_TILE_X"] * 8
    for y in range(zh):
        ty = zy0 + y
        if not (0 <= ty < groove_y):      # BG_A hides everything from here down
            continue
        for x in range(zw):
            v = zpx[y * zw + x]
            if v:
                scr[ty * SCREEN_W + zx0 + x] = v

    my0 = C["TITLE_MDMARK_TILE_Y"] * 8
    mx0 = C["TITLE_MDMARK_TILE_X"] * 8
    for y in range(mh):
        for x in range(mw):
            v = mpx[y * mw + x]
            if v:
                scr[(my0 + y) * SCREEN_W + mx0 + x] = v
    return scr


def main():
    C = consts()
    zanac = layer("title_zanac", C["TITLE_ZANAC_TILE_W"], C["TITLE_ZANAC_TILE_H"])
    mark = layer("title_mdmark", C["TITLE_MDMARK_TILE_W"], C["TITLE_MDMARK_TILE_H"])
    travel = C["TITLE_ZANAC_TRAVEL"]
    groove_y = C["TITLE_GROOVE_ROW"] * 8

    print("palette indices in mdmark tiles:", sorted(set(mark[2])))
    print("palette indices in zanac tiles :", sorted(set(zanac[2])))

    # Opaque background above the groove would be a static black patch masking
    # the rising blue -- the whole point of the groove is that BG_A is a wall
    # only from the slot down.
    mw, mh, mpx = mark
    my0 = C["TITLE_MDMARK_TILE_Y"] * 8
    stuck = sum(1 for y in range(mh) for x in range(mw)
                if mpx[y * mw + x] == B.OPAQUE_BLACK and my0 + y < groove_y)
    shaded = sum(1 for y in range(mh) for x in range(mw)
                 if mpx[y * mw + x] > B.OPAQUE_BLACK and my0 + y < groove_y)
    print(f"opaque black background above the groove: {stuck} "
          f"(glyph pixels shaded there: {shaded})")
    ok = stuck == 0

    # An anti-alias tone must belong to a shape: it either hugs the solid glyph
    # or sits among other tones of the same ramp, as happens at the tip of the D
    # fan where no pixel reaches full coverage. One stranded in black is noise
    # the coverage pass resurrected.
    family = {}
    for full_idx, ramp in B.AA_SLOTS.items():
        for slot in ramp:
            family[slot] = full_idx
    orphan = 0
    for y in range(mh):
        for x in range(mw):
            here = mpx[y * mw + x]
            if here not in family or here == family[here]:
                continue
            kin = sum(1 for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                      if (dy or dx) and 0 <= y + dy < mh and 0 <= x + dx < mw
                      and family.get(mpx[(y + dy) * mw + (x + dx)]) == family[here])
            if not kin:
                orphan += 1
    aa_total = sum(1 for v in mpx if v in family and v != family[v])
    print(f"anti-alias pixels: {aa_total}, stranded in black: {orphan}")
    if orphan:
        ok = False

    outdir = ROOT / "out" / "anim_preview"
    outdir.mkdir(parents=True, exist_ok=True)

    strip = []
    for pct in (0, 33, 66, 100):
        offset = (travel * (100 - pct)) // 100
        scr = compose(C, zanac, mark, offset)
        blue = sum(1 for v in scr if v == B.BLUE)
        md = sum(1 for v in scr if v in (B.RED, B.GREEN))
        below = sum(1 for y in range(groove_y, SCREEN_H) for x in range(SCREEN_W)
                    if scr[y * SCREEN_W + x] == B.BLUE)
        patch = sum(1 for y in range(groove_y) for x in range(SCREEN_W)
                    if scr[y * SCREEN_W + x] == B.OPAQUE_BLACK)
        print(f"{pct:3d}%  offset={offset:2d}  blue={blue:5d}  MD={md:4d}  "
              f"blue below groove={below}  static black above groove={patch}")
        if below or patch:
            ok = False
        B.write_png(outdir / f"rom_{pct:03d}.png", SCREEN_W, SCREEN_H, scr)
        strip.extend(scr)
        strip.extend([B.OPAQUE_BLACK] * (SCREEN_W * 2))

    sh = len(strip) // SCREEN_W
    big = []
    for y in range(sh):
        row = strip[y * SCREEN_W:(y + 1) * SCREEN_W]
        dbl = [v for v in row for _ in range(2)]
        big.extend(dbl * 2)
    B.write_png(outdir / "rom_strip.png", SCREEN_W * 2, sh * 2, big)
    print(f"wrote {outdir}/rom_strip.png")

    fw, fh, frgb = B.read_png_rgb(ROOT / "res" / "title_md_logo.png")
    pal = B.palette_rgb()
    lut = {}
    for i, c in enumerate(pal):
        lut.setdefault(c, i)
    ref = [lut[p] for p in frgb]
    final = compose(C, mark=mark, zanac=zanac, offset=0)
    diff = 0
    for y in range(fh):
        for x in range(fw):
            want = ref[y * fw + x] or B.OPAQUE_BLACK
            got = final[(C["TITLE_MD_Y"] + y) * SCREEN_W + C["TITLE_MD_X"] + x] or B.OPAQUE_BLACK
            if want != got:
                diff += 1
    print(f"final frame vs reference logo: {diff} differing pixels")
    if diff or not ok:
        sys.exit("VERIFICATION FAILED")
    print("OK")


if __name__ == "__main__":
    main()
