"""Build the game's sprite sheets from Balatro's original sheets in sources/ (upscaled 4x, crisp pixels).

    python3 tools/make_sheets.py          -> SPRITESHEETS/*.png, SPRITESHEETS/manifest.json, tools/font.json

Each sheet is re-packed into the tile order the Desmos graph uses (the order of the game repo's
dev/reference/*.json files); where a sprite sits in Balatro's own sheet comes from the game's position table
(game.lua: pos = {x, y}), copied into POS below.
The pixel font (sources/font.png, managore's m6x11 specimen drawn at 2x) is cut into glyph bitmaps:
tools/font.json — text is rendered from it by the game repo's tools.
"""
import json
import os
import re

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "sources")
OUT = os.path.join(ROOT, "SPRITESHEETS")
GAME_REF = os.path.join(os.path.dirname(ROOT), "balatro final take", "dev", "reference")
GAME_LUA = os.environ.get("BALATRO_GAME_LUA", "/private/tmp/claude-502/bsrc/game.lua")
BASE_URL = "https://vasiniks.github.io/BAlrotro/"
UP = 4


def load(name):
    return Image.open(os.path.join(SRC, name)).convert("RGBA")


def tile(sheet, x, y, w, h):
    return sheet.crop((x * w, y * h, (x + 1) * w, (y + 1) * h))


def up(im):
    return im.resize((im.width * UP, im.height * UP), Image.NEAREST)


def positions():
    """key -> (x, y) from game.lua's centre / blind / tag / stake tables (cached in tools/positions.json)."""
    cache = os.path.join(ROOT, "tools", "positions.json")
    if os.path.exists(GAME_LUA):
        pos = {}
        for line in open(GAME_LUA, encoding="utf-8"):
            m = re.match(r"\s*([a-z]+_[a-z0-9_]+)\s*=\s*\{.*?pos\s*=\s*\{\s*x\s*=\s*(\d+)\s*,\s*y\s*=\s*(\d+)", line)
            if m and m.group(1) not in pos:
                pos[m.group(1)] = (int(m.group(2)), int(m.group(3)))
        json.dump(pos, open(cache, "w"), indent=0)
    return {k: tuple(v) for k, v in json.load(open(cache)).items()}


