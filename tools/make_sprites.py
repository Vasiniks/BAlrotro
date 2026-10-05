#!/usr/bin/env python3
"""Generate the original sprite sheets for the Desmos Balatro clone.

    python3 tools/make_sprites.py                  # every sheet + SPRITESHEETS/manifest.json
    python3 tools/make_sprites.py blinds tags      # only these sheets (the manifest is always rewritten)
    python3 tools/make_sprites.py --preview DIR    # also write enlarged contact sheets to DIR
    python3 tools/make_sprites.py --atlas PATH     # where to copy cards-atlas.png from

Sheets written to SPRITESHEETS/ (order = the reference data of the game repo, dev/reference/*.json):
    blinds.png    30 blind chips    34x34 art -> 136x136 tiles, vertical strip
    tags.png      24 skip tags      34x34 art -> 136x136 tiles, vertical strip
    vouchers.png  32 vouchers       71x95 art -> 284x380 tiles, grid 4 columns x 8 rows (row-major)
    boosters.png  32 booster packs  71x95 art -> 284x380 tiles, grid 4 columns x 8 rows (row-major)
    stakes.png     8 stake chips    29x29 art -> 116x116 tiles, vertical strip
    cards-atlas.png                 copied from the game repo (assets/cards-atlas.png)

Everything here is drawn by this script (pixel bitmaps typed in below, a few shapes computed),
at Balatro's native pixel size, then upscaled 4x with nearest-neighbour like the other sheets.
No Balatro sprite is read or copied. Text uses the two bitmap fonts defined below.
Needs only Pillow.
"""
import json
import math
import os
import shutil
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEETS = os.path.join(ROOT, 'SPRITESHEETS')
BASE_URL = 'https://vasiniks.github.io/BAlrotro/SPRITESHEETS/'
SCALE = 4
DEFAULT_ATLAS = os.path.join(os.path.dirname(ROOT), 'balatro final take', 'assets', 'cards-atlas.png')


# ============================================================================ colours

def hx(s):
    s = s.lstrip('#')
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), 255)


def mix(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)


def dark(c, t):
    return mix(c, (0, 0, 0), t)


def light(c, t):
    return mix(c, (255, 255, 255), t)


def lum(c):
    return (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]) / 255


CLEAR = (0, 0, 0, 0)
INK = hx('2b2333')          # general dark outline
CREAM = hx('fbf3df')

# Named colours usable in any bitmap below ('#' and '+' are given by the caller).
NAMED = {
    'K': INK, 'w': CREAM, 'W': hx('ffffff'),
    'l': hx('dfe4ec'), 's': hx('b9c3cf'), 'S': hx('7f8a9a'), 'm': hx('5b6372'),
    'y': hx('ffd34d'), 'Y': hx('d9961c'), 'o': hx('ff9a3c'), 'O': hx('c8621a'),
    'r': hx('ef4b4b'), 'R': hx('a6262e'), 'p': hx('ff8fc0'), 'P': hx('c44f86'),
    'g': hx('62cf6e'), 'G': hx('2e8c46'), 'b': hx('4f9cf0'), 'B': hx('2b5cb8'),
    'c': hx('8be6f5'), 'C': hx('2fa4c0'), 'v': hx('b48af0'), 'V': hx('7048b8'),
    'n': hx('b0723c'), 'N': hx('6e4220'), 't': hx('ecc28c'), 'k': hx('3c3c4a'),
    'u': hx('f2a0a0'),
}


# ============================================================================ canvas

class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.im = Image.new('RGBA', (w, h), CLEAR)
        self.p = self.im.load()

    def ok(self, x, y):
        return 0 <= x < self.w and 0 <= y < self.h

    def put(self, x, y, c):
        if self.ok(x, y):
            self.p[x, y] = c

    def get(self, x, y):
        return self.p[x, y] if self.ok(x, y) else CLEAR

    def rect(self, x0, y0, x1, y1, c):
        """Filled rectangle, corners inclusive."""
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.put(x, y, c)

    def hline(self, x0, x1, y, c):
        self.rect(x0, y, x1, y, c)

    def vline(self, x, y0, y1, c):
        self.rect(x, y0, x, y1, c)

    def scaled(self, k=SCALE):
        return self.im.resize((self.w * k, self.h * k), Image.NEAREST)


def neighbours(eight):
    n4 = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    return n4 + [(1, 1), (1, -1), (-1, 1), (-1, -1)] if eight else n4


def stamp_pixels(cv, pts, outline=None, eight=True, shadow=None):
    """pts: {(x, y): colour}. Draws an optional drop shadow (down-right), an outline, then the pixels."""
    if shadow is not None:
        for (x, y) in pts:
            for q in ((x + 1, y + 1), (x + 1, y + 2), (x, y + 2)) if False else ((x + 1, y + 1),):
                if q not in pts:
                    cv.put(q[0], q[1], shadow)
    if outline is not None:
        ring = set()
        for (x, y) in pts:
            for dx, dy in neighbours(eight):
                q = (x + dx, y + dy)
                if q not in pts:
                    ring.add(q)
        if shadow is not None:  # shadow sits outside the outline
            for (x, y) in list(ring):
                q = (x + 1, y + 1)
                if q not in pts and q not in ring:
                    cv.put(q[0], q[1], shadow)
        for q in ring:
            cv.put(q[0], q[1], outline)
    for (x, y), c in pts.items():
        cv.put(x, y, c)


def art_size(art):
    return max(len(r) for r in art), len(art)


def art_pixels(art, x0, y0, pal):
    pts = {}
    for j, row in enumerate(art):
        for i, ch in enumerate(row):
            if ch in '. ':
                continue
            c = pal.get(ch) or NAMED.get(ch)
            if c is None:
                raise KeyError('no colour for %r' % ch)
            pts[(x0 + i, y0 + j)] = c
    return pts


def stamp(cv, art, cx, cy, fill, detail, outline=None, eight=True, shadow=None, pal=None):
    """Draw bitmap `art` centred on (cx, cy). '#' = fill, '+' = detail, letters = NAMED colours."""
    w, h = art_size(art)
    x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
    p = {'#': fill, '+': detail}
    if pal:
        p.update(pal)
    stamp_pixels(cv, art_pixels(art, x0, y0, p), outline, eight, shadow)
    return x0, y0, w, h


# ============================================================================ fonts

# Large font: 7 rows, mostly 4 columns wide (letters that need it are 5; I is 3).
FONT_L = {
    'A': [".##.", "#..#", "#..#", "####", "#..#", "#..#", "#..#"],
    'B': ["###.", "#..#", "#..#", "###.", "#..#", "#..#", "###."],
    'C': [".##.", "#..#", "#...", "#...", "#...", "#..#", ".##."],
    'D': ["###.", "#..#", "#..#", "#..#", "#..#", "#..#", "###."],
    'E': ["####", "#...", "#...", "###.", "#...", "#...", "####"],
    'F': ["####", "#...", "#...", "###.", "#...", "#...", "#..."],
    'G': [".##.", "#..#", "#...", "#.##", "#..#", "#..#", ".###"],
    'H': ["#..#", "#..#", "#..#", "####", "#..#", "#..#", "#..#"],
    'I': ["###", ".#.", ".#.", ".#.", ".#.", ".#.", "###"],
    'J': ["..##", "...#", "...#", "...#", "#..#", "#..#", ".##."],
    'K': ["#..#", "#..#", "#.#.", "##..", "#.#.", "#..#", "#..#"],
    'L': ["#...", "#...", "#...", "#...", "#...", "#...", "####"],
    'M': ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    'N': ["#..#", "##.#", "##.#", "#.##", "#.##", "#..#", "#..#"],
    'O': [".##.", "#..#", "#..#", "#..#", "#..#", "#..#", ".##."],
    'P': ["###.", "#..#", "#..#", "###.", "#...", "#...", "#..."],
    'Q': [".##.", "#..#", "#..#", "#..#", "#..#", "#.#.", ".#.#"],
    'R': ["###.", "#..#", "#..#", "###.", "#.#.", "#..#", "#..#"],
    'S': [".##.", "#..#", "#...", ".##.", "...#", "#..#", ".##."],
    'T': ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    'U': ["#..#", "#..#", "#..#", "#..#", "#..#", "#..#", ".##."],
    'V': ["#...#", "#...#", "#...#", ".#.#.", ".#.#.", ".#.#.", "..#.."],
    'W': ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"],
    'X': ["#...#", ".#.#.", ".#.#.", "..#..", ".#.#.", ".#.#.", "#...#"],
    'Y': ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    'Z': ["####", "...#", "..#.", "..#.", ".#..", "#...", "####"],
    '0': [".##.", "#..#", "#.##", "##.#", "#..#", "#..#", ".##."],
    '1': [".#.", "##.", ".#.", ".#.", ".#.", ".#.", "###"],
    '2': [".##.", "#..#", "...#", "..#.", ".#..", "#...", "####"],
    '3': [".##.", "#..#", "...#", ".##.", "...#", "#..#", ".##."],
    '4': ["..#.", ".##.", "#.#.", "#.#.", "####", "..#.", "..#."],
    '5': ["####", "#...", "###.", "...#", "...#", "#..#", ".##."],
    '6': [".##.", "#...", "#...", "###.", "#..#", "#..#", ".##."],
    '7': ["####", "...#", "..#.", "..#.", ".#..", ".#..", ".#.."],
    '8': [".##.", "#..#", "#..#", ".##.", "#..#", "#..#", ".##."],
    '9': [".##.", "#..#", "#..#", ".###", "...#", "...#", ".##."],
    "'": ["#", "#", ".", ".", ".", ".", "."],
    '.': [".", ".", ".", ".", ".", ".", "#"],
    '!': ["#", "#", "#", "#", "#", ".", "#"],
    '-': ["...", "...", "...", "###", "...", "...", "..."],
    '+': [".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."],
    '$': ["..#..", ".####", "#.#..", ".###.", "..#.#", "####.", "..#.."],
    'x': [".....", ".....", "#...#", ".#.#.", "..#..", ".#.#.", "#...#"],
    '%': ["##...", "##..#", "...#.", "..#..", ".#...", "#..##", "...##"],
    '?': [".##.", "#..#", "...#", "..#.", "..#.", "....", "..#."],
    ' ': ["..", "..", "..", "..", "..", "..", ".."],
}

