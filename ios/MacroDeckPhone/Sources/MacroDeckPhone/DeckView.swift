import SwiftUI

/// Deck: PC'deki MacroDeck butonları. Sayfalar, kare butonlar, durum rozetleri, sürgüler.
struct DeckView: View {
    @Environment(DeckConnection.self) private var deck
    @State private var pageName = ""

    var body: some View {
        NavigationStack {
            Group {
                if let config = deck.config, let page = currentPage(config) {
                    ScrollView {
                        VStack(spacing: 14) {
                            if config.pages.count > 1 {
                                Picker("Sayfa", selection: pageSelection(config)) {
                                    ForEach(config.pages) { page in
                                        Text(page.name).tag(page.name)
                                    }
                                }
                                .pickerStyle(.segmented)
                            }
                            DeckGrid(page: page, columns: max(1, config.gridColumns))
                        }
                        .padding(16)
                    }
                } else {
                    ContentUnavailableView(
                        "Buton yok",
                        systemImage: "square.grid.2x2",
                        description: Text("PC'deki MacroDeck ayarlarından buton ekleyebilirsin.")
                    )
                }
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle("Deck")
            .navigationBarTitleDisplayMode(.inline)
            .safeAreaInset(edge: .top) { ConnectionBanner() }
        }
    }

    private func currentPage(_ config: DeckConfig) -> Page? {
        config.pages.first { $0.name == pageName } ?? config.pages.first
    }

    private func pageSelection(_ config: DeckConfig) -> Binding<String> {
        Binding(
            get: { currentPage(config)?.name ?? "" },
            set: { pageName = $0 }
        )
    }
}

struct ConnectionBanner: View {
    @Environment(DeckConnection.self) private var deck

    var body: some View {
        if deck.state == .reconnecting {
            Label("Bağlantı koptu, yeniden bağlanılıyor…", systemImage: "wifi.exclamationmark")
                .font(.footnote.weight(.medium))
                .padding(.horizontal, 14)
                .padding(.vertical, 8)
                .frame(maxWidth: .infinity)
                .background(.orange.opacity(0.9))
                .foregroundStyle(.white)
        }
    }
}

private struct DeckRow: Identifiable {
    let buttons: [DeckButton]
    var id: String { buttons.map { $0.id }.joined(separator: "+") }
}

struct DeckGrid: View {
    let page: Page
    let columns: Int

    /// Kare butonlar `columns` kadarlık satırlara dizilir, sürgüler tam genişlikte kendi satırını alır.
    private var rows: [DeckRow] {
        var result: [DeckRow] = []
        var current: [DeckButton] = []
        for button in page.buttons {
            if case .gain = button.kind {
                if !current.isEmpty { result.append(DeckRow(buttons: current)); current = [] }
                result.append(DeckRow(buttons: [button]))
            } else {
                current.append(button)
                if current.count == columns { result.append(DeckRow(buttons: current)); current = [] }
            }
        }
        if !current.isEmpty { result.append(DeckRow(buttons: current)) }
        return result
    }

    var body: some View {
        VStack(spacing: 12) {
            ForEach(rows) { row in
                if row.buttons.count == 1, case .gain = row.buttons[0].kind {
                    GainTile(page: page, button: row.buttons[0])
                } else {
                    HStack(spacing: 12) {
                        ForEach(row.buttons) { button in
                            ButtonTile(page: page, button: button)
                        }
                        ForEach(0..<(columns - row.buttons.count), id: \.self) { _ in
                            Color.clear.frame(maxWidth: .infinity)
                        }
                    }
                }
            }
        }
    }
}

/// iPhone ana ekranındaki uygulama simgeleri gibi sürekli köşeli kare.
private let tileShape = RoundedRectangle(cornerRadius: 22, style: .continuous)

struct ButtonTile: View {
    @Environment(DeckConnection.self) private var deck
    let page: Page
    let button: DeckButton
    @State private var taps = 0

    private var isOn: Bool {
        if case .toggle(let key, _, _) = button.kind { return deck.values[key]?.isOn ?? false }
        return false
    }

    var body: some View {
        Group {
            if case .hold = button.kind {
                face
                    .onLongPressGesture(minimumDuration: 0, maximumDistance: 60, pressing: { pressing in
                        if pressing { taps += 1 }
                        deck.sendEvent(page: page.name, button: button.id, event: pressing ? "press" : "release")
                    }, perform: {})
            } else {
                Button {
                    taps += 1
                    deck.sendEvent(page: page.name, button: button.id, event: "press")
                } label: { face }
                    .buttonStyle(TilePressStyle())
            }
        }
        .sensoryFeedback(.impact(weight: .light), trigger: taps)
        .accessibilityLabel(button.label)
        .accessibilityValue(stateText ?? "")
    }

    private var stateText: String? {
        if case .toggle(_, let on, let off) = button.kind { return isOn ? on : off }
        return nil
    }

