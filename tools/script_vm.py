"""Ogre Battle Gaiden (NGPC) event-script VM: opcode grammar and a linear parser.

Derived from the dispatcher at CPU 0x20023D (signed byte index into the
16-bit handler table centred on 0x2007A1). Opcodes are even bytes.
"""
import glob
import os

ROM_BASE = 0x200000
HERE = os.path.dirname(os.path.abspath(__file__))
ROM_PATH = glob.glob(os.path.join(HERE, '..', '*.ngc'))[0]

# Total instruction length in bytes (opcode included). None = special handling.
LEN = {
    0x00: 5, 0x02: 1, 0x04: 1, 0x06: 1, 0x08: 4, 0x0A: 2, 0x0C: 3, 0x0E: 2,
    0x10: 2, 0x12: 3, 0x14: 2, 0x16: 2, 0x18: 2, 0x1A: 2, 0x1C: 2, 0x1E: 3,
    0x20: 1, 0x22: 3, 0x24: 1, 0x26: 7, 0x28: 7, 0x2A: 8, 0x2C: 8, 0x2E: 4,
    0x30: None,  # inline native code (jp (XDE))
    0x32: None,  # message: text until a byte >= 0xDF (inclusive)
    0x34: 3, 0x36: 2, 0x38: 4, 0x3A: 4, 0x3C: 4, 0x3E: 5, 0x40: 5, 0x42: 4,
    0x44: 2, 0x46: 2, 0x48: 5, 0x4A: 2,
    0x80: 1, 0x82: 2, 0x84: 1, 0x86: 4, 0x88: 5, 0x8A: 7, 0x8C: 5, 0x8E: 5,
    0x90: 5, 0x92: 4, 0x94: 4, 0x96: 4, 0x98: 3, 0x9A: 4, 0x9C: 6, 0x9E: 4,
    0xA0: 4, 0xA2: 4, 0xA4: 3, 0xA6: 3, 0xA8: 3, 0xAA: 4, 0xAC: 5, 0xAE: 7,
    0xB0: 5, 0xB2: 5, 0xB4: 5, 0xB6: 4, 0xB8: 4, 0xBA: 4, 0xBC: 3, 0xBE: 4,
    0xC0: 6, 0xC2: 4, 0xC4: 4, 0xC6: 4, 0xC8: 3, 0xCA: 3, 0xCC: 3, 0xCE: 2,
    0xD0: 2, 0xD2: 2, 0xD4: 4, 0xD6: 4, 0xD8: 4, 0xDA: 4, 0xDC: 4, 0xDE: 4,
    0xE0: 1, 0xE2: 1, 0xE4: 6, 0xE6: 5, 0xE8: 6, 0xEA: 5, 0xEC: 1, 0xEE: 5,
    0xF0: 2, 0xF2: 4, 0xF4: 1, 0xF6: 4, 0xF8: 1, 0xFA: 1, 0xFC: 1, 0xFE: 6,
}
# Opcodes whose operand holds a 16-bit relative branch: (offset of rel16 within the instruction)
REL16 = {0x34: 1, 0x38: 2, 0x3A: 2, 0x3C: 2, 0x3E: 3, 0x40: 3, 0x42: 2}
# Opcodes with a 24-bit absolute script pointer at offset 1
ABS24 = {0xD4, 0xD6, 0xD8, 0xDA, 0xDC, 0xDE}
TEXT_END = 0xDF
# Opcodes carrying a 32-bit immediate right after the opcode
IMM32 = {0x48, 0x8A, 0x9C, 0xAE, 0xC0, 0xEE}
NATIVE_RETURN = bytes([0x1D, 0x3C, 0x02, 0x20])  # call 0x20023C


def load_rom():
    return open(ROM_PATH, 'rb').read()


def parse(rom, start, end):
    """Linear parse of [start, end). Yields (offset, opcode, raw bytes)."""
    o = start
    while o < end:
        op = rom[o]
        if op == 0x32:
            e = o + 1
            while rom[e] < TEXT_END:
                e += 1
            yield o, op, rom[o:e + 1]
            o = e + 1
            continue
        if op == 0x30:
            # Inline native code; it re-enters the VM with `call 0x20023C`,
            # and bytecode resumes right after that call.
            e = rom.find(NATIVE_RETURN, o + 1, end)
            if e < 0:
                raise ValueError(f'native block at {o:06X} has no VM re-entry')
            yield o, op, rom[o:e + len(NATIVE_RETURN)]
            o = e + len(NATIVE_RETURN)
            continue
        n = LEN.get(op)
        if n is None:
            raise ValueError(f'cannot parse opcode {op:02X} at {o:06X}')
        yield o, op, rom[o:o + n]
        o += n


