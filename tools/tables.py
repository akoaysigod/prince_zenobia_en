"""Offset-table text: menu help lines, class/unit/item names, tarot cards, item descriptions.

Code finds string i with `ld XIY, <table>` + `call 0x201B77` (index in A):
    start(i)  = table + 2*i + entry[i]
    length(i) = entry[i+1] - entry[i] + 2      (so strings are contiguous)
The last entry only marks the end. Help-style strings end their lines with 00 and
the string with 00 00; name lists are packed with no terminators.

A translated table is rebuilt in free space and every `ld XIY, <table>` or
`lda XIY, (<table>)` that loads it is repointed, so English strings can be any length.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import script_vm as vm  # noqa: E402

LOOKUP_CALL = bytes.fromhex('1d771b20')  # call 0x201B77
LD_XIY = 0x45                            # ld XIY, imm32
LDA, LDA_XIY = 0xF2, 0x35                # lda XIY, (addr24)

# Tables to dump: ROM offset -> (name, kind). kind 'help' = lines with 00, ends 00 00;
# 'name' = packed, no terminator (shown in a fixed-width field); 'record' = data header + name;
# 'desc' = lines separated by 00 with no terminator, 01 used as the space.
# Dumped in this order, so add new tables at the end to keep existing entry ids stable.
TABLES = {
    0x0C3C8C: ('menu_help_main', 'help'),
    0x0C3D86: ('menu_help_unit', 'help'),
    0x0C3EA5: ('menu_help_tactics', 'help'),
    0x0C3F07: ('menu_help_formation', 'help'),
    0x0C402B: ('menu_help_items', 'help'),
    0x01BCEB: ('tarot_names', 'name'),
    0x01BD84: ('tarot_help', 'help'),
    0x073334: ('town_types', 'name'),
    0x00E49D: ('class_names', 'name'),
    0x0166B8: ('item_names', 'record'),
    0x0C4124: ('item_help', 'desc'),
}

# Tables added after the system strings were dumped; their entries come last.
TABLES_LATE = {
    0x00FCEA: ('unit_names', 'name'),
}

# Tables whose last offset is not an end marker but the start of one more 00 00-terminated
# string (the game finds a string's end by its terminator, so the table never marks it).
LAST_IS_STRING = {0x0C3D86}  # menu_help_unit: entry 10 is the "class change" help


def split_record(s):
    """Item record -> (data header, name). The header is 4 bytes; equipment (4th byte not 0)
    adds stat bytes (codes >= 0xDD and small values) before the name."""
    h = 4
    if s[3] != 0:
        while h < len(s) and (s[h] < 0x26 or s[h] >= 0xDD):
            h += 1
    return s[:h], s[h:]


def read_table(rom, t):
    """Return the list of raw strings in the table at ROM offset t."""
    first = rom[t] | rom[t + 1] << 8
    count = first // 2 - 1  # last entry is the end marker
    entry = [rom[t + 2 * i] | rom[t + 2 * i + 1] << 8 for i in range(count + 1)]
    out = [bytes(rom[t + 2 * i + entry[i]:t + 2 * (i + 1) + entry[i + 1]]) for i in range(count)]
    if t in LAST_IS_STRING:
        p = t + 2 * count + entry[count]
        out.append(bytes(rom[p:rom.index(b'\x00\x00', p) + 2]))
    return out


def base_count(rom, t):
    """Number of strings the table's own end marker accounts for (without LAST_IS_STRING)."""
    return (rom[t] | rom[t + 1] << 8) // 2 - 1


def build_table(strings):
    """Inverse of read_table: entries (including the end marker) followed by the strings."""
    n = len(strings) + 1
    entry, pos = [], 2 * n  # pos = offset of the next string from the table start
    for i, s in enumerate(strings):
        entry.append(pos - 2 * i)
        pos += len(s)
    entry.append(pos - 2 * len(strings))
    if max(entry) > 0xFFFF:
        raise ValueError('table too large')
    return b''.join(e.to_bytes(2, 'little') for e in entry) + b''.join(strings)


def references(rom, t):
    """Instructions that load table t, as (operand offset, operand size):
    `ld XIY, <table>` (45 + 32-bit) and `lda XIY, (<table>)` (F2 + 24-bit + 35)."""
    refs = []
    pat = bytes([LD_XIY]) + (vm.ROM_BASE + t).to_bytes(4, 'little')
    i = rom.find(pat)
    while i != -1:
        refs.append((i + 1, 4))
        i = rom.find(pat, i + 1)
    pat = bytes([LDA]) + (vm.ROM_BASE + t).to_bytes(3, 'little') + bytes([LDA_XIY])
    i = rom.find(pat)
    while i != -1:
        refs.append((i + 1, 3))
        i = rom.find(pat, i + 1)
    return refs
