import SwiftUI

struct ClipboardView: View {
    @Environment(DeckConnection.self) private var deck
    @AppStorage("autoCopy") private var autoCopy = false
    @State private var sent = false
    @State private var copied = false

    var body: some View {
        NavigationStack {
            Form {
                Section("PC panosu") {
                    if deck.pcClipboard.isEmpty {
                        Text("PC'de kopyalanan metin burada görünür.").foregroundStyle(.secondary)
                    } else {
                        Text(deck.pcClipboard)
                            .lineLimit(12)
                            .textSelection(.enabled)
                    }
                    Button {
                        UIPasteboard.general.string = deck.pcClipboard
                        copied.toggle()
                    } label: {
                        Label("Telefona kopyala", systemImage: "doc.on.doc")
                    }
                    .disabled(deck.pcClipboard.isEmpty)
                    .sensoryFeedback(.success, trigger: copied)
                }

                Section {
                    Button {
                        if let text = UIPasteboard.general.string, !text.isEmpty {
                            deck.sendClipboard(text)
                            sent.toggle()
                        }
                    } label: {
                        Label("Telefondaki panoyu PC'ye gönder", systemImage: "arrow.up.doc")
                    }
                    .sensoryFeedback(.success, trigger: sent)
                } footer: {
                    Text("iOS, başka bir uygulamanın panosunu okurken \"Yapıştırmaya izin ver\" diye sorabilir.")
                }

                Section {
                    Toggle("PC'de kopyalananı otomatik al", isOn: $autoCopy)
                } footer: {
                    Text("Uygulama açıkken PC'de kopyaladığın metin telefon panosuna da geçer.")
                }
            }
            .navigationTitle("Pano")
            .safeAreaInset(edge: .top) { ConnectionBanner() }
        }
    }
}
