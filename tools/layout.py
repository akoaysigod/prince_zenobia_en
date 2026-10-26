"""Automatic line wrapping and box splitting for English text.

Messages are written as plain text in messages.json. This module word-wraps them
to the width of their screen and starts a new box ({PAGE}) every BOX_LINES lines.
An explicit \\n or {PAGE} in the text still forces a break.
"""
import re

STORY_WIDTH = 16   # stage dialogue box
WIDE_WIDTH = 18    # tarot intro and system screens
ANSWER_WIDTH = 14  # tarot answers: a blank column, the letter, ") ", then 14 letters = the window's 18 columns
ANSWER_PREFIX = ') '  # drawn after the A/B/C letter
BOX_LINES = 3
NAME_LEN = 8       # longest player name; {NAME} is counted at this width
NUM_LEN = 5        # widest number shown by {NUM}
PAGE = '{PAGE}'
TAG_WIDTH = {'{01}': 1, '{NAME}': NAME_LEN, '{NUM}': NUM_LEN}  # {01} skips one column (a blank)
TAG_RE = re.compile(r'\{01\}|\{NAME\}|\{NUM\}|\{X\}')
X_WIDTH = {'number': NUM_LEN, 'name': NAME_LEN, 'class': 8, 'item': 8, 'town': 17, 'tarot': 8}  # {X} in native text


def width_of(text, x_width=8):
    """On-screen width of text, counting tags at their displayed size ({X} at x_width)."""
    return len(TAG_RE.sub('', text)) + sum(TAG_WIDTH.get(t, x_width) for t in TAG_RE.findall(text))


def entry_width(m):
    if 'width' in m:
        return m['width']
    if m['kind'] == 'choices':
        return ANSWER_WIDTH
    return STORY_WIDTH if isinstance(m['block'], int) else WIDE_WIDTH


def wrap(paragraph, width, x_width=8):
    """Greedy word wrap. A word longer than width stays on its own line (check_width flags it)."""
    lines, line = [], ''
    for word in paragraph.split():
        candidate = f'{line} {word}' if line else word
        if line and width_of(candidate, x_width) > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


SENTENCE_END = re.compile(r'(?<=[.!?])\s+|(?<=…)\s+(?=[A-Z…"])')


def paginate(text, width):
    """Split text into boxes of at most BOX_LINES wrapped lines.

    Prefers starting each new box at a sentence, unless that would need more
    boxes than plain word-by-word filling.
    """
    plain = wrap(text, width)
    plain = [plain[i:i + BOX_LINES] for i in range(0, len(plain), BOX_LINES)]
    by_sentence = _paginate_sentences(text, width)
    return by_sentence if len(by_sentence) <= len(plain) else plain


def _paginate_sentences(text, width):
    """Pack whole sentences into each box while they fit; an overlong sentence continues word by word."""
    boxes, current = [], ''
    for sentence in SENTENCE_END.split(text):
        trial = f'{current} {sentence}' if current else sentence
        if len(wrap(trial, width)) <= BOX_LINES:
            current = trial
            continue
        if current:
            boxes.append(wrap(current, width))
        lines = wrap(sentence, width)
        while len(lines) > BOX_LINES:
            boxes.append(lines[:BOX_LINES])
            lines = wrap(' '.join(lines[BOX_LINES:]), width)
        current = ' '.join(lines)
    if current:
        boxes.append(wrap(current, width))
    return boxes


def layout(m, can_page=True):
    """Return m's English as game text: wrapped lines joined by \\n, boxes joined by {PAGE}.

    can_page=False keeps everything in one box (used for tarot questions, whose
    answers are drawn right after them); overflow is then left for check_width to flag.
    """
    en = m['en']
    if m['kind'] == 'choices':
        en = '\n'.join(en) if isinstance(en, list) else en
        return en.replace('…', '...')
    en = en.replace('…', '...')  # house style: three periods, not the ellipsis glyph
    if m['kind'] == 'fixed' or (m['kind'] == 'native' and m['mode'] != 'reloc'):
        return en  # fixed screen position or fixed-width fields: laid out by hand
    if m['kind'] == 'native':  # one box; wrap each line, counting {X} at its width
        xw = X_WIDTH.get(m.get('x'), 8)
        return '\n'.join(l for part in en.split('\n') for l in (wrap(part, m['width'], xw) or ['']))
    width = entry_width(m)
    boxes = []
    for chunk in en.split(PAGE):
        chunk = chunk.rstrip('\n')
        if can_page and '\n' not in chunk:
            boxes += paginate(chunk, width) or [[]]
            continue
        # explicit line breaks, or a single-box message: wrap each line, no automatic boxes
        lines = [l for part in chunk.split('\n') for l in (wrap(part, width) or [''])]
        if can_page:
            boxes += [lines[i:i + BOX_LINES] for i in range(0, len(lines), BOX_LINES)] or [[]]
        else:
            boxes.append(lines)
    text = PAGE.join('\n'.join(b) for b in boxes)
    if m['jp'].endswith('\n'):  # keep the original's trailing line break
        text += '\n'
    return text


def no_page_ids(msgs):
    """Messages that must stay in one box. None at the moment: tarot questions used to be
    kept to one box because the answers follow them, but extra boxes work (the answer
    list is drawn after the last one)."""
    return set()


def last_box_lines(m):
    """Lines the last box may use. A yes/no question (terminator FC) draws Yes/No on line 3."""
    return 2 if m['kind'] == 'message' and m.get('terminator') == 'FC' else BOX_LINES
