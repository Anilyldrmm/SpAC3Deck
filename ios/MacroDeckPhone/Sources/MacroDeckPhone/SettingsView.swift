import SwiftUI

struct SettingsView: View {
    @Environment(DeckConnection.self) private var deck
    @AppStorage("padSpeed") private var speed = 1.6
    @AppStorage("naturalScroll") private var natural = true
    @AppStorage("autoLandscape") private var autoLandscape = true
    @State private var confirmDisconnect = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Bağlantı") {
                    LabeledContent("PC", value: deck.host)
                    LabeledContent("Durum", value: statusText)
                    if let version = deck.serverVersion {
                        LabeledContent("MacroDeck sürümü", value: version)
                    }
                    if let last = deck.lastDisconnect {
                        LabeledContent("Son kopma", value: last)
                    }
                    Button("Bağlantıyı kes", role: .destructive) { confirmDisconnect = true }
                }

                Section {
                    VStack(alignment: .leading) {
                        Text("İmleç hızı")
                        Slider(value: $speed, in: 0.6...3.5) {
                            Text("İmleç hızı")
                        } minimumValueLabel: {
                            Image(systemName: "tortoise")
                        } maximumValueLabel: {
                            Image(systemName: "hare")
                        }
                    }
                    Toggle("Doğal kaydırma", isOn: $natural)
                    Toggle("PC ekranı açılınca yatay çevir", isOn: $autoLandscape)
                } header: {
                    Text("İz pedi")
                } footer: {
                    Text("Doğal kaydırmada parmağın yukarı gidince sayfa da yukarı kayar.")
                }

                Section {
                    LabeledContent("Sürüm", value: Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "1.0")
                }
            }
            .navigationTitle("Ayarlar")
            .safeAreaInset(edge: .top) { ConnectionBanner() }
            .confirmationDialog("PC ile bağlantı kesilsin mi?", isPresented: $confirmDisconnect, titleVisibility: .visible) {
                Button("Bağlantıyı kes", role: .destructive) { deck.disconnect() }
            } message: {
                Text("Kayıtlı PIN silinir; tekrar bağlanmak için yeniden girmen gerekir.")
            }
        }
    }

    private var statusText: String {
        switch deck.state {
        case .connected: return "Bağlı"
        case .reconnecting: return "Yeniden bağlanıyor…"
        case .connecting: return "Bağlanıyor…"
        default: return "Bağlı değil"
        }
    }
}
