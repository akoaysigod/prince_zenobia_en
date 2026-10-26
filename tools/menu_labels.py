"""Menu command labels: small pictures, not text.

The field/battle menus show a caption under the icon row ("へんせいがめん", "アイテム"...).
Each caption is a 64x8 picture of 8 sprite tiles (2bpp, 128 bytes), stored one after
another from ROM 0x18112. Code at 0x217291 copies caption n from 0x218112 + 128*n to
the sprite tiles at 0xC0, so the English is drawn into the same 128 bytes.

Style (as the Japanese): 1-pixel strokes in colour 1, six rows tall (rows 1-6), with a
colour-3 outline around them; colour 0 is transparent. Text is centred.

Also here: small framed tags drawn into a sheet of interface tiles (TAGS), such as
"はけん中" (dispatched) on the unit list. Only the inside of the frame is redrawn.
"""

BASE = 0x18112
SIZE = 128            # 8 tiles of 16 bytes
WIDTH, HEIGHT = 64, 8
MAX_PX = WIDTH - 2    # strokes, leaving a column for the outline on each side
INK, OUTLINE = 1, 3
GAP = 1               # columns between letters

# The Japanese caption of each picture, in ROM order (read off the graphics).
JP = [
    'ユニットをはけん', 'アイテム', 'ステータスをみる', 'けっさんのよそう', 'モニター',
    'タロット カード', 'マップへもどる', 'へんせい', 'キャラをいれる', 'キャラをはずす',
    'フォーメーション', 'キャラをさくじょ', 'クラスチェンジ', 'リーダーチェンジ', 'いどう',
    'もくてきちをみる', 'バトル コマンド', 'キャラをこうかん', 'キャラをほじゅう', 'アイテムをかう',
    'ふっかつのぎしき', 'にげる', 'せっとく', 'キャラクター', 'アイテムをつかう',
    'アイテムをそうび', 'アイテムをはずす', 'アイテムをうる', 'アイテムをすてる', 'ならべかえ',
    'アイテムをせいり', 'ユニットいれかえ', 'へんせいがめん', 'アニメーション', 'ちゅうだん',
    'NEXT', 'たいせん', 'キャラをあげる', 'キャラをもらう', 'タイプ1ルール',
    'タイプ2ルール', 'プレイヤーとうろく', 'カスタム', 'アイテムをあげる', 'アイテムをもらう',
]
COUNT = len(JP)

# Framed tags in the interface tile sheet (0x14A00, with an identical copy at 0xE736A).
# Pixels x0..x1 of rows 1-6 are the inside of the frame, filled with colour `bg`.
TAGS = [
    dict(offset=0x014A00, copies=[0x0E736A], tiles=5, x0=5, x1=34, bg=2, jp='はけん中'),
]

# Capitals, digits and a little punctuation, 6 rows each ('#' = stroke).
_FONT = """
A .##. #..# #..# #### #..# #..#
B ###. #..# ###. #..# #..# ###.
C .##. #..# #... #... #..# .##.
D ###. #..# #..# #..# #..# ###.
E ### #.. ##. #.. #.. ###
F ### #.. ##. #.. #.. #..
G .##. #... #.## #..# #..# .###
H #..# #..# #### #..# #..# #..#
I ### .#. .#. .#. .#. ###
J ..## ...# ...# ...# #..# .##.
K #..# #.#. ##.. #.#. #..# #..#
L #.. #.. #.. #.. #.. ###
M #...# ##.## #.#.# #...# #...# #...#
N #..# ##.# #.## #..# #..# #..#
O .##. #..# #..# #..# #..# .##.
P ###. #..# #..# ###. #... #...
Q .##. #..# #..# #..# #.#. .#.#
R ###. #..# #..# ###. #.#. #..#
S .### #... .##. ...# ...# ###.
T ### .#. .#. .#. .#. .#.
U #..# #..# #..# #..# #..# .##.
V #...# #...# #...# .#.#. .#.#. ..#..
W #...# #...# #...# #.#.# ##.## #...#
X #..# #..# .##. .##. #..# #..#
Y #.# #.# #.# .#. .#. .#.
Z #### ...# ..#. .#.. #... ####
0 .#. #.# #.# #.# #.# .#.
1 .#. ##. .#. .#. .#. ###
2 ##. ..# ..# .#. #.. ###
3 ##. ..# .#. ..# ..# ##.
4 #.# #.# #.# ### ..# ..#
5 ### #.. ##. ..# ..# ##.
6 .## #.. ##. #.# #.# .#.
7 ### ..# ..# .#. .#. .#.
8 .#. #.# .#. #.# #.# .#.
9 .#. #.# #.# .## ..# ##.
. . . . . . #
- ... ... ### ... ... ...
/ ..# ..# .#. .#. #.. #..
' # # . . . .
& .#.. #.#. .#.. #.## #.#. .#.#
, .. .. .. .. .# #.
! # # # # . #
? .##. #..# ..#. .#.. .... .#..
"""
FONT = {}
for _line in _FONT.strip('\n').split('\n'):
    _ch, *_rows = _line.split(' ')
    FONT[_ch] = _rows
