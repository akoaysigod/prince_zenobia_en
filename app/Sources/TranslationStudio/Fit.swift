import Foundation

/// The size rules for each kind of entry, mirroring tools/layout.py and tools/insert.py.
/// They decide what you're allowed to type; the build and the preview still use the Python originals.
enum Fit {
    static let page = "{PAGE}"
    static let storyWidth = 16, wideWidth = 18, answerWidth = 14, boxLines = 3
    static var nameWidth = 8, numWidth = 5
    static var xWidth: [String: Int] = ["number": 5, "name": 8, "class": 8, "item": 8, "town": 17, "tarot": 8]
    /// Characters the English font can draw (filled in from the helper).
    /// Menu captions (pictures): pixel width of each letter, the gap between letters, and the limit.
    static var labelWidths: [Character: Int] = [:]
    static var labelGap = 1, labelMax = 62
    static var typeable = Set(" !\"#%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[]_abcdefghijklmnopqrstuvwxyz~…")

    static let tags = ["{01}", "{NAME}", "{NUM}", "{X}"]
    private static let tagRE = try! NSRegularExpression(pattern: #"\{01\}|\{NAME\}|\{NUM\}|\{X\}"#)

    /// On-screen width of text, counting tags at their displayed size ({X} at xw).
    static func widthOf(_ text: String, xw: Int = 8) -> Int {
        let t = text.replacingOccurrences(of: "…", with: "...")
        let ns = t as NSString
        var w = 0, last = 0
        for m in tagRE.matches(in: t, range: NSRange(location: 0, length: ns.length)) {
            w += ns.substring(with: NSRange(location: last, length: m.range.location - last)).unicodeScalars.count
            switch ns.substring(with: m.range) {
            case "{01}": w += 1
            case "{NAME}": w += nameWidth
            case "{NUM}": w += numWidth
            default: w += xw
            }
            last = m.range.location + m.range.length
        }
        return w + ns.substring(from: last).unicodeScalars.count
    }

    /// Greedy word wrap, as layout.wrap.
    static func wrap(_ paragraph: String, width: Int, xw: Int = 8) -> [String] {
        var lines: [String] = [], line = ""
        for word in paragraph.split(whereSeparator: { $0.isWhitespace }).map(String.init) {
            let candidate = line.isEmpty ? word : line + " " + word
            if !line.isEmpty && widthOf(candidate, xw: xw) > width {
                lines.append(line)
                line = word
            } else {
                line = candidate
            }
        }
        if !line.isEmpty { lines.append(line) }
        return lines
    }

    /// Lines a box's text takes: explicit \n breaks, each part word-wrapped.
    static func boxLines(_ text: String, width: Int, xw: Int) -> [String] {
        text.components(separatedBy: "\n").flatMap { part -> [String] in
            let w = wrap(part, width: width, xw: xw)
            return w.isEmpty ? [""] : w
        }
    }

    static func count(_ tag: String, in text: String) -> Int { text.components(separatedBy: tag).count - 1 }

    /// Pixel width of a menu caption; nil if a letter isn't in the caption font.
    static func labelWidth(_ text: String) -> Int? {
        var w = 0
        for c in text { guard let a = labelWidths[c] else { return nil }; w += a }
        return w + labelGap * max(text.count - 1, 0)
    }

    /// A title card's lines as (text, tall), as tools/title_cards.lines_of: with a line break, the
    /// first line is a tall heading and the rest is small text; without, it's all tall.
    static func cardLines(_ text: String, width: Int) -> [(String, Bool)] {
        if let nl = text.firstIndex(of: "\n") {
            let head = text[..<nl].trimmingCharacters(in: .whitespaces)
            let rest = text[text.index(after: nl)...].components(separatedBy: "\n")
            return [(head, true)] + rest.flatMap { cardWrap($0, width: width) }.map { ($0, false) }
        }
        return cardWrap(text, width: width).map { ($0, true) }
    }

    /// Word wrap by letter count (every letter takes one 8-pixel cell on a card).
    static func cardWrap(_ text: String, width: Int) -> [String] {
        var lines: [String] = [], line = ""
        for w in text.split(separator: " ").map(String.init) {
            let cand = line.isEmpty ? w : line + " " + w
            if !line.isEmpty && cand.count > width { lines.append(line); line = w } else { line = cand }
        }
        if !line.isEmpty { lines.append(line) }
        return lines
    }

    /// Every character is drawable, once whole tags are taken out.
    static func drawable(_ text: String, allowNewline: Bool) -> Bool {
        let stripped = tagRE.stringByReplacingMatches(in: text, range: NSRange(location: 0, length: (text as NSString).length), withTemplate: "")
        return stripped.allSatisfy { typeable.contains($0) || (allowNewline && $0 == "\n") }
    }
}

/// How an entry is edited, and its limits.
enum EditorSpec: Equatable {
    case boxes(width: Int, lines: Int, lastLines: Int, xw: Int, canPage: Bool)
    case label(maxPx: Int)
    case card(width: Int)
    case choices(width: Int)
    case name(maxLen: Int)
    case slots(widths: [Int])
    case free(length: Int, maxTiles: Int?)
    case plain

