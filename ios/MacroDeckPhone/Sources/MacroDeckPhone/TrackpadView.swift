import SwiftUI
import UIKit

/// Tam ekran iz pedi: tüm yüzey jest alanı. Düğme yok; üstte yalnızca küçük bir çubuk var.
struct TrackpadView: View {
    @Environment(DeckConnection.self) private var deck
    @AppStorage("padSpeed") private var speed = 1.6
    @AppStorage("naturalScroll") private var natural = true
    @State private var stream = ScreenStream()
    @State private var showScreen = false
    @State private var showKeyboard = false
    @State private var showHelp = false
    @State private var fullscreen = false
    @State private var monitors: [PCMonitor] = []
    @State private var monitor = 0
    let onClose: () -> Void

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            if showScreen, let image = stream.image {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFit()
                    .opacity(0.9)
                    .ignoresSafeArea()
            } else if !showScreen {
                Text("İz pedi")
                    .font(.title3.weight(.medium))
                    .foregroundStyle(.white.opacity(0.18))
                    .accessibilityHidden(true)
            }
            PadSurface(deck: deck, speed: speed, natural: natural)
                .ignoresSafeArea()
            KeyCapture(deck: deck, active: $showKeyboard)
                .frame(width: 1, height: 1)
                .opacity(0.01)
                .accessibilityHidden(true)
        }
        .overlay(alignment: .top) { fullscreen ? AnyView(handle) : AnyView(topBar) }
        .toolbar(.hidden, for: .tabBar)
        .statusBarHidden(true)
        .persistentSystemOverlays(fullscreen ? .hidden : .automatic)
        .onAppear { UIApplication.shared.isIdleTimerDisabled = true }
        .onDisappear {
            UIApplication.shared.isIdleTimerDisabled = false
            stream.stop()
            showScreen = false
            showKeyboard = false
            fullscreen = false
        }
        .onChange(of: showScreen) { _, on in
            if on { Task { await loadMonitors() }; restartStream() } else { stream.stop() }
        }
        .onChange(of: monitor) { _, _ in restartStream() }
        .onChange(of: fullscreen) { _, _ in restartStream() } // tam ekranda daha keskin kare
        .sheet(isPresented: $showHelp) { PadHelp() }
    }

    private var topBar: some View {
        HStack(spacing: 6) {
            barButton("xmark", label: "Kapat", action: onClose)
            Spacer()
            if showScreen {
                if monitors.count > 1 { monitorMenu }
                barButton("arrow.up.left.and.arrow.down.right", label: "Tam ekran") { fullscreen = true }
            }
            barButton("display", label: showScreen ? "Ekranı gizle" : "PC ekranını göster", on: showScreen) {
                showScreen.toggle()
            }
            barButton("keyboard", label: showKeyboard ? "Klavyeyi kapat" : "Klavye", on: showKeyboard) {
                showKeyboard.toggle()
            }
            barButton("questionmark", label: "Jestler") { showHelp = true }
        }
        .padding(.horizontal, 12)
        .padding(.top, 6)
    }

    /// Tam ekranda tek küçük tutamaç kalır; dokununca çubuk geri gelir.
    private var handle: some View {
        Button { fullscreen = false } label: {
            Image(systemName: "arrow.down.right.and.arrow.up.left")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(.white.opacity(0.8))
                .frame(width: 44, height: 44)
                .background(.ultraThinMaterial.opacity(0.6), in: Circle())
        }
        .accessibilityLabel("Tam ekrandan çık")
        .padding(.top, 4)
    }

    private var monitorMenu: some View {
        Menu {
            ForEach(monitors) { m in
                Button {
                    monitor = m.index
                } label: {
                    Label("Ekran \(m.index + 1) (\(m.width)×\(m.height))" + (m.primary ? " · ana" : ""),
                          systemImage: monitor == m.index ? "checkmark" : "display")
                }
            }
        } label: {
            Text("\(monitor + 1)")
                .font(.system(size: 16, weight: .bold))
                .foregroundStyle(.white)
                .frame(width: 44, height: 44)
                .background(.ultraThinMaterial, in: Circle())
        }
        .accessibilityLabel("Ekran seç")
    }

    private func restartStream() {
        guard showScreen else { return }
        let items = [
            URLQueryItem(name: "monitor", value: String(monitor)),
            URLQueryItem(name: "width", value: fullscreen ? "1600" : "1000"),
        ]
        if let url = deck.wsURL("/ws/screen", items: items) { stream.start(url) }
    }

    private func loadMonitors() async {
        guard let url = deck.restURL("/api/monitors"),
              let (data, _) = try? await URLSession.shared.data(from: url),
              let list = try? JSONDecoder().decode(MonitorList.self, from: data) else { return }
        monitors = list.monitors
        if monitor >= monitors.count { monitor = 0 }
    }

    private func barButton(_ symbol: String, label: String, on: Bool = false, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(on ? Color.black : Color.white)
                .frame(width: 44, height: 44)
                .background(on ? AnyShapeStyle(Brand.accent) : AnyShapeStyle(.ultraThinMaterial), in: Circle())
        }
        .accessibilityLabel(label)
    }
}

