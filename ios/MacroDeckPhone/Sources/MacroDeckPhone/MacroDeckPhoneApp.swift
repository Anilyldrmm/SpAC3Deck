import SwiftUI

@main
struct MacroDeckPhoneApp: App {
    @State private var deck = DeckConnection()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(deck)
                .preferredColorScheme(.dark)
        }
    }
}

struct RootView: View {
    @Environment(DeckConnection.self) private var deck

    var body: some View {
        if deck.state == .connected {
            TabView {
                TrackpadView()
                    .tabItem { Label("İz pedi", systemImage: "rectangle.and.hand.point.up.left") }
                ClipboardView()
                    .tabItem { Label("Pano", systemImage: "doc.on.clipboard") }
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

    var body: some View {
        VStack(spacing: 14) {
            Text("MacroDeck").font(.largeTitle.bold())
            TextField("PC adresi (örn. 192.168.1.41)", text: $host)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .keyboardType(.URL)
                .textFieldStyle(.roundedBorder)
            TextField("PIN", text: $pin)
                .keyboardType(.numberPad)
                .textFieldStyle(.roundedBorder)
            Button(deck.state == .connecting ? "Bağlanıyor…" : "Bağlan") {
                deck.connect(host: host, pin: pin)
            }
            .buttonStyle(.borderedProminent)
            .disabled(host.isEmpty || pin.isEmpty || deck.state == .connecting)
            if case .failed(let message) = deck.state {
                Text(message).foregroundStyle(.red).font(.footnote)
            }
        }
        .padding(24)
        .frame(maxWidth: 420)
    }
}