    static func of(_ e: Entry, singleBox: Set<Int>) -> EditorSpec {
        let wide = e.blockNumber == nil ? Fit.wideWidth : Fit.storyWidth
        switch e.kind {
        case "message":
            // A yes/no question (terminator FC) draws Yes/No on the last box's third line.
            return .boxes(width: e.width ?? wide, lines: Fit.boxLines, lastLines: e.terminator == "FC" ? 2 : Fit.boxLines,
                          xw: 8, canPage: !singleBox.contains(e.id))
        case "string":
            return .boxes(width: e.width ?? wide, lines: Fit.boxLines, lastLines: Fit.boxLines, xw: 8, canPage: false)
        case "pstring", "table":
            return .boxes(width: e.width ?? wide, lines: e.maxLines ?? Fit.boxLines, lastLines: e.maxLines ?? Fit.boxLines, xw: 8, canPage: false)
        case "choices":
            return .choices(width: Fit.answerWidth)
        case "label":
            return .label(maxPx: e.maxPx ?? Fit.labelMax)
        case "card":
            return .card(width: e.obj["max_letters"]?.int ?? 12)
        case "name":
            return .name(maxLen: e.maxLen ?? 8)
        case "native":
            switch e.mode {
            case "slots": return .slots(widths: e.slotWidths)
            case "free": return .free(length: e.length, maxTiles: e.maxTiles)
            case "reloc":
                return .boxes(width: e.width ?? Fit.wideWidth, lines: e.maxLines ?? Fit.boxLines, lastLines: e.maxLines ?? Fit.boxLines,
                              xw: Fit.xWidth[e.x ?? ""] ?? 8, canPage: false)
            default: return .plain
            }
        default:
            return .plain
        }
    }

    /// Does one box's text fit?
    static func boxFits(_ text: String, width: Int, lines: Int, xw: Int) -> Bool {
        guard Fit.drawable(text, allowNewline: true) else { return false }
        let l = Fit.boxLines(text, width: width, xw: xw)
        return l.count <= lines && l.allSatisfy { Fit.widthOf($0, xw: xw) <= width }
    }

    /// Does a menu caption fit (letters in the caption font, within maxPx pixels)?
    static func labelFits(_ text: String, maxPx: Int) -> Bool {
        guard let w = Fit.labelWidth(text) else { return false }
        return w <= maxPx
    }

    /// Does a title card fit: caption-font letters, lines of `width`, and either a tall heading
    /// plus up to 2 small lines, or up to 2 tall lines?
    static func cardFits(_ text: String, width: Int) -> Bool {
        guard text.allSatisfy({ $0 == "\n" || Fit.labelWidths[$0] != nil }) else { return false }
        let lines = Fit.cardLines(text, width: width)
        guard lines.allSatisfy({ $0.0.count <= width }) else { return false }
        let tall = lines.filter { $0.1 }.count, small = lines.count - tall
        return tall <= 2 && (tall < 2 || small == 0) && small <= 2
    }

    /// Does a single-line field fit in `width` cells?
    static func fieldFits(_ text: String, width: Int) -> Bool {
        Fit.drawable(text, allowNewline: false) && Fit.widthOf(text) <= width
    }

    /// Bytes a 'free' text takes in place: each line's characters (a tag is one byte), 00 between lines, 00 00 at the end.
    static func freeBytes(_ text: String) -> (bytes: Int, tiles: Int) {
        var bytes = 0, tiles = 0
        for line in text.components(separatedBy: "\n") {
            var rest = line
            for t in Fit.tags { let n = Fit.count(t, in: rest); bytes += n; rest = rest.replacingOccurrences(of: t, with: "") }
            bytes += rest.unicodeScalars.count
            tiles += rest.filter { $0 != " " }.count
        }
        return (bytes + max(0, text.components(separatedBy: "\n").count - 1) + 2, tiles)
    }

    /// Does the whole entry's current English fit? (Used for the "Doesn't fit" filter.)
    func fits(_ e: Entry) -> Bool {
        guard e.isTranslated else { return true }
        switch self {
        case let .boxes(width, lines, lastLines, xw, _):
            let b = e.en.components(separatedBy: Fit.page)
            return b.enumerated().allSatisfy { i, t in
                EditorSpec.boxFits(t, width: width, lines: i == b.count - 1 ? lastLines : lines, xw: xw)
            }
        case let .label(maxPx):
            return EditorSpec.labelFits(e.en, maxPx: maxPx)
        case let .card(width):
            return EditorSpec.cardFits(e.en, width: width)
        case let .choices(width):
            return e.enList.count == 3 && e.enList.allSatisfy { EditorSpec.fieldFits($0, width: width) }
        case let .name(maxLen):
            return EditorSpec.fieldFits(e.en, width: maxLen)
        case let .slots(widths):
            let parts = e.en.components(separatedBy: "\n")
            return parts.count == widths.count && zip(parts, widths).allSatisfy { EditorSpec.fieldFits($0, width: $1) }
        case let .free(length, maxTiles):
            let (b, t) = EditorSpec.freeBytes(e.en)
            return b <= length && t <= (maxTiles ?? .max)
        case .plain:
            return true
        }
    }
}