private struct MonitorList: Decodable { var monitors: [PCMonitor] }

struct PCMonitor: Decodable, Identifiable {
    var index: Int
    var width: Int
    var height: Int
    var primary: Bool
    var id: Int { index }
}

private struct PadHelp: View {
    @Environment(\.dismiss) private var dismiss

    private let rows: [(String, String, String)] = [
        ("hand.point.up.left", "Bir parmak sürükle", "İmleci taşı"),
        ("hand.tap", "Bir parmakla dokun", "Sol tık"),
        ("hand.tap.fill", "İki parmakla dokun", "Sağ tık"),
        ("circle.grid.3x3", "Üç parmakla dokun", "Orta tık"),
        ("arrow.up.and.down", "İki parmak sürükle", "Kaydır"),
        ("hand.draw", "Dokun, hemen bas ve sürükle", "Tutup sürükle (pencere taşı, metin seç)"),
    ]

    var body: some View {
        NavigationStack {
            List(rows, id: \.1) { symbol, gesture, result in
                Label {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(gesture)
                        Text(result).font(.subheadline).foregroundStyle(.secondary)
                    }
                } icon: {
                    Image(systemName: symbol).foregroundStyle(Brand.accent)
                }
            }
            .navigationTitle("Jestler")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Bitti") { dismiss() } } }
        }
        .presentationDetents([.medium])
    }
}

// MARK: - Jest yüzeyi (UIKit: çok parmaklı jestler SwiftUI'de güvenilir değil)