    @ViewBuilder
    private var face: some View {
        if button.isImageTile {
            imageFace
        } else {
            symbolFace
        }
    }

    private var symbolFace: some View {
        VStack(spacing: 6) {
            IconView(button: button, size: 30)
                .foregroundStyle(isOn ? Color.white : Brand.accent)
            Text(button.label)
                .font(.caption.weight(.medium))
                .multilineTextAlignment(.center)
                .lineLimit(2)
                .minimumScaleFactor(0.8)
                .foregroundStyle(isOn ? Color.white : Color.primary)
            if let text = stateText {
                Text(text)
                    .font(.system(size: 9, weight: .bold))
                    .foregroundStyle(isOn ? Color.white.opacity(0.85) : Color.secondary)
            }
        }
        .padding(6)
        .frame(maxWidth: .infinity)
        .aspectRatio(1, contentMode: .fit)
        .background(isOn ? Brand.accent : Color(.secondarySystemGroupedBackground), in: tileShape)
    }

    private var imageFace: some View {
        Color(.secondarySystemGroupedBackground)
            .aspectRatio(1, contentMode: .fit)
            .overlay { IconView(button: button, size: nil) }
            .overlay(alignment: .bottom) {
                Text(button.label)
                    .font(.caption2.weight(.semibold))
                    .lineLimit(1)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 5)
                    .frame(maxWidth: .infinity)
                    .background(.ultraThinMaterial)
            }
            .clipShape(tileShape)
    }
}

struct TilePressStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.94 : 1)
            .opacity(configuration.isPressed ? 0.85 : 1)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
    }
}

/// Simge: Steam kapağı / yüklenen görsel (PC'den), Lucide simgesi (SF Symbol'e çevrilir) veya emoji.
struct IconView: View {
    @Environment(DeckConnection.self) private var deck
    let button: DeckButton
    let size: CGFloat?

    var body: some View {
        if button.icon.hasPrefix("/api/icon/"), let url = imageURL {
            AsyncImage(url: url) { image in
                if let size {
                    image.resizable().scaledToFit().frame(width: size, height: size)
                } else {
                    image.resizable().scaledToFill()
                }
            } placeholder: {
                ProgressView()
            }
        } else if button.icon.hasPrefix("http") {
            Image(systemName: Icons.symbol(forURL: button.icon))
                .font(.system(size: size ?? 30, weight: .regular))
        } else if !button.icon.isEmpty {
            Text(button.icon).font(.system(size: (size ?? 30) * 0.9))
        } else {
            Image(systemName: Icons.symbol(forAction: button.action))
                .font(.system(size: size ?? 30, weight: .regular))
        }
    }

    private var imageURL: URL? {
        // Steam kapağı kütüphane kapağına geçince eski görsel önbellekte kalmasın diye v=2
        let items = button.icon.hasPrefix("/api/icon/steam/") ? [URLQueryItem(name: "v", value: "2")] : []
        return deck.restURL(button.icon, items: items)
    }
}

/// Voicemeeter sürgüsü: dB değeri, varsayılana dönüş, PC'deki değerle senkron.
struct GainTile: View {
    @Environment(DeckConnection.self) private var deck
    let page: Page
    let button: DeckButton
    @State private var value = 0.0
    @State private var editing = false
    @State private var lastSent = Date.distantPast

    private var stateKey: String {
        if case .gain(let key, _) = button.kind { return key }
        return ""
    }

    private var defaultValue: Double {
        if case .gain(_, let value) = button.kind { return value }
        return 0
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
                IconView(button: button, size: 22).foregroundStyle(Brand.accent)
                Text(button.label).font(.subheadline.weight(.medium))
                Spacer()
                Text("\(value, specifier: "%.1f") dB")
                    .font(.subheadline.monospacedDigit())
                    .foregroundStyle(.secondary)
                Button {
                    value = defaultValue
                    send(value)
                } label: {
                    Image(systemName: "arrow.counterclockwise")
                        .frame(width: 32, height: 32)
                }
                .accessibilityLabel("Varsayılana dön")
            }
            Slider(value: $value, in: -60...12, step: 0.5) { isEditing in
                editing = isEditing
                if !isEditing { send(value) }
            }
            .onChange(of: value) { _, new in
                // sürüklerken ~16 kez/sn gönder, her değeri değil
                if editing, Date().timeIntervalSince(lastSent) > 0.06 { send(new) }
            }
        }
        .padding(16)
        .background(Color(.secondarySystemGroupedBackground), in: tileShape)
        .onAppear { sync(deck.values[stateKey]) }
        .onChange(of: deck.values[stateKey]) { _, new in
            if !editing { sync(new) }
        }
    }

    private func sync(_ new: JSONValue?) {
        if let number = new?.number { value = number }
    }

    private func send(_ value: Double) {
        lastSent = Date()
        deck.sendEvent(page: page.name, button: button.id, event: "set", value: value)
    }
}
