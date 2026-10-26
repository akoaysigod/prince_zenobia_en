# Findings

## Font (step 2)
- 2bpp 8x8 tiles, 16 bytes each (row = little-endian word, leftmost pixel in the top bits).
- ROM 0x0C89 (CPU 0x200C89); glyph g at 0x0C89 + 16*g. About 220 glyphs, then ordinary graphics.
- Order: junk, 0-9, A-Z (uppercase only), hiragana, katakana, punctuation.
- Glyph loader: CPU 0x200BBA-0x200C28.

## Text encoding
- One byte per character: byte = glyph index + 1. Full table in `ogrebattle.tbl`.
- 0xC6-0xDC are punctuation (『』？！、。ヴ．，・‥／＋ー＝：％＆「」…© and a full-width space).
- Inside messages: 0x00 = line break, 0x01 = skip one column (a blank; the Japanese uses it between sentences; confirmed on screen), 0xDD = player name, 0xDE = number.
- A new box is simply another `32` message right after the previous one. The English uses a `{PAGE}` tag for this, and `insert.py` writes it as `FE 32`.
- Any byte >= 0xDF ends a message (0xFE normal, 0xFC yes/no prompt, others not yet classified).

## Event-script VM (step 3)
- Interpreter loop at CPU 0x20023D; script pointer in XDE.
- Dispatch: signed opcode byte indexes a 16-bit handler table centred on CPU 0x2007A1 (0x200721-0x2007EC). Opcodes are even.
- The disassembler prints `(XHL+W)` for that index; the code means `(XHL+A)`.
- Full opcode length table and control flow: `tools/script_vm.py`.
- Key opcodes:
  - 32 = show message (text inline until a byte >= 0xDF)
  - DA = goto ptr24, DC/DE = call ptr24, E0/E2 = return
  - D4/D6/D8 = loops with ptr24
  - 34, 38, 3A, 3C, 3E, 40, 42 = conditional branches with signed 16-bit relative offsets
  - E4/E6 = switch goto, E8/EA = switch call (24-bit pointer tables)
  - 30 = inline native code; it re-enters the VM with `call 0x20023C` (1D 3C 02 20)
  - 80/82/84 = yield (wait frames)

## Stage scripts
- Stage table: 19 records of 18 bytes at ROM 0x261E2; the script pointer is at +5 (24-bit).
- Script blocks: 0x63B0D-0x73328 (block 18 is data only). Shared routines and data: 0x73400-0x75F00.
- `tools/dump_script.py` scans the ROM into `script/rom_scan.json` (1,532 story messages plus the system text, names and native text). Translation Studio (`app/`) merges a scan into `script/messages.json`, which only the app writes.
- Some routines are only reachable through indirect entry points. The parser reads linearly and resyncs over embedded data (834 bytes total).

## Insertion strategy (planned)
- Keep every block the same size, so the relative branches stay valid.
- Replace each Japanese message in place with `DA <ptr24>` (goto) into free ROM (0x168000-0x1FFFFF, about 600 KB empty).
- At that address: `32 <English text> <terminator>` followed by `DA <address after the original message>`.
- Each message needs at least 4 bytes; any shorter ones need special handling.

## Other text found but not yet dumped
- Unit name pool: around 0x10A00 (katakana names, no separators; probably indexed by the table at about 0x10800).
- Item names and data: around 0x16800.
## Native-drawn fixed text (patched in place by `tools/fixed_text.py`)
- Format: glyph bytes, `00` = new line, `01` = skip one column, `00 00` = end.
- Name-entry grid at 0x99470-0x9958F: three pages (hiragana, katakana, ABC) of rows with 10 cells each, laid out as 5 cells, `01`, 5 cells, `00`, then `01 00` as a gap row.
  - Page pointers are at 0x95C08.
  - Page 1 is now a-z and punctuation.
- Tab labels "ひらがなカタカナABCEND" at 0x99592.
- Name confirmation at 0x995A2: dumped as #1586, kind `fixed`.
  - Code at CPU 0x294FE4 builds RAM 0x6000 from 5 bytes at 0x995A2, then the name (the length byte at 0x46A0, then the characters), then 22 bytes from 0x995A7.
  - It prints this with the dynamic routine 0x200BAC, which gives each character code of 2 or more its own new tile from IZ upwards. `01` skips a cell without using a tile.
  - Some box cells (for example the ones left of Yes/No) show tiles in that range. The original's layout (12 characters, newline, 9 blanks, 8 characters) keeps them blank, so the English must use the same character/blank pattern.
- Text printers:
  - 0x200B72 uses the fixed font: tile = base (0x4406) + character.
  - 0x200BAC uses dynamic tiles: the glyph is copied to 0xA000 + tile*16.
  - Yes/No uses whichever applies, depending on (XIY+42); in the dynamic case it starts at IZ+0x24.
