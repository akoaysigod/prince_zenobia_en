import AppKit
import SwiftUI

/// Runs tools/insert.py and shows its result.
@MainActor
final class BuildRunner: ObservableObject {
    enum State { case idle, running, done(ok: Bool) }
    struct Warning: Identifiable { let id = UUID(); let messageID: Int?; let text: String }

    @Published var state: State = .idle
    @Published var log = ""
    @Published var warnings: [Warning] = []

    func run(root: URL) {
        state = .running
        log = ""
        warnings = []
        let p = Process()
        p.executableURL = URL(fileURLWithPath: Python.path)
        p.arguments = ["tools/insert.py"]
        p.currentDirectoryURL = root
        let pipe = Pipe()
        p.standardOutput = pipe
        p.standardError = pipe
        p.terminationHandler = { proc in
            let out = String(decoding: pipe.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self)
            Task { @MainActor in self.finish(out, ok: proc.terminationStatus == 0) }
        }
        do { try p.run() } catch { finish("Couldn't run python3: \(error.localizedDescription)", ok: false) }
    }

    private func finish(_ out: String, ok: Bool) {
        log = out
        let idRE = try! NSRegularExpression(pattern: #"(?:message|entry|name) (\d+)"#)
        let lines = out.split(separator: "\n").map(String.init)
        let interesting = ok ? lines.filter { $0.hasPrefix("warning:") } : lines.suffix(1).map { $0 }
        warnings = interesting.map { line in
            let ns = line as NSString
            let id = idRE.firstMatch(in: line, range: NSRange(location: 0, length: ns.length)).flatMap { Int(ns.substring(with: $0.range(at: 1))) }
            return Warning(messageID: id, text: line.replacingOccurrences(of: "warning: ", with: ""))
        }
        state = .done(ok: ok)
    }
}

struct BuildSheet: View {
    @EnvironmentObject var store: Store
    @StateObject private var runner = BuildRunner()
    @Environment(\.dismiss) private var dismiss
    @State private var showLog = false

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Build patch").font(.title3.weight(.bold))
                Spacer()
                Text("python3 tools/insert.py").font(.system(.caption, design: .monospaced)).foregroundStyle(.secondary)
            }

            HStack(spacing: 10) {
                Step(n: 1, text: "Save messages.json", status: .ok)
                Step(n: 2, text: "Insert text and font", status: stepStatus)
                Step(n: 3, text: resultText, status: resultStatus)
            }

            if !runner.warnings.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    SectionLabel(isFailure ? "ERROR · CLICK TO OPEN THE MESSAGE" : "WARNINGS · CLICK TO OPEN THE MESSAGE")
                    ScrollView {
                        VStack(alignment: .leading, spacing: 6) {
                            ForEach(runner.warnings) { w in
                                Button {
                                    if let id = w.messageID { store.search = ""; store.reviewFilter = .any; store.select(id); dismiss() }
                                } label: {
                                    HStack(alignment: .firstTextBaseline, spacing: 10) {
                                        if let id = w.messageID {
                                            Text(String(format: "#%04d", id)).font(.system(.body, design: .monospaced).weight(.semibold)).foregroundStyle(.orange)
                                        }
                                        Text(w.text).multilineTextAlignment(.leading)
                                        Spacer()
                                    }
                                    .padding(10)
                                    .background(RoundedRectangle(cornerRadius: 8).fill(Color.orange.opacity(0.08)))
                                    .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color.orange.opacity(0.4)))
                                }
                                .buttonStyle(.plain)
                                .disabled(w.messageID == nil)
                            }
                        }
                    }
                    .frame(maxHeight: 180)
                }
            }

            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    SectionLabel("OUTPUT")
                    Spacer()
                    Button(showLog ? "Show less" : "Show full log") { showLog.toggle() }.buttonStyle(.link).font(.caption)
                }
                ScrollView {
                    Text(showLog ? runner.log : lastLines)
                        .font(.system(size: 12, design: .monospaced))
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(10)
                }
                .frame(height: showLog ? 260 : 80)
                .background(RoundedRectangle(cornerRadius: 8).fill(Color(nsColor: .textBackgroundColor)))
            }

            HStack(spacing: 10) {
                Button("Show in Finder") { NSWorkspace.shared.activateFileViewerSelecting([store.builtIPS]) }
                Button("Apply Patch to a ROM…") { store.applyPatchToROM() }
                Spacer()
                Button("Close") { dismiss() }.keyboardShortcut(.cancelAction)
                Button("Open in NgpCraft") { store.openInNgpCraft(); dismiss() }
                    .keyboardShortcut(.defaultAction)
                    .disabled(!isSuccess)
            }
            .disabled(isRunning)
        }
        .padding(24)
        .frame(width: 720)
        .onAppear {
            store.save()
            runner.run(root: store.root)
        }
    }

    private var isRunning: Bool { if case .running = runner.state { return true }; return false }
    private var isSuccess: Bool { if case .done(true) = runner.state { return true }; return false }
    private var isFailure: Bool { if case .done(false) = runner.state { return true }; return false }

    private var lastLines: String { runner.log.split(separator: "\n").suffix(3).joined(separator: "\n") }

    private var stepStatus: Step.Status { isRunning ? .running : (isFailure ? .failed : .ok) }
    private var resultStatus: Step.Status {
        if isRunning { return .waiting }
        if isFailure { return .failed }
        return runner.warnings.isEmpty ? .ok : .warning
    }
    private var resultText: String {
        if isRunning { return "Building…" }
        if isFailure { return "Failed" }
        return runner.warnings.isEmpty ? "Done, 0 warnings" : "Done, \(runner.warnings.count) warning\(runner.warnings.count == 1 ? "" : "s")"
    }
}

