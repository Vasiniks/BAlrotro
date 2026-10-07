"""The in-run background (Balatro's paint shader) for every blind and booster pack, as still pictures in one sheet.

    python3 tools/make_table_bg.py          -> SPRITESHEETS/table-bg.jpg (+ manifest entry)

Balatro draws the table on its 'background' shader, coloured by ease_background_colour_blind (common_events.lua):
Small / Big Blind #50846e (contrast 1); a boss: lighten(mix(boss colour, BLACK, 0.3), 0.1) with the boss colour as
the special colour (contrast 2); showdown bosses BLUE / RED / dark (contrast 3); a won run #4f6367; each booster pack
its own. Generated, not a supplied asset: one frame of the shader per tile, spin 0.
Tiles (6 x 6 grid, row-major): 1..30 = blind id (blinds.json order: Small, Big, then the bosses), 31 won,
32 Arcana (tarot) pack, 33 Celestial (planet), 34 Spectral, 35 Standard, 36 Buffoon. Each tile covers graph units
x -12..12, y -17..15 like menu-bg.png.
"""
import json
import math
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "SPRITESHEETS")
X0, X1, Y0, Y1, PPU = -12.0, 12.0, -17.0, 15.0, 6
SW, SH, UNIT = 1920.0, 1080.0, 96.0
TIME = 37.0
COLS = 6
HEX = lambda h: tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
BLACK, RED, BLUE = HEX("374244"), HEX("fe5f55"), HEX("009dff")
# boss colours by blind id (the game repo's F_ColR / F_ColG / F_ColB, from game.lua boss_colour)
COL_R = [0, 174, 168, 185, 81, 138, 80, 104, 185, 62, 239, 185, 198, 169, 87, 75, 174, 112, 67, 126, 92, 172, 181, 229, 106, 253, 86, 138, 172, 0]
COL_G = [104, 124, 64, 91, 134, 89, 191, 101, 203, 133, 192, 92, 224, 162, 87, 113, 113, 146, 154, 103, 110, 157, 45, 106, 56, 162, 167, 113, 50, 156]
COL_B = [173, 27, 36, 8, 168, 165, 124, 243, 146, 189, 60, 150, 235, 149, 87, 228, 142, 132, 79, 82, 49, 180, 45, 47, 71, 0, 134, 225, 50, 253]


def mix(a, b, p):
    return tuple(a[i] * p + b[i] * (1 - p) for i in range(3))


def lighten(c, p):
    return tuple(x * (1 - p) + p for x in c)


def darken(c, p):
    return tuple(x * (1 - p) for x in c)


def background(new, special=None, tertiary=None, contrast=1.0):
    """G.C.BACKGROUND (L, C, D) as ease_background_colour sets it"""
    if special and tertiary:
        return new, special, tertiary, contrast
    L = tuple(x * 1.3 for x in new)
    C = special if special else tuple(x * 0.9 for x in new)
    D = tuple(x * (0.4 if special else 0.7) for x in new)
    return L, C, D, contrast


def variants():
    out = []
    small = background(HEX("50846e"))
    for bid in range(1, 31):
        if bid <= 2:
            out.append(small)
        elif bid >= 26:                                      # showdown bosses
            out.append(background(BLUE, RED, darken(BLACK, 0.4), 3))
        else:
            boss = (COL_R[bid - 1] / 255, COL_G[bid - 1] / 255, COL_B[bid - 1] / 255)
            out.append(background(lighten(mix(boss, BLACK, 0.3), 0.1), boss, None, 2))
    out.append(background(HEX("4f6367")))                                       # won
    out.append(background(HEX("8867a5"), darken(BLACK, 0.2), None, 1.5))        # Arcana pack
    out.append(background(BLACK, None, None, 3))                                # Celestial pack
    out.append(background(HEX("4584fa"), darken(BLACK, 0.2), None, 2))          # Spectral pack
    out.append(background(darken(BLACK, 0.2), RED, None, 3))                    # Standard pack
    out.append(background(HEX("ff9a00"), BLACK, None, 2))                       # Buffoon pack
    return out