FONT[' '] = ['..'] * 6
CHARS = ''.join(sorted(FONT))


def advance(ch):
    return len(FONT[ch][0])


def width(text):
    """Stroke width in pixels (letters plus 1-pixel gaps)."""
    return sum(advance(c) for c in text) + GAP * max(len(text) - 1, 0) if text else 0


def tag_at(offset):
    """The TAGS spec whose picture is at this ROM offset, or None for a menu caption."""
    return next((t for t in TAGS if t['offset'] == offset), None)


def max_px(tag=None):
    return tag['x1'] - tag['x0'] + 1 if tag else MAX_PX


def check(text, tag=None):
    """Problems with an English caption, as a list of strings (empty = fine)."""
    bad = sorted({c for c in text if c not in FONT})
    out = [f'No letter for {c!r} (captions use capitals, digits and . , ! ? - / \' &)' for c in bad]
    if not bad and width(text) > max_px(tag):
        out.append(f'Caption is {width(text)} pixels wide; it fits {max_px(tag)}.')
    return out


def _draw(ink, text, x0, x1):
    x = x0 + (x1 - x0 + 1 - width(text)) // 2
    for c in text:
        for r, row in enumerate(FONT[c]):
            for i, p in enumerate(row):
                if p == '#' and x0 <= x + i <= x1:
                    ink[1 + r][x + i] = 1
        x += advance(c) + GAP


def _outline(out, ink, x0, x1, y0, y1):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if not ink[y][x] and any(ink[y + dy][x + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                                     if 0 <= y + dy < HEIGHT and 0 <= x + dx < len(ink[0])):
                out[y][x] = OUTLINE


def render(text, tag=None, original=None):
    """Pixel values (rows of ints 0-3) for an English caption: 64x8, or the tag's size
    (drawn over its original picture, `original`, inside the frame)."""
    if tag is None:
        ink = [[0] * WIDTH for _ in range(HEIGHT)]
        _draw(ink, text, 1, 1 + MAX_PX - 1)
        out = [[INK if v else 0 for v in row] for row in ink]
        _outline(out, ink, 0, WIDTH - 1, 0, HEIGHT - 1)
        return out
    out = decode(original, tag['tiles'])
    ink = [[0] * len(out[0]) for _ in range(HEIGHT)]
    _draw(ink, text, tag['x0'], tag['x1'])
    for y in range(1, HEIGHT - 1):
        for x in range(tag['x0'], tag['x1'] + 1):
            out[y][x] = INK if ink[y][x] else tag['bg']
    _outline(out, ink, tag['x0'], tag['x1'], 1, HEIGHT - 2)
    return out


def encode(pixels):
    """Pixels (8 rows, 8 per tile) -> 16 bytes per tile, each 8 rows of little-endian words, leftmost pixel in the top bits."""
    out = bytearray()
    for t in range(len(pixels[0]) // 8):
        for y in range(8):
            v = 0
            for x in range(8):
                v |= pixels[y][8 * t + x] << (14 - 2 * x)
            out += v.to_bytes(2, 'little')
    return bytes(out)


def decode(data, tiles=8):
    """16 bytes per tile -> 8 rows of pixel values (8 per tile)."""
    return [[(int.from_bytes(data[16 * (x // 8) + 2 * y:16 * (x // 8) + 2 * y + 2], 'little') >> (14 - 2 * (x % 8))) & 3
             for x in range(8 * tiles)] for y in range(HEIGHT)]


def offset(i):
    return BASE + SIZE * i


def patch(rom, msgs):
    """Draw every translated caption into the ROM. Returns (count, warnings)."""
    done = warnings = 0
    for m in msgs:
        if m['kind'] != 'label' or not m['en']:
            continue
        o = int(m['offset'], 16)
        tag = tag_at(o)
        problems = check(m['en'], tag)
        if problems:
            for p in problems:
                print(f"warning: menu label {m['id']}: {p}")
            warnings += len(problems)
            if any(p.startswith('No letter') for p in problems):
                continue
        if tag:
            n = 16 * tag['tiles']
            new = encode(render(m['en'], tag, bytes(rom[o:o + n])))
            for at in [o] + tag['copies']:
                rom[at:at + n] = new
        else:
            rom[o:o + SIZE] = encode(render(m['en']))
        done += 1
    return done, warnings
