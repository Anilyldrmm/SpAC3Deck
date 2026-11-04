import SwiftUI

enum Brand {
    /// Web arayüzündeki yeşil vurgu (#4caf50).
    static let accent = Color(red: 0.298, green: 0.686, blue: 0.314)
    static let accentDeep = Color(red: 0.180, green: 0.525, blue: 0.239)
    static let accentGradient = LinearGradient(colors: [accent, accentDeep], startPoint: .topLeading, endPoint: .bottomTrailing)
}

@main
struct MacroDeckPhoneApp: App {
    @State private var deck = DeckConnection()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(deck)
                .tint(Brand.accent)
                .task { deck.autoConnect() }
        }
    }
}

enum AppTab: Hashable {
    case deck, pad, clipboard, files, settings
}

struct RootView: View {
    @Environment(DeckConnection.self) private var deck
    @Environment(\.scenePhase) private var scenePhase
    @State private var tab: AppTab = .deck
    @State private var showSplash = true

    var body: some View {
        ZStack {
            content
            if showSplash {
                SplashView()
                    .transition(.opacity)
                    .zIndex(1)
            }
        }
        .task {
            try? await Task.sleep(nanoseconds: 1_300_000_000)
            withAnimation(.easeOut(duration: 0.45)) { showSplash = false }
        }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { deck.resume() }
        }
    }

    @ViewBuilder
    private var content: some View {
        if deck.config != nil {
            TabView(selection: $tab) {
                DeckView()
                    .tabItem { Label("Deck", systemImage: "square.grid.2x2.fill") }
                    .tag(AppTab.deck)
                TrackpadView(onClose: { tab = .deck })
                    .tabItem { Label("İz pedi", systemImage: "hand.point.up.left.fill") }
                    .tag(AppTab.pad)
                ClipboardView()
                    .tabItem { Label("Pano", systemImage: "doc.on.clipboard.fill") }
                    .tag(AppTab.clipboard)
                FilesView()
                    .tabItem { Label("Dosya", systemImage: "folder.fill") }
                    .tag(AppTab.files)
                SettingsView()
                    .tabItem { Label("Ayarlar", systemImage: "gearshape.fill") }
                    .tag(AppTab.settings)
            }
        } else if deck.state == .reconnecting || deck.state == .connecting {
            // kayıtlı PC'ye bağlanılıyor: PIN formunu gösterme
            VStack(spacing: 18) {
                ProgressView().controlSize(.large)
                Text("PC'ye bağlanılıyor…").font(.headline)
                Text(deck.host).font(.subheadline).foregroundStyle(.secondary)
                if let last = deck.lastDisconnect {
                    Text(last).font(.footnote).foregroundStyle(.orange)
                        .multilineTextAlignment(.center).padding(.horizontal, 24)
                }
                Button("Vazgeç") { deck.cancel() }.buttonStyle(.bordered)
            }
        } else {
            ConnectView()
        }
    }
}

/// Açılış animasyonu: logo yaylanarak büyür, ışık halkası yayılır, ad belirir.
struct SplashView: View {
    @State private var shown = false
    @State private var ring = false

    var body: some View {
        ZStack {
            Color(.systemBackground).ignoresSafeArea()
            VStack(spacing: 22) {
                ZStack {
                    Circle()
                        .stroke(Brand.accent.opacity(0.35), lineWidth: 2)
                        .frame(width: 120, height: 120)
                        .scaleEffect(ring ? 2.2 : 1)
                        .opacity(ring ? 0 : 1)
                    LogoMark(size: 112)
                        .scaleEffect(shown ? 1 : 0.55)
                        .rotationEffect(.degrees(shown ? 0 : -14))
                        .opacity(shown ? 1 : 0)
                }
                Text("MacroDeck")
                    .font(.system(size: 30, weight: .bold, design: .rounded))
                    .opacity(shown ? 1 : 0)
                    .offset(y: shown ? 0 : 10)
            }
        }
        .onAppear {
            withAnimation(.spring(response: 0.6, dampingFraction: 0.62)) { shown = true }
            withAnimation(.easeOut(duration: 1.0).delay(0.15)) { ring = true }
        }
        .accessibilityHidden(true)
    }
}

