import SwiftUI

struct SidebarView: View {
    @EnvironmentObject var store: Store

    var body: some View {
        let list = store.filtered
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 6) {
                    Image(systemName: "magnifyingglass").foregroundStyle(.secondary)
                    TextField("Search text, or #1543 for an ID", text: $store.search)
                        .textFieldStyle(.plain)
                    if !store.search.isEmpty {
                        Button { store.search = "" } label: { Image(systemName: "xmark.circle.fill") }
                            .buttonStyle(.borderless).foregroundStyle(.secondary).help("Clear search")
                    }
                }
                .padding(.horizontal, 8).frame(height: 30)
                .background(RoundedRectangle(cornerRadius: 7).fill(Color(nsColor: .textBackgroundColor)))
                .overlay(RoundedRectangle(cornerRadius: 7).stroke(Color(nsColor: .separatorColor)))

                Picker("Category", selection: $store.category) {
                    ForEach(Entry.Category.allCases, id: \.self) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.segmented).labelsHidden()

                Picker("Review", selection: $store.reviewFilter) {
                    ForEach(Store.ReviewFilter.allCases, id: \.self) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.segmented).labelsHidden()
                .disabled(!store.search.isEmpty)
                .help(store.search.isEmpty ? "" : "Search always shows reviewed and not reviewed messages")

                FlowChips()

                Text(summary(list.count))
                    .font(.caption).foregroundStyle(.secondary)
            }
            .padding(12)

            Divider()

            List(selection: Binding(get: { store.selection }, set: { store.select($0) })) {
                ForEach(list) { e in
                    Row(entry: e, edited: store.isEdited(e), fits: !store.notFitting.contains(e.id))
                        .tag(e.id)
                }
            }
            .listStyle(.sidebar)

            Divider()
            HStack {
                Text("\(store.reviewedCount) of \(store.entries.count) reviewed")
                Spacer()
                if let at = store.savedAt { Text("Saved \(at.formatted(date: .omitted, time: .shortened))") }
            }
            .font(.caption).foregroundStyle(.secondary)
            .padding(.horizontal, 12).padding(.vertical, 6)
        }
    }

    private func summary(_ n: Int) -> String {
        if !store.search.isEmpty { return "\(n) found (reviewed and not reviewed)" }
        return "\(n) shown, of \(store.entries.count)"
    }
}

private struct FlowChips: View {
    @EnvironmentObject var store: Store

    var body: some View {
        HStack(spacing: 6) {
            ForEach(Store.Chip.allCases, id: \.self) { chip in
                let on = store.chips.contains(chip)
                Button {
                    if on { store.chips.remove(chip) } else { store.chips.insert(chip) }
                } label: {
                    Text("\(chip.rawValue) · \(store.count(chip))")
                        .font(.caption)
                        .padding(.horizontal, 8).padding(.vertical, 3)
                        .background(Capsule().fill(on ? Color.accentColor : Color(nsColor: .controlBackgroundColor)))
                        .overlay(Capsule().stroke(Color(nsColor: .separatorColor)))
                        .foregroundStyle(on ? Color.white : .primary)
                }
                .buttonStyle(.plain)
            }
        }
        .fixedSize(horizontal: false, vertical: true)
    }
}

private struct Row: View {
    let entry: Entry
    let edited: Bool
    let fits: Bool

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Circle()
                .fill(entry.reviewed ? Color.clear : Color.accentColor)
                .frame(width: 8, height: 8)
                .padding(.top, 5)
                .accessibilityLabel(entry.reviewed ? "Reviewed" : "Not reviewed")
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(String(format: "#%04d", entry.id)).font(.system(size: 11, design: .monospaced))
                    Text(entry.kindLabel).font(.system(size: 11))
                    Spacer()
                    if !fits { Text("Doesn't fit").font(.system(size: 11)).foregroundStyle(.orange) }
                    if edited { Text("Edited").font(.system(size: 11)) }
                }
                .foregroundStyle(.secondary)
                HStack(spacing: 6) {
                    Text(entry.isTranslated ? firstLine(entry.en) : "Not translated")
                        .foregroundStyle(entry.isTranslated ? .primary : .secondary)
                    if entry.isShortened {
                        Text("= " + firstLine(entry.literal)).foregroundStyle(.secondary)
                    }
                }
                .lineLimit(1)
                Text(firstLine(entry.jp)).font(.system(size: 12)).foregroundStyle(.secondary).lineLimit(1)
            }
        }
        .padding(.vertical, 3)
    }

    private func firstLine(_ s: String) -> String {
        s.replacingOccurrences(of: Fit.page, with: " ").replacingOccurrences(of: "{01}", with: " ")
            .replacingOccurrences(of: "\n", with: " ")
    }
}