private struct Step: View {
    enum Status { case ok, running, waiting, warning, failed }
    let n: Int
    let text: String
    let status: Status

    var body: some View {
        HStack(spacing: 8) {
            switch status {
            case .ok: Image(systemName: "checkmark").foregroundStyle(.green)
            case .running: ProgressView().controlSize(.small)
            case .waiting: Image(systemName: "circle").foregroundStyle(.secondary)
            case .warning: Image(systemName: "exclamationmark").foregroundStyle(.orange)
            case .failed: Image(systemName: "xmark").foregroundStyle(.red)
            }
            Text("\(n)").fontWeight(.bold)
            Text(text)
            Spacer(minLength: 0)
        }
        .padding(10)
        .frame(maxWidth: .infinity)
        .background(RoundedRectangle(cornerRadius: 8).fill(color.opacity(0.1)))
    }

    private var color: Color {
        switch status {
        case .ok: return .green
        case .warning: return .orange
        case .failed: return .red
        default: return .secondary
        }
    }
}

struct SuggestionsSheet: View {
    @EnvironmentObject var store: Store
    @Environment(\.dismiss) private var dismiss
    @State private var items: [Store.Suggestion] = []

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Suggestions").font(.title3.weight(.bold))
            Text("From script/suggestions.json. Accepting one writes it into messages.json; rejecting just removes it.")
                .font(.callout).foregroundStyle(.secondary)
            if items.isEmpty {
                Text("No suggestions waiting.").foregroundStyle(.secondary).padding(.vertical, 20)
            }
            List(items) { s in
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Text(String(format: "#%04d", s.entryID)).font(.system(.body, design: .monospaced).weight(.semibold))
                        Text(s.field == "en" ? "In-game English" : s.field == "literal" ? "Full English" : "Note").foregroundStyle(.secondary)
                        Spacer()
                        Button("Open") { store.search = ""; store.reviewFilter = .any; store.select(s.entryID) }
                        Button("Reject") { store.resolve(s, accept: false, remaining: items); items = store.loadSuggestions() }
                        Button("Accept") { store.resolve(s, accept: true, remaining: items); items = store.loadSuggestions() }
                            .buttonStyle(.borderedProminent)
                    }
                    if let e = store.entry(s.entryID) {
                        Text("Now: " + (s.field == "en" ? e.en : s.field == "literal" ? e.literal : e.note)).foregroundStyle(.secondary)
                    }
                    Text("New: " + Entry.text(s.value))
                    if !s.reason.isEmpty { Text(s.reason).font(.callout).foregroundStyle(.secondary) }
                }
                .padding(.vertical, 6)
            }
            .frame(minHeight: 300)
            HStack { Spacer(); Button("Done") { dismiss() }.keyboardShortcut(.defaultAction) }
        }
        .padding(24)
        .frame(width: 760, height: 560)
        .onAppear { items = store.loadSuggestions() }
    }
}
