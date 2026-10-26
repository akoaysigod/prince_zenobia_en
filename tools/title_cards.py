"""Chapter title cards and area-name cards: pictures built from a sheet of tiles.

Code at 0x29ECB4 copies a 360-tile sheet (0xB40 words) to the tiles from 0x44, then
the card's layout (a 0x040C header word and a 12x4 grid of tile numbers, 0 = blank)
from a per-card table. Two sets, chosen by a story flag:

  table 0x9EEA2, sheet 0x9F34A: chapters ("第1話 胎動"...), the final chapter, bonus titles
  table 0x9EECA, sheet 0xA09CA: area names ("エストラーダの館"...)

Each set has 18 cards (the tables' last entries repeat the 18th). The English is drawn
with the menu-caption font (tools/menu_labels.py), one letter per 8-pixel cell,
white strokes with a blue outline like the Japanese:

  "HEADING\\nsubtitle"  heading in tall letters (16 px), subtitle in small letters,
                       word-wrapped to 2 lines
  "TITLE"              tall letters, word-wrapped to 2 lines

Lines hold 12 letters. Each set's tiles are rebuilt from its English, sharing identical
tiles. The game always copies 360 tiles, but the second sheet's last 32 "tiles" are other
data (the emblem's tile map, from 0xA1E4A), so that set may only use 328.
"""
import menu_labels

COLS, ROWS = 12, 4
SHEET_TILES = 360
FIRST_TILE = 0x44
RECORD = 2 + 2 * COLS * ROWS   # header word + grid
HEADER = 0x040C
WHITE, BLUE = 1, 3
SETS = [  # (table, sheet, Japanese of each card, tiles the set may use)
    (0x09EEA2, 0x09F34A, ['第1話 胎動', '第2話 飢えしものども', '第3話 信じるものは', '第4話 北の王国',
                          '第5話 死者', '第6話 妖術師', '第7話 問う声', '第8話 欲望のまねくもの',
                          '第9話 決心', '第10話 闇の騎士', '第11話 涙', '第12話 闇と静寂、そして',
                          '最終話 白夜', '山奥', '財宝', '血と肉と', 'サムライ', 'フリーバトルエリア'], 360),
    (0x09EECA, 0x0A09CA, ['エストラーダの館', 'グロス地方', 'サツ半島', 'リヒトフロス', 'ローデン地方',
                          'リット島海域', 'ネッサ地方', 'ノロドム地方', 'メガホルテン', 'シャガール湿地',
                          'レゴ群島', 'アム樹海', 'ライカ湖畔', 'クロノ山脈', 'アイン半島', 'ウインド砂丘',
                          'フレイア諸島', 'フリーバトルエリア'], 328),  # emblem map from 0xA1E4A
]


def word(rom, a):
    return rom[a] | rom[a + 1] << 8


def records(rom):
    """[(set index, card index, layout record offset)] for the 18 cards of each set."""
    out = []
    for s, (table, _, jp, _) in enumerate(SETS):
        for i in range(len(jp)):
            out.append((s, i, table + word(rom, table + 2 * i)))
    return out


def set_of(offset, rom):
    for s, i, o in records(rom):
        if o == offset:
            return s, i
    return None


def wrap(text, width=COLS):
    lines, line = [], ''
    for w in text.split():
        cand = f'{line} {w}' if line else w
        if line and len(cand) > width:
            lines.append(line)
            line = w
        else:
            line = cand
    return lines + ([line] if line else [])


def lines_of(text):
    """[(line, tall)] for a card's English."""
    if '\n' in text:
        head, rest = text.split('\n', 1)
        return [(head.strip(), True)] + [(l, False) for part in rest.split('\n') for l in wrap(part)]
    return [(l, True) for l in wrap(text)]


def check(text):
    bad = sorted({c for c in text if c not in menu_labels.FONT and c != '\n'})
    if bad:
        return [f'No letter for {c!r} (cards use capitals, digits and . , ! ? - / \' &)' for c in bad]
    lines = lines_of(text)
    out = [f'Line is {len(l)} letters; a card line holds {COLS}: {l!r}' for l, _ in lines if len(l) > COLS]
    rows = sum(2 if tall else 1 for _, tall in lines)
    tall = [t for _, t in lines]
    if rows > ROWS or tall.count(True) > 2 or (tall[0] and tall.count(False) > 2):
        out.append('Too many lines: one tall heading and 2 small lines, or 2 tall lines.')
    return out