# Small font: 5 rows, mostly 3 columns wide.
FONT_S = {
    'A': [".#.", "#.#", "###", "#.#", "#.#"],
    'B': ["##.", "#.#", "##.", "#.#", "##."],
    'C': [".##", "#..", "#..", "#..", ".##"],
    'D': ["##.", "#.#", "#.#", "#.#", "##."],
    'E': ["###", "#..", "##.", "#..", "###"],
    'F': ["###", "#..", "##.", "#..", "#.."],
    'G': [".##", "#..", "#.#", "#.#", ".##"],
    'H': ["#.#", "#.#", "###", "#.#", "#.#"],
    'I': ["###", ".#.", ".#.", ".#.", "###"],
    'J': ["..#", "..#", "..#", "#.#", ".#."],
    'K': ["#.#", "#.#", "##.", "#.#", "#.#"],
    'L': ["#..", "#..", "#..", "#..", "###"],
    'M': ["#...#", "##.##", "#.#.#", "#...#", "#...#"],
    'N': ["#..#", "##.#", "#.##", "#..#", "#..#"],
    'O': [".#.", "#.#", "#.#", "#.#", ".#."],
    'P': ["##.", "#.#", "##.", "#..", "#.."],
    'Q': [".#.", "#.#", "#.#", "##.", ".##"],
    'R': ["##.", "#.#", "##.", "#.#", "#.#"],
    'S': [".##", "#..", ".#.", "..#", "##."],
    'T': ["###", ".#.", ".#.", ".#.", ".#."],
    'U': ["#.#", "#.#", "#.#", "#.#", "###"],
    'V': ["#.#", "#.#", "#.#", "#.#", ".#."],
    'W': ["#...#", "#...#", "#.#.#", "##.##", "#...#"],
    'X': ["#.#", "#.#", ".#.", "#.#", "#.#"],
    'Y': ["#.#", "#.#", ".#.", ".#.", ".#."],
    'Z': ["###", "..#", ".#.", "#..", "###"],
    '0': ["###", "#.#", "#.#", "#.#", "###"],
    '1': [".#.", "##.", ".#.", ".#.", "###"],
    '2': ["##.", "..#", ".#.", "#..", "###"],
    '3': ["##.", "..#", ".#.", "..#", "##."],
    '4': ["#.#", "#.#", "###", "..#", "..#"],
    '5': ["###", "#..", "##.", "..#", "##."],
    '6': [".##", "#..", "###", "#.#", "###"],
    '7': ["###", "..#", ".#.", ".#.", ".#."],
    '8': ["###", "#.#", "###", "#.#", "###"],
    '9': ["###", "#.#", "###", "..#", "##."],
    "'": ["#", "#", ".", ".", "."],
    '.': [".", ".", ".", ".", "#"],
    '!': ["#", "#", "#", ".", "#"],
    '-': ["...", "...", "###", "...", "..."],
    '+': ["...", ".#.", "###", ".#.", "..."],
    'x': ["...", "#.#", ".#.", "#.#", "..."],
    '$': [".#.", "###", "##.", ".##", "###"],
    ' ': ["..", "..", "..", "..", ".."],
}


def text_width(s, font, gap=1):
    return sum(len(font[ch][0]) for ch in s) + gap * (len(s) - 1) if s else 0


def text_pixels(s, font, x0, y0, colour, gap=1):
    pts = {}
    x = x0
    for ch in s:
        g = font[ch]
        for j, row in enumerate(g):
            for i, b in enumerate(row):
                if b == '#':
                    pts[(x + i, y0 + j)] = colour
        x += len(g[0]) + gap
    return pts


def draw_text(cv, s, font, cx, y0, colour, outline=None, eight=True, gap=1, shadow=None):
    """Text centred horizontally on cx, top at y0."""
    w = text_width(s, font, gap)
    x0 = int(math.floor(cx - w / 2 + 0.5))
    stamp_pixels(cv, text_pixels(s, font, x0, y0, colour, gap), outline, eight, shadow)
    return x0, w


HYPHENATE = {'RECYCLOMANCY': ['RECYCLO-', 'MANCY']}   # syllable splits for words too wide for one line


def wrap(name, font, maxw):
    """Greedy word wrap; a word wider than maxw is split with a hyphen."""
    words = []
    for wd in name.split():
        if text_width(wd, font) > maxw and wd in HYPHENATE:
            words += HYPHENATE[wd]
            continue
        while text_width(wd, font) > maxw:
            k = len(wd) - 1
            while k > 1 and text_width(wd[:k] + '-', font) > maxw:
                k -= 1
            words.append(wd[:k] + '-')
            wd = wd[k:]
        words.append(wd)
    lines, cur = [], ''
    for wd in words:
        t = (cur + ' ' + wd).strip() if not cur.endswith('-') else None
        if t is not None and text_width(t, font) <= maxw:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


# ============================================================================ computed shapes

def grid_art(w, h, test):
    return [''.join(test(x, y) or '.' for x in range(w)) for y in range(h)]


def wheel_art():
    def t(x, y):
        dx, dy = x - 6, y - 6
        d = math.hypot(dx, dy)
        if 5.0 <= d <= 6.6:
            return '#'
        if d <= 1.6:
            return '#' if d > 0.6 else '+'
        if d < 5.0:
            a = math.degrees(math.atan2(dy, dx)) % 45
            if min(a, 45 - a) * math.pi / 180 * d < 0.62:
                return '#'
        return None
    return grid_art(13, 13, t)


def spiral_art():
    pts = set()
    turns, pitch = 2.0, 3.0
    for i in range(4000):
        th = i / 4000 * turns * 2 * math.pi
        r = 0.4 + th * pitch / (2 * math.pi)
        x, y = 6 + r * math.cos(th), 6 + r * math.sin(th)
        pts.add((int(round(x)), int(round(y))))
    return grid_art(13, 13, lambda x, y: '#' if (x, y) in pts else None)


def waves_art():
    pts = set()
    for base in (2, 6, 10):
        for xi in range(0, 1300):
            x = xi / 100
            y = base + 1.0 * math.sin((x - 0.5) * 2 * math.pi / 6.0)
            pts.add((int(round(x)), int(round(y))))
    return grid_art(13, 13, lambda x, y: '#' if (x, y) in pts else None)


class Pix:
    """A small bitmap built from shapes; .rows() gives art rows for stamp()."""

    def __init__(self, w, h):
        self.w, self.h, self.d = w, h, {}

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.d[(x, y)] = c

    def rect(self, x0, y0, x1, y1, c):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.put(x, y, c)

    def disc(self, cx, cy, r, c, test=None):
        for y in range(self.h):
            for x in range(self.w):
                if math.hypot(x - cx, y - cy) <= r and (test is None or test(x, y)):
                    self.put(x, y, c)

    def ring(self, cx, cy, r0, r1, c):
        for y in range(self.h):
            for x in range(self.w):
                if r0 < math.hypot(x - cx, y - cy) <= r1:
                    self.put(x, y, c)

    def line(self, x0, y0, x1, y1, c, th=0.5):
        n = int(max(abs(x1 - x0), abs(y1 - y0)) * 4) + 1
        for i in range(n + 1):
            t = i / n
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            for yy in range(int(y - th - 1), int(y + th + 2)):
                for xx in range(int(x - th - 1), int(x + th + 2)):
                    if math.hypot(xx - x, yy - y) <= th:
                        self.put(xx, yy, c)

    def poly(self, pts, c):
        for y in range(self.h):
            for x in range(self.w):
                if point_in_poly(x, y, pts):
                    self.put(x, y, c)

    def art(self, rows, x0, y0):
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                if ch not in '. ':
                    self.put(x0 + i, y0 + j, ch)

    def rows(self):
        return [''.join(self.d.get((x, y), '.') for x in range(self.w)) for y in range(self.h)]


def point_in_poly(x, y, pts):
    inside = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def manacle_art():
    """Handcuffs: two cuffs joined by a chain arc."""
    return [
        "......#.#......",
        ".....#+#+#.....",
        "....#.....#....",
        "..###.....###..",
        ".#####...#####.",
        "##+++##.##+++##",
        "##+.+##.##+.+##",
        "##+++##.##+++##",
        ".#####...#####.",
        "..###.....###..",
    ]


def ringed_planet_art(w=15, h=11, rp=3.9, a=7.2, b=1.7, tilt=-0.38, planet='#', shade='+', ring='y'):
    """Planet with a tilted ring (front half drawn over the planet)."""
    p = Pix(w, h)
    cx, cy = (w - 1) / 2, (h - 1) / 2
    ca, sa = math.cos(tilt), math.sin(tilt)
    for y in range(h):
        for x in range(w):
            dx, dy = x - cx, y - cy
            u, v = dx * ca + dy * sa, -dx * sa + dy * ca
            e = (u / a) ** 2 + (v / b) ** 2
            on_ring = 0.55 <= e <= 1.05
            d = math.hypot(dx, dy)
            if d <= rp:
                p.put(x, y, shade if (dx + dy) > rp * 0.9 else planet)
                if on_ring and v > 0:
                    p.put(x, y, ring)
            elif on_ring:
                p.put(x, y, ring)
    return p.rows()


def meteor_art():
    p = Pix(12, 12)
    for k, c in ((-3, 'y'), (0, 'o'), (3, 'y')):
        for t in range(0, 9):
            x, y = t, t + k
            if math.hypot(x - 8, y - 8) > 3.9 and 0 <= y < 12:
                if (t + k) % 4 != 3:
                    p.put(x, y, c)
    p.disc(8, 8, 3.3, '#')
    p.put(7, 9, '+'); p.put(9, 7, '+'); p.put(9, 10, '+')
    return p.rows()


def planet_moon_art():
    p = Pix(16, 14)
    p.disc(6, 7.5, 5.6, '#')
    p.disc(6, 7.5, 5.6, '+', test=lambda x, y: (x - 6) + (y - 7.5) > 4.2)
    p.put(3, 5, 'w'); p.put(4, 4, 'w'); p.put(3, 6, 'w')
    p.rect(5, 9, 6, 9, '+'); p.put(8, 6, '+')
    p.disc(13.5, 2.5, 1.6, '#')
    return p.rows()


def constellation_art():
    p = Pix(15, 13)
    stars = [(1, 2), (6, 4), (11, 1), (13, 7), (8, 10), (3, 11)]
    for a, b in zip(stars, stars[1:]):
        p.line(a[0], a[1], b[0], b[1], 's', 0.35)
    for (x, y) in stars:
        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            p.put(x + dx, y + dy, '#')
    return p.rows()