# Switch opcodes: (offset of the 24-bit table pointer, falls through?)
SWITCH = {0xE4: (3, False), 0xE6: (2, False), 0xE8: (3, True), 0xEA: (2, True)}
NO_FALLTHROUGH = {0xDA, 0xE0, 0xE2}
SCRIPT_LO, SCRIPT_HI = 0x063000, 0x076000  # where stage scripts and shared routines live


def p24(rom, o):
    return rom[o] | rom[o + 1] << 8 | rom[o + 2] << 16


def _script_ptr(v):
    o = v - ROM_BASE
    return o if SCRIPT_LO <= o < SCRIPT_HI else None


def decode_one(rom, o):
    """Decode a single instruction at o. Returns (raw, successors, fallthrough)."""
    op = rom[o]
    if op == 0x32:
        e = o + 1
        while rom[e] < TEXT_END:
            e += 1
        return rom[o:e + 1], [], True
    if op == 0x30:
        e = rom.find(NATIVE_RETURN, o + 1, o + 0x400)
        if e < 0:
            raise ValueError(f'native block at {o:06X} has no VM re-entry')
        raw = rom[o:e + len(NATIVE_RETURN)]
        succ = []
        # `ld XDE, imm32` (42 xx xx xx 00) inside native code names another entry point
        i = raw.find(b'\x42')
        while i != -1 and i + 5 <= len(raw):
            t = _script_ptr(int.from_bytes(raw[i + 1:i + 5], 'little'))
            if t is not None:
                succ.append(t)
            i = raw.find(b'\x42', i + 1)
        return raw, succ, True
    n = LEN.get(op)
    if n is None:
        raise ValueError(f'bad opcode {op:02X} at {o:06X}')
    raw = rom[o:o + n]
    succ = []
    if op in ABS24:
        t = _script_ptr(p24(rom, o + 1))
        if t is not None:
            succ.append(t)
    if op in IMM32:
        # a 32-bit immediate that is a script address is a thread entry point
        t = _script_ptr(int.from_bytes(raw[1:5], 'little'))
        if t is not None:
            succ.append(t)
    if op in REL16:
        k = REL16[op]
        rel = int.from_bytes(raw[k:k + 2], 'little', signed=True)
        succ.append(o + n + rel)
    if op in SWITCH:
        k, falls = SWITCH[op]
        tbl = _script_ptr(p24(rom, o + k))
        if tbl is not None:
            j = tbl
            while True:
                t = _script_ptr(p24(rom, j))
                if t is None:
                    break
                succ.append(t)
                j += 3
        return raw, succ, falls
    return raw, succ, op not in NO_FALLTHROUGH


def trace(rom, entries):
    """Follow control flow from entry points. Returns {offset: (op, raw)} and errors."""
    seen, errors, work = {}, [], list(entries)
    while work:
        o = work.pop()
        while o not in seen:
            try:
                raw, succ, falls = decode_one(rom, o)
            except (ValueError, IndexError) as e:
                errors.append(str(e))
                break
            seen[o] = (rom[o], raw)
            work.extend(succ)
            if not falls:
                break
            o += len(raw)
    return seen, errors


def stage_entries(rom, table=0x261E2, count=19, stride=18):
    return [p24(rom, table + stride * i + 5) - ROM_BASE for i in range(count)]


def _runs_clean(rom, o, end, need=8):
    n = 0
    try:
        while n < need and o < end:
            raw, _, _ = decode_one(rom, o)
            o += len(raw)
            n += 1
    except (ValueError, IndexError):
        return False
    return n >= need or o == end


def parse_block(rom, start, end, known=()):
    """Linear parse that skips embedded data.

    On an undecodable byte it resynchronises at the next offset that is a
    known instruction (from `trace`) or from which decoding runs cleanly.
    Yields ('ins', offset, op, raw) and ('data', offset, None, raw).
    """
    known = set(known)
    o = start
    while o < end:
        try:
            raw, _, _ = decode_one(rom, o)
            if o + len(raw) > end:
                raise ValueError('runs past block end')
            yield 'ins', o, rom[o], raw
            o += len(raw)
            continue
        except (ValueError, IndexError):
            pass
        p = o + 1
        while p < end and not (p in known or _runs_clean(rom, p, end)):
            p += 1
        yield 'data', o, None, rom[o:p]
        o = p
