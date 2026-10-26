import AppKit
import CryptoKit
import Foundation

/// messages.json, loaded once and saved back atomically. This app is the only writer.
@MainActor
final class Store: ObservableObject {
    enum ReviewFilter: String, CaseIterable { case any = "Any", notReviewed = "Not reviewed", reviewed = "Reviewed" }
    enum Chip: String, CaseIterable { case untranslated = "Untranslated", doesntFit = "Doesn't fit", edited = "Edited", note = "Has a note", shortened = "Shortened" }

    let root: URL
    var fileURL: URL { root.appendingPathComponent("script/messages.json") }

    @Published private(set) var entries: [Entry] = []
    @Published private(set) var selection: Int?
    @Published var search = ""
    @Published var category: Entry.Category = .all
    @Published var reviewFilter: ReviewFilter = .notReviewed
    @Published var chips: Set<Chip> = []
    @Published var focusedBox = 0
    @Published private(set) var savedAt: Date?
    @Published var errorMessage: String?
    @Published private(set) var notFitting: Set<Int> = []

    @Published var jpFont: GameFont?
    @Published var enFont: GameFont?
    private(set) var singleBox: Set<Int> = []
    var helper: Helper?

    private var index: [Int: Int] = [:]
    private var loadedEN: [Int: String] = [:]
    private var sticky: Int?  // stays in a filtered list until you move on
    private var dirty = false
    private var fileDate: Date?

    init(root: URL) {
        self.root = root
    }

    // MARK: Loading and saving

    func load() {
        do {
            let data = try Data(contentsOf: fileURL)
            guard case .array(let items) = try JSONParser.parse(data) else { throw JSONParseError(offset: 0, message: "not a list") }
            entries = items.compactMap { $0.object }.map(Entry.init)
            for i in entries.indices where entries[i].obj["reviewed"] == nil {  // first run on an old file
                entries[i].obj["literal"] = entries[i].obj["literal"] ?? .string("")
                entries[i].obj["note"] = entries[i].obj["note"] ?? .string("")
                entries[i].reviewed = false
            }
            reindex()
            loadedEN = Dictionary(uniqueKeysWithValues: entries.map { ($0.id, $0.en) })
            fileDate = modificationDate()
            dirty = false
        } catch {
            errorMessage = "Couldn't read messages.json: \(error)"
        }
    }

    func startHelper() async {
        do {
            let h = try Helper(root: root)
            helper = h
            let r = try await h.request(["cmd": "init"])
            if let e = r["error"] as? String { throw NSError(domain: "Helper", code: 2, userInfo: [NSLocalizedDescriptionKey: e]) }
            jpFont = GameFont(r["jp_font"] as? [String] ?? [])
            enFont = GameFont(r["en_font"] as? [String] ?? [])
            singleBox = Set(r["single_box"] as? [Int] ?? [])
            if let t = r["typeable"] as? String { Fit.typeable = Set(t) }
            if let x = r["x_width"] as? [String: Int] { Fit.xWidth = x }
            if let l = r["label_widths"] as? [String: Int] {
                Fit.labelWidths = Dictionary(uniqueKeysWithValues: l.compactMap { k, v in k.first.map { ($0, v) } })
            }
            Fit.labelGap = r["label_gap"] as? Int ?? 1
            Fit.labelMax = r["label_max"] as? Int ?? 62
            Fit.nameWidth = r["name_width"] as? Int ?? 8
            Fit.numWidth = r["num_width"] as? Int ?? 5
            notFitting = Set(entries.filter { !spec(for: $0).fits($0) }.map(\.id))
            objectWillChange.send()
        } catch {
            errorMessage = "The preview helper (tools/studio_helper.py) didn't start: \(error.localizedDescription)"
        }
    }

    private func reindex() {
        index = Dictionary(uniqueKeysWithValues: entries.enumerated().map { ($1.id, $0) })
    }

    private func modificationDate() -> Date? {
        (try? FileManager.default.attributesOfItem(atPath: fileURL.path))?[.modificationDate] as? Date
    }

    /// Saves if anything changed. Returns false if the user chose not to overwrite an outside change.
    @discardableResult
    func save(force: Bool = false) -> Bool {
        guard dirty || force else { return true }
        if let known = fileDate, let now = modificationDate(), now > known.addingTimeInterval(0.5) {
            let alert = NSAlert()
            alert.messageText = "messages.json was changed outside Translation Studio"
            alert.informativeText = "Overwrite it with what's in the app, or reload it and lose the app's unsaved changes?"
            alert.addButton(withTitle: "Overwrite")
            alert.addButton(withTitle: "Reload")
            if alert.runModal() != .alertFirstButtonReturn {
                load()
                return false
            }
        }
        let text = JSONWriter.write(.array(entries.map { .object($0.obj) }))
        do {
            try Data(text.utf8).write(to: fileURL, options: .atomic)
            fileDate = modificationDate()
            dirty = false
            savedAt = Date()
            return true
        } catch {
            errorMessage = "Couldn't save messages.json: \(error.localizedDescription)"
            return false
        }
    }

