"""Text that native code draws or assembles itself (not through the script's message op).

Three ways of writing English, chosen per entry by `mode`:

- 'reloc': the string moves to free space and every instruction that loads its
  address is repointed. Some strings are copied into a RAM buffer in pieces
  around a name, item or number ({X} in the English): each piece ("part") is
  copied with `ld BC/C, <length>` + `ldir`, so those length operands are patched too.
- 'free': rewritten in place; lines (00-separated) can be laid out freely, but the
  whole string must fit in the original bytes. Used for strings drawn at a fixed
  spot by the tile-allocating printer (0x200BAC), so `tiles` also caps how many
  drawn characters it may have.
- 'slots': fixed-width fields rewritten in place, each padded to its original length
  (attack names, terrain, menu labels, town names...).

All addresses are ROM offsets. Every pointer and length operand is checked against
the original ROM before it is patched.
"""

# Length operand forms: (instruction bytes) -> how the value is stored
#   'short' = d9 a8+n  (ld BC, n; n <= 7)
#   'imm8'  = 23 nn    (ld C, nn)
#   'imm16' = 31 lo hi (ld BC, nnnn)
SHORT, IMM8, IMM16 = 'short', 'imm8', 'imm16'

DYNAMIC = 0x01  # space/pad that skips a column (no tile used)
BLANK = 0xDC    # the blank glyph