/// Uygulama simgesine benzeyen yeşil kare logo (ızgara + parlama).
struct LogoMark: View {
    let size: CGFloat

    var body: some View {
        RoundedRectangle(cornerRadius: size * 0.225, style: .continuous)
            .fill(Brand.accentGradient)
            .frame(width: size, height: size)
            .overlay {
                Image(systemName: "square.grid.2x2.fill")
                    .font(.system(size: size * 0.46, weight: .semibold))
                    .foregroundStyle(.white)
            }
            .shadow(color: Brand.accent.opacity(0.4), radius: size * 0.16, y: size * 0.06)
    }
}

struct ConnectView: View {
    @Environment(DeckConnection.self) private var deck
    @AppStorage("deckHost") private var host = ""
    @State private var pin = ""
    @FocusState private var focus: Field?
    @State private var scanning = false

    private enum Field { case host, pin }

    private var busy: Bool { deck.state == .connecting }
    private var canConnect: Bool { !host.trimmingCharacters(in: .whitespaces).isEmpty && !pin.isEmpty && !busy }

    var body: some View {
        ScrollView {
            VStack(spacing: 26) {
                VStack(spacing: 12) {
                    LogoMark(size: 84)
                    Text("MacroDeck").font(.system(size: 28, weight: .bold, design: .rounded))
                    Text("PC'ne bağlan. Bir kere girersin, sonra kendi bağlanır.")
                        .font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
                }
                .padding(.top, 40)

                VStack(spacing: 14) {
                    field("PC adresi", icon: "desktopcomputer") {
                        TextField("masaustu-adi.local veya 192.168.1.20", text: $host)
                            .keyboardType(.numbersAndPunctuation)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .focused($focus, equals: .host)
                            .submitLabel(.next)
                            .onSubmit { focus = .pin }
                    }
                    field("PIN", icon: "lock.fill") {
                        SecureField("4 haneli PIN", text: $pin)
                            .keyboardType(.numberPad)
                            .focused($focus, equals: .pin)
                    }
                }

                Button { focus = nil; scanning = true } label: {
                    Label("QR kodu okut", systemImage: "qrcode.viewfinder")
                        .font(.headline).frame(maxWidth: .infinity).padding(.vertical, 15)
                        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                        .foregroundStyle(Brand.accent)
                }

                if case .failed(let message) = deck.state {
                    Label(message, systemImage: "exclamationmark.triangle.fill")
                        .font(.footnote).foregroundStyle(.red)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }

                Button {
                    focus = nil
                    deck.connect(host: host, pin: pin, persistent: true)
                } label: {
                    HStack {
                        if busy { ProgressView().tint(.white) }
                        Text(busy ? "Bağlanıyor…" : "Bağlan").font(.headline)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 15)
                    .background(canConnect ? AnyShapeStyle(Brand.accentGradient) : AnyShapeStyle(Color.gray.opacity(0.35)),
                                in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                    .foregroundStyle(.white)
                }
                .disabled(!canConnect)

                Text("Adres ve PIN, PC'deki MacroDeck'in tepsi menüsünde yazar. Telefon ve PC aynı Wi-Fi'de olmalı.")
                    .font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center)
            }
            .padding(.horizontal, 24)
            .padding(.bottom, 32)
        }
        .scrollDismissesKeyboard(.interactively)
        .background(Color(.systemGroupedBackground).ignoresSafeArea())
        .onAppear { pin = PinStore.load() ?? "" }
        .sheet(isPresented: $scanning) {
            QRScannerView { scannedHost, scannedPin in
                host = scannedHost
                pin = scannedPin
                deck.connect(host: scannedHost, pin: scannedPin, persistent: true)
            }
        }
    }

    private func field<Content: View>(_ title: String, icon: String, @ViewBuilder content: () -> Content) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon).foregroundStyle(Brand.accent).frame(width: 22)
            content()
        }
        .padding(.horizontal, 16)
        .frame(height: 54)
        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .accessibilityLabel(title)
    }
}