def strip(tiles, cols=1):
    w, h = tiles[0].size
    rows = (len(tiles) + cols - 1) // cols
    out = Image.new("RGBA", (cols * w, rows * h), (0, 0, 0, 0))
    for i, t in enumerate(tiles):
        out.paste(t, ((i % cols) * w, (i // cols) * h))
    return out


def ref(name, key):
    return json.load(open(os.path.join(GAME_REF, name)))[key]


def main():
    P = positions()
    sheets = []

    def save(file, tiles, names, order, cols=1, native=None):
        im = strip(tiles, cols)
        im.save(os.path.join(OUT, file), optimize=True)
        w, h = tiles[0].size
        sheets.append({"file": "SPRITESHEETS/" + file, "url": BASE_URL + "SPRITESHEETS/" + file, "image_px": list(im.size),
                       "tile_px": [w, h], "native_px": native or [w // UP, h // UP], "layout": "vertical strip" if cols == 1 else "grid",
                       "columns": cols, "rows": im.height // h, "count": len(tiles), "order": order, "names": names,
                       "source": "Balatro (LocalThunk); supplied by the repo owner, upscaled x4 nearest-neighbour"})

    # blind chips: 21 animation frames per blind (34x34); frame 0 strip + full animation grid
    chips = load("BlindChips.png")
    blinds = ref("blinds.json", "blinds")
    rows = [P[b["key"]][1] for b in blinds]
    save("blinds.png", [up(tile(chips, 0, r, 34, 34)) for r in rows], [b["name"] for b in blinds],
         "blinds.json order (Small, Big, then the bosses); frame 0 of each chip")
    save("blinds-anim.png", [up(tile(chips, f, r, 34, 34)) for r in rows for f in range(21)], [b["name"] for b in blinds],
         "row = blinds.json order, column = animation frame 0..20", cols=21)

    tags_src = load("Tags.png")
    tags = ref("tags.json", "tags")
    save("tags.png", [up(tile(tags_src, *P[t["key"]], 34, 34)) for t in tags], [t["name"] for t in tags], "tags.json order")

    vsrc = load("Vouchers.png")
    vouchers = ref("vouchers.json", "vouchers")
    save("vouchers.png", [up(tile(vsrc, *P[v["key"]], 71, 95)) for v in vouchers], [v["name"] for v in vouchers],
         "vouchers.json order, row-major, 4 per row", cols=4)

    bsrc = load("BoosterPacks.png")
    packs = ref("packs.json", "pack_types")
    variants = [(p["name"], k) for p in packs for k in p["variants"]]
    save("boosters.png", [up(tile(bsrc, *P[k], 71, 95)) for _, k in variants], [f"{n} ({k})" for n, k in variants],
         "packs.json pack_types order, one tile per art variant (variants list order), row-major, 4 per row", cols=4)

    ssrc = load("Stakes.png")
    stakes = ["white", "red", "green", "black", "blue", "purple", "orange", "gold"]
    save("stakes.png", [up(tile(ssrc, *P["stake_" + s], 29, 29)) for s in stakes], [s.title() + " Stake" for s in stakes],
         "White, Red, Green, Black, Blue, Purple, Orange, Gold")

    # deck backs (Red Deck etc.) from the enhancers sheet
    esrc = load("Enhancers.png")
    backs = ["b_red", "b_blue", "b_yellow", "b_green", "b_black", "b_magic", "b_nebula", "b_ghost", "b_abandoned", "b_checkered",
             "b_zodiac", "b_painted", "b_anaglyph", "b_plasma", "b_erratic", "b_challenge"]
    backs = [b for b in backs if b in P]
    save("backs.png", [up(tile(esrc, *P[b], 71, 95)) for b in backs], backs, "deck backs, Balatro deck order", cols=4)

    sign = load("ShopSign.png")
    save("shop-sign.png", [up(tile(sign, 0, f, 113, 57)) if sign.height > 57 else up(sign.crop((f * 113, 0, (f + 1) * 113, 57)))
                           for f in range(4)], [f"frame {f}" for f in range(4)], "the SHOP sign, animation frames 0..3")
    ui = load("UIAssets.png")
    save("ui-icons.png", [up(ui)], ["UI icons"], "Balatro UI icon sheet as supplied (4 x 4 icons: chip, A, flame, #, "
         "suits; second half = high-contrast colours)")
    stick = load("Stickers.png")
    save("stickers.png", [up(tile(stick, x, y, 71, 95)) for y in range(3) for x in range(5)],
         [f"sticker {i}" for i in range(15)], "Balatro sticker sheet, row-major as in the game (5 per row)", cols=5)

    font()
    man_path = os.path.join(OUT, "manifest.json")
    keep = []
    if os.path.exists(man_path):            # entries other generators wrote (tooltips, card atlas, the older sheets)
        mine = {s["file"] for s in sheets}
        keep = [s for s in json.load(open(man_path))["sheets"] if s["file"] not in mine]
    json.dump({"about": "Sprite sheets served from " + BASE_URL + ". Tiles have no padding. Index i of a sheet with C columns "
                        "sits at column i mod C, row floor(i / C). Rebuild: python3 tools/make_sheets.py",
               "mask_rule": "To show tile (c, r) of a C x R sheet drawn at w x h graph units per tile, centred on Q: image centre = "
                            "Q - ((c - (C-1)/2) w, ((R-1)/2 - r) h); mask with one tile-sized polygon at Q.",
               "sheets": sheets + keep}, open(man_path, "w"), indent=1, ensure_ascii=False)
    print("sheets:", ", ".join(s["file"].split("/")[1] for s in sheets))


# ------------------------------------------------------------------ font
FONT_ROWS = [  # (band top in sheet px, characters in order of their ink segments)
    (32, "aAbBcCdDeEfFgGhHiIjJkKlLmMn"), (64, "NoOpPqQrRsStTuUvVwWxXyYzZ"), (128, "0123456789.Thequick,brown"),
    (160, "foxjumpsoverthelazydog?"), (224, "12+34-56×78÷90=...()[]{}"), (256, "!?,.;:'\"\"/\\<>@#$&*")]


def font():
    """Glyph bitmaps of the 2x specimen: rows top = cap top, baseline at row 10, descenders to row 13."""
    im = load("font.png")
    W, H = im.size
    px = im.load()
    on = lambda x, y: px[x, y][3] > 128 and sum(px[x, y][:3]) > 384
    glyphs = {}
    for top, chars in FONT_ROWS:
        bottom = top + 28
        cols = [x for x in range(W) if any(on(x, y) for y in range(top, bottom))]
        segs, s, p = [], cols[0], cols[0]
        for x in cols[1:]:
            if x != p + 1:
                segs.append((s, p))
                s = x
            p = x
        segs.append((s, p))
        assert len(segs) == len(chars), (top, len(segs), len(chars))
        i = 0
        while i < len(segs):
            ch = chars[i]
            a, b = segs[i]
            if ch == '"' and i + 1 < len(chars) and chars[i + 1] == '"':   # the double quote is two ticks
                b = segs[i + 1][1]
                i += 1
            if ch not in glyphs:
                rows = []
                for y in range(top, bottom, 2):
                    rows.append("".join("1" if on(x, y) else "0" for x in range(a, b + 1, 2)))
                glyphs[ch] = rows
            i += 1
    # '%' isn't in the specimen: drawn here in the same style (6 px wide)
    pct = ["000000", "110001", "110010", "000010", "000100", "000100", "001000", "001000", "010000", "010011", "100011",
           "000000", "000000", "000000"]
    glyphs["%"] = pct
    glyphs[" "] = ["0000"] * 14
    json.dump({"source": "managore's m6x11 specimen (sources/font.png), cut by tools/make_sheets.py",
               "cell_height": 14, "baseline": 10, "cap_height": 11, "spacing": 1, "glyphs": glyphs},
              open(os.path.join(ROOT, "tools", "font.json"), "w"), indent=0)


if __name__ == "__main__":
    main()
