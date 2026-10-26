# Ogre Battle Gaiden (NGPC) translation: roadmap

Each step needs explicit approval before starting.

Status (2026-10-25): steps 1–5 and 7 are done; step 6 is partly done; step 8 has not started. Details in `REVIEW.md`.

## Step 1+2 (done): tooling and font/text table discovery
- Install tooling available through Homebrew only; anything else goes in `TOOLS_NEEDED.md`.
- Find the font tiles, build a character table (`.tbl`), identify text regions, compression, pointer tables.

## Step 3 (done): text dumper / inserter, plus Translation Studio (`app/`)
- Python tool: extract script + pointers to editable CSV/JSON; reinsert and rewrite pointers.
- Check for existing partial translations to reuse as a head start.

## Step 4 (done): font hack ( IBM EGA 8x8 in the hiragana slots, `tools/font.py`)
- Latin font in place of kana/kanji; patch the text routine (TLCS-900 asm) for 1-byte characters / variable width if needed.

## Step 5 (done): space
- Relocate script into free ROM space (large 0x00/0xFF regions), repoint, small ASM hooks.

## Step 6 (partly done): graphics
- Done: menu captions and the unit-list tag (`tools/menu_labels.py`).
- Left: any other text drawn as pictures that turns up in testing. The title logo stays as the original (decided 2026-10-25).

## Step 7 (done, first pass): translation
- Full script: dialog, items, units, classes, spells. Glossary consistent with the Ogre Battle series. LLM first pass + human edit.

## Step 8: QA and release
- Full playthrough, overflow checks. The ROM header has no checksum field, so there's probably nothing to fix there (to confirm on hardware). Ship as an IPS patch only (no ROM).
- Release readme with the font credit: done (`release/README.txt`). `python3 tools/package.py` zips it with the IPS and the font licence.