def render(text):
    """32 rows x 96 pixel values for a card."""
    W, H = 8 * COLS, 8 * ROWS
    ink = [[0] * W for _ in range(H)]
    lines = lines_of(text)
    small = [l for l, t in lines if not t]
    tall = [l for l, t in lines if t]
    if small:  # heading on rows 0-1, subtitle below (centred in rows 2-3 if one line)
        places = [(tall[0], True, 0)] if tall else []
        ys = [20] if len(small) == 1 else [16, 24]
        places += [(l, False, y) for l, y in zip(small, ys)]
    else:
        ys = [8] if len(tall) == 1 else [0, 16]
        places = [(l, True, y) for l, y in zip(tall, ys)]
    for line, is_tall, y in places:
        col = (COLS - len(line)) // 2
        for k, ch in enumerate(line):
            rows = menu_labels.FONT[ch]
            x0 = 8 * (col + k) + (8 - len(rows[0])) // 2
            for r, row in enumerate(rows):
                for i, p in enumerate(row):
                    if p != '#':
                        continue
                    for yy in ((y + 2 + 2 * r, y + 3 + 2 * r) if is_tall else (y + 1 + r,)):
                        if 0 <= yy < H and 0 <= x0 + i < W:
                            ink[yy][x0 + i] = 1
    out = [[WHITE if v else 0 for v in row] for row in ink]
    for y in range(H):
        for x in range(W):
            if not ink[y][x] and any(ink[y + dy][x + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                                     if 0 <= y + dy < H and 0 <= x + dx < W):
                out[y][x] = BLUE
    return out


def tiles_of(pixels):
    """The card's 48 tiles (16 bytes each), row by row."""
    out = []
    for ty in range(ROWS):
        for tx in range(COLS):
            t = bytearray()
            for y in range(8):
                v = 0
                for x in range(8):
                    v |= pixels[8 * ty + y][8 * tx + x] << (14 - 2 * x)
                t += v.to_bytes(2, 'little')
            out.append(bytes(t))
    return out


def original(rom, s, offset):
    """The Japanese card as 32x96 pixels."""
    sheet = SETS[s][1]
    px = [[0] * (8 * COLS) for _ in range(8 * ROWS)]
    for k in range(COLS * ROWS):
        t = word(rom, offset + 2 + 2 * k)
        if not t:
            continue
        a = sheet + 16 * (t - FIRST_TILE)
        for y in range(8):
            v = word(rom, a + 2 * y)
            for x in range(8):
                px[8 * (k // COLS) + y][8 * (k % COLS) + x] = (v >> (14 - 2 * x)) & 3
    return px


def patch(rom, msgs):
    """Rebuild each set that has English. Returns (cards drawn, warnings)."""
    by_offset = {int(m['offset'], 16): m for m in msgs if m['kind'] == 'card'}
    done = warnings = 0
    for s, (table, sheet, jp, limit) in enumerate(SETS):
        cards = [(i, o, by_offset.get(o)) for t, i, o in records(rom) if t == s]
        if not any(m and m['en'] for _, _, m in cards):
            continue
        blank = bytes(16)
        tiles = {}   # tile bytes -> sheet index
        layouts = {}
        for i, o, m in cards:
            if m and m['en']:
                problems = check(m['en'])
                if problems:
                    for p in problems:
                        print(f"warning: title card {m['id']}: {p}")
                    warnings += len(problems)
                    if any(p.startswith('No letter') for p in problems):
                        continue
                grid = []
                for t in tiles_of(render(m['en'])):
                    if t == blank:
                        grid.append(0)
                        continue
                    if t not in tiles:
                        tiles[t] = len(tiles)
                    grid.append(FIRST_TILE + tiles[t])
                layouts[o] = grid
                done += 1
        # Cards still in Japanese keep their tiles: copy them into the new sheet too
        for i, o, m in cards:
            if o in layouts:
                continue
            grid = []
            for k in range(COLS * ROWS):
                t = word(rom, o + 2 + 2 * k)
                if not t:
                    grid.append(0)
                    continue
                a = sheet + 16 * (t - FIRST_TILE)
                data = bytes(rom[a:a + 16])
                if data not in tiles:
                    tiles[data] = len(tiles)
                grid.append(FIRST_TILE + tiles[data])
            layouts[o] = grid
        if len(tiles) > limit:
            print(f'warning: title card set {s + 1} needs {len(tiles)} tiles; the sheet holds {limit}')
            warnings += 1
            continue
        new = bytearray(16 * limit)  # never past the set's own tiles (other data follows set 2)
        for data, k in tiles.items():
            new[16 * k:16 * k + 16] = data
        rom[sheet:sheet + len(new)] = new
        for o, grid in layouts.items():
            assert word(rom, o) == HEADER, f'{o:06X}: not a card layout'
            for k, t in enumerate(grid):
                rom[o + 2 + 2 * k:o + 4 + 2 * k] = t.to_bytes(2, 'little')
        print(f'title card set {s + 1}: {len(tiles)}/{limit} tiles')
    return done, warnings
