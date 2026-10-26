# How to change a translation

## Use Translation Studio
Build it once with `sh app/build.sh`, then open `app/build/Translation Studio.app`.

- **Translation Studio is the only thing that edits `script/messages.json`.** Don't edit the file by hand.
- **Saving:** it saves when you switch messages, before every build, and when you quit.
- **Review marks:** opening a message marks it reviewed. Use "Mark as not reviewed" (⌘U) to come back to it later.
- **Search:** searching by text or `#1234` always shows reviewed and unreviewed messages.
- **In-game English:** edited one box at a time, each exactly the game's size. You can't type past a limit. ⌘↩ splits a box at the cursor.
- **Patch menu:**
  - **Build Patch (⌘B):** runs `tools/insert.py` and lists any warnings; click one to open that message.
  - **Open in NgpCraft:** loads the built ROM in NgpCraft.
  - **Apply Patch to a ROM…:** patches a clean ROM you pick.
  - **Merge ROM Scan:** brings in a fresh `python3 tools/dump_script.py` scan (`script/rom_scan.json`) without touching translations.
  - **Review Suggestions:** shows changes Claude has proposed in `script/suggestions.json`, to accept or reject one by one.

The rest of this file describes the rules behind each kind of entry. The app enforces them as you type.

## 1. Find the message
In Translation Studio, search for the Japanese, the English or `#47`.

## 2. The entry in `script/messages.json`
For reference, an entry looks like this:

```json
{
 "id": 47,
 "block": 0,
 "kind": "message",
 "offset": "0645A3",
 "length": 52,
 "terminator": "FE",
 "jp": "エストラーダ「うむ。\nこまったことがあれば\nまたしらせてくれ。",
 "en": "Estrada: Good. If there's any trouble, say so.",
 "literal": "Estrada: Hm. If you are ever in trouble, let me know again.",
 "note": "",
 "reviewed": false
},
```

- `en` is the in-game English, the only text that goes into the patch.
- `literal` is the full, unshortened translation, for reference.
- `note` is your own note.
- `reviewed` is the review mark.
- Everything else is build data.

## 3. The in-game text
- **Line width:** text is wrapped on whole words:
  - **16 characters** per line for story dialogue;
  - **18 characters** for the tarot intro and system screens.
- **Boxes:** each box holds 3 lines. A message with several boxes stores them separated by `{PAGE}`. Translation Studio shows one editor per box.
- **Line breaks:** `\n` (Return in the app) forces a line break.
- **Yes/No questions** (`"terminator": "FC"`): the game draws Yes/No on line 3 of the last box, so the last box holds only **2 lines**. Earlier boxes still hold 3.

Special codes:
- `{NAME}` is the player's name. It's counted as 8 characters, the longest name allowed.
- `{01}` is a blank column; the Japanese uses it as the space between sentences. Don't use it in English: type a normal space instead.

Allowed characters (IBM EGA 8x8 font):
- `A-Z`, `a-z`, digits `0-9` and spaces
- `' " ; ( ) - * # @ _ < > [ ] ~`
- `. , ! ? : / + = % &`
- For an ellipsis, type three periods `...`. A `…` character is converted to `...` automatically.

To add a character that isn't listed, add it to `SLOTS` in `tools/font.py`. The free slots run up to byte `75`.

Style:
- Write normal sentence case with contractions ("We're off to hunt bandits.").
- Start a speaker's line with `Name: `, for example `Kain: {NAME}!` or `{NAME}: What?`. When a speech runs into a second box, that box simply continues with no prefix.
- Put titles and terms in `"double quotes"`. Inside the JSON, a double quote has to be typed as `\"`, for example `"en": "The \"Key of Glory\"…"`.
- Don't use the Japanese brackets `「 」 『 』` or `・`.

### Tarot intro (entries #1532–#1583, `"block": "tarot"`)
- A question can use several boxes, like any other message. The answers appear after its last box.
- Answer lists (`"kind": "choices"`) are a list of exactly three answers, with at most **14 characters** each:
  ```json
  "en": ["Poison", "Wealth potion", "Elixir of life"]
  ```
  `A) `, `B) ` and `C) ` are added automatically, so don't type them.

### Exception: the church choice (#84)
- This is a choice inside a normal message, so it keeps a `\n` between the two options:
  `"A) They must pay\nB) You're right…"`

### System text (`"block": "system"`, from #1584)
- These are screens outside the story, such as the save-area prompt.
- `"kind": "string"` entries must fit in one box.
- `"kind": "fixed"` entries sit at a fixed spot on screen and are not wrapped, so use `\n` for line breaks.
  - Example: #1586, the name-entry confirmation, ` Is "{NAME}" \n         right?\n      `.
  - The text before `{NAME}` must be exactly as many characters as `"name_at"` says (5 here).
  - **Keep #1586's exact shape**:
    - 5 characters, the name, 2 characters, a line break;
    - 9 spaces, then 6 characters, a line break;
    - then 6 spaces.
    - Why it matters: the game gives every character, spaces included, its own video tile. Some empty cells in the box show tiles from that same range. The 9 spaces keep the empty cells after a short name blank, and the last 6 spaces blank the cells left of OK/No.
    - The total must stay at or under 36 tiles with an 8-letter name, or it runs into the OK/No tiles.