# ---------------------------------------------------------------------------
# Relocated strings. refs = addresses of the instructions that load the string
# (ld r32 / op 8A / op 9C with a 32-bit operand at +1, or lda with a 24-bit one).
# parts: list of {'refs': [...] (omit to continue right after the previous part),
#                 'len': [(form, instruction address), ...] or 'fixed': n, 'term': 0|2}
#   term = how many terminator bytes (00 00) the original copy length included.
# layout: order of parts and inserted values ('X'), e.g. ['X', 0] = name, then part 0.
# x: what {X} is, and its width when checking lines.
# ---------------------------------------------------------------------------
RELOC = [
    # Unit/formation errors (printed in the message window, 18 columns)
    dict(offset=0x002E67, refs=[0x005D1E, 0x012E5A]),
    dict(offset=0x002E82, refs=[0x005D0C]),
    dict(offset=0x003CE9, refs=[0x0033F5]),
    dict(offset=0x0055CD, refs=[0x00554B]),
    dict(offset=0x0055E8, refs=[0x005560]),
    dict(offset=0x00588E, refs=[0x005872]),
    dict(offset=0x006011, refs=[0x005F8E]),
    dict(offset=0x006029, refs=[0x005F63]),
    dict(offset=0x006044, refs=[0x005F5C]),
    dict(offset=0x007773, refs=[0x007418]),
    dict(offset=0x007798, refs=[0x00752A]),
    dict(offset=0x0082A0, refs=[0x007A50]),
    dict(offset=0x008DC2, refs=[0x008D92]),
    dict(offset=0x00A3C8, refs=[0x003C05]),
    dict(offset=0x012CF8, refs=[0x012C25]),
    dict(offset=0x015F11, refs=[0x015CAE]),
    dict(offset=0x015F2E, refs=[0x0159A1, 0x016631]),
    dict(offset=0x015F3C, refs=[0x0159A8]),
    dict(offset=0x015F4E, refs=[0x0159AF, 0x0159B6]),
    dict(offset=0x015F5E, refs=[0x0159D8]),
    dict(offset=0x016122, refs=[0x0160BB]),
    # Formation limits: also printed by script ops 9C at 0x12858 / 0x12843 (same text there)
    dict(offset=0x00CDD6, refs=[0x005860]),
    dict(offset=0x00CE75, refs=[0x005854]),
    dict(offset=0x016228, refs=[0x01621C]),
    dict(offset=0x01626A, refs=[0x01623B]),
    dict(offset=0x016356, refs=[0x016343]),
    dict(offset=0x016487, refs=[0x01647B]),
    dict(offset=0x01664D, refs=[0x016641]),
    dict(offset=0x01666F, refs=[0x016663]),
    # Copied whole into the RAM buffer (length operand patched)
    dict(offset=0x006F29, layout=[0], parts=[dict(refs=[0x006EA0], len=[(IMM16, 0x006EA5)], term=2)]),
    dict(offset=0x006F51, layout=[0], parts=[dict(refs=[0x006ED1], len=[(IMM8, 0x006ED6)], term=2)]),
    # Assembled around a value
    dict(offset=0x006F71, x='number', layout=[0, 'X', 1],      # dispatch cost
         parts=[dict(refs=[0x006EDF], len=[(SHORT, 0x006EE4)], term=0),
                dict(len=[(IMM16, 0x006EF2)], term=2)]),
    dict(offset=0x005B1D, x='number', layout=[0, 'X', 1],      # revive cost
         parts=[dict(refs=[0x005A5A], len=[(SHORT, 0x005A5F)], term=0),
                dict(len=[(IMM16, 0x005A82)], term=2)]),
    dict(offset=0x002ED4, x='class', layout=['X', 0],          # class change
         parts=[dict(refs=[0x006259, 0x01313A], len=[(IMM8, 0x00625E), (IMM8, 0x01313F)], term=2)]),
    dict(offset=0x008848, x='name', layout=['X', 0],           # return to base?
         parts=[dict(refs=[0x008473], len=[(IMM16, 0x008478)], term=2)]),
    dict(offset=0x008864, x='name', layout=['X', 0],           # finished moving
         parts=[dict(refs=[0x00831B], len=[(IMM16, 0x008320)], term=0)]),
    dict(offset=0x00887A, x='town', layout=['X', 0],           # liberated
         parts=[dict(refs=[0x008449], len=[(IMM16, 0x00844E)], term=0)]),
    dict(offset=0x008903, x='item', layout=[0, 'X', 1],        # found item
         parts=[dict(refs=[0x0086F8], len=[(SHORT, 0x0086FD)], term=0),
                dict(refs=[0x008705], len=[(IMM16, 0x00870A)], term=2)]),
    dict(offset=0x008E2F, x='town', layout=['X', 0],           # discovered (church, ...)
         parts=[dict(refs=[0x008D30], len=[(IMM16, 0x008D35)], term=2)]),
    dict(offset=0x008EE3, x='item', layout=[0, 'X', 1],        # buried treasure
         parts=[dict(refs=[0x008E96], len=[(IMM16, 0x008E9B)], term=0),
                dict(refs=[0x008EA4], len=[(SHORT, 0x008EA9)], term=2)]),
    dict(offset=0x00966C, x='name', layout=['X', 0],           # met an enemy unit
         parts=[dict(refs=[0x0091CB], len=[(IMM16, 0x0091D0)], term=2)]),
    dict(offset=0x00968A, x='name', layout=['X', 0],           # met a neutral
         parts=[dict(refs=[0x0090C2], len=[(IMM16, 0x0090C7)], term=2)]),
    dict(offset=0x0096AC, x='item', layout=[0, 'X', 1],        # spoils of battle
         parts=[dict(refs=[0x00938D], len=[(IMM16, 0x009392)], term=0),
                dict(refs=[0x0093B8], len=[(IMM16, 0x0093BD)], term=2)]),
    dict(offset=0x00A3CD, x='town', layout=['X', 0],           # town taken by the enemy
         parts=[dict(refs=[0x00A3A7], len=[(IMM16, 0x00A3AC)], term=2)]),
    # Item obtained / given up: one routine copies 1 byte (ldi), the item, then 0x0D bytes.
    # Both share that length operand, so both tails must be the same length.
    dict(offset=0x015EF5, x='item', layout=[0, 'X', 1],
         parts=[dict(refs=[0x015D7F], fixed=1), dict(len=[(IMM16, 0x015DB3)], term=2)]),
    dict(offset=0x015F03, x='item', layout=[0, 'X', 1],
         parts=[dict(refs=[0x015CD0], fixed=1), dict(len=[(IMM16, 0x015DB3)], term=2)]),
    # Tarot card drawn (after freeing a town; routine 0x208C85): 1 byte (ldi), the card name, then 0x18 bytes
    dict(offset=0x008CD1, x='tarot', layout=[0, 'X', 1],
         parts=[dict(refs=[0x008C97], fixed=1), dict(len=[(IMM8, 0x008CB1)], term=2)]),
]

# ---------------------------------------------------------------------------
# In place, free layout (fixed screen spot, tile-allocating printer)
# ---------------------------------------------------------------------------
FREE = [
    dict(offset=0x08C7C3, tiles=True),   # "for Neo Geo Pocket Color only" (black-and-white NGP)
    dict(offset=0x09BCF1, tiles=True),   # save failed
    dict(offset=0x09BCFF, tiles=True),   # saving
    dict(offset=0x09BD0D, tiles=True),   # save finished
    dict(offset=0x0C79C7, tiles=True),   # persuasion succeeded
    dict(offset=0x0C999F, tiles=True),   # processing command
    dict(offset=0x01270C),               # unit list header (fixed font)
]