struct PadSurface: UIViewRepresentable {
    let deck: DeckConnection
    let speed: Double
    let natural: Bool

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> UIView {
        let view = UIView()
        view.backgroundColor = .clear
        view.isMultipleTouchEnabled = true
        let c = context.coordinator

        func tap(_ touches: Int, _ action: Selector) -> UITapGestureRecognizer {
            let g = UITapGestureRecognizer(target: c, action: action)
            g.numberOfTouchesRequired = touches
            g.delegate = c
            view.addGestureRecognizer(g)
            return g
        }
        _ = tap(1, #selector(Coordinator.leftTap))
        _ = tap(2, #selector(Coordinator.rightTap))
        _ = tap(3, #selector(Coordinator.middleTap))

        let move = UIPanGestureRecognizer(target: c, action: #selector(Coordinator.move(_:)))
        move.minimumNumberOfTouches = 1
        move.maximumNumberOfTouches = 1
        move.delegate = c
        view.addGestureRecognizer(move)

        let scroll = UIPanGestureRecognizer(target: c, action: #selector(Coordinator.scroll(_:)))
        scroll.minimumNumberOfTouches = 2
        scroll.maximumNumberOfTouches = 2
        scroll.delegate = c
        view.addGestureRecognizer(scroll)

        // dokun + hemen bas-tut: sol tuş basılı sürükleme
        let drag = UILongPressGestureRecognizer(target: c, action: #selector(Coordinator.drag(_:)))
        drag.numberOfTapsRequired = 1
        drag.minimumPressDuration = 0.12
        drag.allowableMovement = 10_000
        drag.delegate = c
        view.addGestureRecognizer(drag)
        return view
    }

    func updateUIView(_ view: UIView, context: Context) {
        let c = context.coordinator
        c.deck = deck
        c.speed = speed
        c.natural = natural
    }

    final class Coordinator: NSObject, UIGestureRecognizerDelegate {
        var deck: DeckConnection?
        var speed = 1.6
        var natural = true
        private var dragging = false
        private var dragEnded = Date.distantPast
        private var scrollRemainder = 0.0
        private var moveRemainder = CGPoint.zero
        private let light = UIImpactFeedbackGenerator(style: .light)
        private let heavy = UIImpactFeedbackGenerator(style: .medium)

        func gestureRecognizer(_ g: UIGestureRecognizer, shouldRecognizeSimultaneouslyWith other: UIGestureRecognizer) -> Bool {
            // tap-sürükleme ile imleç hareketi birlikte çalışmalı
            g is UILongPressGestureRecognizer || other is UILongPressGestureRecognizer
        }

        @MainActor @objc func leftTap() {
            // sürükleme bırakıldıktan hemen sonra gelen tap'i yok say
            guard !dragging, Date().timeIntervalSince(dragEnded) > 0.2 else { return }
            light.impactOccurred(intensity: 0.5)
            deck?.click("left")
        }

        @MainActor @objc func rightTap() { light.impactOccurred(); deck?.click("right") }
        @MainActor @objc func middleTap() { light.impactOccurred(); deck?.click("middle") }

        @MainActor @objc func move(_ g: UIPanGestureRecognizer) {
            guard let view = g.view else { return }
            switch g.state {
            case .began:
                moveRemainder = .zero
                g.setTranslation(.zero, in: view)
            case .changed:
                send(pan: g, in: view)
            default: break
            }
        }

        @MainActor @objc func drag(_ g: UILongPressGestureRecognizer) {
            guard let view = g.view else { return }
            switch g.state {
            case .began:
                dragging = true
                moveRemainder = .zero
                lastDragPoint = g.location(in: view)
                heavy.impactOccurred()
                deck?.mouseButton("left", down: true)
            case .changed:
                let point = g.location(in: view)
                let dx = point.x - lastDragPoint.x
                let dy = point.y - lastDragPoint.y
                lastDragPoint = point
                emit(dx: dx, dy: dy, velocity: 0)
            case .ended, .cancelled, .failed:
                if dragging {
                    deck?.mouseButton("left", down: false)
                    dragging = false
                    dragEnded = Date()
                }
            default: break
            }
        }

        private var lastDragPoint = CGPoint.zero

        @MainActor private func send(pan g: UIPanGestureRecognizer, in view: UIView) {
            let t = g.translation(in: view)
            g.setTranslation(.zero, in: view)
            let v = g.velocity(in: view)
            emit(dx: t.x, dy: t.y, velocity: hypot(v.x, v.y))
        }

        /// Hıza bağlı ivme: yavaş = hassas, hızlı = uzun mesafe. Kesirli pikseller biriktirilir.
        @MainActor private func emit(dx: CGFloat, dy: CGFloat, velocity: CGFloat) {
            let gain = speed * (1 + min(Double(velocity) / 1400, 1.8))
            moveRemainder.x += dx * gain
            moveRemainder.y += dy * gain
            let ix = moveRemainder.x.rounded(.towardZero)
            let iy = moveRemainder.y.rounded(.towardZero)
            guard ix != 0 || iy != 0 else { return }
            moveRemainder.x -= ix
            moveRemainder.y -= iy
            deck?.move(dx: Double(ix), dy: Double(iy))
        }

        @MainActor @objc func scroll(_ g: UIPanGestureRecognizer) {
            guard let view = g.view else { return }
            switch g.state {
            case .began:
                scrollRemainder = 0
                g.setTranslation(.zero, in: view)
            case .changed:
                let t = g.translation(in: view)
                g.setTranslation(.zero, in: view)
                // 1 adım = 120 birim; ~14 pt'de bir adım. Pozitif = yukarı kaydır.
                scrollRemainder += Double(t.y) / 14 * (natural ? 1 : -1)
                let steps = Int(scrollRemainder.rounded(.towardZero))
                if steps != 0 {
                    scrollRemainder -= Double(steps)
                    deck?.scroll(steps)
                }
            default: break
            }
        }
    }
}

// MARK: - Klavye (gizli UIKeyInput görünümü: yazılan her karakter anında PC'ye gider)

struct KeyCapture: UIViewRepresentable {
    let deck: DeckConnection
    @Binding var active: Bool

    func makeUIView(context: Context) -> KeyInputView { KeyInputView() }

    func updateUIView(_ view: KeyInputView, context: Context) {
        view.deck = deck
        if active, !view.isFirstResponder {
            DispatchQueue.main.async { view.becomeFirstResponder() }
        } else if !active, view.isFirstResponder {
            DispatchQueue.main.async { _ = view.resignFirstResponder() }
        }
        view.onDismiss = { active = false }
    }
}

final class KeyInputView: UIView, UIKeyInput {
    var deck: DeckConnection?
    var onDismiss: (() -> Void)?

    override var canBecomeFirstResponder: Bool { true }
    var hasText: Bool { true }
    var autocorrectionType: UITextAutocorrectionType = .no
    var autocapitalizationType: UITextAutocapitalizationType = .none
    var spellCheckingType: UITextSpellCheckingType = .no
    var smartQuotesType: UITextSmartQuotesType = .no
    var smartDashesType: UITextSmartDashesType = .no
    var keyboardType: UIKeyboardType = .default

    override func resignFirstResponder() -> Bool {
        let result = super.resignFirstResponder()
        onDismiss?()
        return result
    }

    func insertText(_ text: String) {
        let deck = deck
        Task { @MainActor in
            if text == "\n" { deck?.key("enter") } else { deck?.type(text) }
        }
    }

    func deleteBackward() {
        let deck = deck
        Task { @MainActor in deck?.key("backspace") }
    }
}

// MARK: - PC ekranı akışı

@MainActor @Observable
final class ScreenStream {
    var image: UIImage?
    private var socket: URLSessionWebSocketTask?
    private var task: Task<Void, Never>?

    func start(_ url: URL) {
        stop()
        let socket = URLSession.shared.webSocketTask(with: url)
        self.socket = socket
        socket.resume()
        task = Task {
            while !Task.isCancelled {
                guard let message = try? await socket.receive() else { break }
                if case .data(let data) = message {
                    // 60 fps'te çözme ana iş parçacığını yormasın
                    let frame = await Task.detached(priority: .userInitiated) { UIImage(data: data)?.preparingForDisplay() }.value
                    if let frame { image = frame }
                }
            }
        }
    }

    func stop() {
        task?.cancel()
        task = nil
        socket?.cancel(with: .goingAway, reason: nil)
        socket = nil
        image = nil
    }
}
