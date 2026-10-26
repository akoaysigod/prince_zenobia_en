"""Fixed-position screen text that native code draws from hard-coded addresses.

These are rewritten in place. Each entry records the original bytes, and the
patch refuses to write if the ROM doesn't match them. The English must fit in
the same space, keeping any layout bytes the code depends on:
  00 = new line (00 00 ends the string), 01 = skip one column.
"""
SKIP = '{01}'  # skip one column (cursor positions are counted in columns)

# Grid page 1 of the name-entry screen (was hiragana): 8 rows of 10 cells, in order.
# Blank cells (space) just add a space to the name.
NAME_PAGE1 = list('abcdefghij' 'klmnopqrst' "uvwxyz'-.," '!?&()":;/ ') + [' '] * 40

# (address, original bytes as hex, English text). English may be shorter; the rest is zero-filled.
REPLACEMENTS = [
    # Yes/No prompt, shared by most confirmations (name entry, save). The cursor sits at fixed
    # spots 4 columns apart (code at CPU 0x202FF4), so No stays at column 4 and "Yes" runs
    # right up to the No cursor. 5 tiles, like はい/いいえ.
    (0x0030F5, '3f2701012727290000', 'Yes' + SKIP + 'No'),
    # Two more Yes/No prompts (other menus): No at column 6, so "Yes" still leaves a free column
    (0x0E25D3, '3f2701010101272729', 'Yes' + SKIP * 3 + 'No'),
    (0x0E3B40, '3f2701010101272729', 'Yes' + SKIP * 3 + 'No'),
    # Name-entry tabs: hiragana | katakana | ABC | END, 4+4+3+3 columns
    (0x099592, '404c543a7b857b8a0c0d0e10190f', 'abc KanaABCEND'),
]

# Name confirmation (messages.json #1586): code at CPU 0x294FE4 builds the string in RAM 0x6000
# from 5 bytes at 0x995A2, the name, and a fixed-length tail it copies from 0x995A7. The
# English tail is longer (it also blanks the cells left of Yes/No), so it goes in free space
# and the code's tail pointer and copy length are patched. All addresses are ROM offsets.
RELOCATED_TAILS = {
    0x0995A2: {'ptr_operand': 0x094FFE, 'orig_ptr': 'a7952900',   # ld XIY, 0x2995A7
               'len_operand': 0x095003, 'orig_len': 0x16},         # ld C, 0x16
}

# Default player name: length byte, then 8 cells
DEFAULT_NAME = (0x0995BD, '05899d8285a3dcdcdc', 'Tristan')
NAME_CELLS = 8
NAME_GRID_PAGE1 = 0x099471  # rows: cells, 01 (gap), cells, 00 ... page ends with 00 00


def _encode(text, rev):
    out = bytearray()
    for part in text.split(SKIP):
        out += bytes(rev[c] for c in part) + b'\x01'
    return bytes(out[:-1])


def _check(rom, addr, orig_hex):
    orig = bytes.fromhex(orig_hex)
    if rom[addr:addr + len(orig)] != orig:
        raise SystemExit(f'fixed text at {addr:06X} does not match the original ROM; refusing to patch')
    return orig


def patch(rom, rev):
    """Apply all fixed-position text to rom (a bytearray). rev maps characters to text bytes."""
    count = 0
    for addr, orig_hex, text in REPLACEMENTS:
        orig = _check(rom, addr, orig_hex)
        new = _encode(text, rev)
        if len(new) > len(orig.rstrip(b'\x00')):
            raise SystemExit(f'fixed text at {addr:06X} is too long: {text!r}')
        rom[addr:addr + len(orig)] = new + bytes(len(orig) - len(new))
        count += 1

    addr, orig_hex, name = DEFAULT_NAME
    _check(rom, addr, orig_hex)
    assert len(name) <= NAME_CELLS
    rom[addr] = len(name)
    rom[addr + 1:addr + 1 + NAME_CELLS] = _encode(name, rev) + bytes([rev[' ']]) * (NAME_CELLS - len(name))
    count += 1

    # Name-entry grid, page 1: replace each cell, keeping the 00/01 layout bytes
    cells = iter(NAME_PAGE1)
    o = NAME_GRID_PAGE1
    while rom[o:o + 2] != b'\x00\x00':
        if rom[o] not in (0x00, 0x01):
            rom[o] = rev[next(cells)]
        o += 1
    assert next(cells, None) is None, 'name grid page 1 has fewer cells than expected'
    return count + 1