def _slots_from_strings(start, end, rom):
    """Each 00-separated line of the 00 00-terminated string at start, as (offset, length)."""
    out, o = [], start
    while o < end:
        e = rom.index(0, o)
        out.append((o, e - o))
        o = e + 1
    return out


def slot_entries(rom):
    """Fixed-width fields, as dicts with 'offset' and 'slots' [(offset, length), ...]."""
    out = []

    def strings(start, group, pad, space=None, count=1):
        """count consecutive 00 00-terminated strings starting at start, each line its own slot."""
        o = start
        for _ in range(count):
            end = rom.index(b'\x00\x00', o)
            out.append(dict(offset=o, slots=_slots_from_strings(o, end, rom), pad=pad,
                            space=space or pad, group=group))
            o = end + 2

    # Status screen
    out.append(dict(offset=0x0133A3, slots=[(0x0133A3, 5)], pad=BLANK, group='status'))  # "Unit." + number
    out.append(dict(offset=0x00D603, slots=[(0x00D603, 7), (0x00D60A, 3), (0x00D60D, 3)],
                    pad=BLANK, group='status'))                                          # can/can't lead
    out.append(dict(offset=0x00EB5D, slots=[(0x00EB5D, 3)], pad=BLANK, group='move_type'))  # "type" suffix
    for i in range(10):                                                                   # movement types
        o = 0x00EB61 + 4 * i
        out.append(dict(offset=o, slots=[(o, 4)], pad=BLANK, group='move_type'))
    # Settlement (income and expenses) screen: keep every line where it is
    out.append(dict(offset=0x00825E, slots=_slots_from_strings(0x00825E, 0x0082A0 - 2, rom),
                    pad=DYNAMIC, group='settlement'))
    # Battle tactics: four separate strings, then the same four as one 4-line string
    strings(0x00F0E7, 'tactics', DYNAMIC, count=4)
    strings(0x00F10F, 'tactics', DYNAMIC)
    # Tarot card names and attack/spell names: 8 cells + 00 00 every 10 bytes
    for o in range(0x00F134, 0x00F6C0, 10):
        if any(b != 0x01 for b in rom[o:o + 8]):
            out.append(dict(offset=o, slots=[(o, 8)], pad=DYNAMIC, group='attacks'))
    # Battle field names (7 cells + 00 00 every 9 bytes)
    for i in range(20):
        o = 0x0C82A9 + 9 * i
        if any(b != 0x01 for b in rom[o:o + 7]):
            out.append(dict(offset=o, slots=[(o, 7)], pad=DYNAMIC, group='battlefield'))
    for o in (0x0C835D, 0x0C8361):  # day / night
        out.append(dict(offset=o, slots=[(o, 2)], pad=DYNAMIC, group='battlefield'))
    # Title menu, options and save screens: labels and descriptions padded with blanks
    for o in (0x09BF9A, 0x09BFB9, 0x09BFD8, 0x09BFF7, 0x09C016,
              0x09C315, 0x09C321, 0x09C340, 0x09C34C, 0x09C36B, 0x09C377, 0x09C396, 0x09C3A2,
              0x09C403, 0x09C40F, 0x09C42E, 0x09C43A, 0x09C47D, 0x09C489, 0x09C495,
              0x09C4CE, 0x09C4DA, 0x09C4E6, 0x09C4F2, 0x09C562):
        strings(o, 'menu', BLANK)
    for o in range(0x09C56E, 0x09C652, 12):  # map areas (save slots)
        strings(o, 'menu', BLANK)
    # The church found when a town index is past the map's list (copied up to 11 cells, stops at 01)
    out.append(dict(offset=0x008E22, slots=[(0x008E22, 11)], pad=DYNAMIC, group='towns'))
    # Town names: 16-byte records, name in 8 cells at +7
    for o in TOWN_RECORDS(rom):
        out.append(dict(offset=o + 7, slots=[(o + 7, 8)], pad=DYNAMIC, group='towns'))
    return out