    // MARK: Selection and review marks

    func entry(_ id: Int) -> Entry? { index[id].map { entries[$0] } }

    var selected: Entry? { selection.flatMap(entry) }

    func select(_ id: Int?) {
        guard id != selection else { return }
        save()
        sticky = id
        selection = id
        focusedBox = 0
        if let id, let i = index[id], !entries[i].reviewed {
            entries[i].reviewed = true
            dirty = true
        }
    }

    func setReviewed(_ value: Bool) {
        guard let id = selection, let i = index[id] else { return }
        entries[i].reviewed = value
        dirty = true
    }

    func step(_ delta: Int) {
        let list = filtered
        guard !list.isEmpty else { return }
        let pos = list.firstIndex { $0.id == selection } ?? (delta > 0 ? -1 : list.count)
        let next = min(max(pos + delta, 0), list.count - 1)
        select(list[next].id)
    }

    // MARK: Editing

    func update(_ id: Int, _ change: (inout Entry) -> Void) {
        guard let i = index[id] else { return }
        var e = entries[i]
        change(&e)
        guard e != entries[i] else { return }
        entries[i] = e
        dirty = true
        if spec(for: e).fits(e) { notFitting.remove(id) } else { notFitting.insert(id) }
    }

    func spec(for e: Entry) -> EditorSpec { EditorSpec.of(e, singleBox: singleBox) }

    func isEdited(_ e: Entry) -> Bool { loadedEN[e.id] != e.en }

    // MARK: The list

    var filtered: [Entry] {
        let q = search.trimmingCharacters(in: .whitespaces)
        var idQuery: Int?
        if q.hasPrefix("#") { idQuery = Int(q.dropFirst()) } else if !q.isEmpty, q.allSatisfy(\.isNumber) { idQuery = Int(q) }
        let needle = q.lowercased()
        return entries.filter { e in
            if category != .all && e.category != category { return false }
            if let idQuery { return e.id == idQuery }
            if !needle.isEmpty {
                // Searching always shows reviewed and unreviewed messages alike.
                guard e.jp.lowercased().contains(needle) || e.en.lowercased().contains(needle)
                    || e.literal.lowercased().contains(needle) || e.note.lowercased().contains(needle) else { return false }
            } else if e.id != sticky {
                switch reviewFilter {
                case .notReviewed: if e.reviewed { return false }
                case .reviewed: if !e.reviewed { return false }
                case .any: break
                }
            }
            for c in chips {
                switch c {
                case .untranslated: if e.isTranslated { return false }
                case .doesntFit: if !notFitting.contains(e.id) { return false }
                case .edited: if !isEdited(e) { return false }
                case .note: if e.note.isEmpty { return false }
                case .shortened: if !e.isShortened { return false }
                }
            }
            return true
        }
    }

    func count(_ chip: Chip) -> Int {
        switch chip {
        case .untranslated: return entries.filter { !$0.isTranslated }.count
        case .doesntFit: return notFitting.count
        case .edited: return entries.filter(isEdited).count
        case .note: return entries.filter { !$0.note.isEmpty }.count
        case .shortened: return entries.filter(\.isShortened).count
        }
    }

    var reviewedCount: Int { entries.filter(\.reviewed).count }

    // MARK: Merging a ROM scan (tools/dump_script.py writes script/rom_scan.json)

    func mergeROMScan() -> String {
        let url = root.appendingPathComponent("script/rom_scan.json")
        guard let data = try? Data(contentsOf: url), case .array(let items)? = try? JSONParser.parse(data) else {
            return "No script/rom_scan.json to merge. Run python3 tools/dump_script.py first."
        }
        let keep: Set<String> = ["id", "en", "literal", "note", "reviewed"]
        func key(_ o: JObject) -> String { "\(Entry.text(o["block"]))|\(o["kind"]?.string ?? "")|\(o["offset"]?.string ?? "")" }
        var byKey: [String: Int] = [:]
        for (i, e) in entries.enumerated() { byKey[key(e.obj)] = i }
        var updated = 0, added = 0
        var nextID = (entries.map(\.id).max() ?? -1) + 1
        for case .object(let scan) in items {
            if let i = byKey[key(scan)] {
                var o = entries[i].obj
                for (k, v) in scan.pairs where !keep.contains(k) { o[k] = v }
                if o != entries[i].obj { entries[i].obj = o; updated += 1 }
            } else {
                var o = scan
                o["id"] = .number(String(nextID))
                nextID += 1
                o["literal"] = .string("")
                o["note"] = .string("")
                o["reviewed"] = .bool(false)
                entries.append(Entry(o))
                added += 1
            }
        }
        reindex()
        dirty = updated + added > 0
        save()
        return "Merged the ROM scan: \(updated) entries refreshed, \(added) new. Translations, notes and review marks were kept."
    }

