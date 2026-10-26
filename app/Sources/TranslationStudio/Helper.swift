import Foundation

/// Finds python3 the same way regardless of how the app was launched (Finder has no shell PATH).
enum Python {
    static var path: String {
        for p in ["/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3"]
        where FileManager.default.isExecutableFile(atPath: p) { return p }
        return "/usr/bin/python3"
    }
}

struct RenderResult {
    var jp: [[[Int]]] = []
    var en: [[[Int]]] = []
    var warnings: [String] = []
    var error: String?
    /// Menu captions: 8 rows of 64 pixel values (0-3).
    var jpImage: [[UInt8]]?
    var enImage: [[UInt8]]?
}

/// tools/studio_helper.py, kept running and spoken to in JSON lines. Requests are answered in order.
final class Helper {
    private let process = Process()
    private let input = Pipe()
    private let output = Pipe()
    private let queue = DispatchQueue(label: "studio.helper")
    private var buffer = Data()

    init(root: URL) throws {
        process.executableURL = URL(fileURLWithPath: Python.path)
        process.arguments = [root.appendingPathComponent("tools/studio_helper.py").path]
        process.currentDirectoryURL = root
        process.standardInput = input
        process.standardOutput = output
        process.standardError = FileHandle.nullDevice
        try process.run()
    }

    deinit { process.terminate() }

    func request(_ req: [String: Any]) async throws -> [String: Any] {
        try await withCheckedThrowingContinuation { cont in
            queue.async { [self] in
                do {
                    var line = try JSONSerialization.data(withJSONObject: req)
                    line.append(0x0A)
                    try input.fileHandleForWriting.write(contentsOf: line)
                    while !buffer.contains(0x0A) {
                        let chunk = output.fileHandleForReading.availableData
                        if chunk.isEmpty { throw NSError(domain: "Helper", code: 1, userInfo: [NSLocalizedDescriptionKey: "The preview helper stopped."]) }
                        buffer.append(chunk)
                    }
                    let nl = buffer.firstIndex(of: 0x0A)!
                    let reply = buffer[buffer.startIndex..<nl]
                    buffer = Data(buffer[buffer.index(after: nl)...])
                    let obj = try JSONSerialization.jsonObject(with: reply) as? [String: Any] ?? [:]
                    cont.resume(returning: obj)
                } catch {
                    cont.resume(throwing: error)
                }
            }
        }
    }

    func render(_ e: Entry, singleBox: Bool) async -> RenderResult {
        do {
            let r = try await request(["cmd": "render", "entry": JSON.object(e.obj).foundation, "single_box": singleBox])
            var out = RenderResult()
            out.error = r["error"] as? String
            out.jp = r["jp"] as? [[[Int]]] ?? []
            out.en = r["en"] as? [[[Int]]] ?? []
            out.warnings = r["warnings"] as? [String] ?? []
            out.jpImage = (r["jp_image"] as? [String]).map { $0.map { $0.utf8.map { $0 - 48 } } }
            out.enImage = (r["en_image"] as? [String]).map { $0.map { $0.utf8.map { $0 - 48 } } }
            return out
        } catch {
            return RenderResult(error: error.localizedDescription)
        }
    }
}

/// The game's 8x8 2bpp font: 256 glyphs, 64 pixel values (0-3) each. Index = text byte.
struct GameFont {
    var glyphs: [[UInt8]]

    init(_ strings: [String]) {
        glyphs = strings.map { $0.utf8.map { $0 - 48 } }
    }
}
