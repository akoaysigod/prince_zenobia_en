import AppKit
import SwiftUI

/// Draws text boxes with the game's own 8x8 font, scaled up with hard pixel edges.
enum BoxRenderer {
    static let paper: (UInt8, UInt8, UInt8) = (32, 48, 104)
    static let ink: (UInt8, UInt8, UInt8) = (240, 240, 232)
    static let frame: (UInt8, UInt8, UInt8) = (200, 200, 216)
    static let pad = 6

    /// One box at 1x: `cols` x `rows` cells, lines 16 px apart like the game's dialogue box.
    static func image(lines: [[Int]], cols: Int, rows: Int, font: GameFont) -> NSImage {
        let w = cols * 8 + 2 * pad, h = max(rows, 1) * 16 - 8 + 2 * pad
        var px = [UInt8](repeating: 255, count: w * h * 4)
        func set(_ x: Int, _ y: Int, _ c: (UInt8, UInt8, UInt8)) {
            let o = (y * w + x) * 4
            px[o] = c.0; px[o + 1] = c.1; px[o + 2] = c.2
        }
        for y in 0..<h { for x in 0..<w { set(x, y, paper) } }
        for x in 0..<w { set(x, 1, frame); set(x, h - 2, frame) }
        for y in 1..<(h - 1) { set(1, y, frame); set(w - 2, y, frame) }
        for (r, line) in lines.prefix(rows).enumerated() {
            for (c, code) in line.prefix(cols).enumerated() where code > 0 && code < font.glyphs.count {
                let g = font.glyphs[code]
                guard g.count == 64 else { continue }
                for y in 0..<8 { for x in 0..<8 where g[y * 8 + x] == 1 || g[y * 8 + x] == 3 {
                    set(pad + c * 8 + x, pad + r * 16 + y, ink)
                } }
            }
        }
        let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: w, pixelsHigh: h, bitsPerSample: 8,
                                   samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB,
                                   bytesPerRow: w * 4, bitsPerPixel: 32)!
        px.withUnsafeBufferPointer { memcpy(rep.bitmapData!, $0.baseAddress!, px.count) }
        let img = NSImage(size: NSSize(width: w, height: h))
        img.addRepresentation(rep)
        return img
    }
}

/// A 64x8 menu caption on a dark map-green background, in the game's caption colours.
struct CaptionImage: View {
    let pixels: [[UInt8]]
    let scale: Int

    var body: some View {
        let h = pixels.count, w = pixels.first?.count ?? 0, pad = 3
        let W = w + 2 * pad, H = h + 2 * pad
        let colors: [(UInt8, UInt8, UInt8)] = [(40, 88, 40), (248, 248, 248), (150, 150, 150), (16, 16, 16)]
        var px = [UInt8](repeating: 255, count: W * H * 4)
        for y in 0..<H { for x in 0..<W {
            let v = (y >= pad && y < pad + h && x >= pad && x < pad + w) ? Int(pixels[y - pad][x - pad]) : 0
            let c = colors[min(v, 3)], o = (y * W + x) * 4
            px[o] = c.0; px[o + 1] = c.1; px[o + 2] = c.2
        } }
        let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: W, pixelsHigh: H, bitsPerSample: 8,
                                   samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB,
                                   bytesPerRow: W * 4, bitsPerPixel: 32)!
        px.withUnsafeBufferPointer { memcpy(rep.bitmapData!, $0.baseAddress!, px.count) }
        let img = NSImage(size: NSSize(width: W, height: H))
        img.addRepresentation(rep)
        return Image(nsImage: img).interpolation(.none).resizable()
            .frame(width: CGFloat(W * scale * 2), height: CGFloat(H * scale * 2))
            .clipShape(RoundedRectangle(cornerRadius: 3))
    }
}

struct PixelBox: View {
    let lines: [[Int]]
    let cols: Int
    let rows: Int
    let font: GameFont
    let scale: Int
    var highlighted = false

    var body: some View {
        let img = BoxRenderer.image(lines: lines, cols: cols, rows: rows, font: font)
        Image(nsImage: img)
            .interpolation(.none)
            .resizable()
            .frame(width: img.size.width * CGFloat(scale), height: img.size.height * CGFloat(scale))
            .clipShape(RoundedRectangle(cornerRadius: 3))
            .overlay(RoundedRectangle(cornerRadius: 4).stroke(Color.accentColor, lineWidth: highlighted ? 3 : 0).padding(-3))
    }
}

