import Foundation

/// One record of messages.json. The app only ever writes `en`, `literal`, `note` and `reviewed`;
/// every other field is build data and is saved back untouched, in its original order.
struct Entry: Identifiable, Equatable {
    var obj: JObject
    let id: Int

    init(_ obj: JObject) {
        self.obj = obj
        self.id = obj["id"]?.int ?? -1
    }

    var kind: String { obj["kind"]?.string ?? "" }
    var mode: String? { obj["mode"]?.string }
    var blockNumber: Int? { obj["block"]?.int }
    var blockName: String { obj["block"]?.string ?? "block \(blockNumber ?? 0)" }
    var offset: String { obj["offset"]?.string ?? "" }
    var x: String? { obj["x"]?.string }
    var width: Int? { obj["width"]?.int }
    var maxLines: Int? { obj["max_lines"]?.int }
    var maxLen: Int? { obj["max_len"]?.int }
    var maxTiles: Int? { obj["max_tiles"]?.int }
    var maxPx: Int? { obj["max_px"]?.int }
    var terminator: String { obj["terminator"]?.string ?? "" }
    var length: Int { obj["length"]?.int ?? 0 }
    var slotWidths: [Int] { obj["slot_widths"]?.array?.compactMap(\.int) ?? [] }

    /// Japanese as one string (answer lists joined by newlines).
    var jp: String { Entry.text(obj["jp"]) }

    var isList: Bool { obj["en"]?.array != nil }

    var en: String {
        get { Entry.text(obj["en"]) }
        set { obj["en"] = isList ? .array(newValue.components(separatedBy: "\n").map { .string($0) }) : .string(newValue) }
    }

    var enList: [String] {
        get { obj["en"]?.array?.map { $0.string ?? "" } ?? [en] }
        set { obj["en"] = .array(newValue.map { .string($0) }) }
    }

    var literal: String {
        get { Entry.text(obj["literal"]) }
        set { obj["literal"] = .string(newValue) }
    }

    var literalList: [String] {
        get { obj["literal"]?.array?.map { $0.string ?? "" } ?? [literal] }
        set { obj["literal"] = .array(newValue.map { .string($0) }) }
    }

    var note: String {
        get { obj["note"]?.string ?? "" }
        set { obj["note"] = .string(newValue) }
    }

    var reviewed: Bool {
        get { obj["reviewed"]?.bool ?? false }
        set { obj["reviewed"] = .bool(newValue) }
    }

    /// A name or fixed-width field whose in-game English is a short form of the full English
    /// (what ABBREVIATIONS.md used to list).
    var isShortened: Bool {
        guard kind == "name" || kind == "label" || kind == "card" || (kind == "native" && mode == "slots"), isTranslated, !literal.isEmpty else { return false }
        let short = en.replacingOccurrences(of: "{01}", with: "").trimmingCharacters(in: .whitespacesAndNewlines)
        let full = literal.trimmingCharacters(in: .whitespacesAndNewlines)
        return short.lowercased() != full.lowercased() && short.count < full.count
    }

    var isTranslated: Bool { !en.replacingOccurrences(of: "\n", with: "").isEmpty }

    enum Category: String, CaseIterable { case all = "All", story = "Story", system = "System", names = "Names" }

    static let nameBlocks: Set<String> = ["towns", "attacks", "battlefield", "move_type", "tactics"]

    var category: Category {
        if blockNumber != nil { return .story }
        if kind == "name" || Entry.nameBlocks.contains(blockName) { return .names }
        return .system
    }

    var kindLabel: String {
        if kind == "label" { return "Menu caption" }
        if kind == "card" { return "Title card" }
        switch category {
        case .story: return "Story"
        case .names: return "Name"
        default: return "System"
        }
    }

    static func text(_ v: JSON?) -> String {
        if let a = v?.array { return a.map { $0.string ?? "" }.joined(separator: "\n") }
        return v?.string ?? ""
    }
}