def diamond_art(w=11, h=13):
    cx, cy = (w - 1) / 2, (h - 1) / 2
    return grid_art(w, h, lambda x, y: '#' if abs(x - cx) / (cx + 0.6) + abs(y - cy) / (cy + 0.6) <= 1 else None)


# ============================================================================ bitmap icon library
# '#' = fill (light), '+' = detail (dark); other letters are NAMED colours.

ICON = {
    'star4': [
        "....#....",
        "....#....",
        "...###...",
        "..#####..",
        "#########",
        "..#####..",
        "...###...",
        "....#....",
        "....#....",
    ],
    'star5': [
        "......#......",
        ".....###.....",
        ".....###.....",
        "....#####....",
        "#############",
        ".###########.",
        "..#########..",
        "...#######...",
        "...#######...",
        "..####.####..",
        "..###...###..",
        ".##.......##.",
    ],
    'hook': [
        ".....##...",
        "....#++#..",
        "....#++#..",
        ".....##...",
        ".....##...",
        ".....##...",
        ".....##...",
        ".#...##...",
        "##...##...",
        "##...##...",
        "##..##....",
        ".####.....",
        "..##......",
    ],
    'ox': [
        "#...........#",
        "##.........##",
        ".##.......##.",
        "..###...###..",
        "...#######...",
        "..#########..",
        "..##+###+##..",
        "...#######...",
        "...#######...",
        "...##+#+##...",
        "....#####....",
    ],
    'house': [
        "......#......",
        ".....###.....",
        "....#####....",
        "...#######...",
        "..#########..",
        ".###########.",
        "#############",
        "..#########..",
        "..#++###++#..",
        "..#++###++#..",
        "..####+####..",
        "..###+++###..",
        "..###+++###..",
    ],
    'wall': [
        "######+######",
        "######+######",
        "+++++++++++++",
        "##+######+###",
        "##+######+###",
        "+++++++++++++",
        "######+######",
        "######+######",
        "+++++++++++++",
        "##+######+###",
        "##+######+###",
    ],
    'arm': [
        ".........##..",
        "........####.",
        "........####.",
        ".........###.",
        "....###..###.",
        "...#####.###.",
        "..##########.",
        "############.",
        "############.",
        "###########..",
        ".#########...",
    ],
    'club': [
        "....###....",
        "...#####...",
        "...#####...",
        ".##.###.##.",
        "###########",
        "###########",
        ".##..#..##.",
        ".....#.....",
        "....###....",
    ],
    'fish': [
        "...#####.....",
        ".########..##",
        "##+#######.##",
        "###########..",
        ".#########.##",
        "..#######..##",
        "....###......",
    ],
    'spade': [
        ".....#.....",
        "....###....",
        "...#####...",
        "..#######..",
        ".#########.",
        "###########",
        "###########",
        ".###.#.###.",
        ".....#.....",
        "....###....",
    ],
    'eye': [
        ".....###.....",
        "...#######...",
        ".####+++####.",
        "####+++++####",
        "###++w++++###",
        "####+++++####",
        ".####+++####.",
        "...#######...",
        ".....###.....",
    ],
    'mouth': [
        "..###...###..",
        ".#####.#####.",
        "#############",
        "#+++++++++++#",
        ".###########.",
        "..#########..",
        "....#####....",
    ],
    'plant': [
        ".###.....###.",
        "#####...#####",
        "##+###.###+##",
        ".##+##.##+##.",
        "...####+##...",
        ".....###.....",
        "......#......",
        "......#......",
        "......#......",
        "...#######...",
    ],
    'serpent': [
        ".......####..",
        "......##+###.",
        ".....###..rr.",
        "....###......",
        "....###......",
        ".....####....",
        ".......####..",
        ".........###.",
        ".........###.",
        "........###..",
        "..#######....",
        ".#####.......",
    ],
    'pillar': [
        "###########",
        ".#########.",
        "..#+#+#+#..",
        "..#+#+#+#..",
        "..#+#+#+#..",
        "..#+#+#+#..",
        "..#+#+#+#..",
        "..#+#+#+#..",
        "..#+#+#+#..",
        "..#+#+#+#..",
        ".#########.",
        "###########",
    ],
    'needle': [
        "..........##.",
        ".........#+#.",
        "........#+#..",
        ".......###...",
        "......###....",
        ".....###.....",
        "....###......",
        "...###.......",
        "..###........",
        ".##..........",
        "#............",
    ],
    'heart': [
        ".###...###.",
        "#####.#####",
        "###########",
        "###########",
        "###########",
        ".#########.",
        "..#######..",
        "...#####...",
        "....###....",
        ".....#.....",
    ],
    'heart_big': [
        "..###...###..",
        ".#####.#####.",
        "##ww#########",
        "#ww##########",
        "#w###########",
        "#############",
        ".###########.",
        "..#########..",
        "...#######...",
        "....#####....",
        ".....###.....",
        "......#......",
    ],
    'tooth': [
        ".####.####.",
        "###########",
        "##w########",
        "#w#########",
        "###########",
        "###########",
        ".#########.",
        ".###...###.",
        ".###...###.",
        ".##.....##.",
        ".##.....##.",
        "..#.....#..",
    ],
    'flame': [
        ".....#.....",
        ".....##....",
        "....###....",
        "...####..#.",
        "..#####.##.",
        "..########.",
        ".##########",
        ".####y#####",
        "####yyy####",
        "####yyyy###",
        ".###yyyy##.",
        "..##yyy##..",
        "...#####...",
    ],
    'mark': [
        "##.......##",
        "###.....###",
        ".###...###.",
        "..###.###..",
        "...#####...",
        "....###....",
        "...#####...",
        "..###.###..",
        ".###...###.",
        "###.....###",
        "##.......##",
    ],
    'acorn': [
        ".....+.....",
        ".....+.....",
        "..nnnnnnn..",
        ".nNnNnNnNn.",
        "nnnnnnnnnnn",
        ".NNNNNNNNN.",
        ".##w######.",
        ".#w#######.",
        "..#######..",
        "..#######..",
        "...#####...",
        "....###....",
        ".....#.....",
    ],
    'leaf': [
        "..........###",
        "........#####",
        "......#######",
        ".....######+#",
        "....######+##",
        "...######+###",
        "..######+###.",
        "..#####+###..",
        ".#####+###...",
        ".####+###....",
        ".###+###.....",
        ".#+.###......",
        "#+...........",
    ],
    'vase': [
        "..#######..",
        "...#####...",
        "....###....",
        "....###....",
        "...#####...",
        ".#########.",
        "###########",
        "##+++++++##",
        "###########",
        "###########",
        ".#########.",
        "..#######..",
        "...#####...",
    ],
    'bell': [
        ".....#.....",
        "....#+#....",
        "....###....",
        "...#####...",
        "..#w#####..",
        "..#w#####..",
        "..#w#####..",
        "..#w#####..",
        ".##w######.",
        "###########",
        "#+++++++++#",
        "....###....",
        ".....#.....",
    ],
    # ---------------------------------------------------------------- tags / packs / vouchers
    'jester': [
        "y.....y.....y",
        "#.....#.....#",
        "##...###...##",
        "###.#####.###",
        ".###########.",
        "..#########..",
        "..+++++++++..",
    ],
    'card_shine': [
        ".#######.",
        "######s##",
        "#####s###",
        "####s###s",
        "###s###s#",
        "##s###s##",
        "#s###s###",
        "s###s####",
        "###s#####",
        "##s######",
        "#s#######",
        ".#######.",
    ],
    'card_heart': [
        ".#######.",
        "#r#######",
        "#########",
        "##rr#rr##",
        "#rrrrrrr#",
        "#rrrrrrr#",
        "##rrrrr##",
        "###rrr###",
        "####r####",
        "#########",
        "#######r#",
        ".#######.",
    ],
    'money_bag': [
        "..#.....#..",
        "...#####...",
        "....+++....",
        "...#####...",
        "..###+###..",
        ".###+++###.",
        "####+######",
        "#####+#####",
        "######+####",
        "####+++####",
        ".####+####.",
        "..#######..",
    ],
    'ticket': [
        "#############",
        "#########+###",
        "####+########",
        ".##+++###+##.",
        "..+++++####..",
        ".##+++###+##.",
        "###+#+#######",
        "#########+###",
        "#############",
    ],
    'dollar': [
        "....#....",
        "..#####..",
        ".##.#.##.",
        ".##.#....",
        "..#####..",
        "....#.##.",
        ".##.#.##.",
        "..#####..",
        "....#....",
    ],
    'skull': [
        "...#####...",
        ".#########.",
        "###########",
        "##+++#+++##",
        "##+++#+++##",
        "###########",
        ".####+####.",
        "..#######..",
        "..#+#+#+#..",
        "...#####...",
    ],
    'moon_star': [
        "....####.....",
        "..###........",
        ".###......#..",
        ".##......###.",
        "###.......#..",
        "###..........",
        "###..........",
        ".###.........",
        ".####.....##.",
        "..#########..",
        "....#####....",
    ],
    'hand': [
        "....#.#....",
        "..#.#.#.#..",
        "..#.#.#.#..",
        "..#.#.#.#..",
        "..#######..",
        "#.#######..",
        "##########.",
        ".#########.",
        "..########.",
        "...######..",
        "...######..",
    ],
    'trash': [
        "....###....",
        "###########",
        "###########",
        ".#########.",
        ".#+#+#+#+#.",
        ".#+#+#+#+#.",
        ".#+#+#+#+#.",
        ".#+#+#+#+#.",
        ".#+#+#+#+#.",
        "..#######..",
    ],
    'ghost': [
        "...#####...",
        "..#######..",
        ".#########.",
        ".##+###+##.",
        ".##+###+##.",
        ".#########.",
        "####+++####",
        "###########",
        "###########",
        "###########",
        "##.###.###.",
        "#...#...#..",
    ],
    'juggle': [
        "....###....",
        "...#rrr#...",
        "...#rrr#...",
        "....###....",
        "...........",
        ".###...###.",
        "#bbb#.#yyy#",
        "#bbb#.#yyy#",
        ".###...###.",
    ],
    'die': [
        ".#########.",
        "##+#####+##",
        "###########",
        "###########",
        "#####+#####",
        "###########",
        "###########",
        "##+#####+##",
        ".#########.",
    ],
    'arrow_up': [
        ".....#.....",
        "....###....",
        "...#####...",
        "..#######..",
        ".#########.",
        "....###....",
        "....###....",
        "....###....",
        "....###....",
        "....###....",
    ],
    'fast': [
        "#.....#....",
        "##....##...",
        "###...###..",
        "####..####.",
        "###########",
        "####..####.",
        "###...###..",
        "##....##...",
        "#.....#....",
    ],
    'sun': [
        "......#......",
        "..#...#...#..",
        "...#.....#...",
        ".....###.....",
        "....#####....",
        "...#######...",
        "##.#######.##",
        "...#######...",
        "....#####....",
        ".....###.....",
        "...#.....#...",
        "..#...#...#..",
        "......#......",
    ],
    'crystal': [
        "...#####...",
        "..##w####..",
        ".##w######.",
        ".#w#######.",
        ".#########.",
        ".#########.",
        "..#######..",
        "...#####...",
        "..+++++++..",
        ".+++++++++.",
    ],
    'gem': [
        "..#######..",
        ".##w#w#w##.",
        "###########",
        "#+#+#+#+#+#",
        ".##+###+##.",
        "..##+#+##..",
        "...##+##...",
        "....###....",
        ".....#.....",
    ],
}

