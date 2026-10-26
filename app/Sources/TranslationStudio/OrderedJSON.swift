import Foundation

/// A JSON value that keeps object keys in file order, so saving messages.json
/// writes it back exactly as Python's json.dump(indent=1, ensure_ascii=False) does.
enum JSON: Equatable {
    case object(JObject)
    case array([JSON])
    case string(String)
    case number(String)  // kept as written
    case bool(Bool)
    case null

    var string: String? { if case .string(let s) = self { return s }; return nil }
    var int: Int? { if case .number(let n) = self { return Int(n) }; return nil }
    var bool: Bool? { if case .bool(let b) = self { return b }; return nil }
    var array: [JSON]? { if case .array(let a) = self { return a }; return nil }
    var object: JObject? { if case .object(let o) = self { return o }; return nil }

    /// Plain Foundation value, for talking to the helper with JSONSerialization.
    var foundation: Any {
        switch self {
        case .object(let o): return Dictionary(uniqueKeysWithValues: o.pairs.map { ($0.0, $0.1.foundation) })
        case .array(let a): return a.map(\.foundation)
        case .string(let s): return s
        case .number(let n): return Int(n) ?? Double(n) ?? 0
        case .bool(let b): return b
        case .null: return NSNull()
        }
    }
}

struct JObject: Equatable {
    private(set) var keys: [String] = []
    private var values: [String: JSON] = [:]

    var pairs: [(String, JSON)] { keys.map { ($0, values[$0]!) } }

    subscript(key: String) -> JSON? {
        get { values[key] }
        set {
            if let v = newValue {
                if values[key] == nil { keys.append(key) }
                values[key] = v
            } else if values.removeValue(forKey: key) != nil {
                keys.removeAll { $0 == key }
            }
        }
    }
}

struct JSONParseError: Error, CustomStringConvertible {
    let offset: Int
    let message: String
    var description: String { "JSON error at byte \(offset): \(message)" }
}

struct JSONParser {
    private let b: [UInt8]
    private var i = 0

    static func parse(_ data: Data) throws -> JSON {
        var p = JSONParser(b: [UInt8](data))
        p.skip()
        let v = try p.value()
        p.skip()
        guard p.i == p.b.count else { throw JSONParseError(offset: p.i, message: "trailing data") }
        return v
    }

    private init(b: [UInt8]) { self.b = b }

    private mutating func skip() {
        while i < b.count, b[i] == 0x20 || b[i] == 0x0A || b[i] == 0x0D || b[i] == 0x09 { i += 1 }
    }

    private func fail(_ m: String) -> JSONParseError { JSONParseError(offset: i, message: m) }

    private mutating func value() throws -> JSON {
        guard i < b.count else { throw fail("unexpected end") }
        switch b[i] {
        case UInt8(ascii: "{"):
            i += 1
            var o = JObject()
            skip()
            if b[i] == UInt8(ascii: "}") { i += 1; return .object(o) }
            while true {
                skip()
                guard b[i] == UInt8(ascii: "\"") else { throw fail("expected key") }
                let k = try str()
                skip()
                guard b[i] == UInt8(ascii: ":") else { throw fail("expected :") }
                i += 1
                skip()
                o[k] = try value()
                skip()
                if b[i] == UInt8(ascii: ",") { i += 1; continue }
                if b[i] == UInt8(ascii: "}") { i += 1; return .object(o) }
                throw fail("expected , or }")
            }
        case UInt8(ascii: "["):
            i += 1
            var a: [JSON] = []
            skip()
            if b[i] == UInt8(ascii: "]") { i += 1; return .array(a) }
            while true {
                skip()
                a.append(try value())
                skip()
                if b[i] == UInt8(ascii: ",") { i += 1; continue }
                if b[i] == UInt8(ascii: "]") { i += 1; return .array(a) }
                throw fail("expected , or ]")
            }
        case UInt8(ascii: "\""):
            return .string(try str())
        case UInt8(ascii: "t"):
            i += 4; return .bool(true)
        case UInt8(ascii: "f"):
            i += 5; return .bool(false)
        case UInt8(ascii: "n"):
            i += 4; return .null
        default:
            let start = i
            while i < b.count, "+-0123456789.eE".utf8.contains(b[i]) { i += 1 }
            guard i > start else { throw fail("unexpected character") }
            return .number(String(decoding: b[start..<i], as: UTF8.self))
        }
    }

