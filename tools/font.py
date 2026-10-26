"""English font: IBM EGA 8x8 glyphs written over the game's font in the patched ROM.

The game font is 8x8 2bpp tiles at ROM 0x0C89; text byte b draws glyph b-1.
Every byte value is already taken, so lowercase and the extra punctuation
reuse the hiragana slots (bytes 26-75), which translated text no longer needs.
Katakana (76-D3) is kept for the untranslated names and menus.

Font credit and licence: tools/fonts/README.md (CC BY-SA 4.0, VileR / int10h.org).
"""
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
FON = os.path.join(HERE, 'fonts', 'Bm437_IBM_EGA_8x8.FON')
FONT_BASE = 0x0C89
INK, PAPER = 1, 2  # 2bpp pixel values the game font uses

# Character -> text byte. Bytes 02-25 and the punctuation keep their meaning and just
# get the new glyph shape; 26 onwards replaces hiragana.
SLOTS = {}
SLOTS.update({c: 0x02 + i for i, c in enumerate('0123456789')})
SLOTS.update({c: 0x0C + i for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ')})
SLOTS.update({c: 0x26 + i for i, c in enumerate('abcdefghijklmnopqrstuvwxyz')})
SLOTS.update({c: 0x40 + i for i, c in enumerate('\'";()-*#@_<>[]~')})
SLOTS.update({'?': 0xC8, '!': 0xC9, '.': 0xCD, ',': 0xCE, '/': 0xD1, '+': 0xD2,
              '=': 0xD4, ':': 0xD5, '%': 0xD6, '&': 0xD7})
SLOTS.update({'☼': 0x4F, '☾': 0x50})  # day / night icons on the battle screen (2-cell field)
HIRAGANA = range(0x26, 0x76)

# Glyphs not under their own character in the font: CP437 code, or our own 8x8 rows
FON_CODE = {'☼': chr(0x0F)}
CUSTOM = {'☾': [0x1C, 0x38, 0x70, 0x70, 0x70, 0x38, 0x1C, 0x00]}  # crescent moon

# Glyphs redrawn without being added to SLOTS (English text never encodes to them).
# DA is the Japanese "…" (three dots at mid-height); English writes "...", but #500 is
# a lone 3-byte "…" too short to relocate, so draw it as baseline dots like ".".
REDRAW = {0xDA: [0x00, 0x00, 0x00, 0x00, 0x00, 0xDB, 0xDB, 0x00]}


def load_fon(path=FON):
    """Return {char: [8 row bytes, leftmost pixel in bit 7]} from an 8x8 Windows .FON."""
    d = open(path, 'rb').read()
    ne = struct.unpack_from('<I', d, 0x3C)[0]
    rt = ne + struct.unpack_from('<H', d, ne + 0x24)[0]
    shift = struct.unpack_from('<H', d, rt)[0]
    p = rt + 2
    while True:
        tid, cnt = struct.unpack_from('<HH', d, p)
        p += 8
        if tid == 0x8008:  # RT_FONT
            break
        assert tid != 0, 'no font resource'
        p += 12 * cnt
    r = d[struct.unpack_from('<H', d, p)[0] << shift:]
    assert struct.unpack_from('<HH', r, 86) == (8, 8), 'font is not 8x8'
    ver, first, last = struct.unpack_from('<H', r, 0)[0], r[95], r[96]
    tab, es = (118, 4) if ver == 0x200 else (148, 6)
    glyphs = {}
    for c in range(first, last + 1):
        bo = struct.unpack_from('<H' if es == 4 else '<I', r, tab + es * (c - first) + 2)[0]
        glyphs[chr(c)] = list(r[bo:bo + 8])
    return glyphs


def to_2bpp(rows):
    """8 rows of 1bpp -> 16 bytes of NGPC 2bpp (row = little-endian word, leftmost pixel in the top bits)."""
    out = bytearray()
    for bits in rows:
        word = 0
        for x in range(8):
            word |= (INK if bits & (0x80 >> x) else PAPER) << (14 - 2 * x)
        out += word.to_bytes(2, 'little')
    return bytes(out)


def patch(rom):
    """Write every glyph in SLOTS into rom (a bytearray). Returns the number of glyphs written."""
    glyphs = load_fon()
    for ch, byte in SLOTS.items():
        o = FONT_BASE + 16 * (byte - 1)
        rows = CUSTOM.get(ch) or glyphs[FON_CODE.get(ch, ch)]
        rom[o:o + 16] = to_2bpp(rows)
    for byte, rows in REDRAW.items():
        o = FONT_BASE + 16 * (byte - 1)
        rom[o:o + 16] = to_2bpp(rows)
    return len(SLOTS) + len(REDRAW)
