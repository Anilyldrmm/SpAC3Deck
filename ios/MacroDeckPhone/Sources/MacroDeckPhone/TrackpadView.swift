import SwiftUI

/// Telefon = trackpad + klavye. Tek parmak imleç, dokunma sol tık, sağ kenar şeridi kaydırma.
struct TrackpadView: View {
    @Environment(DeckConnection.self) private var deck
    @State private var last: CGPoint?
    @State private var started = Date()
    @State private var travelled: Double = 0
    @State private var scrollAccumulator: Double = 0
    @State private var typed = ""

    private let tapSlop: Double = 8
    private let tapSeconds: Double = 0.25
    private let speed: Double = 1.6
    private let scrollPixelsPerStep: Double = 24

    var body: some View {
        VStack(spacing: 10) {
            HStack(spacing: 10) {
                pad
                scrollStrip
            }
            HStack {
                TextField("Yaz…", text: $typed)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .textFieldStyle(.roundedBorder)
                    .onChange(of: typed) { _, new in
                        guard !new.isEmpty else { return }
                        deck.type(new)
                        typed = ""
                    }
                keyButton("Sil", "backspace")
                keyButton("Enter", "enter")
                keyButton("Esc", "esc")
                keyButton("Tab", "tab")
            }
            HStack(spacing: 10) {
                Button("Sol tık") { deck.click("left") }
                    .frame(maxWidth: .infinity, minHeight: 48)
                    .buttonStyle(.bordered)
                Button("Sağ tık") { deck.click("right") }
                    .frame(maxWidth: .infinity, minHeight: 48)
                    .buttonStyle(.bordered)
            }
        }
        .padding(14)
    }

    private var pad: some View {
        RoundedRectangle(cornerRadius: 16)
            .fill(Color(white: 0.11))
            .overlay(Text("Parmağını sürükle, dokun = tık").foregroundStyle(.secondary).font(.footnote))
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { value in
                        if let previous = last {
                            let dx = value.location.x - previous.x
                            let dy = value.location.y - previous.y
                            travelled += abs(dx) + abs(dy)
                            deck.move(dx: dx * speed, dy: dy * speed)
                        } else {
                            started = Date()
                            travelled = 0
                        }
                        last = value.location
                    }
                    .onEnded { _ in
                        if Date().timeIntervalSince(started) < tapSeconds, travelled < tapSlop {
                            deck.click("left")
                        }
                        last = nil
                    }
            )
    }

    private var scrollStrip: some View {
        RoundedRectangle(cornerRadius: 16)
            .fill(Color(white: 0.16))
            .frame(width: 56)
            .overlay(Text("Kaydır").font(.caption2).foregroundStyle(.secondary).rotationEffect(.degrees(-90)).fixedSize())
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { value in
                        scrollAccumulator += value.translation.height - lastScrollHeight
                        lastScrollHeight = value.translation.height
                        let steps = Int(scrollAccumulator / scrollPixelsPerStep)
                        if steps != 0 {
                            scrollAccumulator -= Double(steps) * scrollPixelsPerStep
                            deck.scroll(steps)
                        }
                    }
                    .onEnded { _ in
                        lastScrollHeight = 0
                        scrollAccumulator = 0
                    }
            )
    }

    @State private var lastScrollHeight: Double = 0

    private func keyButton(_ title: String, _ key: String) -> some View {
        Button(title) { deck.key(key) }
            .buttonStyle(.bordered)
            .frame(minHeight: 44)
    }
}