ICON['wheel'] = wheel_art()
ICON['spiral'] = spiral_art()
ICON['waves'] = waves_art()
ICON['diamond'] = diamond_art()
ICON['manacle'] = manacle_art()
ICON['orbit'] = ringed_planet_art()
ICON['meteor'] = meteor_art()
ICON['constellation'] = constellation_art()
ICON['planet_small'] = planet_moon_art()


# ============================================================================ data (orders from dev/reference)

# blinds.json order; colours = game.lua boss_colour (same table as dev/patches/bosses.py)
BLINDS = [
    ("Small Blind", "0068ad", 'star4'), ("Big Blind", "e08a1c", 'star5'),
    ("The Hook", "a84024", 'hook'), ("The Ox", "b95b08", 'ox'), ("The House", "5186a8", 'house'),
    ("The Wall", "8a59a5", 'wall'), ("The Wheel", "50bf7c", 'wheel'), ("The Arm", "6865f3", 'arm'),
    ("The Club", "b9cb92", 'club'), ("The Fish", "3e85bd", 'fish'), ("The Psychic", "efc03c", 'spiral'),
    ("The Goad", "b95c96", 'spade'), ("The Water", "c6e0eb", 'waves'), ("The Window", "a9a295", 'diamond'),
    ("The Manacle", "575757", 'manacle'), ("The Eye", "4b71e4", 'eye'), ("The Mouth", "ae718e", 'mouth'),
    ("The Plant", "709284", 'plant'), ("The Serpent", "439a4f", 'serpent'), ("The Pillar", "7e6752", 'pillar'),
    ("The Needle", "5c6e31", 'needle'), ("The Head", "ac9db4", 'heart'), ("The Tooth", "b52d2d", 'tooth'),
    ("The Flint", "e56a2f", 'flame'), ("The Mark", "6a3847", 'mark'),
    ("Amber Acorn", "fda200", 'acorn'), ("Verdant Leaf", "56a786", 'leaf'), ("Violet Vessel", "8a71e1", 'vase'),
    ("Crimson Heart", "ac3232", 'heart_big'), ("Cerulean Bell", "009cfd", 'bell'),
]
SHOWDOWN_FROM = 25  # index of Amber Acorn

# tags.json order: (name, body colour, icon or None, caption, big text)
TAGS = [
    ("Uncommon Tag", "3fae78", 'jester', "UNC", None),
    ("Rare Tag", "e0483f", 'jester', "RARE", None),
    ("Negative Tag", "2c2540", 'card_shine', "NEG", None),
    ("Foil Tag", "7fa6d4", 'card_shine', "FOIL", None),
    ("Holographic Tag", "e26aa8", 'card_shine', "HOLO", None),
    ("Polychrome Tag", "poly", 'card_shine', "POLY", None),
    ("Investment Tag", "c98a26", 'money_bag', None, None),
    ("Voucher Tag", "f2672e", 'ticket', None, None),
    ("Boss Tag", "8c2f39", 'skull', None, None),
    ("Standard Tag", "d9dee6", 'card_heart', None, None),
    ("Charm Tag", "8f63c9", 'moon_star', None, None),
    ("Meteor Tag", "2f6fd0", 'meteor', None, None),
    ("Buffoon Tag", "f08a2a", 'jester', None, None),
    ("Handy Tag", "35a39a", 'hand', None, None),
    ("Garbage Tag", "7d8a52", 'trash', None, None),
    ("Ethereal Tag", "3d4fb0", 'ghost', None, None),
    ("Coupon Tag", "e3b23c", None, None, "FREE"),
    ("Double Tag", "7c8796", None, None, "2x"),
    ("Juggle Tag", "5b8fd6", 'juggle', None, None),
    ("D6 Tag", "4fb3a0", 'die', None, None),
    ("Top-up Tag", "6b7fe0", 'arrow_up', None, None),
    ("Speed Tag", "29b6d8", 'fast', None, None),
    ("Orbital Tag", "2a4f9e", 'orbit', None, None),
    ("Economy Tag", "f0c030", 'dollar', None, None),
]

# vouchers.json order (base, upgrade alternate)
VOUCHERS = [
    "Overstock", "Overstock Plus", "Clearance Sale", "Liquidation", "Hone", "Glow Up",
    "Reroll Surplus", "Reroll Glut", "Crystal Ball", "Omen Globe", "Telescope", "Observatory",
    "Grabber", "Nacho Tong", "Wasteful", "Recyclomancy", "Tarot Merchant", "Tarot Tycoon",
    "Planet Merchant", "Planet Tycoon", "Seed Money", "Money Tree", "Blank", "Antimatter",
    "Magic Trick", "Illusion", "Hieroglyph", "Petroglyph", "Director's Cut", "Retcon",
    "Paint Brush", "Palette",
]

# packs.json pack_types order, one tile per art variant
PACK_TYPES = [
    ("Arcana", "normal", 4), ("Arcana", "jumbo", 2), ("Arcana", "mega", 2),
    ("Celestial", "normal", 4), ("Celestial", "jumbo", 2), ("Celestial", "mega", 2),
    ("Standard", "normal", 4), ("Standard", "jumbo", 2), ("Standard", "mega", 2),
    ("Buffoon", "normal", 2), ("Buffoon", "jumbo", 1), ("Buffoon", "mega", 1),
    ("Spectral", "normal", 2), ("Spectral", "jumbo", 1), ("Spectral", "mega", 1),
]

STAKES = [
    ("White Stake", "eef0f3"), ("Red Stake", "e2443c"), ("Green Stake", "3fae5a"), ("Black Stake", "33313b"),
    ("Blue Stake", "3a72dc"), ("Purple Stake", "8a4fc8"), ("Orange Stake", "f08a2a"), ("Gold Stake", "f0bd34"),
]


# ============================================================================ chips (blinds, stakes)

def chip(size, face, rim, notch, line, n=8, rim_w=3.0, notch_px=3.4):
    """A round poker chip on a transparent square: outline, notched rim, groove, shaded face."""
    cv = Canvas(size, size)
    c = size / 2
    R = size / 2 - 1
    rf = R - 1 - rim_w
    rmid = (R - 1 + rf + 1) / 2
    seg = 2 * math.pi / n
    hw = notch_px / 2 / rmid
    for y in range(size):
        for x in range(size):
            dx, dy = x + 0.5 - c, y + 0.5 - c
            d = math.hypot(dx, dy)
            if d > R:
                continue
            ld = -(dx + dy) / (d * math.sqrt(2)) if d > 0 else 0   # +1 toward the top-left light
            if d > R - 1:
                col = line
            elif d > rf + 1:
                a = math.atan2(dy, dx) + math.pi / 2 + seg / 2
                t = a % seg
                col = notch if abs(t - seg / 2) < hw else rim
                if ld > 0.5:
                    col = light(col, 0.18)
                elif ld < -0.5:
                    col = dark(col, 0.16)
            elif d > rf:
                col = line
            else:
                col = face
                if d > rf - 1.6:
                    if ld < -0.35:
                        col = dark(face, 0.14)
                    elif ld > 0.45:
                        col = light(face, 0.22)
            cv.put(x, y, col)
    return cv


def blind_tile(i):
    name, hexc, icon = BLINDS[i]
    face = hx(hexc)
    showdown = i >= SHOWDOWN_FROM
    rim = dark(face, 0.38)
    notch = hx('ffd659') if showdown else light(face, 0.55)
    line = dark(face, 0.72)
    cv = chip(34, face, rim, notch, line)
    art = ICON[icon]
    if lum(face) > 0.8:   # The Water: dark emblem straight on the pale face
        d = dark(face, 0.62)
        stamp(cv, art, 17, 17, d, d, outline=None, shadow=dark(face, 0.25))
    else:
        outl = dark(face, 0.7)
        stamp(cv, art, 17, 17, CREAM, outl, outline=outl, eight=True, shadow=dark(face, 0.3))
    return cv


def stake_tile(i):
    name, hexc = STAKES[i]
    face = hx(hexc)
    if name == "White Stake":
        rim, notch, line = hx('aab3bf'), hx('ffffff'), hx('4a5260')
    elif name == "Black Stake":
        rim, notch, line = hx('1c1b22'), hx('8a8796'), hx('0c0c10')
    elif name == "Gold Stake":
        rim, notch, line = hx('b07a12'), hx('fff1a8'), hx('5a3a06')
    else:
        rim, notch, line = dark(face, 0.38), light(face, 0.55), dark(face, 0.72)
    cv = chip(29, face, rim, notch, line, n=8, rim_w=2.6, notch_px=3.0)
    digit = str(i + 1)
    if name == "White Stake":
        fill, outl = hx('3d4452'), hx('ffffff')
    elif name == "Black Stake":
        fill, outl = hx('e8e6f0'), hx('0c0c10')
    else:
        fill, outl = CREAM, dark(face, 0.7)
    w = text_width(digit, FONT_L)
    draw_text(cv, digit, FONT_L, 14.5, 11, fill, outline=outl, eight=True, shadow=dark(face, 0.3))
    return cv


# ============================================================================ tags

def rounded_inside(x, y, x0, y0, x1, y1, r):
    if x < x0 or x > x1 or y < y0 or y > y1:
        return False
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r + 0.5


