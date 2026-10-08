"""The main menu's swirling red / blue background, from the real game (sources/MenuBackground.png, supplied by the owner).

    python3 tools/make_menu_bg.py          -> SPRITESHEETS/menu-bg.jpg (+ manifest entry)

The supplied 1280x720 frame of Balatro's splash swirl fills the game area: graph x -12..12 (its full width), centred on
y = 0, so 13.5 units tall. The picture covers graph x -12..12, y -17..15 like every full-screen layer (any window shape);
above and below the frame it continues as its own mirror image, fading darker, so a tall window never shows an edge.
64 pixels per graph unit (1.2x the source, Lanczos): smooth on a 4K screen. JPEG: no transparency, a sixth of a PNG.
"""
import json
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "SPRITESHEETS")
X0, X1, Y0, Y1, PPU = -12.0, 12.0, -17.0, 15.0, 64


def swirl_canvas(src, ppu):
    """the source frame across x -12..12 centred on y = 0, mirrored above / below to fill y -17..15"""
    w, h = round((X1 - X0) * ppu), round((Y1 - Y0) * ppu)
    band = src.resize((w, round(w * src.height / src.width)), Image.LANCZOS)
    top = round((Y1 - band.height / ppu / 2) * ppu)          # rows above the band (y = 0 is Y1 units from the top)
    out = Image.new("RGB", (w, h))
    out.paste(band, (0, top))
    flip = band.transpose(Image.FLIP_TOP_BOTTOM)
    for k in range(1, 4):                                  # mirrored copies until the picture is full
        out.paste(flip if k % 2 else band, (0, top - k * band.height))
        out.paste(flip if k % 2 else band, (0, top + k * band.height))
    # outside the frame, fade smoothly towards 45 % darker (no step at the seam)
    shade = Image.new("L", (1, h))
    for j in range(h):
        d = max(top - j, j - (top + band.height), 0) / (0.6 * band.height)
        shade.putpixel((0, j), round(255 * 0.45 * min(1.0, d)))
    return Image.composite(Image.new("RGB", (w, h)), out, shade.resize((w, h)))


def main():
    src = Image.open(os.path.join(ROOT, "sources", "MenuBackground.png")).convert("RGB")
    im = swirl_canvas(src, PPU)
    file = "SPRITESHEETS/menu-bg.jpg"
    im.save(os.path.join(ROOT, file), quality=90, optimize=True, progressive=True)
    man_path = os.path.join(OUT, "manifest.json")
    man = json.load(open(man_path))
    entry = {"file": file, "url": "https://vasiniks.github.io/BAlrotro/" + file, "image_px": list(im.size), "layout": "single",
             "graph_units": {"x": [X0, X1], "y": [Y0, Y1]},
             "source": "tools/make_menu_bg.py from sources/MenuBackground.png (Balatro's main-menu swirl, supplied by the owner)"}
    man["sheets"] = [s for s in man["sheets"] if s["file"] not in (file, "SPRITESHEETS/menu-bg.png")] + [entry]
    with open(man_path, "w") as fh:
        json.dump(man, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print(file, im.size)


if __name__ == "__main__":
    main()