- Default name at 0x995BD: a length byte, then 8 cells.
- Yes/No: 0x30F5 (used from 0x2FF5, general confirmations), plus 0xE25D3 and 0xE3B40, which have wider spacing.

## Offset tables (`tools/tables.py`)
- Code does `ld XIY, <table>`, then `call 0x201B77` with the index in A:
  - start(i) = table + 2i + entry[i];
  - length(i) = entry[i+1] - entry[i] + 2;
  - the last entry is an end marker.
- Tables found:
  - 0x0E49D: 118 class names.
  - 0x0FCEA: 1,682 unit names.
  - 0x166B8: 190 item records (name mixed with data).
  - 0x1BCEB: 23 tarot names.
  - 0x1BD84: 23 tarot descriptions.
  - 0x73334: 9 town types.
  - 0xC3C8C, 0xC3D86, 0xC3EA5, 0xC3F07, 0xC402B: menu help lines (dumped as #1587-#1626).
  - 0xC4124: 190 item descriptions.
- Five more calls (at 0xC803F, 0xC8108, 0xE378A, 0xE4B89, 0xE55A5) pass the table in a register; not traced yet.
- `insert.py` rebuilds any table that has English in free space and repoints every `ld XIY, <table>`.
- The menu command labels themselves (ユニット/はけん/へんせい…) are not stored as text anywhere I've found, so they may be graphics.
- System messages that still need dumping:
  - 0x6F41 and 0x8282 (dispatch and settlement), 0x15F65 (item use), 0xCE88 (formation limits);
  - 0x9C318: an options-style screen with 　-padded labels.

## Item records (0x166B8) and descriptions (0xC4124)
- **Records:** a 4-byte header (type, price…), then the name.
  - Equipment (4th byte not 0) has extra stat bytes before the name: codes of 0xDD and up, values under 0x26.
  - `tables.split_record` separates them, and all 189 parsed names checked out.
- **Descriptions:** lines separated by `00`, with no terminator. `01` serves as the space.

## Battle help pointer cells (0xF6E4–0xFAC4)
- These are 32-bit pointers to `00 00`-terminated strings: tarot effects, battle commands, tactics and battle items.
- The window is about 10 columns wide.
- Dumped as `"kind": "pstring"`, and `insert.py` repoints each cell.

## Op 9C = print a text string
- Format: `9C <ptr32> <byte>`. The text has lines ending in `00` and a final extra `00`. Tarot answer lists are a lettered variant.
- `insert.py` handles these as `"kind": "string"` (or `"choices"`): it writes the English into free space and repoints the op.
- A scan for `9C` finds about 30 system/menu strings, for example at 0x4829 (power-off/save notice), 0x5AC9 ("not enough money"), 0x8548 and 0x8931 (tarot card use/stock), and 0x12843-0x1418D (unit formation), plus shared "よろしいですか？" at 0x2E5D.
  - These aren't dumped yet. Add them to `SYSTEM_STRINGS` in `dump_script.py` one by one after checking each, because a blind scan also matches code.

## New game: save-area screen (dumped as #1584-#1585, `"block": "system"`)
- 0x95357: message "choose a save area".
- 0x94D87: `9C` pointing at 0x952DC, "OK to overwrite?".

## Tarot intro (dumped as #1532-#1583)
- Script routines at 0x995C8, 0x99659, 0x9966C and 0x99698, called from native code (for example `DE C8 95 29` at 0x94DDD).
- Question table at 0x996D8: 22 ptr24s. Each question is `32 <question> FE`, then `9C <ptr32> 20`, then a jump to the shared tail at 0x99756.
- Answer lists: `01 <0C|0D|0E> text 00` three times, then `00`. Each list is referenced only by its `9C` pointer, so `insert.py` writes a new list into free space and repoints it.
- Widest Japanese line: 18 characters for messages, 16 for answers.
- Still to find: class names, spells, location names, menu labels, battle messages.

## Native-drawn text (`tools/native_text.py`, entries from #3946)
- The game's own code prints these strings, not the script VM. Code loads them in three ways:
  - `ld r32, <addr>` (40–47 + 32-bit);
  - script ops `8A` / `9C` with a 32-bit pointer;
  - `lda r, (<addr24>)` (F2 + 24-bit + opcode).
- **Composed messages:** the code copies pieces into RAM 0x6000 and prints them with `9C 0x6000`.
  - Each piece is copied with `ld XIY, <src>` + `ld BC/C, <len>` + `ldir`.
  - Between the pieces, a routine adds a value:
    - a name: 0x20CC9A;
    - a town (type + name): 0x208DE6;
    - an item: 0x215E86, or the record table 0x2166B8;
    - a number: 0x200C74.
  - Lengths come in three forms:
    - `d9 a8+n` (ld BC, n ≤ 7);
    - `23 nn` (ld C, nn);
    - `31 nn nn` (ld BC, nnnn).
  - `insert.py` relocates each piece and patches the pointers and lengths.
- **Town names:** 16-byte records in the stage data (0x26000–0x2D000), with the name in 8 cells at +7, padded with `01`.
  - Routine 0x208DE6 copies the town type (table 0x73334) and then the name. It stops at `01`.
  - An index past the map's list gives the church name at 0x8E22 (up to 11 cells).
- **Attack/spell names:** a table at 0xF134 with 10 bytes per entry (8 cells + `00 00`). The tarot card names come first.
- **Movement type:** 10 × 4-cell terrain words at 0xEB61. The 3-cell "タイプ" at 0xEB5D is read as entry −1 and printed after every word.
- **Battle screen:**
  - field names at 0xC82A9 (9 bytes each: 7 cells + `00 00`);
  - day/night at 0xC835D (4 bytes each).
  - Both are drawn by 0x200BAC from small tile bases, so they can't grow.
- **Tactics:** 0xF0E7 (4 separate strings) and 0xF10F (one 4-line string), 8 cells each.
- **Title menu, options and save areas:** 0x9BF9A–0x9C652. Labels are 10 cells and descriptions 14 × 2, padded with blank glyphs (DC) and reached through pointer structures. They're rewritten in place.
- **Settlement screen:** 0x825E, drawn with fixed line spacing. "そうしさん" at 0x8299 is also printed on its own.
- **Stat change message:** built at 0x208620 as `[prefix 0x8895][stat 0x88EB][amount 0x889C][up 0x88AB | down 0x88B1]`. The Chaos Frame version uses 0x88B7.
  - The digit goes at `(XDE-5)`, 5 bytes before the end of the amount piece.
  - "Down" is reached by skipping the same count that's copied for "up".
- **Tables also loaded with `lda XIY, (table)`:**
  - class names, at 0xC803A and 0xC8103 (battle) and at 0xE3785 and 0xE4B84 (link);
  - item names, at 0xE55A0.
  - `tables.references` now repoints these too.
- **menu_help_unit (0xC3D86):** its last offset is not an end marker but an 11th string (the class change help). See `tables.LAST_IS_STRING`.

## Menu captions (`tools/menu_labels.py`)
- The caption under the field/battle menu icons is a 64x8 picture: 8 sprite tiles, 2bpp, 128 bytes.
- 45 captions are stored back to back from ROM 0x18112, with the menu icons just before them.
- Code at 0x217291 does `ld XIY, 0x218112` + 128 * index and copies 0x40 words to the sprite tiles from 0xC0.
- Style: colour 1 strokes on rows 1-6, colour 3 outline, colour 0 transparent.

## Tarot card drawn (#4433)
- Routine 0x208C85 builds `『` (1 byte, `ldi`), the card name (table 0x1BCEB), then 0x18 bytes from 0x8CD2 (`ld C,0x18` at 0x8CB1) into RAM 0x6000. Script ops `9C 0x6000` at 0x855E and 0x891A print it.

## Yes/No questions (terminator FC)
- Yes/No is drawn on line 3 of the last box. A `{PAGE}` before it is fine.
- #84 (church choice) has no cursor: code after the message tests bit 5 of (XIY+0x23), the B button. B goes to #86, A to #85.

## NgpCraftEmulator save states
- States are in `/Applications/NgpCraftEmulator.app/Contents/MacOS/savestates/<rom>.s0`, uncompressed ("NGPCST04").
- CPU address 0x9000-0xBFFF (tile maps and tile RAM) sits at file offset address + 0xAFC. Sprite table 0x8800 and palettes 0x8200 follow the same offset.
- Unit list tag はけん中: sprite tiles 0x13B-0x13F, from a sheet of interface tiles at 0x14A00 (identical copy at 0xE736A).

## Title cards (`tools/title_cards.py`)
- Routine 0x29ECB4 copies a sheet of 360 tiles (0xB40 words) to tiles 0x44 onwards. It then copies the card's layout (49 words: header 0x040C, then a 12x4 grid of tile numbers, 0 = blank) to RAM 0x6080.
- The set is chosen by bit (chapter) of (0x546E):
  - table 0x9EEA2 with sheet 0x9F34A: chapter cards plus bonus titles;
  - table 0x9EECA with sheet 0xA09CA: area-name cards.
- 18 layouts each, at 0xA2144 / 0xA2828, every 0x62 bytes. Table entries 19 and 20 repeat the 18th.
- Only 328 tiles of sheet 2 are lettering. The game copies 360, but from 0xA1E4A on it's the emblem's tile map (plane 2, at about 0xA1F90), so it must not be overwritten. Erasing it left the emblem as random tiles.

## Tarot questions over several boxes
- Fine: `32 … FE 32 … FE`, then the answer op. The other fan patch does the same.