def poly_colour(x, y):
    import colorsys
    h = ((x + y) / 40.0) % 1.0
    r, g, b = colorsys.hsv_to_rgb(h, 0.55, 0.95)
    return (round(r * 255), round(g * 255), round(b * 255), 255)


def tag_tile(i):
    name, hexc, icon, caption, big = TAGS[i]
    cv = Canvas(34, 34)
    poly = hexc == 'poly'
    body = hx('d77fd0') if poly else hx(hexc)
    neg = name == "Negative Tag"
    line = hx('e9e4ff') if neg else dark(body, 0.68)
    x0, y0, x1, y1, r = 2, 3, 31, 31, 4.0
    inside = lambda x, y: rounded_inside(x, y, x0, y0, x1, y1, r)
    for y in range(34):
        for x in range(34):
            if not inside(x, y):
                continue
            edge = any(not inside(x + dx, y + dy) for dx, dy in neighbours(False))
            if edge:
                cv.put(x, y, line)
                continue
            col = poly_colour(x, y) if poly else body
            # bevel: light top/left inner rim, dark bottom/right
            if not inside(x, y - 2) or not inside(x - 2, y):
                col = light(col, 0.28)
            elif not inside(x, y + 2) or not inside(x + 2, y):
                col = dark(col, 0.2)
            cv.put(x, y, col)
    # punched hole with an eyelet ring (transparent centre)
    hcx, hcy = 8.0, 9.0
    for y in range(4, 14):
        for x in range(3, 14):
            d = math.hypot(x + 0.5 - hcx, y + 0.5 - hcy)
            if d < 1.45:
                cv.put(x, y, CLEAR)
            elif d < 2.6:
                cv.put(x, y, hx('6b7382') if (x + 0.5 - hcx) + (y + 0.5 - hcy) > 0 else hx('e7ebf0'))
    # contents
    fill = CREAM
    outl = dark(body, 0.72) if not neg else hx('0d0b14')
    if neg:
        fill = hx('ffffff')
    cy = 19
    if caption:
        cy = 16
    if icon:
        pal = {}
        if icon == 'card_shine':
            sh = {'Negative Tag': hx('3a3352'), 'Foil Tag': hx('9fd2ff'), 'Holographic Tag': hx('ff7fc4'),
                  'Polychrome Tag': hx('7fd8a8')}[name]
            pal['s'] = sh
            if neg:
                fill = hx('1a1626')
                pal['s'] = hx('8a7fff')
                outl = hx('f4f0ff')
        stamp(cv, ICON[icon], 18, cy, fill, outl, outline=outl, eight=True, shadow=dark(body, 0.3) if not neg else None,
              pal=pal)
    if big:
        draw_text(cv, big, FONT_L, 18, 15, fill, outline=outl, eight=True, shadow=dark(body, 0.3))
    if caption:
        draw_text(cv, caption, FONT_S, 18, 24, fill, outline=outl, eight=True)
    return cv


# ============================================================================ voucher icons (multi-colour)

def sparkle(p, x, y, c='W'):
    for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        p.put(x + dx, y + dy, c)


def v_crate():
    return [
        "..wwwww.wwwww.wwwww..",
        "..wrwww.wbwww.wrwww..",
        "..wwwww.wwwww.wwwww..",
        "..wwwww.wwwww.wwwww..",
        "ttttttttttttttttttttt",
        "NNNNNNNNNNNNNNNNNNNNN",
        "nNtttttttttttttttttNn",
        "nNtttttttttttttttttNn",
        "nNnnnnnnnnnnnnnnnnnNn",
        "nNtttttttttttttttttNn",
        "nNtttttttttttttttttNn",
        "nNnnnnnnnnnnnnnnnnnNn",
        "nNtttttttttttttttttNn",
        "nNtttttttttttttttttNn",
        "nnnnnnnnnnnnnnnnnnnnn",
    ]


def v_price_tag():
    p = Pix(22, 14)
    p.poly([(-0.5, 6.5), (5.5, -0.5), (21.5, -0.5), (21.5, 13.5), (5.5, 13.5)], 'y')
    for x in range(22):
        if (x, 13) in p.d:
            p.put(x, 13, 'Y')
    p.disc(5, 6.5, 1.3, '+')
    pct = ["rr...r", "rr..r.", "...r..", "..r...", ".r..rr", "r...rr"]
    p.art(pct, 11, 4)
    return p.rows()


def v_gem():
    p = Pix(19, 16)
    p.poly([(4.5, 1.5), (14.5, 1.5), (18.5, 6), (0.5, 6)], 'c')
    p.poly([(0.5, 6), (18.5, 6), (9.5, 15.6)], 'C')
    p.line(9.5, 15, 5, 6.5, 'c', 0.45)
    p.line(9.5, 15, 14, 6.5, 'c', 0.45)
    p.line(7, 2, 5.5, 5.5, 'W', 0.45)
    p.line(12, 2, 13.5, 5.5, 'W', 0.45)
    for x in range(1, 19):
        if (x, 6) in p.d:
            p.put(x, 6, 'W')
    p.put(9, 3, 'W'); p.put(10, 3, 'W')
    return p.rows()


def v_dice():
    p = Pix(21, 20)
    p.rect(7, 0, 20, 12, 'l')
    p.rect(7, 12, 20, 12, 's'); p.rect(20, 0, 20, 12, 's')
    for (x, y) in ((10, 2), (17, 2), (17, 9)):
        p.rect(x, y, x + 1, y + 1, 'S')
    p.rect(0, 6, 13, 19, 'K')
    p.rect(1, 7, 12, 18, 'w')
    p.rect(1, 18, 12, 18, 's'); p.rect(12, 7, 12, 18, 's')
    for (x, y) in ((3, 9), (9, 9), (3, 15), (9, 15), (6, 12)):
        p.rect(x, y, x + 1, y + 1, 'r' if (x, y) == (6, 12) else 'k')
    return p.rows()


def v_crystal_ball():
    p = Pix(17, 19)
    p.disc(8, 7.5, 7.2, 'b')
    p.disc(8, 7.5, 7.2, 'c', test=lambda x, y: (x - 8) + (y - 7.5) < -3)
    p.disc(8, 7.5, 7.2, 'B', test=lambda x, y: (x - 8) + (y - 7.5) > 5)
    p.put(4, 3, 'W'); p.put(5, 3, 'W'); p.put(4, 4, 'W'); p.put(3, 5, 'W')
    p.put(10, 6, 'v'); p.put(9, 8, 'v'); p.put(11, 9, 'v'); p.put(8, 10, 'v')
    p.rect(3, 15, 13, 15, 'n')
    p.rect(2, 16, 14, 17, 'n')
    p.rect(2, 17, 14, 17, 'N')
    p.rect(5, 14, 11, 14, 'N')
    return p.rows()


def v_telescope():
    p = Pix(23, 21)
    p.line(10, 11, 4, 20, 'n', 0.6)
    p.line(11, 11, 11, 20, 'n', 0.6)
    p.line(12, 11, 18, 20, 'n', 0.6)
    p.line(2, 14, 18, 4, 's', 1.9)
    p.line(3, 15, 18, 5.5, 'S', 0.6)
    p.line(17, 2, 21, 7.5, 'Y', 1.2)
    p.line(19.5, 1, 22, 4.5, 'c', 0.6)
    p.line(9, 8, 10.5, 11, 'Y', 1.0)
    p.rect(0, 14, 2, 16, 'S')
    return p.rows()


def v_hand():
    return [
        "......ww.......",
        "...ww.ww.ww....",
        "...ww.ww.ww....",
        "...ww.ww.ww.ww.",
        "...ww.ww.ww.ww.",
        "...ww.ww.ww.ww.",
        "...wwwwwwwwwww.",
        "ww.wwwwwwwwwww.",
        "www.wwwwwwwwww.",
        ".wwwwwwwwwwwws.",
        "..wwwwwwwwwwws.",
        "...wwwwwwwwws..",
        "....wwwwwwwss..",
        "....rrrrrrrr...",
        "....RRRRRRRR...",
    ]


def v_trash():
    return [
        ".....sssss.....",
        ".....s...s.....",
        "sssssssssssssss",
        "SSSSSSSSSSSSSSS",
        ".lllllllllllll.",
        ".lllsllsllslll.",
        ".lllsllsllslll.",
        ".lllsllsllslll.",
        ".lllsllsllslll.",
        ".lllsllsllslll.",
        ".lllsllsllslll.",
        "..llsllsllsll..",
        "..llsllsllsll..",
        "..lllllllllll..",
        "..SSSSSSSSSSS..",
    ]


def v_tarot():
    p = Pix(14, 20)
    p.rect(0, 0, 13, 19, 'w')
    p.rect(2, 2, 11, 13, 'V')
    p.disc(6.5, 7.5, 3.4, 'y')
    p.disc(8.0, 6.6, 2.9, 'V')
    for (x, y) in ((9, 3), (4, 11), (10, 11)):
        p.put(x, y, 'W')
    p.rect(2, 15, 11, 17, 'v')
    p.rect(4, 16, 9, 16, 'w')
    return p.rows()


def v_planet():
    return ringed_planet_art(w=23, h=15, rp=5.7, a=10.6, b=2.3, tilt=-0.33, planet='o', shade='O', ring='y')


def v_seed_money():
    p = Pix(17, 21)
    p.disc(8, 14, 6.4, 'Y')
    p.disc(8, 14, 5.2, 'y')
    p.art([".YYY.", "Y.Y..", ".YYY.", "..Y.Y", ".YYY."], 6, 12)
    p.line(8, 7.6, 8, 3, 'G', 0.5)
    p.poly([(8, 4), (3, 0.5), (1.5, 3.5), (5, 5.5)], 'g')
    p.poly([(8, 3.5), (13, 0), (15, 3), (11, 5)], 'g')
    return p.rows()


def v_blank():
    p = Pix(15, 20)
    p.rect(0, 0, 14, 19, 'w')
    for x in range(2, 13):
        if x % 2 == 0:
            p.put(x, 2, 'S'); p.put(x, 17, 'S')
    for y in range(2, 18):
        if y % 2 == 0:
            p.put(2, y, 'S'); p.put(12, y, 'S')
    p.rect(14, 1, 14, 19, 'l'); p.rect(1, 19, 14, 19, 'l')
    return p.rows()


