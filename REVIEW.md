# Review list: things to check, and things not translated yet

Everything below was built without being seen on screen. Each item is either done but worth a look, a guess, or a known gap.

Short forms used to fit fixed-width fields: use the **Shortened** filter in Translation Studio (each row shows `short = full`).

## 1. Check on screen (most likely to need fixing)

| What | IDs | Why it might be wrong |
|---|---|---|
| Name fields: classes, tarot cards, items, unit names | #1627–#1648, #1671–#1984, #2263–#3944 | Names are capped at **8 characters** (the longest Japanese name in each list), so many are shortened. If a name looks cut off or runs into other text, the field is narrower than 8. |
| Tarot answers `A) …` | #1541–#1583 (answer lists) | Up to 14 characters after `A) `: with the blank column before the letter that's the window's 18 columns. Confirmed on screen: 15 is too many (#1567). |
| Item descriptions | #1985–#2173 | 3 lines × 18 characters, with spaces drawn as blank columns (`01`) like the original. Stat lines use `Phys/Fire/Cold/Thun/Dark/Holy`. |
| Tarot descriptions | #1649–#1670 | A quoted title line plus 2 lines. |
| Battle-menu help | #2204–#2262 | A narrow window: **10 columns × 3 lines** (the width of the Japanese). Check that nothing spills over. |
| System confirmations | #2174–#2203 | Printed by the same script op as the save prompt, at 18 columns × 3 lines. |
| Menu help lines | #1587–#1626, #3945 | 18 columns, 2–3 lines. #3945 ("Change a character's class.") was missing from the last build. Its help line was stored past the end of its list, so it showed garbage. |
| Name entry | #1586 + `tools/fixed_text.py` | The confirmation (`Is "Name" right?`), the a–z page, the tabs, Yes/No. |
| Choices inside dialogue (`A) … / B) …`) | e.g. #84, #179, #329, #1140 | Each option fits in 16 characters. Check that the cursor still lines up. |
| **New: system messages built around a value** | #3946–#3991 | Shop, dispatch, revive, formation, item, treasure, town liberated/lost and encounter messages. The game copies them into a buffer around a name, item, town or number (`{X}`), and the copy lengths in the code were changed to fit the English. Check that the whole sentence shows, with nothing missing or doubled. Good places to test: buy with no money, revive a character, liberate a town, find buried treasure, class change. |
| **New: stat change message** | #3999–#4003 | "Character's STR / 3 points up." and "Chaos Frame / 2 points down." The game writes the digit into the middle of the text. Check that the number lands in the right place. |
| **New: status screen** | #4004–#4016, attacks #4023–#4162 | F:/B: attack names (8 cells), MOVE type (4 cells plus 3 blank), "Unit 1", "Leader: No/OK". |
| **New: tactics, battlefield, day/night** | #4018–#4022, #4163–#4183 | Battle screen. Day/night are sun/moon icons (☼ ☾) in a 2-cell field. The battlefield name is 7 cells. |
| **New: title menu, options, save areas** | #4184–#4227 | Labels are 10 cells and descriptions are 2 × 14, padded with blanks like the Japanese. |
| **New: settlement screen** | #4017 | Finances / Grants / Costs / Reserve / Total. Each label keeps its original spot and length. |
| **New: town names** | #4228–#4432 | 8 cells each, shown on the map and in messages like "Fortress Hind / was liberated." The town type ("Fortress ") goes right in front of the name. |
| **New: save messages, persuasion, NGP warning** | #3992–#3998 | Drawn at a fixed spot with a set number of tiles. The English was kept within the original tile count. |
| **New: menu captions** | #4434–#4478, #4479 | The caption under the menu icons and the unit-list tag (SENT) are pictures, redrawn by `tools/menu_labels.py`. Check that each one is readable and centred, and look for any caption still in Japanese (a menu I haven't seen). |
| **New: Yes/No questions** | e.g. #76, #169, #255 | Yes/No is drawn on line 3 of the last box, so that box holds 2 lines. Check the text and Yes/No no longer overlap. |
| **New: tarot card drawn** | #4433 | `"Death" card drawn.` after freeing a town. |
| **New: title cards** | #4480–#4515 | Chapter and area-name cards, redrawn as pictures. Check the lettering is centred and the blue outline looks right. |
| **New: tarot questions over 2 boxes** | #1540–#1582 | Check that the answers still appear after the second box. |

## 2. Not translated yet

- **Link-cable menus** (0xE14F8–0xE5481): skipped on purpose. The link-cable labels on the title menu (Link, Versus, Give Char, Get Char) *are* translated.
- **Title logo:** kept as the original artwork, on purpose.
- **Message #500:** a 3-byte "…" (the pause before the Holy Rod is handed over), too short to relocate. Instead, the "…" glyph (byte DA) was redrawn as three baseline dots, so it matches English "..." (`REDRAW` in `tools/font.py`).
- **Katakana page of the name entry:** unchanged on purpose (it still works).
- **"OK…A  NG…B" on the save screen:** already Latin letters, so left as is.

Anything still in hiragana shows as scrambled lowercase letters, because the hiragana glyphs were replaced by the English font. If you see scrambled lowercase anywhere, send a screenshot: that text was missed.

## 3. Uncertain translations

- **#3966 (0x16122):** ストックには、つかえません → "Can't use this from the stock." It's unclear whether "stock" means the item stock or characters held in reserve.
- **Attacks:** ドラッグイーター (DrugEatr: drug or drag?) and パンプフォール (PumpFall: pumpkin drop?).
- **Tactics:** Best/Strong/Leader/Weak follow the SNES game, not the literal Japanese. The full meaning is in each entry's Full English and note (#4018–#4021).
- **Movement types:** 4-letter words; the meaning is in each entry's note (#4007–#4016).

## 4. Romanizations I chose (no official English release exists)

Check `script/glossary.json`. These are the less certain ones:
- **Characters:** Vanya, Yorkleif, Orosof, Marenoa, Birkin, Rhode, Daram.
- **Places and items:** Rard, Gring, Colombin, Polruk, Brunn, Highhandra, Rochefort (the church, ロシュフォル).
- **Town names (#4228–#4432):** romanized from katakana.
  - Some are real places and use their real spelling: Peshawar, Anatolia, Bahia, Erzurum, Kayseri, Antalya, Gaziantep, Mato Grosso, Minas Gerais, Sergipe, Roraima, Alagoas, Goias, Maranhao and Krasnodar.
  - The rest are my best reading: Kakarko, Ijiriko, Jipis, Sietch, Hidecker, Kattoito and others.
- **Mythological unit names:** mostly Greek/Roman names, shortened to 8 letters.
