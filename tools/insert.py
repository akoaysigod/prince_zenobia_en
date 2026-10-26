"""Insert English messages into a copy of the ROM.

Every message with a non-empty `en` in script/messages.json is laid out by
layout.py (word wrap, new boxes as needed) and written to
free ROM space as `32 <text> <terminator> DA <return ptr>`, and the original
message is overwritten in place with `DA <new ptr>`. Block sizes never change,
so the script's relative branches stay valid.

Usage: python3 tools/insert.py
Writes build/ogre_battle_en.ngc and build/ogre_battle_en.ips.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fixed_text  # noqa: E402
import font  # noqa: E402
import layout  # noqa: E402
import menu_labels  # noqa: E402
import title_cards  # noqa: E402
import native_text  # noqa: E402
import script_vm as vm  # noqa: E402
import tables  # noqa: E402
from dump_script import load_table  # noqa: E402

ROOT = os.path.join(HERE, '..')
BUILD = os.path.join(ROOT, 'build')
FREE_START, FREE_END = 0x168000, 0x200000
OP_MESSAGE, OP_GOTO, OP_PRINT = 0x32, 0xDA, 0x9C
CHOICE_LETTER = 0x0C  # glyph 'A'
PAGE = layout.PAGE  # ends the box and opens a new one (FE 32), as the original script does

# English characters: the new font's slots (font.SLOTS), plus the blank glyph for space
ALIASES = {**font.SLOTS, ' ': 0xDC}
TAGS = {'{01}': 0x01, '{NAME}': 0xDD, '{NUM}': 0xDE, '\n': 0x00}
TAG_RE = re.compile(r'(\{01\}|\{NAME\}|\{NUM\}|\n)')


def build_encoder():
    rev = {v: k for k, v in load_table().items()}
    rev.update(ALIASES)
    return rev


def encode(text, rev, msg_id):
    out = bytearray()
    for part in TAG_RE.split(text):
        if part in TAGS:
            out.append(TAGS[part])
            continue
        for ch in part:
            if ch not in rev:
                raise ValueError(f'message {msg_id}: no glyph for {ch!r}')
            out.append(rev[ch])
    return bytes(out)


def encode_pages(text, rev, msg_id):
    """Encode a message; each {PAGE} becomes FE 32 so the text continues in a new box."""
    pages = [encode(p, rev, msg_id) for p in text.split(PAGE)]
    return bytes([0xFE, OP_MESSAGE]).join(pages)


def encode_string(text, rev, msg_id, lettered=False):
    """Encode text printed by op 9C: each line ends in 00, plus a final 00.

    Answer lists (lettered) also prefix each line with `01 <A|B|C>`.
    """
    out = bytearray()
    for i, line in enumerate(text.split('\n')):
        if lettered:
            out += bytes([0x01, CHOICE_LETTER + i]) + encode(layout.ANSWER_PREFIX, rev, msg_id)
        out += encode(line, rev, msg_id) + b'\x00'
    return bytes(out) + b'\x00'


def check_width(text, msg_id, width, max_lines=layout.BOX_LINES, last_lines=None):
    """Warn on lines over width and boxes over max_lines (last_lines for the last box). Returns the warning count."""
    warnings = 0
    pages = text.split(PAGE)
    for n, page in enumerate(pages):
        lines = page.rstrip('\n').split('\n')
        limit = last_lines if last_lines is not None and n == len(pages) - 1 else max_lines
        if len(lines) > limit:
            print(f'warning: message {msg_id} box has {len(lines)} lines: {page!r}')
            warnings += 1
        for line in lines:
            n = layout.width_of(line)
            if n > width:
                print(f'warning: message {msg_id} line is {n} chars: {line!r}')
                warnings += 1
    return warnings


def ptr24(offset):
    return (vm.ROM_BASE + offset).to_bytes(3, 'little')


def write_ips(orig, patched, path):
    """Minimal IPS writer: one record per changed run (split at 0xFFFF bytes)."""
    out = bytearray(b'PATCH')
    i, n = 0, len(orig)
    while i < n:
        if orig[i] == patched[i]:
            i += 1
            continue
        j = i
        while j < n and orig[j] != patched[j] and j - i < 0xFFFF:
            j += 1
        if i == 0x454F46:  # 'EOF' as an offset would end the patch early
            i -= 1
        out += i.to_bytes(3, 'big') + (j - i).to_bytes(2, 'big') + patched[i:j]
        i = j
    out += b'EOF'
    with open(path, 'wb') as f:
        f.write(out)


def encode_spaced(text, rev, msg_id, space):
    """encode(), with spaces written as `space` (01 = skip a column, DC = blank glyph)."""
    return encode(text.replace(' ', '{01}') if space == 0x01 else text, rev, msg_id)


def patch_native(rom, orig, msgs, rev, cursor):
    """Write every translated 'native' entry (see tools/native_text.py). Returns (done, warnings, cursor)."""
    specs = native_text.specs(orig)
    lengths = {}  # length operand address -> value written (shared operands must agree)
    done = warnings = 0
    stat = {m['role']: m for m in msgs if m['kind'] == 'native' and m['mode'] == 'stat'}
    if stat and all(m['en'] for m in stat.values()):
        cursor = _stat_message(rom, orig, stat, rev, cursor)
        done += len(stat)
    for m in msgs:
        if m['kind'] != 'native' or not m['en'] or m['mode'] == 'stat':
            continue
        spec = specs[int(m['offset'], 16)]
        mid = m['id']
        if m['mode'] == 'slots':
            lines = m['en'].split('\n')
            if len(lines) != len(spec['slots']):
                sys.exit(f"entry {mid}: needs exactly {len(spec['slots'])} lines")
            for line, (o, n) in zip(lines, spec['slots']):
                b = encode_spaced(line, rev, mid, spec.get('space', spec['pad']))
                if len(b) > n:
                    print(f'warning: entry {mid} {line!r} is {len(b)} cells; the field has {n}')
                    warnings += 1
                    b = b[:n]
                rom[o:o + n] = b + bytes([spec['pad']]) * (n - len(b))
        elif m['mode'] == 'free':
            if '' in m['en'].split('\n'):
                sys.exit(f"entry {mid}: an empty line would end the text early; use {{01}} for a blank line")
            space = 0x01 if spec.get('tiles') else 0xDC
            b = b'\x00'.join(encode_spaced(l, rev, mid, space) for l in m['en'].split('\n')) + b'\x00\x00'
            if len(b) > m['length']:
                sys.exit(f"entry {mid} is {len(b)} bytes; only {m['length']} fit in place")
            if 'max_tiles' in m and sum(1 for x in b if x > 1) > m['max_tiles']:
                sys.exit(f"entry {mid} draws {sum(1 for x in b if x > 1)} characters; "
                         f"the screen has tiles for {m['max_tiles']} (spaces are free)")
            o = spec['offset']
            rom[o:o + m['length']] = b + bytes(m['length'] - len(b))
        else:
            cursor = _reloc_native(rom, orig, m, spec, rev, cursor, lengths)
            text = layout.layout(m)
            xw = layout.X_WIDTH.get(m.get('x'), 8)
            lines = text.split('\n')
            if len(lines) > m['max_lines']:
                print(f'warning: entry {mid} has {len(lines)} lines: {text!r}')
                warnings += 1
            for line in lines:
                if layout.width_of(line, xw) > m['width']:
                    print(f'warning: entry {mid} line is {layout.width_of(line, xw)} chars: {line!r}')
                    warnings += 1
        done += 1
    return done, warnings, cursor


def _stat_message(rom, orig, parts, rev, cursor):
    """The stat change message (see native_text.STAT_MESSAGE): rewrite its pieces in free space."""
    for name, (at, orig_hex) in native_text.STAT_PATCH.items():
        if orig[at:at + len(orig_hex) // 2] != bytes.fromhex(orig_hex):
            sys.exit(f'stat message: code at {at:06X} is not the original; refusing to patch')
    enc = {r: encode(m['en'], rev, m['id']) for r, m in parts.items() if r != 'amount'}
    before, after = parts['amount']['en'].split('{X}')
    amount = encode(before, rev, parts['amount']['id']) + bytes([0x02]) + encode(after, rev, parts['amount']['id'])
    back = len(amount) - len(encode(before, rev, 0))  # digit position, counted back from the end
    updown = max(len(enc['up']), len(enc['down'])) + 2
    for r in ('prefix', 'chaos'):
        if not 1 <= len(enc[r]) <= 0xFF:
            sys.exit(f"entry {parts[r]['id']}: must be 1-255 characters")
    if back > 0x80 or len(amount) > 0xFF or updown > 0xFF:
        sys.exit(f"entry {parts['amount']['id']}: too long")
    # [prefix][amount][up][down] in a row, then [chaos]
    a_prefix = cursor
    a_amount = a_prefix + len(enc['prefix'])
    data = enc['prefix'] + amount
    for r in ('up', 'down'):
        data += enc[r] + bytes(updown - len(enc[r]))
    a_chaos = cursor + len(data)
    data += enc['chaos'] + b'\x00\x00'
    rom[cursor:cursor + len(data)] = data
    P = native_text.STAT_PATCH
    rom[P['prefix_ptr'][0] + 1:P['prefix_ptr'][0] + 5] = (vm.ROM_BASE + a_prefix).to_bytes(4, 'little')
    rom[P['chaos_ptr'][0] + 1:P['chaos_ptr'][0] + 5] = (vm.ROM_BASE + a_chaos).to_bytes(4, 'little')
    rom[P['amount_ptr'][0] + 1:P['amount_ptr'][0] + 5] = (vm.ROM_BASE + a_amount).to_bytes(4, 'little')
    rom[P['prefix_len'][0] + 1] = len(enc['prefix'])
    rom[P['chaos_len'][0] + 1] = len(enc['chaos'])
    rom[P['amount_len'][0] + 1] = len(amount)
    rom[P['updown_len'][0] + 1] = updown
    rom[P['digit_at'][0] + 1] = 0x100 - back
    print(f'stat message -> {cursor:06X} ({len(data)} bytes)')
    return cursor + len(data)


def _reloc_native(rom, orig, m, spec, rev, cursor, lengths):
    """Write a relocated native string (in parts, if the game assembles it) and repoint/resize."""
    parts = spec.get('parts') or [dict(refs=spec['refs'], term=2, whole=True)]
    texts = native_text.split_parts(layout.layout(m), spec.get('layout', [0]))
    data = bytearray()
    for i, part in enumerate(parts):
        b = encode(texts[i], rev, m['id'])
        if b'\x00\x00' in b or b.endswith(b'\x00') and i + 1 == len(parts):
            sys.exit(f"entry {m['id']}: an empty line would end the text early")
        if 'fixed' in part and len(b) != part['fixed']:
            sys.exit(f"entry {m['id']}: the text before {{X}} must be exactly {part['fixed']} character(s)")
        if part.get('refs'):
            if data:
                data += b'\x00\x00'
            start = cursor + len(data)
            for at in part['refs']:
                op, size, target = native_text.pointer_target(orig, at)
                if not 0 <= target - spec['offset'] < 0x100:
                    sys.exit(f"entry {m['id']}: pointer at {at:06X} is not the original; refusing to patch")
                rom[op:op + size] = (vm.ROM_BASE + start).to_bytes(size, 'little')
        if part.get('term') == 2 and i + 1 < len(parts) and not parts[i + 1].get('refs'):
            sys.exit(f"entry {m['id']}: part {i} ends the string but the next part continues it")
        data += b
        for form, at in part.get('len', []):
            native_text.read_len(orig, form, at)  # checks the instruction is the expected one
            n = len(b) + part['term']
            if lengths.setdefault(at, n) != n:
                sys.exit(f"entry {m['id']}: shares a length with another entry, so its text after {{X}} "
                         f"must be {lengths[at] - part['term']} bytes (now {len(b)})")
            native_text.write_len(rom, form, at, n)
    data += b'\x00\x00'
    if cursor + len(data) > FREE_END:
        sys.exit('out of free space')
    rom[cursor:cursor + len(data)] = data
    print(f"#{m['id']:04d} {m['offset']} -> {cursor:06X} ({len(data)} bytes)")
    return cursor + len(data)


def main():
    orig = vm.load_rom()
    rom = bytearray(orig)
    rev = build_encoder()
    with open(os.path.join(ROOT, 'script', 'messages.json'), encoding='utf-8') as f:
        msgs = json.load(f)

    if any(rom[FREE_START:FREE_END].strip(b'\x00\xff')):
        sys.exit('free space is not empty; refusing to overwrite')

    glyphs = font.patch(rom)
    fixed = fixed_text.patch(rom, rev)
    single_box = layout.no_page_ids(msgs)
    cursor = FREE_START
    done = warnings = 0
    for m in msgs:
        if not m['en'] or m['kind'] in ('table', 'name', 'native', 'label', 'card'):
            continue
        off, length = int(m['offset'], 16), m['length']
        text = layout.layout(m, can_page=m['id'] not in single_box and m['kind'] == 'message')
        width = layout.entry_width(m)
        if m['kind'] == 'fixed':
            # Rewritten in place: the text before {NAME} must keep its original length,
            # because the game prints the rest from that fixed offset after the name.
            before, after = text.split('{NAME}')
            head = encode(before, rev, m['id'])
            if len(head) != m['name_at']:
                sys.exit(f"entry {m['id']}: text before {{NAME}} must be exactly {m['name_at']} characters")
            tail = encode_string(after, rev, m['id'])
            reloc = fixed_text.RELOCATED_TAILS.get(off)
            if reloc:
                # Tail goes in free space; repoint the code that copies it and fix its length
                p, n = reloc['ptr_operand'], reloc['len_operand']
                if rom[p:p + 4] != bytes.fromhex(reloc['orig_ptr']) or rom[n] != reloc['orig_len']:
                    sys.exit(f"entry {m['id']}: copy code at {p:06X} is not the original; refusing to patch")
                if len(tail) > 0xFF:
                    sys.exit(f"entry {m['id']}: tail is too long")
                warnings += check_width(text, m['id'], width)
                rom[off:off + len(head)] = head
                rom[cursor:cursor + len(tail)] = tail
                rom[p:p + 4] = (vm.ROM_BASE + cursor).to_bytes(4, 'little')
                rom[n] = len(tail)
                print(f"#{m['id']:04d} {off:06X} head in place, tail -> {cursor:06X} ({len(tail)} bytes)")
                cursor += len(tail)
                done += 1
                continue
            new = head + tail
            if len(new) > length:
                sys.exit(f"entry {m['id']} is {len(new)} bytes; only {length} fit")
            warnings += check_width(text, m['id'], width)
            rom[off:off + length] = new + bytes(length - len(new))
            print(f"#{m['id']:04d} {off:06X} rewritten in place ({len(new)}/{length} bytes)")
            done += 1
            continue
        if m['kind'] == 'pstring':
            # String reached through a 32-bit pointer cell: write it to free space, repoint the cell
            if rom[off + 3] != 0:
                sys.exit(f"entry {m['id']}: {off:06X} is not a pointer cell")
            text = layout.layout(m, can_page=False)
            warnings += check_width(text, m['id'], width, m['max_lines'])
            new = encode_string(text.replace(' ', '{01}'), rev, m['id'])  # 01 = blank column, no tile
            patch = (vm.ROM_BASE + cursor).to_bytes(4, 'little')
        elif m['kind'] in ('choices', 'string'):
            # New text in free space; repoint the 9C op's 32-bit pointer at it
            assert rom[off] == OP_PRINT, f"entry {m['id']} does not start with opcode 9C"
            if m['kind'] == 'choices':
                n_old = len(m['jp'].split('\n'))
                if len(text.split('\n')) != n_old:
                    sys.exit(f"entry {m['id']} needs exactly {n_old} answers")
            warnings += check_width(text, m['id'], width)
            new = encode_string(text, rev, m['id'], lettered=m['kind'] == 'choices')
            patch = bytes([OP_PRINT]) + (vm.ROM_BASE + cursor).to_bytes(4, 'little')
        else:
            if length < 4:
                if text.strip() in ('...', '…'):  # the original "…" glyph is redrawn as three dots (font.REDRAW)
                    continue
                sys.exit(f"message {m['id']} is only {length} bytes; cannot fit a goto")
            assert rom[off] == OP_MESSAGE, f"message {m['id']} does not start with opcode 32"
            warnings += check_width(text, m['id'], width, last_lines=layout.last_box_lines(m))
            body = encode_pages(text, rev, m['id'])
            term = int(m['terminator'], 16)
            new = bytes([OP_MESSAGE]) + body + bytes([term, OP_GOTO]) + ptr24(off + length)
            patch = bytes([OP_GOTO]) + ptr24(cursor)
        if cursor + len(new) > FREE_END:
            sys.exit('out of free space')
        rom[cursor:cursor + len(new)] = new
        rom[off:off + len(patch)] = patch
        print(f"#{m['id']:04d} {off:06X} -> {cursor:06X} ({len(new)} bytes)")
        cursor += len(new)
        done += 1

    # Offset tables: rebuild each table that has any English, in free space, and repoint its loads
    by_table = {}
    for m in msgs:
        if m['kind'] in ('table', 'name'):
            t, i = m['offset'].split(':')
            by_table.setdefault(int(t, 16), {})[int(i)] = m
    for t, entries in sorted(by_table.items()):
        if not any(m['en'] for m in entries.values()):
            continue
        strings = tables.read_table(orig, t)
        for i, m in entries.items():
            if not m['en']:
                continue
            if m['kind'] == 'name':  # packed name in a fixed-width field
                strings[i] = encode(m['en'], rev, m['id'])
                if len(strings[i]) > m['max_len']:
                    print(f"warning: name {m['id']} {m['en']!r} is {len(strings[i])} chars; field fits {m['max_len']}")
                    warnings += 1
                strings[i] = bytes.fromhex(m.get('header', '')) + strings[i]
                continue
            text = layout.layout(m, can_page=False)
            warnings += check_width(text, m['id'], layout.entry_width(m), m['max_lines'])
            if m.get('packed'):  # lines joined by 00, no terminator, 01 as the space
                strings[i] = b'\x00'.join(encode(l.replace(' ', '{01}'), rev, m['id'])
                                           for l in text.split('\n'))
            else:
                strings[i] = encode_string(text, rev, m['id'])
        new = tables.build_table(strings)
        refs = tables.references(orig, t)
        if not refs:
            sys.exit(f'table {t:06X}: no code loads it; refusing to move it')
        if cursor + len(new) > FREE_END:
            sys.exit('out of free space')
        rom[cursor:cursor + len(new)] = new
        for at, size in refs:
            rom[at:at + size] = (vm.ROM_BASE + cursor).to_bytes(size, 'little')
        print(f"table {t:06X} -> {cursor:06X} ({len(new)} bytes, {len(refs)} loads repointed)")
        cursor += len(new)
        done += sum(1 for m in entries.values() if m['en'])

    n, w, cursor = patch_native(rom, orig, msgs, rev, cursor)
    done += n
    warnings += w
    n, w = menu_labels.patch(rom, msgs)  # menu captions, redrawn in place
    done += n
    warnings += w
    n, w = title_cards.patch(rom, msgs)  # chapter and area title cards
    done += n
    warnings += w

    os.makedirs(BUILD, exist_ok=True)
    with open(os.path.join(BUILD, 'ogre_battle_en.ngc'), 'wb') as f:
        f.write(rom)
    write_ips(orig, bytes(rom), os.path.join(BUILD, 'ogre_battle_en.ips'))
    print(f'{glyphs} font glyphs, {fixed} fixed screen texts written; {done} messages inserted, {warnings} warnings; '
          f'free space used up to {cursor:06X}')


if __name__ == '__main__':
    main()
