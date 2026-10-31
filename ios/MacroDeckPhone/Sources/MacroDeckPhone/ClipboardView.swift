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
                        // pano okuması (Evrensel Pano / izin penceresi) ana iş parçacığını bekletmesin
                        Task {
                            let text = await Task.detached { UIPasteboard.general.string }.value
                            if let text, !text.isEmpty {
                                deck.sendClipboard(text)
                                sent.toggle()
                            }
                        }
                    } label: {
                        Label("Telefondaki panoyu PC'ye gönder", systemImage: "arrow.up.doc")
                    }
                    .sensoryFeedback(.success, trigger: sent)
                } footer: {
                    Text("iOS, başka bir uygulamanın panosunu okurken \"Yapıştırmaya izin ver\" diye sorabilir.")
                }

                if deck.clipHistory.count > 1 {
                    Section("Geçmiş") {
                        ForEach(deck.clipHistory.dropFirst()) { entry in
                            Button {
                                UIPasteboard.general.string = entry.text
                                copied.toggle()
                            } label: {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(entry.text).lineLimit(2).foregroundStyle(.primary)
                                    Text(entry.date.formatted(date: .omitted, time: .shortened))
                                        .font(.caption2).foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
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
