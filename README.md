# Ogre Battle Gaiden (NGPC) English translation

The project for an English fan translation of *Densetsu no Ogre Battle Gaiden: Zenobia no Ouji* for the Neo Geo Pocket Color. The release is an IPS patch only. I am currently playing through the game and fixing/re-translating as I go.

## Working on it

1. **Edit translations in Translation Studio.** Build it with `sh app/build.sh`, then open `app/build/Translation Studio.app`.
   - It's the only thing that writes `script/messages.json`.
   - It shows the Japanese, the full English and the in-game English for every message, with a preview in the game's font. It won't let you type more than fits.
2. **Build the patch:** **Patch › Build Patch** (⌘B), which runs `python3 tools/insert.py`.
   - Output: `build/ogre_battle_en.ngc` and `build/ogre_battle_en.ips`.
3. **Test** in NgpCraftEmulator (**Patch › Open in NgpCraft**). Quit the emulator first so it loads the new build.
4. **Package a release:** `python3 tools/package.py`.
   - It writes `build/ogre_battle_en_patch.zip`: the IPS, `release/README.txt` (the player readme, with credits) and the font licence.
   - Ship that zip.

Requirements: macOS 14+, Xcode command-line tools (Swift), and the system `/usr/bin/python3`. Python needs nothing beyond its standard library.

## Files

| Path | What it is |
|---|---|
| `script/messages.json` | Every translatable text: Japanese, in-game English, full English, note, review mark. Edited only by Translation Studio. |
| `script/suggestions.json` | Proposed changes, to accept or reject in **Patch › Review Suggestions**. |
| `script/rom_scan.json` | A fresh scan of the ROM (`python3 tools/dump_script.py`), merged in with **Patch › Merge ROM Scan**. |
| `script/glossary.json` | Names and terms, kept consistent across the script. |
| `tools/insert.py` | Builds the patched ROM and the IPS. |
| `tools/layout.py` | Word wrap and box rules (16/18 columns, 3 lines; 2 in a Yes/No question's last box). |
| `tools/font.py` | The English font, written over the hiragana glyphs. |
| `tools/menu_labels.py` | Redraws the menu captions and the unit-list tag, which are pictures. |
| `tools/native_text.py`, `fixed_text.py`, `tables.py` | Text drawn by the game's own code, fixed screens, offset tables. |
| `tools/studio_helper.py` | The preview helper Translation Studio runs. |
| `app/` | Translation Studio (SwiftUI). |
| `release/README.txt` | The readme that ships with the patch. |

## Documentation

- `INSTRUCTIONS.md`: how to change a translation, and the rules for each kind of text.
- `REVIEW.md`: what to check on screen, what's not translated, uncertain translations.
- `FINDINGS.md`: technical notes on the ROM (font, script VM, pointers, graphics).
- `REMAINING_STEPS.md`: the roadmap.

## Credits

The English font is **IBM EGA 8x8** from [The Ultimate Oldschool PC Font Pack](https://int10h.org/oldschool-pc-fonts/) by VileR, (c) 2016-2020 VileR, licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). See `tools/fonts/README.md`.

The converted font in the patch is shared under the same licence. Any release must carry this credit and the licence; `tools/package.py` includes both.

*Densetsu no Ogre Battle Gaiden: Zenobia no Ouji* is (c) SNK and Quest. This is an unofficial fan project.