def v_top_hat():
    p = Pix(22, 18)
    p.rect(4, 1, 14, 12, 'k')
    p.rect(5, 1, 5, 11, 'm')
    p.rect(4, 9, 14, 11, 'r')
    p.rect(4, 11, 14, 11, 'R')
    p.rect(0, 13, 18, 14, 'k')
    p.rect(1, 13, 17, 13, 'm')
    p.line(14, 17, 21, 6, 'k', 0.6)
    p.line(20.4, 7, 21, 6, 'W', 0.6)
    sparkle(p, 18, 2, 'y')
    sparkle(p, 2, 4, 'y')
    return p.rows()


def v_pyramid():
    p = Pix(23, 16)
    p.disc(4, 3, 2.6, 'y')
    p.poly([(11.5, 1.5), (22.6, 15.6), (0.4, 15.6)], 't')
    p.poly([(11.5, 1.5), (22.6, 15.6), (14.5, 15.6)], 'n')
    for y in (6, 10, 14):
        for x in range(23):
            if p.d.get((x, y)) == 't' and x % 2 == 0:
                p.put(x, y, 'Y')
    p.art(["kkk", "k.k", "kkk"], 10, 8)
    p.put(11, 9, 'w')
    return p.rows()


def v_clapper():
    p = Pix(20, 18)
    p.rect(1, 6, 18, 17, 'k')
    p.rect(3, 9, 16, 9, 'm'); p.rect(3, 12, 12, 12, 'm'); p.rect(3, 15, 14, 15, 'm')
    p.rect(1, 1, 18, 4, 'k')
    for x in range(1, 19):
        for y in range(1, 5):
            if ((x + y) // 3) % 2 == 0:
                p.put(x, y, 'w')
    p.rect(0, 5, 19, 5, 'S')
    p.rect(0, 4, 1, 6, 's')
    return p.rows()


def v_brush():
    p = Pix(21, 21)
    p.line(2, 19, 11, 10, 'n', 1.1)
    p.line(3, 19, 11, 11, 'N', 0.4)
    p.line(11.5, 9.5, 14, 7, 's', 1.4)
    p.line(14.5, 6.5, 18.5, 2.5, 'r', 1.7)
    p.line(19, 2, 20, 1, 'r', 0.7)
    p.line(15, 7.5, 18, 4.5, 'R', 0.5)
    p.disc(4, 5, 1.6, 'r'); p.put(4, 7, 'r')
    p.disc(17, 16, 1.4, 'b')
    return p.rows()


VOUCHER_ICON = [v_crate, v_price_tag, v_gem, v_dice, v_crystal_ball, v_telescope, v_hand, v_trash,
                v_tarot, v_planet, v_seed_money, v_blank, v_top_hat, v_pyramid, v_clapper, v_brush]
VOUCHER_BG = ["2f8f8a", "c84a3c", "9b5fc0", "3e9a5a", "4b4fa8", "24407a", "3a78c2", "a0523a",
              "7a52b8", "2f6fbf", "6a9a2e", "7d8590", "6a3070", "c08a38", "3a3a46", "d8742c"]


# ============================================================================ vouchers (71 x 95)

def voucher_tile(i):
    name = VOUCHERS[i]
    up = i % 2 == 1
    pair = i // 2
    W, H = 71, 95
    cv = Canvas(W, H)
    if up:
        trim, trim_l, trim_d, line = hx('e8b23a'), hx('fde58a'), hx('a8701c'), hx('5a3608')
        paper = hx('fbefcf')
    else:
        trim, trim_l, trim_d, line = hx('b9c2cf'), hx('eef2f7'), hx('7c8696'), hx('3a404c')
        paper = hx('f4efe4')
    x0, y0, x1, y1, r = 1, 1, 69, 93, 4.0
    ny = 64                       # perforation row (notches on both sides)
    def inside(x, y):
        if not rounded_inside(x, y, x0, y0, x1, y1, r):
            return False
        for nx in (x0 - 0.5, x1 + 0.5):
            if math.hypot(x - nx, y - ny) < 4.3:
                return False
        return True
    def depth(x, y):  # distance (in pixels) to the outside, capped at 4
        for k in range(1, 4):
            for dx, dy in ((k, 0), (-k, 0), (0, k), (0, -k)):
                if not inside(x + dx, y + dy):
                    return k
        return 4
    for y in range(H):
        for x in range(W):
            if not inside(x, y):
                continue
            k = depth(x, y)
            if k == 1:
                col = line
            elif k <= 3:
                col = trim
                if not inside(x - 3, y - 3) and inside(x + 3, y + 3) and k == 2:
                    col = trim_l
                elif not inside(x + 3, y + 3) and k == 3:
                    col = trim_d
            else:
                col = paper
            cv.put(x, y, col)
    # inner hairline of the trim
    for y in range(H):
        for x in range(W):
            if cv.get(x, y) == paper and depth(x, y) == 4 and any(
                    cv.get(x + dx, y + dy) in (trim, trim_l, trim_d) for dx, dy in neighbours(False)):
                cv.put(x, y, mix(paper, trim_d, 0.45))
    # perforation
    for x in range(6, 65):
        if x % 3 != 2:
            cv.put(x, ny, mix(paper, line, 0.55))
    # art panel
    bg = hx(VOUCHER_BG[pair])
    px0, py0, px1, py1 = 7, 7, 63, 56
    for y in range(py0, py1 + 1):
        for x in range(px0, px1 + 1):
            edge = x in (px0, px1) or y in (py0, py1)
            corner = (x in (px0, px1)) and (y in (py0, py1))
            if corner:
                continue
            if edge:
                cv.put(x, y, line)
                continue
            col = bg
            cx, cy = x - 35, y - 31.5
            if up:   # sunburst rays
                a = (math.atan2(cy, cx) + math.pi) / (2 * math.pi) * 16
                if int(a) % 2 == 0:
                    col = light(bg, 0.14)
            else:    # soft dot pattern
                if (x + 2 * y) % 6 == 0 and y % 3 == 0:
                    col = light(bg, 0.16)
            dd = math.hypot(cx, cy * 1.1)
            if dd < 17.5:
                col = light(bg, 0.22) if dd < 16.5 else light(bg, 0.32)
            if y == py0 + 1 or x == px0 + 1:
                col = dark(col, 0.25)
            cv.put(x, y, col)
    # icon
    art = VOUCHER_ICON[pair]()
    stamp(cv, art, 35, 31, CREAM, INK, outline=INK, eight=True, shadow=dark(bg, 0.45))
    # tier stars on a small plaque across the panel's bottom edge
    stars = 2 if up else 1
    sw = 5 * stars + 2 * (stars - 1)
    bx0, bx1 = 35 - sw // 2 - 3, 35 - sw // 2 - 3 + sw + 5
    cv.rect(bx0, 53, bx1, 60, line)
    cv.rect(bx0 + 1, 54, bx1 - 1, 59, trim)
    cv.hline(bx0 + 1, bx1 - 1, 54, trim_l)
    star = [".#.", "###", ".#."]
    star5 = ["..#..", ".###.", "#####", ".###.", ".#.#."]
    sx = bx0 + 3
    for k in range(stars):
        stamp_pixels(cv, art_pixels(star5, sx, 55, {'#': hx('fff6c8') if up else hx('ffffff')}), None)
        sx += 7
    # name
    font = FONT_L
    lines = wrap(name.upper(), FONT_L, 59)
    if len(lines) > 2:
        font = FONT_S
        lines = wrap(name.upper(), FONT_S, 59)
    lh = len(font['A']) + (3 if font is FONT_L else 2)
    total = lh * len(lines) - (lh - len(font['A']))
    ty = 67 + (88 - 67 - total + 1) // 2 + 1
    ink = hx('3b2a24') if not up else hx('4a2a0c')
    for t in lines:
        draw_text(cv, t, font, 35.5, ty, ink)
        ty += lh
    return cv


# ============================================================================ boosters (71 x 95)

PACK_STYLE = {
    # kind: (body, sheen, dark, label fill, label ink)
    'Arcana': ('7b4fc4', 'b996f0', '41237a', 'f5ecff', '41237a'),
    'Celestial': ('3d86d9', '9fd0ff', '1d4686', 'eef7ff', '1d4686'),
    'Spectral': ('25317a', '5fd3e6', '0f1640', 'e6fbff', '18205a'),
    'Standard': ('f1ede4', 'ffffff', 'b8b0a2', 'd8383a', 'fff6ee'),
    'Buffoon': ('f08a2a', 'ffc878', '8e4410', 'fff3e0', '8e4410'),
}

PACK_EMBLEMS = {
    'Arcana': ['moon_star', 'sun', 'star5', 'eye'],
    'Celestial': ['orbit', 'meteor', 'planet_small', 'constellation'],
    'Standard': ['heart', 'spade', 'diamond', 'club'],
    'Buffoon': ['jester', 'joker_face'],
    'Spectral': ['ghost', 'gem'],
}

ICON['joker_face'] = [
    "y.....r.....y",
    "##...rrr...##",
    ".##.rrrrr.##.",
    "..#########..",
    "..#+##+##+#..",
    "..#########..",
    "...#r###r#...",
    "....#rrr#....",
    ".....###.....",
]


def pack_list():
    out = []
    for kind, size, n in PACK_TYPES:
        for v in range(1, n + 1):
            out.append((kind, size, v))
    return out


PACKS = pack_list()


def pack_key(kind, size, v):
    return 'p_%s_%s_%d' % (kind.lower(), size, v)


def pack_name(kind, size, v):
    base = {'normal': '', 'jumbo': 'Jumbo ', 'mega': 'Mega '}[size] + kind + ' Pack'
    return '%s (art %d)' % (base, v)


def booster_tile(i):
    kind, size, v = PACKS[i]
    body_h, sheen_h, dark_h, lab_h, ink_h = PACK_STYLE[kind]
    body, sheen, dk, lab, ink = hx(body_h), hx(sheen_h), hx(dark_h), hx(lab_h), hx(ink_h)
    line = dark(dk, 0.45)
    W, H = 71, 95
    cv = Canvas(W, H)
    crimp_top, crimp_bot = (2, 10), (84, 92)
    if size == 'mega':
        cr, cr_l, cr_d = hx('e8b23a'), hx('fde58a'), hx('9a6512')
    elif size == 'jumbo':
        cr, cr_l, cr_d = hx('c3ccd8'), hx('f2f5f9'), hx('7c8696')
    else:
        cr, cr_l, cr_d = (hx('d8383a'), hx('f07070'), hx('8e1c20')) if kind == 'Standard' else (dk, mix(dk, body, 0.6), dark(dk, 0.3))

    def inset(y):        # pillow shape: body narrows next to the crimps
        if crimp_top[1] < y < crimp_bot[0]:
            t = min(y - crimp_top[1], crimp_bot[0] - y)
            return 1 if t <= 2 else 0
        return 1

    def inside(x, y):
        if y < crimp_top[0] or y > crimp_bot[1]:
            return False
        a = 3 + inset(y)
        b = 67 - inset(y)
        if y == crimp_top[0] or y == crimp_bot[1]:     # serrated edges
            return a <= x <= b and (x // 2) % 2 == 0
        return a <= x <= b

    for y in range(H):
        for x in range(W):
            if not inside(x, y):
                continue
            edge = any(not inside(x + dx, y + dy) for dx, dy in neighbours(False))
            if edge:
                cv.put(x, y, line)
                continue
            if y <= crimp_top[1] or y >= crimp_bot[0]:
                col = cr_l if x % 2 == 0 else cr
                if y in (crimp_top[1], crimp_bot[0]):
                    col = cr_d
                cv.put(x, y, col)
                continue
            col = body
            # variant pattern
            if v == 1 and (x + y) % 8 == 0 and (x - y) % 8 == 0:
                col = mix(body, sheen, 0.45)
            elif v == 1 and ((x + y) % 8 == 0 or (x - y) % 8 == 0):
                col = mix(body, dk, 0.12)
            elif v == 2 and x % 6 == 0 and y % 6 == 0:
                col = mix(body, sheen, 0.5)
            elif v == 3 and (x + y) % 7 in (0, 1):
                col = mix(body, dk, 0.12)
            elif v == 4 and ((x * 7 + y * 13) % 29 == 0):
                col = mix(body, sheen, 0.7)
            # foil sheen: two diagonal light bands
            s = (x - 0.55 * y) % 46
            if 30 <= s < 34 or 37 <= s < 38:
                col = mix(col, sheen, 0.55)
            # side shading
            if x <= 5:
                col = mix(col, sheen, 0.35)
            elif x >= 64:
                col = mix(col, dk, 0.3)
            cv.put(x, y, col)
    if kind == 'Standard':   # red stripes down the white pouch
        for y in range(crimp_top[1] + 1, crimp_bot[0]):
            for x in (8, 9, 61, 62):
                if inside(x, y) and cv.get(x, y) != line:
                    cv.put(x, y, hx('d8383a') if x in (8, 61) else hx('a8262a'))

    # round badge behind the emblem
    bcx, bcy, br = 35, 29, 13.2
    for y in range(H):
        for x in range(W):
            d = math.hypot(x - bcx, y - bcy)
            if d <= br:
                if d > br - 1:
                    col = line if kind != 'Standard' else hx('a8262a')
                elif d > br - 2:
                    col = mix(body, sheen, 0.6) if kind != 'Standard' else hx('d8383a')
                else:
                    col = mix(body, dk, 0.42) if kind != 'Standard' else hx('fffdf8')
                    if kind != 'Standard' and (x - bcx) + (y - bcy) < -14:
                        col = mix(col, sheen, 0.25)
                cv.put(x, y, col)
    # emblem(s)
    names = PACK_EMBLEMS[kind]
    if kind == 'Standard' and size != 'normal':
        pair = [('heart', 'spade'), ('diamond', 'club')][v - 1]
        for k, nm in enumerate(pair):
            red = nm in ('heart', 'diamond')
            stamp(cv, ICON[nm], 29 + 13 * k, 29, hx('e0383a') if red else hx('3a3a48'), INK,
                  outline=hx('fff8ee'), eight=True, shadow=hx('b8b0a2'))
    elif kind == 'Standard':
        nm = names[v - 1]
        red = nm in ('heart', 'diamond')
        stamp(cv, ICON[nm], 35, 29, hx('e0383a') if red else hx('3a3a48'), INK,
              outline=hx('fff8ee'), eight=True, shadow=hx('b8b0a2'))
    else:
        nm = names[(v - 1 + {'normal': 0, 'jumbo': 1, 'mega': 2}[size]) % len(names)]
        pal = {'s': light(body, 0.4)}
        stamp(cv, ICON[nm], 35, 29, CREAM, line, outline=line, eight=True, shadow=dark(dk, 0.2), pal=pal)
    if size != 'normal':      # sparkles around the emblem
        for (x, y) in ((13, 17), (57, 19), (14, 39), (56, 38)):
            for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                cv.put(x + dx, y + dy, hx('fff6c8') if size == 'mega' else hx('ffffff'))

    # name plaque
    label = kind.upper()
    tw = text_width(label, FONT_L)
    lx0, lx1, ly0, ly1 = 35 - tw // 2 - 5, 35 - tw // 2 - 5 + tw + 9, 47, 59
    for y in range(ly0, ly1 + 1):
        for x in range(lx0, lx1 + 1):
            if not rounded_inside(x, y, lx0, ly0, lx1, ly1, 2.0):
                continue
            edge = any(not rounded_inside(x + dx, y + dy, lx0, ly0, lx1, ly1, 2.0) for dx, dy in neighbours(False))
            cv.put(x, y, line if edge else (dark(lab, 0.12) if y == ly1 - 1 else lab))
    draw_text(cv, label, FONT_L, 35.5, 50, ink)

    # size banner
    word = {'normal': 'PACK', 'jumbo': 'JUMBO', 'mega': 'MEGA'}[size]
    if size == 'normal':
        draw_text(cv, word, FONT_L, 35.5, 66, CREAM if kind != 'Standard' else hx('d8383a'),
                  outline=line if kind != 'Standard' else hx('fff8ee'), eight=True)
    else:
        rib, rib_l, rib_d = (hx('e8b23a'), hx('fde58a'), hx('9a6512')) if size == 'mega' else \
                            (hx('c3ccd8'), hx('f2f5f9'), hx('7c8696'))
        tw = text_width(word, FONT_L)
        rx0, rx1, ry0, ry1 = 35 - tw // 2 - 6, 35 - tw // 2 - 6 + tw + 11, 63, 74
        mid = (ry0 + 3 + ry1 + 3) / 2
        for side in (-1, 1):            # swallow-tail ends, tucked behind the band
            xs = range(rx0 - 6, rx0) if side < 0 else range(rx1 + 1, rx1 + 7)
            for x in xs:
                far = (rx0 - x) if side < 0 else (x - rx1)
                for y in range(ry0 + 3, ry1 + 4):
                    if far >= 4 and abs(y - mid) <= (far - 4) + 0.5:
                        continue
                    edge = y in (ry0 + 3, ry1 + 3) or far == 6 or (far >= 4 and abs(y - mid) <= far - 3 + 0.5)
                    cv.put(x, y, line if edge else rib_d)
        for y in range(ry0, ry1 + 1):
            for x in range(rx0, rx1 + 1):
                edge = x in (rx0, rx1) or y in (ry0, ry1)
                cv.put(x, y, line if edge else (rib_l if y == ry0 + 1 else (dark(rib, 0.12) if y == ry1 - 1 else rib)))
        draw_text(cv, word, FONT_L, 35.5, 66, hx('fffaf0'), outline=dark(rib_d, 0.35), eight=True)
    return cv


# ============================================================================ manifest

JOKER_NAMES = [
    'Joker', 'Greedy Joker', 'Lusty Joker', 'Wrathful Joker', 'Gluttonous Joker', 'Jolly Joker', 'Zany Joker',
    'Mad Joker', 'Crazy Joker', 'Droll Joker', 'Sly Joker', 'Wily Joker', 'Clever Joker', 'Devious Joker',
    'Crafty Joker', 'Half Joker', 'Joker Stencil', 'Four Fingers', 'Mime', 'Credit Card', 'Ceremonial Dagger',
    'Banner', 'Mystic Summit', 'Marble Joker', 'Loyalty Card', '8 Ball', 'Misprint', 'Dusk', 'Raised Fist',
    'Chaos the Clown', 'Fibonacci', 'Steel Joker', 'Scary Face', 'Abstract Joker', 'Delayed Gratification', 'Hack',
    'Pareidolia', 'Gros Michel', 'Even Steven', 'Odd Todd', 'Scholar', 'Business Card', 'Supernova', 'Ride the Bus',
    'Space Joker', 'Egg', 'Burglar', 'Blackboard', 'Runner', 'Ice Cream', 'DNA', 'Splash', 'Blue Joker',
    'Sixth Sense', 'Constellation', 'Hiker', 'Faceless Joker', 'Green Joker', 'Superposition', 'To Do List',
    'Cavendish', 'Card Sharp', 'Red Card', 'Madness', 'Square Joker', 'Seance', 'Riff-Raff', 'Vampire', 'Shortcut',
    'Hologram', 'Vagabond', 'Baron', 'Cloud 9', 'Rocket', 'Obelisk', 'Midas Mask', 'Luchador', 'Photograph',
    'Gift Card', 'Turtle Bean', 'Erosion', 'Reserved Parking', 'Mail-In Rebate', 'To the Moon', 'Hallucination',
    'Fortune Teller', 'Juggler', 'Drunkard', 'Stone Joker', 'Golden Joker', 'Lucky Cat', 'Baseball Card', 'Bull',
    'Diet Cola', 'Trading Card', 'Flash Card', 'Popcorn', 'Spare Trousers', 'Ancient Joker', 'Ramen',
    'Walkie Talkie', 'Seltzer', 'Castle', 'Smiley Face', 'Campfire', 'Golden Ticket', 'Mr. Bones', 'Acrobat',
    'Sock and Buskin', 'Swashbuckler', 'Troubadour', 'Certificate', 'Smeared Joker', 'Throwback', 'Hanging Chad',
    'Rough Gem', 'Bloodstone', 'Arrowhead', 'Onyx Agate', 'Glass Joker', 'Showman', 'Flower Pot', 'Blueprint',
    'Wee Joker', 'Merry Andy', 'Oops! All 6s', 'The Idol', 'Seeing Double', 'Matador', 'Hit the Road', 'The Duo',
    'The Trio', 'The Family', 'The Order', 'The Tribe', 'Stuntman', 'Invisible Joker', 'Brainstorm', 'Satellite',
    'Shoot the Moon', "Driver's License", 'Cartomancer', 'Astronomer', 'Burnt Joker', 'Bootstraps', 'Canio',
    'Triboulet', 'Yorick', 'Chicot', 'Perkeo',
]
TAROT_NAMES = [
    'The Fool', 'The Magician', 'The High Priestess', 'The Empress', 'The Emperor', 'The Hierophant', 'The Lovers',
    'The Chariot', 'Justice', 'The Hermit', 'The Wheel of Fortune', 'Strength', 'The Hanged Man', 'Death',
    'Temperance', 'The Devil', 'The Tower', 'The Star', 'The Moon', 'The Sun', 'Judgement', 'The World',
]
PLANET_NAMES = ['Eris', 'Ceres', 'Planet X', 'Mercury', 'Venus', 'Earth', 'Mars', 'Jupiter', 'Saturn', 'Uranus',
                'Neptune', 'Pluto']
SPECTRAL_NAMES = ['The Soul', 'Black Hole', 'Familiar', 'Grim', 'Incantation', 'Talisman', 'Aura', 'Wraith', 'Sigil',
                  'Ouija', 'Ectoplasm', 'Immolate', 'Ankh', 'Deja Vu', 'Hex', 'Trance', 'Medium', 'Cryptid']
OVERLAY_NAMES = ['Red Deck back', 'Blank card front', 'Gold Seal', 'Stone Card', 'Gold Card', 'Bonus Card',
                 'Mult Card', 'Wild Card', 'Lucky Card', 'Glass Card', 'Steel Card', 'Purple Seal', 'Red Seal',
                 'Blue Seal']
SUITS = ['Hearts', 'Clubs', 'Diamonds', 'Spades']
RANKS_2A = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'Jack', 'Queen', 'King', 'Ace']
RANKS_AK = ['Ace'] + RANKS_2A[:-1]


def atlas_names():
    names = []
    for neg in (False, True):
        for s in SUITS:
            for r in RANKS_AK:
                names.append(('Negative ' if neg else '') + '%s of %s' % (r, s))
    fronts = ['Blank', 'Bonus', 'Mult', 'Wild', 'Glass', 'Steel', 'Stone', 'Gold', 'Lucky']
    names += ['%s front' % f for f in fronts] + ['Gold Seal', 'Red Seal', 'Blue Seal', 'Purple Seal']
    names += ['Negative %s front' % f for f in fronts] + ['Foil sheen', 'Holographic sheen', 'Polychrome sheen',
                                                          'Negative sheen']
    return names


def sheet_entry(fname, tile, names, order, native=None, generated=False, cols_hint=None):
    path = os.path.join(SHEETS, fname)
    w, h = Image.open(path).size if os.path.exists(path) else (None, None)
    tw, th = tile
    entry = {'file': 'SPRITESHEETS/' + fname, 'url': BASE_URL + fname}
    if w is not None:
        cols, rows = w // tw, h // th
        assert cols * tw == w and rows * th == h, (fname, w, h, tile)
        entry['image_px'] = [w, h]
    else:
        cols, rows = cols_hint, None
    entry['tile_px'] = [tw, th]
    if native:
        entry['native_px'] = list(native)
        entry['scale'] = SCALE
    entry['layout'] = 'vertical strip' if cols == 1 else 'grid'
    entry['columns'] = cols
    entry['rows'] = rows
    entry['count'] = len(names)
    entry['order'] = order
    entry['names'] = names
    entry['source'] = 'tools/make_sprites.py (original art)' if generated else 'existing'
    return entry


def write_manifest():
    sheets = [
        sheet_entry('blinds.png', (136, 136), [b[0] for b in BLINDS],
                    'Small Blind, Big Blind, then the 28 bosses in dev/reference/blinds.json order '
                    '(index = blind id - 1). Face colour = game.lua boss_colour; showdown bosses have gold notches.',
                    native=(34, 34), generated=True),
        sheet_entry('tags.png', (136, 136), [t[0] for t in TAGS], 'dev/reference/tags.json order (index = tag id - 1)',
                    native=(34, 34), generated=True),
        sheet_entry('vouchers.png', (284, 380), VOUCHERS,
                    'dev/reference/vouchers.json order (index = voucher id - 1), row-major, 4 per row: '
                    'even index = base voucher (silver trim, 1 star), odd = its upgrade (gold trim, 2 stars)',
                    native=(71, 95), generated=True),
        sheet_entry('boosters.png', (284, 380), [pack_name(*p) for p in PACKS],
                    'dev/reference/packs.json pack_types order, one tile per art variant (variants list order), '
                    'row-major, 4 per row', native=(71, 95), generated=True),
        sheet_entry('stakes.png', (116, 116), [s[0] for s in STAKES], 'White, Red, Green, Black, Blue, Purple, '
                    'Orange, Gold (chip shows the stake number 1-8)', native=(29, 29), generated=True),
        sheet_entry('spritesheet.png', (284, 380), JOKER_NAMES, 'jokers, Balatro collection order, row-major'),
        sheet_entry('tarot.png', (284, 380), TAROT_NAMES, 'major arcana 0 (The Fool) .. 21 (The World)'),
        sheet_entry('planet.png', (284, 380), PLANET_NAMES,
                    'NOT planet-id / poker-hand order: Eris, Ceres, Planet X, then Mercury .. Pluto'),
        sheet_entry('spectral.png', (284, 380), SPECTRAL_NAMES, 'The Soul, Black Hole, then Familiar .. Cryptid'),
        sheet_entry('cards.png', (284, 380), ['%s of %s' % (r, s) for s in SUITS for r in RANKS_2A],
                    'rank/suit art on a transparent background; Hearts, Clubs, Diamonds, Spades; ranks 2..10, J, Q, K, A'),
        sheet_entry('overlays.png', (284, 380), OVERLAY_NAMES, 'card back, blank front, enhancements and seals'),
        sheet_entry('cards-atlas.png', (284, 380), atlas_names(),
                    'generated playing-card atlas (game repo dev/modules/cards.atlas.py), 13 x 10, row-major. '
                    'Rows 0-3: faces col = rank-1 (Ace..King), row = suit-1 (Hearts, Clubs, Diamonds, Spades); '
                    'rows 4-7: the same through the Negative shader; row 8: fronts for C_Enh 0..8 then seals '
                    '(Gold, Red, Blue, Purple); row 9: Negative fronts then edition sheens (Foil, Holo, Poly, Negative)',
                    cols_hint=13),
    ]
    doc = {
        'about': 'Sprite sheets served from ' + BASE_URL + '. Tiles have no padding or margin. Index i (0-based) '
                 'of a sheet with C columns sits at column i mod C, row floor(i / C). Regenerate the original sheets '
                 'and this file with: python3 tools/make_sprites.py',
        'mask_rule': 'To show tile (c, r) of a C x R sheet drawn at w x h graph units per tile, centred on Q: '
                     'image centre = Q - ((c - (C-1)/2) w, ((R-1)/2 - r) h); mask with one tile-sized polygon at Q.',
        'sheets': sheets,
    }
    with open(os.path.join(SHEETS, 'manifest.json'), 'w') as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
        f.write('\n')


# ============================================================================ preview / sheets

def save_strip(tiles, path):
    tw, th = tiles[0].w * SCALE, tiles[0].h * SCALE
    sheet = Image.new('RGBA', (tw, th * len(tiles)), CLEAR)
    for k, t in enumerate(tiles):
        sheet.paste(t.scaled(), (0, k * th))
    sheet.save(path, optimize=True)
    return sheet


def save_grid(tiles, cols, path):
    tw, th = tiles[0].w * SCALE, tiles[0].h * SCALE
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new('RGBA', (tw * cols, th * rows), CLEAR)
    for k, t in enumerate(tiles):
        sheet.paste(t.scaled(), ((k % cols) * tw, (k // cols) * th))
    sheet.save(path, optimize=True)
    return sheet


def preview(tiles, cols, path, k=SCALE, bg=(48, 52, 60, 255)):
    tw, th = tiles[0].w * k, tiles[0].h * k
    rows = (len(tiles) + cols - 1) // cols
    pad = 4
    sheet = Image.new('RGBA', (cols * (tw + pad) + pad, rows * (th + pad) + pad), bg)
    for n, t in enumerate(tiles):
        im = t.im.resize((t.w * k, t.h * k), Image.NEAREST)
        sheet.alpha_composite(im, (pad + (n % cols) * (tw + pad), pad + (n // cols) * (th + pad)))
    sheet.save(path)


def main(argv):
    global SHEETS
    only, prev, atlas = set(), None, DEFAULT_ATLAS
    it = iter(argv)
    for a in it:
        if a == '--preview':
            prev = next(it)
        elif a == '--atlas':
            atlas = next(it)
        elif a == '--out':            # write the sheets somewhere else (testing)
            SHEETS = next(it)
        else:
            only.add(a)
    want = lambda k: not only or k in only
    if prev:
        os.makedirs(prev, exist_ok=True)
    if want('blinds'):
        tiles = [blind_tile(i) for i in range(len(BLINDS))]
        save_strip(tiles, os.path.join(SHEETS, 'blinds.png'))
        if prev:
            preview(tiles, 10, os.path.join(prev, 'blinds.png'), k=3)
    if want('tags'):
        tiles = [tag_tile(i) for i in range(len(TAGS))]
        save_strip(tiles, os.path.join(SHEETS, 'tags.png'))
        if prev:
            preview(tiles, 8, os.path.join(prev, 'tags.png'), k=3)
    if want('stakes'):
        tiles = [stake_tile(i) for i in range(len(STAKES))]
        save_strip(tiles, os.path.join(SHEETS, 'stakes.png'))
        if prev:
            preview(tiles, 8, os.path.join(prev, 'stakes.png'), k=4)
    if want('vouchers'):
        tiles = [voucher_tile(i) for i in range(len(VOUCHERS))]
        save_grid(tiles, 4, os.path.join(SHEETS, 'vouchers.png'))
        if prev:
            preview(tiles, 8, os.path.join(prev, 'vouchers.png'), k=2)
    if want('boosters'):
        tiles = [booster_tile(i) for i in range(len(PACKS))]
        save_grid(tiles, 4, os.path.join(SHEETS, 'boosters.png'))
        if prev:
            preview(tiles, 8, os.path.join(prev, 'boosters.png'), k=2)
    if want('atlas'):
        dst = os.path.join(SHEETS, 'cards-atlas.png')
        if os.path.exists(atlas):
            shutil.copyfile(atlas, dst)
        else:
            print('cards-atlas.png: source %s not found, kept the existing copy' % atlas)
    write_manifest()


if __name__ == '__main__':
    main(sys.argv[1:])
