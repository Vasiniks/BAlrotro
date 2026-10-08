"""The in-run background for every blind and booster pack, as stills in one sheet: the real swirl recoloured.

    python3 tools/make_table_bg.py          -> SPRITESHEETS/table-bg.jpg (+ manifest entry)

The pattern is the supplied frame of Balatro's swirl (sources/MenuBackground.png, see make_menu_bg.py), coloured the way
ease_background_colour_blind (common_events.lua) colours the in-run shader: Small / Big Blind #50846e (contrast 1); a
boss: lighten(mix(boss colour, BLACK, 0.3), 0.1) with the boss colour as the special colour (contrast 2); showdown
bosses BLUE / RED / dark (contrast 3); a won run #4f6367; each booster pack its own.
Recolouring: the splash shader mixes RED, BLUE and BLACK and adds a white flash, so every source pixel is
u1 RED + u2 BLUE + u3 BLACK + f WHITE with u1+u2+u3+f = 1: a fixed linear function of its RGB. The background shader
puts C (special) where RED was, L (light) where BLUE was, D (dark) for BLACK (plus its 0.3/contrast wash of C), and
keeps the flash as gloss. Linear in RGB, so each tile is one colour-matrix conversion of the frame.
Tiles (6 x 6 grid, row-major): 1..30 = blind id (blinds.json order: Small, Big, then the bosses), 31 won,
32 Arcana (tarot) pack, 33 Celestial (planet), 34 Spectral, 35 Standard, 36 Buffoon. Each tile covers graph units
x -12..12, y -17..15 like menu-bg.jpg, at 20 pixels per unit.
"""
import json
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "SPRITESHEETS")
X0, X1, Y0, Y1, PPU = -12.0, 12.0, -17.0, 15.0, 20
GLOSS = 0.6                     # how much of the frame's white flash stays on the table (the paint is less shiny)
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


def solve4(m, v):
    """x with m x = v (4x4, Gauss-Jordan)"""
    a = [list(r) + [v[i]] for i, r in enumerate(m)]
    for c in range(4):
        p = max(range(c, 4), key=lambda r: abs(a[r][c]))
        a[c], a[p] = a[p], a[c]
        a[c] = [x / a[c][c] for x in a[c]]
        for r in range(4):
            if r != c:
                a[r] = [x - a[r][c] * y for x, y in zip(a[r], a[c])]
    return [a[r][4] for r in range(4)]


def unmix():
    """weights (u1 RED, u2 BLUE, u3 BLACK, f WHITE) = W · (r, g, b, 1), RGB in 0..1: columns of the inverse matrix"""
    m = [[RED[q], BLUE[q], BLACK[q], 1.0] for q in range(3)] + [[1.0, 1.0, 1.0, 1.0]]
    cols = [solve4(m, [1.0 if i == j else 0.0 for i in range(4)]) for j in range(4)]   # column j of the inverse
    return [[cols[j][i] for j in range(4)] for i in range(4)]                           # W[i][j]


def recolour_matrix(L, C, D, contrast):
    """PIL 12-tuple: out = base C + (1 - base)(u1 C + u2 L + u3 D) + GLOSS f, as an affine map of the source RGB"""
    W = unmix()
    base = 0.3 / contrast
    out = []
    for q in range(3):
        coef = [(1 - base) * C[q], (1 - base) * L[q], (1 - base) * D[q], GLOSS]   # per weight u1, u2, u3, f
        row = [sum(coef[i] * W[i][j] for i in range(4)) for j in range(4)]           # times (r, g, b, 1)
        out += [row[0], row[1], row[2], 255 * (row[3] + base * C[q])]
    return tuple(out)


def main():
    import make_menu_bg
    src = Image.open(os.path.join(ROOT, "sources", "MenuBackground.png")).convert("RGB")
    frame = make_menu_bg.swirl_canvas(src, PPU)
    w, h = frame.size
    vs = variants()
    rows = (len(vs) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * w, rows * h))
    for k, (L, C, D, contrast) in enumerate(vs):
        sheet.paste(frame.convert("RGB", recolour_matrix(L, C, D, contrast)), ((k % COLS) * w, (k // COLS) * h))
    file = "SPRITESHEETS/table-bg.jpg"               # smooth paint, no transparency: a JPEG is a sixth of the PNG
    sheet.save(os.path.join(ROOT, file), quality=86, optimize=True, progressive=True)
    man_path = os.path.join(OUT, "manifest.json")
    man = json.load(open(man_path))
    entry = {"file": file, "url": "https://vasiniks.github.io/BAlrotro/" + file, "image_px": list(sheet.size), "tile_px": [w, h],
             "layout": "grid", "columns": COLS, "rows": rows, "count": len(vs),
             "order": "1..30 blind id (Small, Big, bosses), 31 won, 32 Arcana, 33 Celestial, 34 Spectral, 35 Standard, 36 Buffoon",
             "graph_units": {"x": [X0, X1], "y": [Y0, Y1]},
             "source": "tools/make_table_bg.py: the supplied swirl (sources/MenuBackground.png) recoloured per blind / pack"}
    man["sheets"] = [s for s in man["sheets"] if s["file"] not in (file, "SPRITESHEETS/table-bg.png")] + [entry]
    with open(man_path, "w") as fh:
        json.dump(man, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print(file, sheet.size, len(vs), "tiles")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
