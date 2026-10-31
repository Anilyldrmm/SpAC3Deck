import SwiftUI
#if canImport(UIKit)
import UIKit
#endif

/// PC panosu otomatik gelir; telefondaki pano tek dokunuşla PC'ye gönderilir.
struct ClipboardView: View {
    @Environment(DeckConnection.self) private var deck
    @State private var status = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("PC panosu").font(.footnote).foregroundStyle(.secondary)
            ScrollView {
                Text(deck.pcClipboard.isEmpty ? "PC'de kopyaladığın metin burada görünür" : deck.pcClipboard)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .foregroundStyle(deck.pcClipboard.isEmpty ? .secondary : .primary)
                    .textSelection(.enabled)
            }
            .padding(12)
            .background(Color(white: 0.11), in: RoundedRectangle(cornerRadius: 14))

            Button("Telefona kopyala") {
                #if canImport(UIKit)
                UIPasteboard.general.string = deck.pcClipboard
                #endif
                status = "Kopyalandı"
            }
            .buttonStyle(.borderedProminent)
            .disabled(deck.pcClipboard.isEmpty)

            Button("Telefon panosunu PC'ye gönder") {
                #if canImport(UIKit)
                if let text = UIPasteboard.general.string, !text.isEmpty {
                    deck.sendClipboard(text)
                    status = "Gönderildi"
                } else {
                    status = "Telefon panosunda metin yok"
                }
                #endif
            }
            .buttonStyle(.bordered)

            Text(status).font(.footnote).foregroundStyle(.secondary)
        }
        .padding(14)
    }
}
