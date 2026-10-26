"""Helper process for Translation Studio (app/): renders previews with the build's own rules.

Speaks JSON lines on stdin/stdout. Requests:
  {"cmd": "init"}             -> fonts (original and English), single-box ids, typeable characters
  {"cmd": "render", "entry": m, "single_box": bool}
                              -> the entry's Japanese and English as boxes of lines of glyph codes
Glyph codes are text bytes (glyph = byte - 1); -1 is an empty cell.
Menu captions (kind "label") are pictures: they come back as jp_image / en_image,
8 strings of 64 pixel values (0-3) each.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import font  # noqa: E402
import insert  # noqa: E402
import layout  # noqa: E402
import menu_labels  # noqa: E402
import title_cards  # noqa: E402
from dump_script import load_table  # noqa: E402

ROOT = os.path.join(HERE, '..')
ORIG_ROM = os.path.join(ROOT, 'Densetsu no Ogre Battle Gaiden - Zenobia no Ouji.ngc')
SAMPLE_NAME = 'Tristan'  # the default player name
SAMPLE_X = {'number': '300', 'name': 'Kain', 'class': 'Knight', 'item': 'Potion', 'town': 'Fortress Hind', 'tarot': 'Magician'}
BLANK = (0x01, 0xDC)

EN_REV = insert.build_encoder()
JP_REV = {v: k for k, v in load_table().items()}


def glyphs(rom):
    """256 glyphs as strings of 64 pixel values (0-3), row by row; index = text byte."""
    out = ['0' * 64]
    for b in range(1, 256):
        t = rom[font.FONT_BASE + 16 * (b - 1):font.FONT_BASE + 16 * b]
        out.append(''.join(str((int.from_bytes(t[2 * r:2 * r + 2], 'little') >> (14 - 2 * x)) & 3)
                           for r in range(8) for x in range(8)))
    return out


def encode_line(text, rev, warnings):
    out = []
    for part in insert.TAG_RE.split(text):
        if part == '{01}':
            out.append(-1)
        elif part in ('{NAME}', '{NUM}', '\n') or not part:
            continue
        else:
            for ch in part:
                b = rev.get(ch)
                if b is None:
                    warnings.append(f'No glyph for {ch!r}')
                    b = rev.get('?', 0xC8)
                out.append(-1 if b in BLANK else b)
    return out


def sample(text, m, jp=False):
    text = text.replace('{NAME}', 'トリスタン' if jp else SAMPLE_NAME).replace('{NUM}', '12')
    return text.replace('{X}', 'ＸＸＸ' if jp else SAMPLE_X.get(m.get('x'), '300'))


def en_boxes(m, single_box, warnings):
    """English as the build lays it out: list of boxes, each a list of line strings."""
    if not m['en'] or m['en'] == ['', '', '']:
        return []
    if m['kind'] == 'choices':
        return [[f'{"ABC"[i]}{layout.ANSWER_PREFIX}{a}' for i, a in enumerate(m['en'])]]
    if m['kind'] == 'name':
        return [[m['en']]]
    can_page = not single_box and m['kind'] == 'message'
    text = layout.layout(m, can_page=can_page) if m['kind'] != 'table' else layout.layout(m, can_page=False)
    return [b.rstrip('\n').split('\n') for b in text.split(layout.PAGE)]


def check(m, boxes, warnings):
    if m['kind'] in ('name', 'fixed') or (m['kind'] == 'native' and m.get('mode') != 'reloc'):
        return
    width = layout.entry_width(m) if m['kind'] != 'native' else m['width']
    if m['kind'] == 'choices':  # the boxes include the "A) " the game draws before each answer
        width += 1 + len(layout.ANSWER_PREFIX)
    xw = layout.X_WIDTH.get(m.get('x'), 8)
    for i, box in enumerate(boxes):
        limit = layout.last_box_lines(m) if i == len(boxes) - 1 else m.get('max_lines', layout.BOX_LINES)
        if len(box) > limit:
            why = ' (Yes/No goes on line 3)' if limit < layout.BOX_LINES else ''
            warnings.append(f'Box {i + 1} has {len(box)} lines; it holds {limit}{why}.')
        for line in box:
            if layout.width_of(line, xw) > width:
                warnings.append(f'Line is {layout.width_of(line, xw)} wide; the box is {width}: {line!r}')


def pixels(rows):
    return [''.join(map(str, r)) for r in rows]


def render_label(m):
    o = int(m['offset'], 16)
    tag = menu_labels.tag_at(o)
    tiles = tag['tiles'] if tag else 8
    original = ORIG[o:o + 16 * tiles]
    out = {'jp': [], 'en': [], 'en_text': [], 'jp_image': pixels(menu_labels.decode(original, tiles))}
    warnings = menu_labels.check(m['en'], tag) if m['en'] else []
    if m['en'] and not any(w.startswith('No letter') for w in warnings):
        out['en_image'] = pixels(menu_labels.render(m['en'], tag, original))
    out['warnings'] = warnings
    return out


def render_card(m):
    o = int(m['offset'], 16)
    s, _ = title_cards.set_of(o, ORIG)
    out = {'jp': [], 'en': [], 'en_text': [], 'jp_image': pixels(title_cards.original(ORIG, s, o))}
    warnings = title_cards.check(m['en']) if m['en'] else []
    if m['en'] and not any(w.startswith('No letter') for w in warnings):
        out['en_image'] = pixels(title_cards.render(m['en']))
    out['warnings'] = warnings
    return out


def render(m, single_box):
    if m['kind'] == 'label':
        return render_label(m)
    if m['kind'] == 'card':
        return render_card(m)
    warnings = []
    jp = m['jp'] if isinstance(m['jp'], str) else '\n'.join(m['jp'])
    jp_lines = [encode_line(sample(l, m, jp=True), JP_REV, []) for l in jp.rstrip('\n').split('\n')]
    boxes = en_boxes(m, single_box, warnings)
    check(m, boxes, warnings)
    en = [[encode_line(sample(l, m), EN_REV, warnings) for l in box] for box in boxes]
    return {'jp': [jp_lines], 'en': en, 'en_text': boxes, 'warnings': sorted(set(warnings))}


ORIG = open(ORIG_ROM, 'rb').read()


def init():
    orig = ORIG
    patched = bytearray(orig)
    font.patch(patched)
    msgs = json.load(open(os.path.join(ROOT, 'script', 'messages.json'), encoding='utf-8'))
    # The English font, plus anything the current English already uses that still encodes (e.g. ー, ☼).
    used = {c for m in msgs for c in ''.join(m['en'] if isinstance(m['en'], list) else [m['en']]) if c in EN_REV}
    typeable = sorted(set(font.SLOTS) | {' ', '…'} | used)
    return {'jp_font': glyphs(orig), 'en_font': glyphs(patched),
            'single_box': sorted(layout.no_page_ids(msgs)), 'typeable': ''.join(typeable),
            'label_widths': {c: menu_labels.advance(c) for c in menu_labels.FONT},
            'label_gap': menu_labels.GAP, 'label_max': menu_labels.MAX_PX,
            'x_width': layout.X_WIDTH, 'name_width': layout.NAME_LEN, 'num_width': layout.NUM_LEN}


def main():
    for line in sys.stdin:
        try:
            req = json.loads(line)
            if req['cmd'] == 'init':
                res = init()
            elif req['cmd'] == 'render':
                res = render(req['entry'], req.get('single_box', False))
            else:
                res = {'error': f"unknown command {req['cmd']}"}
        except Exception as e:  # report and keep serving
            res = {'error': f'{type(e).__name__}: {e}'}
        sys.stdout.write(json.dumps(res, ensure_ascii=False) + '\n')
        sys.stdout.flush()


if __name__ == '__main__':
    main()