    private mutating func hex4() throws -> UInt32 {
        guard i + 4 <= b.count, let v = UInt32(String(decoding: b[i..<i + 4], as: UTF8.self), radix: 16)
        else { throw fail("bad \\u escape") }
        i += 4
        return v
    }

    private mutating func str() throws -> String {
        i += 1  // opening quote
        var out = [UInt8]()
        while true {
            guard i < b.count else { throw fail("unterminated string") }
            let c = b[i]
            i += 1
            if c == UInt8(ascii: "\"") { break }
            if c != UInt8(ascii: "\\") { out.append(c); continue }
            let e = b[i]
            i += 1
            switch e {
            case UInt8(ascii: "n"): out.append(0x0A)
            case UInt8(ascii: "t"): out.append(0x09)
            case UInt8(ascii: "r"): out.append(0x0D)
            case UInt8(ascii: "b"): out.append(0x08)
            case UInt8(ascii: "f"): out.append(0x0C)
            case UInt8(ascii: "u"):
                var v = try hex4()
                if (0xD800..<0xDC00).contains(v), i + 1 < b.count, b[i] == UInt8(ascii: "\\"), b[i + 1] == UInt8(ascii: "u") {
                    i += 2
                    let lo = try hex4()
                    v = 0x10000 + ((v - 0xD800) << 10) + (lo - 0xDC00)
                }
                out += Array(String(Character(Unicode.Scalar(v) ?? "?")).utf8)
            default: out.append(e)  // \" \\ \/
            }
        }
        return String(decoding: out, as: UTF8.self)
    }
}

enum JSONWriter {
    /// Same text as Python's json.dump(value, f, ensure_ascii=False, indent=1).
    static func write(_ v: JSON) -> String {
        var s = ""
        s.reserveCapacity(2_000_000)
        emit(v, 0, &s)
        return s
    }

    private static func emit(_ v: JSON, _ level: Int, _ s: inout String) {
        switch v {
        case .object(let o):
            if o.keys.isEmpty { s += "{}"; return }
            s += "{\n"
            for (n, (k, val)) in o.pairs.enumerated() {
                if n > 0 { s += ",\n" }
                s += String(repeating: " ", count: level + 1)
                quote(k, &s)
                s += ": "
                emit(val, level + 1, &s)
            }
            s += "\n" + String(repeating: " ", count: level) + "}"
        case .array(let a):
            if a.isEmpty { s += "[]"; return }
            s += "[\n"
            for (n, val) in a.enumerated() {
                if n > 0 { s += ",\n" }
                s += String(repeating: " ", count: level + 1)
                emit(val, level + 1, &s)
            }
            s += "\n" + String(repeating: " ", count: level) + "]"
        case .string(let str): quote(str, &s)
        case .number(let n): s += n
        case .bool(let b): s += b ? "true" : "false"
        case .null: s += "null"
        }
    }

    private static func quote(_ str: String, _ s: inout String) {
        s += "\""
        for u in str.unicodeScalars {
            switch u {
            case "\"": s += "\\\""
            case "\\": s += "\\\\"
            case "\n": s += "\\n"
            case "\r": s += "\\r"
            case "\t": s += "\\t"
            case "\u{08}": s += "\\b"
            case "\u{0C}": s += "\\f"
            default:
                if u.value < 0x20 { s += String(format: "\\u%04x", u.value) } else { s.unicodeScalars.append(u) }
            }
        }
        s += "\""
    }
}
