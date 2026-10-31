import SwiftUI

enum Brand {
    /// Web arayüzündeki yeşil vurgu (#4caf50).
    static let accent = Color(red: 0.298, green: 0.686, blue: 0.314)
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
    @State private var tab: AppTab = .deck

    var body: some View {
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
        } else {
            ConnectView()
        }
    }
}

struct ConnectView: View {
    @Environment(DeckConnection.self) private var deck
    @AppStorage("deckHost") private var host = ""
    @State private var pin = ""
    @FocusState private var focus: Field?

    private enum Field { case host, pin }

    private var busy: Bool { deck.state == .connecting }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("PC adresi (örn. 192.168.1.20)", text: $host)
                        .keyboardType(.numbersAndPunctuation)
                        .textContentType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .focused($focus, equals: .host)
                        .submitLabel(.next)
                        .onSubmit { focus = .pin }
                    SecureField("PIN", text: $pin)
                        .keyboardType(.numberPad)
                        .focused($focus, equals: .pin)
                } header: {
                    Text("Bilgisayar")
                } footer: {
                    Text("Adres ve PIN, PC'deki MacroDeck'in tepsi menüsünde yazar. Telefon ve PC aynı Wi-Fi'de olmalı.")
                }

                if case .failed(let message) = deck.state {
                    Section { Label(message, systemImage: "exclamationmark.triangle.fill").foregroundStyle(.red) }
                }

                Section {
                    Button {
                        focus = nil
                        deck.connect(host: host, pin: pin)
                    } label: {
                        HStack {
                            Text(busy ? "Bağlanıyor…" : "Bağlan").fontWeight(.semibold)
                            if busy { Spacer(); ProgressView() }
                        }
                    }
                    .disabled(busy || host.trimmingCharacters(in: .whitespaces).isEmpty || pin.isEmpty)
                }
            }
            .navigationTitle("MacroDeck")
            .onAppear { pin = Keychain.get("pin") ?? "" }
        }
    }
}
