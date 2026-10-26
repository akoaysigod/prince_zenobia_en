import AppKit
import SwiftUI

/// A monospaced text box that refuses any edit `validate` rejects, so you can't type past a limit.
struct LockedTextView: NSViewRepresentable {
    @Binding var text: String
    var columns: Int
    var rows: Int
    var multiline = true
    var fontSize: CGFloat = 16
    var validate: (String) -> Bool
    var onReject: (_ wasPaste: Bool) -> Void = { _ in }
    var onFocus: () -> Void = {}
    var onSplit: ((Int) -> Void)?

    static func font(_ size: CGFloat) -> NSFont { .monospacedSystemFont(ofSize: size, weight: .regular) }

    static func size(columns: Int, rows: Int, fontSize: CGFloat) -> CGSize {
        let f = font(fontSize)
        let charW = ("M" as NSString).size(withAttributes: [.font: f]).width
        let lineH = ceil(f.ascender - f.descender + f.leading) + 4
        return CGSize(width: ceil(charW * CGFloat(columns)) + 16 + 2, height: lineH * CGFloat(rows) + 12)
    }

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeNSView(context: Context) -> LockedNSTextView {
        let tv = LockedNSTextView()
        tv.delegate = context.coordinator
        tv.font = Self.font(fontSize)
        tv.isRichText = false
        tv.allowsUndo = true
        tv.isAutomaticQuoteSubstitutionEnabled = false
        tv.isAutomaticDashSubstitutionEnabled = false
        tv.isAutomaticTextReplacementEnabled = false
        tv.isAutomaticSpellingCorrectionEnabled = false
        tv.isContinuousSpellCheckingEnabled = false
        tv.textContainerInset = NSSize(width: 8, height: 6)
        tv.textContainer?.lineFragmentPadding = 0
        tv.textContainer?.widthTracksTextView = true
        tv.drawsBackground = true
        tv.backgroundColor = .textBackgroundColor
        let para = NSMutableParagraphStyle()
        para.minimumLineHeight = ceil(Self.font(fontSize).ascender - Self.font(fontSize).descender) + 4
        tv.defaultParagraphStyle = para
        tv.typingAttributes[.paragraphStyle] = para
        tv.string = text
        tv.onSplit = onSplit
        return tv
    }

    func updateNSView(_ tv: LockedNSTextView, context: Context) {
        context.coordinator.parent = self
        tv.onSplit = onSplit
        if tv.string != text { tv.string = text }
    }

    final class Coordinator: NSObject, NSTextViewDelegate {
        var parent: LockedTextView
        init(_ p: LockedTextView) { parent = p }

        func textView(_ textView: NSTextView, shouldChangeTextIn range: NSRange, replacementString s: String?) -> Bool {
            guard let s else { return true }
            if !parent.multiline && s.contains("\n") { return false }
            let candidate = (textView.string as NSString).replacingCharacters(in: range, with: s)
            if parent.validate(candidate) { return true }
            NSSound.beep()
            parent.onReject(s.count > 1)
            return false
        }

        func textDidChange(_ n: Notification) {
            guard let tv = n.object as? NSTextView else { return }
            parent.text = tv.string
        }

        func textDidBeginEditing(_ n: Notification) { parent.onFocus() }

        func textView(_ textView: NSTextView, doCommandBy sel: Selector) -> Bool {
            if sel == #selector(NSResponder.insertTab(_:)) { textView.window?.selectNextKeyView(nil); return true }
            if sel == #selector(NSResponder.insertBacktab(_:)) { textView.window?.selectPreviousKeyView(nil); return true }
            if !parent.multiline && sel == #selector(NSResponder.insertNewline(_:)) { return true }
            return false
        }
    }
}

final class LockedNSTextView: NSTextView {
    var onSplit: ((Int) -> Void)?

    override func becomeFirstResponder() -> Bool {
        let ok = super.becomeFirstResponder()
        if ok { (delegate as? LockedTextView.Coordinator)?.parent.onFocus() }
        return ok
    }

    override func keyDown(with event: NSEvent) {
        // ⌘↩ splits the box at the cursor
        if event.keyCode == 36, event.modifierFlags.contains(.command), let onSplit {
            onSplit(selectedRange().location)
            return
        }
        super.keyDown(with: event)
    }
}