### Menu help, tarot and item descriptions (`"kind": "table"`)
- Covers the menu help (#1587–#1626), tarot descriptions (#1649–#1670) and item descriptions (#1985–#2173).
- They wrap at **18 characters**, and each entry allows up to `"max_lines"` lines, the same as the Japanese.
- Where there's a title or stat line, put it on its own line with `\n`:
  - `"\"Use Item\"\nUse an item you carry."`
  - `"A crescent-shaped ice sword.\nSTR+3"`

### Names (`"kind": "name"`)
- Covers tarot card names (#1627–#1648), town types (#1671–#1678), classes (#1679–#1795), items (#1796–#1984) and unit/character names (#2263–#3944).
- At most `"max_len"` characters, currently 8. Names aren't wrapped.
- Town types are printed straight in front of a town name, so they end with a space (`"Fortress "`). Their limit is 9.
- Item entries also carry a `"header"` (the item's data bytes). Leave it alone.

### More system text and battle help
- **System confirmations** (`"kind": "string"`, #2174–#2203): one box, 18 characters × 3 lines.
- **Battle-menu help** (`"kind": "pstring"`, #2204–#2262): a narrow window. Wraps at `"width"` (10) × 3 lines.

### Text drawn by the game's own code (`"kind": "native"`, from #3946)
These come in four `"mode"`s.

- **`reloc`**: system messages (#3946–#3991). Write them like a story message: they wrap at 18 characters and must fit in **one box of 3 lines**.
  - Some contain `{X}`. That's where the game inserts a value; `"x"` says what it is:
    - `name`, counted as 8;
    - `class`, 8;
    - `item`, 8;
    - `town`, 17 (town type + name);
    - `number`, 5.
  - Keep exactly as many `{X}` as the entry has, in a place where English can follow it. The game builds these in pieces around the value, and most pieces can be any length. A few small ones are limited:
    - The text before `{X}` in the two costs ("Cost: ") and in "Found \"" can be at most 7 characters.
    - The text after `{X}` in the treasure message ("\"!") can be at most 5.
    - The item obtained / given up messages (#3990, #3991) need exactly 1 character before `{X}`.
    - The build stops with a message if a piece doesn't fit.
  - #3990 and #3991 share one length in the game's code. The text after `{X}` must be the same length in both. Pad the shorter one with a space if needed.
- **`slots`**: fixed-width fields. These are:
  - attack names, 8 cells;
  - movement types, 4;
  - battle field names, 7;
  - town names, 8;
  - menu labels, 10;
  - menu descriptions, 2 lines × 14.
  - Each line of `"en"` fills one field. `"slot_widths"` gives the sizes. Shorter text is padded automatically, and longer text is cut off with a warning.
  - To leave a field blank, use a single space; an empty `"en"` means "untranslated".
- **`free`**: short texts drawn at a fixed spot (#3992–#3998), such as the save messages.
  - They are rewritten in place, so the whole text (lines + 2) must fit in `"length"` bytes.
  - If there's a `"max_tiles"`, the number of letters (spaces don't count) can't go above it.
  - Never leave a line empty; use `{01}` for a blank line.
- **`stat`**: the five pieces of the stat change message (#3999–#4003). The game shows them as:
  - `[prefix][stat name][amount][up or down]`
  - `[chaos][amount][up or down]`
  - The `{X}` in "amount" is where the game writes the digit.

### Menu captions (`"kind": "label"`, `"block": "menu_labels"`)
- The caption under the menu icons ("ITEMS", "ORGANIZE"…) is a small picture, not text. There are 45, stored at ROM 0x18112, 128 bytes each.
- The build draws the English into each picture with a small outlined font (`tools/menu_labels.py`).
- Allowed: capitals `A-Z`, digits, space and `. - / ' &`. At most `"max_px"` (62) pixels wide. Most letters are 4 pixels, plus 1 between letters.
- `"jp"` was read off the graphics by hand. An empty `"en"` keeps the Japanese picture.
- The unit-list tag はけん中 (0x14A00, copied to 0xE736A) is the same kind of entry. Only the inside of its frame is redrawn, 30 pixels wide.

### Title cards (`"kind": "card"`, `"block": "title_cards"`)
- The chapter cards (第1話 胎動…) and area-name cards (エストラーダの館…) are pictures, redrawn by `tools/title_cards.py`.
- Type a heading, a line break, then a subtitle, e.g. `CHAPTER 1\nFIRST STIRRINGS`. The heading is drawn tall, and the subtitle small, wrapped to 2 lines.
- Without a line break, the text is drawn tall and wrapped to 2 lines.
- Each line holds 12 letters. Allowed: capitals, digits, space and `. , ! ? - / ' &`.
- All 18 cards of a set share one sheet of 360 tiles. The build warns if a set needs more, which is unlikely: the current English uses 87 and 35 tiles.

**Short forms:** a shortened name keeps its full form in Full English (`literal`). To list them all, use the **Shortened** filter in Translation Studio; each row shows `short = full`.

See `REVIEW.md` for what's still untranslated and what to check on screen.

## 4. Build the patch
Use **Patch › Build Patch** (⌘B) in Translation Studio. It saves first, then runs `python3 tools/insert.py`.

- **Warnings:** if something doesn't fit, the build lists a warning with the message number. Click it to open that message.
- **Missing characters:** a character the font doesn't have stops the build with an error.
- **Success:** the build should end with `0 warnings`.

## 5. Test
Use **Open in NgpCraft**, or load `build/ogre_battle_en.ngc` in NgpCraftEmulator yourself.

Old save states hold the previous version of the game, so don't use them to check the change. Play to the line from a normal in-game save or a new game instead.

---

`tools/dump_script.py` no longer writes `messages.json` or `messages.txt`. It writes `script/rom_scan.json`, which you bring in with **Patch › Merge ROM Scan**.