def TOWN_RECORDS(rom):
    """Town records in the stage data (0x26000-0x2D000): name = kana padded with 01, then 00.

    The last record of a map's list is followed by other data instead of 00, so a
    record right after a run is accepted without that check."""
    def is_record(a, strict=True):
        name = rom[a + 7:a + 15]
        if strict and rom[a + 15] != 0:
            return False
        k = 0
        while k < 8 and 0x26 <= name[k] <= 0xDB:
            k += 1
        return k >= 2 and all(b == 0x01 for b in name[k:])
    hits = [a for a in range(0x26000, 0x2D000) if is_record(a)]
    found = set(hits)
    keep = {a for a in hits if a - 16 in found or a + 16 in found} | set(EXTRA_TOWNS)
    for a in sorted(keep):
        if a + 16 not in keep and is_record(a + 16, strict=False):
            keep.add(a + 16)
    return sorted(keep)


EXTRA_TOWNS = [0x02664A]  # a stage with a single town


# Stat change message, built by code at 0x208620 (and 0x2087C9 for the Chaos Frame):
#   [prefix][stat name: "STR", "HP/MAX"...][amount][up | down]
#   [chaos ][amount][up | down]
# The amount piece must directly follow the prefix, and up/down must directly follow the
# amount (the code reads them in a row). The code writes the digit 5 bytes before the end
# of the amount piece ({X}), and skips from "up" to "down" by the same length it copies.
STAT_MESSAGE = {
    'prefix': (0x008895, 7), 'amount': (0x00889C, 15), 'up': (0x0088AB, 6), 'down': (0x0088B1, 6),
    'chaos': (0x0088B7, 7),
}
STAT_PATCH = {  # name: (instruction address, original bytes)
    'prefix_ptr': (0x008624, '4395882000'), 'prefix_len': (0x008629, 'f00731'),
    'chaos_ptr': (0x0087CD, '43b7882000'), 'chaos_len': (0x0087D2, 'f00731'),
    'amount_ptr': (0x0087D5, '469c882000'), 'amount_len': (0x00864E, '230f'),
    'digit_at': (0x008661, 'bafb41'), 'updown_len': (0x008652, '2306'),
}
STAT_DIGIT = 0x19  # placeholder byte in the original amount piece


def specs(rom):
    """Every native entry's spec, keyed by ROM offset."""
    out = {s['offset']: dict(s, mode='reloc') for s in RELOC}
    out.update({s['offset']: dict(s, mode='free') for s in FREE})
    out.update({s['offset']: dict(s, mode='slots') for s in slot_entries(rom)})
    out.update({o: dict(offset=o, mode='stat', role=r, length=n) for r, (o, n) in STAT_MESSAGE.items()})
    return out


def _check(cond, msg):
    if not cond:
        raise SystemExit(msg)


def pointer_target(rom, at):
    """(operand offset, size, ROM offset it points to) for the instruction at `at`."""
    if rom[at] == 0xF2:  # lda r, (addr24)
        return at + 1, 3, int.from_bytes(rom[at + 1:at + 4], 'little') - 0x200000
    _check(0x40 <= rom[at] <= 0x47 or rom[at] in (0x8A, 0x9C), f'{at:06X}: not a pointer load')
    return at + 1, 4, int.from_bytes(rom[at + 1:at + 5], 'little') - 0x200000


def read_len(rom, form, at):
    if form == SHORT:
        _check(rom[at] == 0xD9 and rom[at + 1] & 0xF8 == 0xA8, f'{at:06X}: not ld BC, n')
        return rom[at + 1] - 0xA8
    if form == IMM8:
        _check(rom[at] == 0x23, f'{at:06X}: not ld C, nn')
        return rom[at + 1]
    _check(rom[at] == 0x31, f'{at:06X}: not ld BC, nnnn')
    return rom[at + 1] | rom[at + 2] << 8


def write_len(rom, form, at, n):
    limit = {SHORT: 7, IMM8: 0xFF, IMM16: 0xFFFF}[form]
    _check(0 <= n <= limit, f'{at:06X}: length {n} does not fit (max {limit})')
    if form == SHORT:
        rom[at + 1] = 0xA8 + n
    elif form == IMM8:
        rom[at + 1] = n
    else:
        rom[at + 1:at + 3] = n.to_bytes(2, 'little')


def split_parts(en, order):
    """Map the English (with {X} placeholders) onto the parts in `order` -> {part index: text}."""
    segs = en.split('{X}')
    _check(len(segs) - 1 == order.count('X'), f'needs exactly {order.count("X")} {{X}}: {en!r}')
    texts, s = {}, 0
    for t in order:
        if t == 'X':
            s += 1
        else:
            texts[t] = segs[s]
            segs[s] = None
    _check(all(not x for x in segs if x is not None), f'text where the game puts {{X}}: {en!r}')
    return texts
