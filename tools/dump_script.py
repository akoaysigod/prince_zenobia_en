"""Scan the ROM for every message and write script/rom_scan.json.

Only Translation Studio (app/) writes script/messages.json; it merges a scan in
with File > Merge ROM Scan, keeping all translations, notes and review marks.

Usage: python3 tools/dump_script.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import layout  # noqa: E402
import menu_labels  # noqa: E402
import title_cards  # noqa: E402
import native_text  # noqa: E402
import tables  # noqa: E402
import script_vm as vm  # noqa: E402

ROOT = os.path.join(HERE, '..')
OUT = os.path.join(ROOT, 'script')

# Bytes inside message text that are not glyphs
TAGS = {0x00: '\n', 0x01: '{01}', 0xDD: '{NAME}', 0xDE: '{NUM}'}

# Tarot intro: routines called from native code, and the 22-entry question table
TAROT_ENTRIES = [0x995C8, 0x99659, 0x9966C, 0x99698]
TAROT_QUESTIONS = 0x996D8
CHOICE_LETTER = 0x0C  # glyph 'A'; answers are lettered A, B, C

# System text outside the stage blocks, listed by hand (a blind scan for 9C also hits code)
SYSTEM_MESSAGES = [0x95357]  # new game: "choose a save area"
SYSTEM_STRINGS = [0x94D87]   # 9C ops; new game: "OK to overwrite?"
# More 9C ops, dumped after the tables to keep ids stable: system confirmations and errors
SYSTEM_STRINGS_2 = [0x4829, 0x485F, 0x486D, 0x5AC9, 0x5C18, 0x5D3E, 0x5E60, 0x5FAA, 0x620F, 0x8548,
                   0x8814, 0x8931, 0x8959, 0x89C7, 0x12843, 0x12858, 0x12866, 0x128AB, 0x128E0, 0x1297B,
                   0x129C4, 0x12AB3, 0x12BD5, 0x12D68, 0x12E2E, 0x12E77, 0x12F0E, 0x12F71, 0x13111, 0x1418D]
# 32-bit pointer cells to battle-menu help (tarot, commands, tactics, battle items): narrow window
POINTER_STRINGS = list(range(0xF6E4, 0xF740, 4)) + list(range(0xF941, 0xF95D, 4)) + \
    list(range(0xF9F2, 0xFA02, 4)) + list(range(0xFA5E, 0xFAC6, 4))
# Strings drawn by native code from fixed addresses, so they are rewritten in place.
# (start, end of available bytes, name position): the code prints the name at that
# offset and then prints the rest of the string again from start+name position.
FIXED_STRINGS = [(0x995A2, 0x995BD, 5)]  # name entry: "なまえは「NAME」で / よろしいですか？"


def load_table():
    t = {}
    with open(os.path.join(ROOT, 'ogrebattle.tbl'), encoding='utf-8') as f:
        for line in f:
            k, v = line.rstrip('\n').split('=', 1)
            t[int(k, 16)] = v
    return t


def decode_text(body, table):
    out = []
    for b in body:
        if b in TAGS:
            out.append(TAGS[b])
        elif b in table:
            out.append(table[b])
        else:
            out.append('{%02X}' % b)
    return ''.join(out)


def load_existing_en():
    """English already written into messages.json, keyed by offset, so re-dumping keeps it."""
    path = os.path.join(OUT, 'messages.json')
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as f:
        return {m['offset']: m['en'] for m in json.load(f) if m['en']}


def read_choices(rom, p):
    """Answer list at ROM offset p: `01 <letter> text 00` per answer, ended by an extra 00."""
    items = []
    while rom[p] != 0:
        assert rom[p] == 0x01 and rom[p + 1] == CHOICE_LETTER + len(items), f'bad answer list at {p:06X}'
        end = rom.index(0, p)
        items.append(rom[p + 2:end])
        p = end + 1
    return items


def read_string(rom, p):
    """Text printed by op 9C: lines separated by 00, ended by 00 00."""
    return rom[p:rom.index(b'\x00\x00', p)].split(b'\x00')


def tarot_scripts(rom):
    """Yield (offset, op, raw) for every op in the tarot intro's script routines.

    The routines sit outside the stage blocks, so they are walked linearly from
    their entry points until a goto/return.
    """
    questions = [vm.p24(rom, o) - vm.ROM_BASE for o in range(TAROT_QUESTIONS, TAROT_QUESTIONS + 66, 3)]
    seen = set()
    for o in TAROT_ENTRIES + questions:
        while o not in seen:
            seen.add(o)
            raw, _, _ = vm.decode_one(rom, o)
            yield o, raw[0], raw
            if raw[0] in vm.NO_FALLTHROUGH:
                break
            o += len(raw)


def native_parts(rom, spec):
    """Original bytes of each part of a relocated native string (without terminators)."""
    out, o = [], spec['offset']
    for part in spec.get('parts') or [dict(refs=[spec['offset']], term=2, whole=True)]:
        if part.get('refs') and not part.get('whole'):
            o = native_text_target(rom, part['refs'][0])
        if part.get('whole'):
            n = rom.index(b'\x00\x00', o) - o
        elif 'fixed' in part:
            n = part['fixed']
        else:
            form, at = part['len'][0]
            n = native_text_len(rom, form, at) - part['term']
        out.append(bytes(rom[o:o + n]))
        o += n
    return out


def native_text_target(rom, at):
    """ROM offset that the pointer operand of the instruction at `at` refers to."""
    if rom[at] == 0xF2:  # lda r, (addr24)
        return int.from_bytes(rom[at + 1:at + 4], 'little') - vm.ROM_BASE
    return int.from_bytes(rom[at + 1:at + 5], 'little') - vm.ROM_BASE


def native_text_len(rom, form, at):
    if form == native_text.SHORT:
        return rom[at + 1] - 0xA8
    if form == native_text.IMM8:
        return rom[at + 1]
    return rom[at + 1] | rom[at + 2] << 8


def dump_native(rom, table, existing, msgs):
    """Native-drawn text (tools/native_text.py), appended after everything else."""
    def add(spec, mode, jp, extra):
        key = f"{spec['offset']:06X}"
        msgs.append({'id': len(msgs), 'block': spec.get('group', 'native'), 'kind': 'native', 'mode': mode,
                     'offset': key, 'length': extra.pop('length'), 'terminator': '', **extra,
                     'jp': jp, 'en': existing.get(key, '')})

    for spec in native_text.RELOC:
        parts = native_parts(rom, spec)
        order = spec.get('layout', [0])
        jp = ''.join('{X}' if t == 'X' else '\n'.join(decode_text(l, table) for l in parts[t].split(b'\x00'))
                     for t in order)
        extra = {'length': sum(len(p) for p in parts), 'width': layout.WIDE_WIDTH,
                 'max_lines': layout.BOX_LINES}
        if 'x' in spec:
            extra['x'] = spec['x']
        add(spec, 'reloc', jp, extra)
    for spec in native_text.FREE:
        o = spec['offset']
        body = rom[o:rom.index(b'\x00\x00', o)]
        tiles = sum(1 for b in body if b > 1)
        extra = {'length': len(body) + 2}
        if spec.get('tiles'):
            extra['max_tiles'] = tiles
        add(spec, 'free', '\n'.join(decode_text(l, table) for l in body.split(b'\x00')), extra)
    for role, (o, n) in native_text.STAT_MESSAGE.items():
        raw = bytes(rom[o:o + n])
        if role in ('up', 'down'):
            raw = raw.rstrip(b'\x00')
        jp = '\n'.join(decode_text(l, table) for l in raw.split(b'\x00'))
        if role == 'amount':  # the digit placeholder
            jp = jp.replace(table[native_text.STAT_DIGIT], '{X}')
        add(dict(offset=o, group='stat_message'), 'stat', jp, {'length': n, 'role': role})
    for spec in native_text.slot_entries(rom):
        jp = '\n'.join(decode_text(rom[o:o + n], table) for o, n in spec['slots'])
        add(spec, 'slots', jp, {'length': sum(n for _, n in spec['slots']),
                                'slot_widths': [n for _, n in spec['slots']]})


def main():
    rom = vm.load_rom()
    table = load_table()
    existing = load_existing_en()
    entries = vm.stage_entries(rom)
    seen, _ = vm.trace(rom, entries)
    bounds = list(zip(entries, entries[1:] + [0x73400]))
    msgs = []

    def add(block, kind, o, length, term, jp):
        msgs.append({
            'id': len(msgs),
            'block': block,
            'kind': kind,
            'offset': f'{o:06X}',
            'length': length,
            'terminator': term,
            'jp': jp,
            'en': existing.get(f'{o:06X}', ''),
        })

    for blk, (a, b) in enumerate(bounds):
        for kind, o, op, raw in vm.parse_block(rom, a, b, seen):
            if kind == 'ins' and op == 0x32:
                add(blk, 'message', o, len(raw), f'{raw[-1]:02X}', decode_text(raw[1:-1], table))

    # Tarot intro (new game): messages, plus answer lists referenced by op 9C
    for o, op, raw in sorted(tarot_scripts(rom)):
        if op == 0x32:
            add('tarot', 'message', o, len(raw), f'{raw[-1]:02X}', decode_text(raw[1:-1], table))
        elif op == 0x9C:
            items = read_choices(rom, int.from_bytes(raw[1:5], 'little') - vm.ROM_BASE)
            add('tarot', 'choices', o, len(raw), '', '\n'.join(decode_text(i, table) for i in items))

    for o in SYSTEM_MESSAGES:
        raw, _, _ = vm.decode_one(rom, o)
        assert raw[0] == 0x32, f'no message at {o:06X}'
        add('system', 'message', o, len(raw), f'{raw[-1]:02X}', decode_text(raw[1:-1], table))
    for o in SYSTEM_STRINGS:
        assert rom[o] == 0x9C, f'no 9C op at {o:06X}'
        lines = read_string(rom, int.from_bytes(rom[o + 1:o + 5], 'little') - vm.ROM_BASE)
        add('system', 'string', o, 6, '', '\n'.join(decode_text(i, table) for i in lines))
    for start, end, name_at in FIXED_STRINGS:
        lines = '\n'.join(decode_text(i, table) for i in read_string(rom, start))
        add('system', 'fixed', start, end - start, '', lines[:name_at] + '{NAME}' + lines[name_at:])
        msgs[-1]['name_at'] = name_at
    # Offset tables (menu help, ...): one entry per string, keyed by table offset + index
    def dump_table(t, name, kind, extra_only=False):
        """extra_only: just the strings past the table's end marker (dumped last to keep ids stable)."""
        strings = tables.read_table(rom, t)
        if kind == 'help':
            assert all(s.endswith(b'\x00\x00') or not s for s in strings), f'unexpected string in table {t:06X}'
            limit = {'max_lines': max(s[:-2].count(b'\x00') + 1 for s in strings)}
        elif kind == 'desc':
            limit = {'max_lines': max(s.count(b'\x00') + 1 for s in strings), 'packed': True}
        elif kind == 'record':
            limit = {'max_len': max(len(tables.split_record(s)[1]) for s in strings if s)}
        else:
            limit = {'max_len': max(len(s) for s in strings)}
            if name == 'town_types':  # only ever printed right before a town name, which needs a space
                limit['max_len'] += 1
        for i, s in enumerate(strings):
            if not s or (i >= tables.base_count(rom, t)) != extra_only:
                continue  # empty slot (index 0 is often unused), or not in this pass
            key = f'{t:06X}:{i}'
            extra = {}
            if kind == 'help':
                body = s[:-2]
            elif kind == 'record':
                header, body = tables.split_record(s)
                extra = {'header': header.hex()}
            else:
                body = s
            msgs.append({
                'id': len(msgs), 'block': name, 'kind': 'table' if kind in ('help', 'desc') else 'name',
                'offset': key, 'length': len(s), 'terminator': '', **limit, **extra,
                'jp': '\n'.join(decode_text(l, table) for l in body.split(b'\x00')),
                'en': existing.get(key, ''),
            })

    for t, (name, kind) in tables.TABLES.items():
        dump_table(t, name, kind)
    for o in SYSTEM_STRINGS_2:
        assert rom[o] == 0x9C, f'no 9C op at {o:06X}'
        lines = read_string(rom, int.from_bytes(rom[o + 1:o + 5], 'little') - vm.ROM_BASE)
        add('system', 'string', o, 6, '', '\n'.join(decode_text(i, table) for i in lines))
    for o in POINTER_STRINGS:
        p = int.from_bytes(rom[o:o + 4], 'little') - vm.ROM_BASE
        lines = [decode_text(i, table) for i in read_string(rom, p)]
        if not any(c not in ' {}01' for c in ''.join(lines)):
            continue  # blank slot
        add('battle', 'pstring', o, 4, '', '\n'.join(lines))
        msgs[-1]['width'] = max(10, max(len(l) for l in lines))
        msgs[-1]['max_lines'] = 3

    for t, (name, kind) in tables.TABLES_LATE.items():  # added later; dumped last to keep ids stable
        dump_table(t, name, kind)
    for t in sorted(tables.LAST_IS_STRING):
        dump_table(t, *tables.TABLES[t], extra_only=True)
    dump_native(rom, table, existing, msgs)
    for i, jp in enumerate(menu_labels.JP):  # menu captions: pictures, so the Japanese is read off the graphics
        key = f'{menu_labels.offset(i):06X}'
        msgs.append({'id': len(msgs), 'block': 'menu_labels', 'kind': 'label', 'offset': key,
                     'length': menu_labels.SIZE, 'terminator': '', 'max_px': menu_labels.MAX_PX,
                     'jp': jp, 'en': existing.get(key, '')})
    for tag in menu_labels.TAGS:  # framed tags in the interface tile sheet
        key = f"{tag['offset']:06X}"
        msgs.append({'id': len(msgs), 'block': 'menu_labels', 'kind': 'label', 'offset': key,
                     'length': 16 * tag['tiles'], 'terminator': '', 'max_px': menu_labels.max_px(tag),
                     'jp': tag['jp'], 'en': existing.get(key, '')})
    for s, i, o in title_cards.records(rom):  # chapter and area title cards (pictures)
        key = f'{o:06X}'
        msgs.append({'id': len(msgs), 'block': 'title_cards', 'kind': 'card', 'offset': key,
                     'length': title_cards.RECORD, 'terminator': '', 'max_letters': title_cards.COLS,
                     'jp': title_cards.SETS[s][2][i], 'en': existing.get(key, '')})
    os.makedirs(OUT, exist_ok=True)
    # messages.json belongs to Translation Studio (app/). A re-scan goes to rom_scan.json,
    # which the app merges in (File > Merge ROM Scan) without touching translations.
    with open(os.path.join(OUT, 'rom_scan.json'), 'w', encoding='utf-8') as f:
        json.dump(msgs, f, ensure_ascii=False, indent=1)
    print(f'{len(msgs)} messages written to {OUT}/rom_scan.json; merge it in Translation Studio')


if __name__ == '__main__':
    main()