def weights(sx, sy, contrast, spin=0.0):
    """the shader's colour weights at one screen pixel: (c1p, c2p, c3p, light)"""
    diag = math.hypot(SW, SH)
    px = diag / 745.0
    ux = (math.floor(sx / px) * px - 0.5 * SW) / diag
    uy = (math.floor(sy / px) * px - 0.5 * SH) / diag
    ln = math.hypot(ux, uy)
    ang = math.atan2(uy, ux) + 302.2 - 20.0 * (spin * ln + (1.0 - spin))
    mx, my = SW / diag / 2, SH / diag / 2
    vx, vy = (ln * math.cos(ang) + mx - mx) * 30, (ln * math.sin(ang) + my - my) * 30
    speed = TIME * 2.0
    u2x = u2y = vx + vy
    for _ in range(5):
        m = math.sin(max(vx, vy))
        u2x, u2y = u2x + m + vx, u2y + m + vy
        vx += 0.5 * math.cos(5.1123314 + 0.353 * u2y + speed * 0.131121)
        vy += 0.5 * math.sin(u2x - 0.113 * speed)
        t = math.cos(vx + vy) - math.sin(vx * 0.711 - vy)
        vx, vy = vx - t, vy - t
    cm = 0.25 * contrast + 0.5 * spin + 1.2
    res = min(2.0, max(0.0, math.hypot(vx, vy) * 0.035 * cm))
    c1 = max(0.0, 1.0 - cm * abs(1.0 - res))
    c2 = max(0.0, 1.0 - cm * abs(res))
    c3 = 1.0 - min(1.0, c1 + c2)
    return c1, c2, c3


def main():
    w, h = round((X1 - X0) * PPU), round((Y1 - Y0) * PPU)
    vs = variants()
    rows = (len(vs) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * w, rows * h))
    cache = {}
    for k, (L, C, D, contrast) in enumerate(vs):
        if contrast not in cache:                      # the weights only depend on the contrast
            cache[contrast] = [[weights(SW / 2 + (X0 + (i + 0.5) / PPU) * UNIT, SH / 2 - (Y1 - (j + 0.5) / PPU) * UNIT, contrast)
                                for i in range(w)] for j in range(h)]
        wt = cache[contrast]
        tile = Image.new("RGB", (w, h))
        px = tile.load()
        base = 0.3 / contrast
        for j in range(h):
            for i in range(w):
                c1, c2, c3 = wt[j][i]
                px[i, j] = tuple(round(255 * min(1.0, max(0.0, base * C[q] + (1 - base) * (C[q] * c1 + L[q] * c2 + D[q] * c3))))
                                 for q in range(3))
        sheet.paste(tile, ((k % COLS) * w, (k // COLS) * h))
    file = "SPRITESHEETS/table-bg.jpg"               # smooth paint, no transparency: a JPEG is a sixth of the PNG
    sheet.save(os.path.join(ROOT, file), quality=88, optimize=True)
    man_path = os.path.join(OUT, "manifest.json")
    man = json.load(open(man_path))
    entry = {"file": file, "url": "https://vasiniks.github.io/BAlrotro/" + file, "image_px": list(sheet.size), "tile_px": [w, h],
             "layout": "grid", "columns": COLS, "rows": rows, "count": len(vs),
             "order": "1..30 blind id (Small, Big, bosses), 31 won, 32 Arcana, 33 Celestial, 34 Spectral, 35 Standard, 36 Buffoon",
             "graph_units": {"x": [X0, X1], "y": [Y0, Y1]},
             "source": "generated by tools/make_table_bg.py: stills of Balatro's background shader in each blind / pack colour"}
    man["sheets"] = [s for s in man["sheets"] if s["file"] not in (file, "SPRITESHEETS/table-bg.png")] + [entry]
    with open(man_path, "w") as fh:
        json.dump(man, fh, indent=1, ensure_ascii=False)
    print(file, sheet.size, len(vs), "tiles")


if __name__ == "__main__":
    main()