struct PreviewView: View {
    @EnvironmentObject var store: Store
    let entry: Entry
    let result: RenderResult
    @AppStorage("previewScale") private var scale = 3

    private var spec: EditorSpec { store.spec(for: entry) }

    /// Box size in cells for the English side.
    private var enCols: Int {
        let longest = result.en.flatMap { $0 }.map(\.count).max() ?? 0
        switch spec {
        case let .boxes(width, _, _, _, _): return max(width, longest)
        case let .choices(width): return max(width + 3, longest)
        case let .name(maxLen): return max(maxLen, longest)
        case let .slots(widths): return max(widths.max() ?? 1, longest)
        default: return max(longest, 1)
        }
    }

    private var enRows: Int {
        let most = result.en.map(\.count).max() ?? 1
        if case let .boxes(_, lines, _, _, _) = spec { return max(lines, most) }
        return max(most, 1)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                HStack {
                    Text("Preview").font(.headline)
                    Spacer()
                    Picker("Scale", selection: $scale) {
                        Text("2×").tag(2); Text("3×").tag(3); Text("4×").tag(4)
                    }
                    .pickerStyle(.segmented)
                    .labelsHidden()
                    .frame(width: 130)
                }

                if let jp = result.jpImage {
                    VStack(alignment: .leading, spacing: 6) {
                        SectionLabel("JAPANESE · ORIGINAL ROM")
                        CaptionImage(pixels: jp, scale: scale)
                    }
                    VStack(alignment: .leading, spacing: 6) {
                        SectionLabel("IN-GAME ENGLISH · AS THE BUILD DRAWS IT")
                        if let en = result.enImage { CaptionImage(pixels: en, scale: scale) } else { Text("Not translated").foregroundStyle(.secondary) }
                    }
                } else if let font = store.jpFont, let jp = result.jp.first {
                    VStack(alignment: .leading, spacing: 6) {
                        SectionLabel("JAPANESE · ORIGINAL ROM")
                        PixelBox(lines: jp, cols: max(jp.map(\.count).max() ?? 1, 1), rows: max(jp.count, 1), font: font, scale: scale)
                    }
                }

                if result.jpImage == nil, let font = store.enFont {
                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            SectionLabel("IN-GAME ENGLISH · PATCHED FONT")
                            Spacer()
                            if result.en.count > 1 {
                                Button { store.focusedBox = max(store.focusedBox - 1, 0) } label: { Image(systemName: "chevron.left") }
                                    .help("Previous box (⌥←)")
                                Text("Box \(min(store.focusedBox, result.en.count - 1) + 1) of \(result.en.count)").font(.callout.weight(.semibold))
                                Button { store.focusedBox = min(store.focusedBox + 1, result.en.count - 1) } label: { Image(systemName: "chevron.right") }
                                    .help("Next box (⌥→)")
                            }
                        }
                        if result.en.isEmpty {
                            Text("Not translated").foregroundStyle(.secondary)
                        }
                        ForEach(Array(result.en.enumerated()), id: \.offset) { i, box in
                            VStack(alignment: .leading, spacing: 4) {
                                if result.en.count > 1 {
                                    Text(i == store.focusedBox ? "\(i + 1) · editing" : "\(i + 1)")
                                        .font(.caption.weight(.semibold))
                                        .foregroundStyle(i == store.focusedBox ? Color.accentColor : .secondary)
                                }
                                PixelBox(lines: box, cols: enCols, rows: enRows, font: font, scale: scale,
                                         highlighted: result.en.count > 1 && i == store.focusedBox)
                            }
                        }
                    }
                }

                if let err = result.error {
                    Label(err, systemImage: "exclamationmark.triangle").foregroundStyle(.orange)
                }
                ForEach(result.warnings, id: \.self) { w in
                    Label(w, systemImage: "exclamationmark.triangle").foregroundStyle(.orange).font(.callout)
                }
                if entry.blockNumber != nil || entry.kind == "message" {
                    Text("Wrapped by the same rules the build uses. {NAME} is shown as Tristan.")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            .padding(20)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(Color(nsColor: .underPageBackgroundColor).opacity(0.25))
    }
}

struct SectionLabel: View {
    let text: String
    init(_ t: String) { text = t }
    var body: some View {
        Text(text).font(.caption.weight(.bold)).tracking(0.6).foregroundStyle(.secondary)
    }
}
