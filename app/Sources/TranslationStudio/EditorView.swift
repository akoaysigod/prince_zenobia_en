import AppKit
import SwiftUI

/// Editor + preview for the selected message. Re-renders the preview (debounced) as you type.
struct DetailView: View {
    @EnvironmentObject var store: Store
    let entry: Entry
    @State private var result = RenderResult()

    var body: some View {
        HSplitView {
            EditorView(entry: entry)
                .frame(minWidth: 460, maxWidth: .infinity, maxHeight: .infinity)
            PreviewView(entry: entry, result: result)
                .frame(minWidth: 380, idealWidth: 540, maxWidth: .infinity, maxHeight: .infinity)
        }
        .task(id: "\(entry.id)|\(entry.en)") {
            try? await Task.sleep(for: .milliseconds(60))
            guard !Task.isCancelled, let h = store.helper else { return }
            let r = await h.render(entry, singleBox: store.singleBox.contains(entry.id))
            if !Task.isCancelled { result = r }
        }
    }
}

struct EditorView: View {
    @EnvironmentObject var store: Store
    let entry: Entry
    @State private var rejected: String?
    @State private var confirmRemove: Int?

    private var spec: EditorSpec { store.spec(for: entry) }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                header
                reviewBar
                japanese
                fullEnglish
                inGame
                noteField
            }
            .padding(.horizontal, 24)
            .padding(.vertical, 20)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .onChange(of: entry.id) { rejected = nil }
    }

    // MARK: Sections

    private var header: some View {
        HStack(spacing: 10) {
            Text(String(format: "#%04d", entry.id)).font(.system(.title2, design: .monospaced).weight(.bold))
            Tag(text: "\(entry.kindLabel) · \(entry.blockName)", accent: true)
            Tag(text: limitText)
            Tag(text: "0x\(entry.offset)", mono: true)
            Spacer()
            Button { store.step(-1) } label: { Image(systemName: "chevron.left") }.help("Previous message (⌘[)")
            Button { store.step(1) } label: { Image(systemName: "chevron.right") }.help("Next message (⌘])")
        }
    }

    private var limitText: String {
        switch spec {
        case let .boxes(width, lines, lastLines, _, canPage):
            return "\(width) per line, \(lines) lines per box" + (canPage ? "" : ", one box")
                + (lastLines < lines ? ", \(lastLines) in the last (Yes/No)" : "")
        case let .label(maxPx): return "\(maxPx) pixels, capitals"
        case let .card(width): return "\(width) letters per line, capitals"
        case let .choices(width): return "3 answers, \(width) each"
        case let .name(maxLen): return "\(maxLen) characters"
        case let .slots(widths): return "Fields: " + widths.map(String.init).joined(separator: ", ")
        case let .free(length, tiles): return "\(length) bytes" + (tiles.map { ", \($0) letters" } ?? "")
        case .plain: return "Fixed layout"
        }
    }

    private var reviewBar: some View {
        HStack(spacing: 10) {
            Image(systemName: entry.reviewed ? "checkmark" : "circle.fill")
                .foregroundStyle(entry.reviewed ? Color.green : Color.accentColor)
                .font(entry.reviewed ? .body.weight(.bold) : .system(size: 8))
            Text(entry.reviewed ? "Reviewed" : "Not reviewed").fontWeight(.semibold)
            Text(entry.reviewed ? "marked when you opened it" : "you'll come back to this one")
                .font(.callout).foregroundStyle(.secondary)
            Spacer()
            Button(entry.reviewed ? "Mark as not reviewed" : "Mark as reviewed") { store.setReviewed(!entry.reviewed) }
                .keyboardShortcut("u", modifiers: .command)
        }
        .padding(.horizontal, 12).padding(.vertical, 8)
        .background(RoundedRectangle(cornerRadius: 8).fill(entry.reviewed ? Color.green.opacity(0.12) : Color.accentColor.opacity(0.1)))
    }

    private var japanese: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack { SectionLabel("JAPANESE"); Text("original · read-only").font(.caption).foregroundStyle(.secondary) }
            Text(entry.jp.replacingOccurrences(of: "{01}", with: "　"))
                .font(.system(size: 16))
                .lineSpacing(5)
                .textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(12)
                .background(RoundedRectangle(cornerRadius: 8).fill(Color(nsColor: .controlBackgroundColor)))
        }
    }

    private var fullEnglish: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack { SectionLabel("FULL ENGLISH"); Text("literal · no length limit · not in the game").font(.caption).foregroundStyle(.secondary) }
            if entry.kind == "choices" {
                ForEach(0..<3, id: \.self) { i in
                    HStack {
                        Text("ABC".map(String.init)[i]).fontWeight(.semibold).frame(width: 16)
                        TextField("Answer", text: Binding(
                            get: { entry.literalList.indices.contains(i) ? entry.literalList[i] : "" },
                            set: { v in store.update(entry.id) { e in var l = e.literalList; while l.count < 3 { l.append("") }; l[i] = v; e.literalList = l } }))
                        .textFieldStyle(.roundedBorder)
                    }
                }
            } else {
                TextEditor(text: Binding(get: { entry.literal }, set: { v in store.update(entry.id) { $0.literal = v } }))
                    .font(.system(size: 14))
                    .frame(minHeight: 64, maxHeight: 110)
                    .padding(4)
                    .overlay(RoundedRectangle(cornerRadius: 6).stroke(Color(nsColor: .separatorColor)))
            }
        }
    }

    private var inGame: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                SectionLabel("IN-GAME ENGLISH")
                Text("goes into the patch").font(.caption).foregroundStyle(.secondary)
                Spacer()
                if entry.jp.contains("{NAME}") {
                    Button("Insert {NAME}") { insertAtCursor("{NAME}") }.controlSize(.small)
                        .help("The player's name; takes 8 spaces")
                }
            }
            switch spec {
            case let .boxes(width, lines, lastLines, xw, canPage):
                boxEditors(width: width, lines: lines, lastLines: lastLines, xw: xw, canPage: canPage)
            case let .label(maxPx): labelEditor(maxPx: maxPx)
            case let .card(width): cardEditor(width: width)
            case let .choices(width): choiceEditors(width: width)
            case let .name(maxLen): nameEditor(maxLen: maxLen)
            case let .slots(widths): slotEditors(widths: widths)
            case let .free(length, tiles): freeEditor(length: length, maxTiles: tiles)
            case .plain: plainEditor
            }
            if let rejected {
                Label(rejected, systemImage: "nosign").font(.callout).foregroundStyle(.orange)
            }
        }
    }

    private var noteField: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack { SectionLabel("NOTE"); Text("optional").font(.caption).foregroundStyle(.secondary) }
            TextField("e.g. second sentence dropped to fit", text: Binding(get: { entry.note }, set: { v in store.update(entry.id) { $0.note = v } }))
                .textFieldStyle(.roundedBorder)
        }
    }

    // MARK: In-game editors

    private var boxes: [String] {
        let b = entry.en.components(separatedBy: Fit.page)
        return b.isEmpty ? [""] : b
    }

    private func setBoxes(_ b: [String]) {
        store.update(entry.id) { $0.en = b.joined(separator: Fit.page) }
    }

    private func reject(_ paste: Bool, _ what: String) {
        rejected = paste ? "That paste doesn't fit in \(what), so it was refused." : "\(what.prefix(1).uppercased() + what.dropFirst()) is full."
    }

    private func boxEditors(width: Int, lines: Int, lastLines: Int, xw: Int, canPage: Bool) -> some View {
        let size = LockedTextView.size(columns: width, rows: lines, fontSize: 16)
        let all = boxes
        return VStack(alignment: .leading, spacing: 8) {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: size.width + 4, maximum: size.width + 4), spacing: 14, alignment: .topLeading)],
                      alignment: .leading, spacing: 12) {
                ForEach(Array(all.enumerated()), id: \.offset) { i, text in
                    let wrapped = Fit.boxLines(text, width: width, xw: xw)
                    let limit = i == all.count - 1 ? lastLines : lines
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text(all.count > 1 ? (i == store.focusedBox ? "Box \(i + 1) · editing" : "Box \(i + 1)") : "Box")
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(i == store.focusedBox && all.count > 1 ? Color.accentColor : .secondary)
                            Spacer()
                            if all.count > 1 {
                                Button { confirmRemove = i } label: { Image(systemName: "minus.circle") }
                                    .buttonStyle(.borderless).help("Remove box \(i + 1)")
                            }
                        }
                        LockedTextView(
                            text: Binding(get: { i < boxes.count ? boxes[i] : "" },
                                          set: { v in var b = boxes; if i < b.count { b[i] = v; setBoxes(b) } }),
                            columns: width, rows: lines,
                            validate: { cand in
                                EditorSpec.boxFits(cand, width: width, lines: limit, xw: xw)
                                    && Fit.count("{X}", in: cand) == Fit.count("{X}", in: text)
                            },
                            onReject: { reject($0, "box \(i + 1)") },
                            onFocus: { store.focusedBox = i; rejected = nil },
                            onSplit: canPage ? { at in split(box: i, at: at, width: width, lines: lines, xw: xw) } : nil)
                        .frame(width: size.width, height: size.height)
                        .overlay(RoundedRectangle(cornerRadius: 5).stroke(i == store.focusedBox ? Color.accentColor : Color(nsColor: .separatorColor),
                                                                          lineWidth: i == store.focusedBox ? 2 : 1))
                        Text("\(wrapped.count) / \(limit) lines" + (limit < lines ? " (Yes/No on line 3)" : "") + " · longest \(wrapped.map { Fit.widthOf($0, xw: xw) }.max() ?? 0) / \(width)")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
            HStack(spacing: 10) {
                if canPage {
                    Button("+ Add box") { var b = boxes; b.insert("", at: min(store.focusedBox + 1, b.count)); setBoxes(b); store.focusedBox = min(store.focusedBox + 1, b.count - 1) }
                    Text("⌘↩ splits a box at the cursor.").font(.caption).foregroundStyle(.secondary)
                } else {
                    Text("This message has to fit in one box.").font(.caption).foregroundStyle(.secondary)
                }
            }
            Text("Words wrap as you type; when a box is full, extra typing is ignored. {NAME} takes \(Fit.nameWidth) spaces"
                 + (entry.en.contains("{X}") ? ", {X} (the value the game inserts) takes \(xw)." : "."))
                .font(.caption).foregroundStyle(.secondary)
        }
        .confirmationDialog("Remove this box?", isPresented: Binding(get: { confirmRemove != nil }, set: { if !$0 { confirmRemove = nil } })) {
            Button("Remove Box", role: .destructive) {
                if let i = confirmRemove { var b = boxes; b.remove(at: i); setBoxes(b); store.focusedBox = max(0, min(store.focusedBox, b.count - 1)) }
                confirmRemove = nil
            }
        } message: {
            Text("Its text will be deleted.")
        }
    }

    private func split(box i: Int, at location: Int, width: Int, lines: Int, xw: Int) {
        var b = boxes
        let ns = b[i] as NSString
        let loc = min(location, ns.length)
        let head = ns.substring(to: loc).trimmingCharacters(in: .whitespacesAndNewlines)
        let tail = ns.substring(from: loc).trimmingCharacters(in: .whitespacesAndNewlines)
        b[i] = head
        b.insert(tail, at: i + 1)
        setBoxes(b)
        store.focusedBox = i + 1
    }

    private func labelEditor(maxPx: Int) -> some View {
        let size = LockedTextView.size(columns: 16, rows: 1, fontSize: 15)
        let w = Fit.labelWidth(entry.en)
        return VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 10) {
                LockedTextView(
                    text: Binding(get: { entry.en }, set: { v in store.update(entry.id) { $0.en = v } }),
                    columns: 16, rows: 1, multiline: false, fontSize: 15,
                    validate: { EditorSpec.labelFits($0, maxPx: maxPx) },
                    onReject: { reject($0, "the caption") },
                    onFocus: { rejected = nil })
                .frame(width: size.width, height: size.height)
                .overlay(RoundedRectangle(cornerRadius: 5).stroke(Color(nsColor: .separatorColor)))
                Text(w.map { "\($0) / \(maxPx) px" } ?? "letters not in the caption font").font(.caption).foregroundStyle(.secondary)
            }
            Text("A picture under the menu icons, drawn by the build with a small outlined font: capitals, digits and . - / ' & only. Leave it empty to keep the Japanese picture.")
                .font(.caption).foregroundStyle(.secondary)
        }
    }

    private func cardEditor(width: Int) -> some View {
        let size = LockedTextView.size(columns: 24, rows: 3, fontSize: 15)
        let lines = Fit.cardLines(entry.en, width: width)
        return VStack(alignment: .leading, spacing: 6) {
            LockedTextView(
                text: Binding(get: { entry.en }, set: { v in store.update(entry.id) { $0.en = v } }),
                columns: 24, rows: 3, fontSize: 15,
                validate: { EditorSpec.cardFits($0, width: width) },
                onReject: { reject($0, "the card") },
                onFocus: { rejected = nil })
            .frame(width: size.width, height: size.height)
            .overlay(RoundedRectangle(cornerRadius: 5).stroke(Color(nsColor: .separatorColor)))
            Text(lines.map { "\($0.1 ? "tall" : "small"): \($0.0.count)/\(width)" }.joined(separator: " · "))
                .font(.caption).foregroundStyle(.secondary)
            Text("A picture drawn by the build. Type a heading, Return, then a subtitle (e.g. CHAPTER 1 ⏎ FIRST STIRRINGS): the heading is tall, the subtitle small and wrapped to 2 lines. Without Return, the text is tall and wraps to 2 lines. Capitals, digits and . , ! ? - / ' & only.")
                .font(.caption).foregroundStyle(.secondary)
        }
    }

    private func choiceEditors(width: Int) -> some View {
        let size = LockedTextView.size(columns: width, rows: 1, fontSize: 15)
        return VStack(alignment: .leading, spacing: 8) {
            ForEach(0..<3, id: \.self) { i in
                let list = entry.enList
                let value = list.indices.contains(i) ? list[i] : ""
                HStack(spacing: 10) {
                    Text("ABC".map(String.init)[i]).fontWeight(.semibold).frame(width: 16)
                    LockedTextView(
                        text: Binding(get: { value }, set: { v in store.update(entry.id) { e in var l = e.enList; while l.count < 3 { l.append("") }; l[i] = v; e.enList = l } }),
                        columns: width, rows: 1, multiline: false, fontSize: 15,
                        validate: { EditorSpec.fieldFits($0, width: width) },
                        onReject: { reject($0, "answer \("ABC".map(String.init)[i])") },
                        onFocus: { rejected = nil })
                    .frame(width: size.width, height: size.height)
                    .overlay(RoundedRectangle(cornerRadius: 5).stroke(Color(nsColor: .separatorColor)))
                    Text("\(Fit.widthOf(value)) / \(width)").font(.caption).foregroundStyle(.secondary)
                }
            }
            Text("\"A) \" is added by the build.").font(.caption).foregroundStyle(.secondary)
        }
    }

    private func nameEditor(maxLen: Int) -> some View {
        let size = LockedTextView.size(columns: maxLen, rows: 1, fontSize: 16)
        return HStack(spacing: 10) {
            LockedTextView(
                text: Binding(get: { entry.en }, set: { v in store.update(entry.id) { $0.en = v } }),
                columns: maxLen, rows: 1, multiline: false,
                validate: { EditorSpec.fieldFits($0, width: maxLen) },
                onReject: { reject($0, "the name field") },
                onFocus: { rejected = nil })
            .frame(width: size.width, height: size.height)
            .overlay(RoundedRectangle(cornerRadius: 5).stroke(Color(nsColor: .separatorColor)))
            Text("\(Fit.widthOf(entry.en)) / \(maxLen)").font(.caption).foregroundStyle(.secondary)
            if entry.blockName == "town_types" {
                Text("Ends in a space: it's printed right before a town name.").font(.caption).foregroundStyle(.secondary)
            }
        }
    }

    private func slotEditors(widths: [Int]) -> some View {
        let parts = entry.en.components(separatedBy: "\n")
        return VStack(alignment: .leading, spacing: 8) {
            ForEach(Array(widths.enumerated()), id: \.offset) { i, w in
                let value = parts.indices.contains(i) ? parts[i] : ""
                let size = LockedTextView.size(columns: w, rows: 1, fontSize: 15)
                HStack(spacing: 10) {
                    Text(widths.count > 1 ? "Field \(i + 1)" : "Field").font(.callout).foregroundStyle(.secondary).frame(width: 56, alignment: .leading)
                    LockedTextView(
                        text: Binding(get: { value }, set: { v in
                            store.update(entry.id) { e in
                                var p = e.en.components(separatedBy: "\n")
                                while p.count < widths.count { p.append("") }
                                p[i] = v
                                e.en = p.joined(separator: "\n")
                            }
                        }),
                        columns: w, rows: 1, multiline: false, fontSize: 15,
                        validate: { EditorSpec.fieldFits($0, width: w) },
                        onReject: { reject($0, "field \(i + 1)") },
                        onFocus: { rejected = nil })
                    .frame(width: size.width, height: size.height)
                    .overlay(RoundedRectangle(cornerRadius: 5).stroke(Color(nsColor: .separatorColor)))
                    Text("\(Fit.widthOf(value)) / \(w)").font(.caption).foregroundStyle(.secondary)
                }
            }
            Text("Each field stops at its width. Short text is padded by the build. To leave a field blank, type a single space.")
                .font(.caption).foregroundStyle(.secondary)
        }
    }

    private func freeEditor(length: Int, maxTiles: Int?) -> some View {
        let lines = entry.en.components(separatedBy: "\n")
        let cols = max(lines.map { Fit.widthOf($0) }.max() ?? 10, 18)
        let size = LockedTextView.size(columns: cols, rows: max(lines.count, 2), fontSize: 15)
        let (bytes, tiles) = EditorSpec.freeBytes(entry.en)
        return VStack(alignment: .leading, spacing: 6) {
            LockedTextView(
                text: Binding(get: { entry.en }, set: { v in store.update(entry.id) { $0.en = v } }),
                columns: cols, rows: max(lines.count, 2), fontSize: 15,
                validate: { cand in
                    let (b, t) = EditorSpec.freeBytes(cand)
                    return Fit.drawable(cand, allowNewline: true) && b <= length && t <= (maxTiles ?? .max)
                },
                onReject: { reject($0, "this text") },
                onFocus: { rejected = nil })
            .frame(width: size.width, height: size.height)
            .overlay(RoundedRectangle(cornerRadius: 5).stroke(Color(nsColor: .separatorColor)))
            Text("\(bytes) / \(length) bytes" + (maxTiles.map { " · \(tiles) / \($0) letters (spaces are free)" } ?? "")
                 + ". Drawn at a fixed spot; use {01} for a blank line.")
                .font(.caption).foregroundStyle(.secondary)
        }
    }

    private var plainEditor: some View {
        VStack(alignment: .leading, spacing: 6) {
            TextEditor(text: Binding(get: { entry.en }, set: { v in store.update(entry.id) { $0.en = v } }))
                .font(.system(size: 15, design: .monospaced))
                .frame(minHeight: 70, maxHeight: 120)
                .padding(4)
                .overlay(RoundedRectangle(cornerRadius: 6).stroke(Color(nsColor: .separatorColor)))
            Text(entry.kind == "fixed"
                 ? "Fixed screen layout: keep its exact shape (see INSTRUCTIONS.md). Not limited while typing; the build checks it."
                 : "Part of a message the game assembles; the build checks it.")
                .font(.caption).foregroundStyle(.secondary)
        }
    }

    private func insertAtCursor(_ s: String) {
        guard let tv = NSApp.keyWindow?.firstResponder as? NSTextView else { NSSound.beep(); return }
        tv.insertText(s, replacementRange: tv.selectedRange())
    }
}

struct Tag: View {
    let text: String
    var accent = false
    var mono = false
    var body: some View {
        Text(text)
            .font(mono ? .system(.caption, design: .monospaced) : .caption.weight(accent ? .semibold : .regular))
            .padding(.horizontal, 7).padding(.vertical, 2)
            .background(RoundedRectangle(cornerRadius: 4).fill(accent ? Color.accentColor.opacity(0.12) : Color.secondary.opacity(0.12)))
            .foregroundStyle(accent ? Color.accentColor : .primary)
    }
}