    // MARK: Suggestions (script/suggestions.json, written by Claude for you to accept or reject)

    struct Suggestion: Identifiable {
        let id = UUID()
        let entryID: Int
        let field: String
        let value: JSON
        let reason: String
    }

    var suggestionsURL: URL { root.appendingPathComponent("script/suggestions.json") }

    func loadSuggestions() -> [Suggestion] {
        guard let data = try? Data(contentsOf: suggestionsURL), case .array(let items)? = try? JSONParser.parse(data) else { return [] }
        return items.compactMap { item in
            guard let o = item.object, let id = o["id"]?.int, let field = o["field"]?.string, let v = o["value"],
                  ["en", "literal", "note"].contains(field) else { return nil }
            return Suggestion(entryID: id, field: field, value: v, reason: o["reason"]?.string ?? "")
        }
    }

    func resolve(_ s: Suggestion, accept: Bool, remaining: [Suggestion]) {
        if accept {
            update(s.entryID) { $0.obj[s.field] = s.value }
            save()
        }
        let rest = remaining.filter { $0.id != s.id }
        if rest.isEmpty {
            try? FileManager.default.removeItem(at: suggestionsURL)
        } else {
            let arr = JSON.array(rest.map { r in
                var o = JObject()
                o["id"] = .number(String(r.entryID)); o["field"] = .string(r.field); o["value"] = r.value; o["reason"] = .string(r.reason)
                return .object(o)
            })
            try? Data(JSONWriter.write(arr).utf8).write(to: suggestionsURL, options: .atomic)
        }
    }

    // MARK: Patch

    var builtROM: URL { root.appendingPathComponent("build/ogre_battle_en.ngc") }
    var builtIPS: URL { root.appendingPathComponent("build/ogre_battle_en.ips") }
    var originalROM: URL { root.appendingPathComponent("Densetsu no Ogre Battle Gaiden - Zenobia no Ouji.ngc") }

    func openInNgpCraft() {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/open")
        p.arguments = ["-a", "NgpCraftEmulator", builtROM.path]
        do {
            try p.run()
            p.waitUntilExit()
            if p.terminationStatus != 0 { errorMessage = "Couldn't open NgpCraft. Is it in Applications?" }
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    /// Applies build/ogre_battle_en.ips to a ROM the user picks, after checking it's the right original.
    func applyPatchToROM() {
        let open = NSOpenPanel()
        open.message = "Choose an unpatched Densetsu no Ogre Battle Gaiden ROM"
        guard open.runModal() == .OK, let src = open.url else { return }
        do {
            let rom = try Data(contentsOf: src)
            let expected = try Data(contentsOf: originalROM)
            guard SHA256.hash(data: rom) == SHA256.hash(data: expected) else {
                errorMessage = "That file isn't the original ROM this patch was made for (its checksum differs)."
                return
            }
            let patched = try IPS.apply(try Data(contentsOf: builtIPS), to: rom)
            let save = NSSavePanel()
            save.nameFieldStringValue = "Ogre Battle Gaiden (English).ngc"
            save.directoryURL = src.deletingLastPathComponent()
            guard save.runModal() == .OK, let dst = save.url else { return }
            try patched.write(to: dst, options: .atomic)
        } catch {
            errorMessage = "Couldn't apply the patch: \(error.localizedDescription)"
        }
    }
}

enum IPS {
    struct Bad: LocalizedError { var errorDescription: String? { "The .ips file is damaged." } }

    static func apply(_ ips: Data, to rom: Data) throws -> Data {
        let p = [UInt8](ips)
        var out = [UInt8](rom)
        guard p.count >= 8, Array(p[0..<5]) == Array("PATCH".utf8) else { throw Bad() }
        var i = 5
        while i + 3 <= p.count {
            if Array(p[i..<i + 3]) == Array("EOF".utf8) { return Data(out) }
            let off = Int(p[i]) << 16 | Int(p[i + 1]) << 8 | Int(p[i + 2])
            guard i + 5 <= p.count else { throw Bad() }
            let size = Int(p[i + 3]) << 8 | Int(p[i + 4])
            i += 5
            var bytes: [UInt8]
            if size == 0 {
                guard i + 3 <= p.count else { throw Bad() }
                let n = Int(p[i]) << 8 | Int(p[i + 1])
                bytes = Array(repeating: p[i + 2], count: n)
                i += 3
            } else {
                guard i + size <= p.count else { throw Bad() }
                bytes = Array(p[i..<i + size])
                i += size
            }
            if off + bytes.count > out.count { out += Array(repeating: 0, count: off + bytes.count - out.count) }
            out.replaceSubrange(off..<off + bytes.count, with: bytes)
        }
        throw Bad()
    }
}
