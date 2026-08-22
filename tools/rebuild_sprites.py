"""Rebuild zanac-md objs.png + ship.png from MSX Zanac ROM patterns.
Folds complements into primaries, bakes typical SAT TMS color indices,
appends luster_A / umber_B frames missing from the prior 53-frame strip.
"""
from pathlib import Path
from PIL import Image

ROM = Path(r"C:\Users\Filipe\Downloads\_MSX1ROM\MSX1 ROMS\Zanac (Japan).rom")
OUT_OBJS = Path(r"C:\Users\Filipe\GitRepos\zanac-md\res\sprites\objs.png")
OUT_SHIP = Path(r"C:\Users\Filipe\GitRepos\zanac-md\res\sprites\ship.png")

# TMS9918 approximate RGB (matches map_script.c s_tms_pal)
TMS_RGB = [
    (0, 0, 0), (0, 0, 0), (33, 200, 66), (94, 220, 120),
    (84, 85, 237), (125, 118, 252), (212, 82, 77), (66, 235, 245),
    (252, 85, 84), (255, 121, 120), (212, 193, 84), (230, 206, 128),
    (33, 176, 59), (201, 91, 186), (204, 204, 204), (255, 255, 255),
]

def decompress(rom: bytes, addr: int, max_out: int = 8192) -> bytes:
    i = addr - 0x4000
    out = bytearray()
    special = 0xFF
    mode = 0

    def read():
        nonlocal i
        b = rom[i]
        i += 1
        return b

    def unit(a):
        nonlocal i
        cnt = 1 if mode == 0 else read()
        out.extend([a] * cnt)

    while len(out) < max_out:
        a = read()
        if a != special:
            unit(a)
            continue
        a2 = read()
        if a2 != special:
            i -= 1
            mode ^= 1
            continue
        cmd = read()
        if cmd == 0:
            break
        if cmd == 1:
            special = read()
        elif cmd == 2:
            M = read()
            start = i
            for _ in range(M):
                i = start
                N = read()
                for __ in range(N):
                    unit(read())
        else:
            raise ValueError(f"bad cmd {cmd}")
    return bytes(out)

def pat_bits(pat: bytes):
    bits = [[0] * 16 for _ in range(16)]
    for y in range(16):
        left, right = pat[y], pat[16 + y]
        for x in range(8):
            if left & (0x80 >> x):
                bits[y][x] = 1
            if right & (0x80 >> x):
                bits[y][8 + x] = 1
    return bits

def fold_frame(primary, compl, color: int):
    """Primary bits -> color; complement-only bits -> 1 (black)."""
    pb = pat_bits(primary)
    cb = pat_bits(compl) if compl is not None else None
    pix = []
    for y in range(16):
        for x in range(16):
            if pb[y][x]:
                pix.append(color)
            elif cb and cb[y][x]:
                pix.append(1)
            else:
                pix.append(0)
    return pix

def compl_only(compl):
    cb = pat_bits(compl)
    return [1 if cb[y][x] else 0 for y in range(16) for x in range(16)]

def primary_only(primary, color: int):
    pb = pat_bits(primary)
    return [color if pb[y][x] else 0 for y in range(16) for x in range(16)]

rom = ROM.read_bytes()
pats = decompress(rom, 0x6976, 2048)
assert len(pats) == 2048
P = [pats[i * 32:(i + 1) * 32] for i in range(64)]

