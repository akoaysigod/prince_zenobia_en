import AppKit
import SwiftUI

@main
struct TranslationStudioApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @StateObject private var store = Store(root: ProjectRoot.find())
    @State private var showBuild = false
    @State private var showSuggestions = false
    @State private var info: String?

    var body: some Scene {
        WindowGroup("Ogre Battle Gaiden — Translation Studio") {
            ContentView(showBuild: $showBuild, showSuggestions: $showSuggestions, info: $info)
                .environmentObject(store)
                .frame(minWidth: 1100, minHeight: 680)
                .task {
                    AppDelegate.store = store
                    store.load()
                    await store.startHelper()
                    if store.selection == nil, let first = store.filtered.first { store.select(first.id) }
                }
        }
        .defaultSize(width: 1440, height: 900)
        .commands {
            CommandGroup(replacing: .newItem) {}
            CommandGroup(replacing: .saveItem) {
                Button("Save") { store.save(force: true) }.keyboardShortcut("s")
            }
            CommandMenu("Message") {
                Button("Next Message") { store.step(1) }.keyboardShortcut("]")
                Button("Previous Message") { store.step(-1) }.keyboardShortcut("[")
                Divider()
                Button("Next Box") { store.focusedBox += 1 }.keyboardShortcut(.rightArrow, modifiers: [.command, .option])
                Button("Previous Box") { store.focusedBox = max(0, store.focusedBox - 1) }.keyboardShortcut(.leftArrow, modifiers: [.command, .option])
                Divider()
                Button("Find") { NSApp.keyWindow?.makeFirstResponder(nil); store.search = store.search }.keyboardShortcut("f")
            }
            CommandMenu("Patch") {
                Button("Build Patch") { showBuild = true }.keyboardShortcut("b")
                Button("Open in NgpCraft") { store.openInNgpCraft() }.keyboardShortcut("r")
                Button("Apply Patch to a ROM…") { store.applyPatchToROM() }
                Divider()
                Button("Review Suggestions…") { showSuggestions = true }
                Button("Merge ROM Scan…") { info = store.mergeROMScan() }
            }
        }
    }
}

struct ContentView: View {
    @EnvironmentObject var store: Store
    @Binding var showBuild: Bool
    @Binding var showSuggestions: Bool
    @Binding var info: String?

    var body: some View {
        NavigationSplitView {
            SidebarView()
                .navigationSplitViewColumnWidth(min: 300, ideal: 350, max: 480)
        } detail: {
            if let e = store.selected {
                DetailView(entry: e)
            } else {
                Text(store.entries.isEmpty ? "Loading…" : "Choose a message").foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .toolbar {
            ToolbarItemGroup(placement: .primaryAction) {
                if store.savedAt != nil {
                    Label("Saved to messages.json", systemImage: "checkmark").labelStyle(.titleAndIcon).foregroundStyle(.secondary)
                }
                Button("Open in NgpCraft") { store.openInNgpCraft() }
                Button("Build Patch") { showBuild = true }.buttonStyle(.borderedProminent)
            }
        }
        .sheet(isPresented: $showBuild) { BuildSheet().environmentObject(store) }
        .sheet(isPresented: $showSuggestions) { SuggestionsSheet().environmentObject(store) }
        .alert("Translation Studio", isPresented: Binding(get: { store.errorMessage != nil }, set: { if !$0 { store.errorMessage = nil } })) {
            Button("OK") { store.errorMessage = nil }
        } message: { Text(store.errorMessage ?? "") }
        .alert("Translation Studio", isPresented: Binding(get: { info != nil }, set: { if !$0 { info = nil } })) {
            Button("OK") { info = nil }
        } message: { Text(info ?? "") }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    @MainActor static weak var store: Store?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    @MainActor
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        AppDelegate.store?.save()  // save on quit
        return .terminateNow
    }
}

/// The translation project folder: the one holding script/messages.json above this app.
enum ProjectRoot {
    static func find() -> URL {
        let starts = [Bundle.main.bundleURL, URL(fileURLWithPath: CommandLine.arguments[0]).resolvingSymlinksInPath(),
                      URL(fileURLWithPath: FileManager.default.currentDirectoryPath)]
        for start in starts {
            var dir = start
            for _ in 0..<8 {
                if FileManager.default.fileExists(atPath: dir.appendingPathComponent("script/messages.json").path) { return dir }
                dir = dir.deletingLastPathComponent()
            }
        }
        if let saved = UserDefaults.standard.string(forKey: "projectRoot") { return URL(fileURLWithPath: saved) }
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.message = "Choose the translation project folder (the one with script/messages.json)"
        if panel.runModal() == .OK, let url = panel.url {
            UserDefaults.standard.set(url.path, forKey: "projectRoot")
            return url
        }
        return URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
    }
}