# FRAME index -> (pat, compl_pat or None, tms_color)
# Matches entity.c FRAME_* order 0..52, then new 53..56
FRAMES = [
    # 0-12 original core
    (10, None, 15),   # SHOT
    (22, 23, 9),      # DUSTER 0x89
    (24, 25, 10),     # TERUZO 0x8A
    (30, 32, 14),     # LUSTER_B 0x8E
    (53, 54, 15),     # BOX 0x8F
    (1, None, 11),    # CHIP
    (7, None, 15),    # LEAD
    (28, None, 15),   # SIG
    (11, None, 15),   # SHOT_D
    (12, None, 15),   # SHOT_T
    (3, None, 15),    # FIRE target
    (9, None, 15),    # CIRCLE
    (2, None, 15),    # COMET
    # 13-15 degid
    (59, None, 15),
    (60, None, 15),
    (61, None, 15),
    # 16-20 veybar primary (default cyan 0x83)
    (33, 38, 7),
    (34, 39, 7),
    (35, 40, 7),
    (36, 41, 7),
    (37, 42, 7),
    # 21-25 veybar compl (black stand-alone for mkspr)
    (38, None, 1),
    (39, None, 1),
    (40, None, 1),
    (41, None, 1),
    (42, None, 1),
    # 26-29 other compls
    (23, None, 1),    # DUSTER_C
    (25, None, 1),    # TERUZO_C
    (54, None, 1),    # BOX_C
    (32, None, 1),    # LUSTER_C (B)
    # 30-33 umber/stealth
    (55, 57, 15),     # UMBER_A 0x8F
    (57, None, 1),    # UMBER_C
    (51, 52, 8),      # STEALTH 0x88
    (52, None, 1),    # STEALTH_C
    # 34-41 spinner
    (43, 47, 14),     # 0x8E
    (44, 48, 14),
    (45, 49, 14),
    (46, 50, 14),
    (47, None, 1),
    (48, None, 1),
    (49, None, 1),
    (50, None, 1),
    # 42-52 rest
    (62, 63, 7),      # SART 0x83
    (63, None, 1),
    (18, 19, 15),     # LOGA 0x8F default
    (19, None, 1),
    (16, 17, 7),      # PLANE 0x83 cyan (was wrongly 3)
    (17, None, 1),
    (13, None, 15),   # BOLT
    (6, None, 4),     # LIGHT_BAR 0x84
    (26, None, 15),   # SIG_TRIPLE
    (27, None, 15),   # SIG_DOUBLE
    (8, None, 6),     # MED_CIRCLE 0x86
    # 53-56 NEW
    (29, 31, 11),     # LUSTER_A 0x8B
    (31, None, 1),    # LUSTER_A_C
    (56, 58, 7),      # UMBER_B 0x83
    (58, None, 1),    # UMBER_B_C
]

# Frames that are complement-only slots (drawn via mkspr): no fold
COMPL_ONLY = {
    21, 22, 23, 24, 25, 26, 27, 28, 29, 31, 33, 38, 39, 40, 41, 43, 45, 47, 54, 56
}

n = len(FRAMES)
strip = Image.new("P", (n * 16, 16))
pal = []
for rgb in TMS_RGB:
    pal.extend(rgb)
pal.extend([0] * (768 - len(pal)))
strip.putpalette(pal)

for fi, (pat, cpat, color) in enumerate(FRAMES):
    if fi in COMPL_ONLY or cpat is None:
        if fi in COMPL_ONLY:
            pix = primary_only(P[pat], 1) if color == 1 else primary_only(P[pat], color)
            # pure complement frames: force black
            pix = compl_only(P[pat])
        else:
            pix = primary_only(P[pat], color)
    else:
        pix = fold_frame(P[pat], P[cpat], color)
    fr = Image.new("P", (16, 16))
    fr.putpalette(pal)
    fr.putdata(pix)
    strip.paste(fr, (fi * 16, 0))

strip.save(OUT_OBJS, optimize=False)
print(f"wrote {OUT_OBJS} {strip.size} frames={n}")

# Ship: fold pat15 black into pat14 white
ship_pix = fold_frame(P[14], P[15], 15)
ship = Image.new("P", (16, 16))
ship.putpalette(pal)
ship.putdata(ship_pix)
ship.save(OUT_SHIP, optimize=False)
print(f"wrote {OUT_SHIP} folded ship on={sum(1 for p in ship_pix if p)} primary={sum(1 for p in ship_pix if p==15)} black={sum(1 for p in ship_pix if p==1)}")

# sanity: plane frame 46 should be cyan(7)+black
plane = list(strip.crop((46 * 16, 0, 47 * 16, 16)).getdata())
print("plane idxs", sorted(set(plane)), "cyan", plane.count(7), "blk", plane.count(1))
duster = list(strip.crop((16, 0, 32, 16)).getdata())
print("duster idxs", sorted(set(duster)))
lusta = list(strip.crop((53 * 16, 0, 54 * 16, 16)).getdata())
print("luster_A idxs", sorted(set(lusta)), "yellow", lusta.count(11), "blk", lusta.count(1))
