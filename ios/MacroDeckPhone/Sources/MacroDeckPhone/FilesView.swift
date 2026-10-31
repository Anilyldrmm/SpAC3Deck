import SwiftUI
import UniformTypeIdentifiers

private struct FileList: Decodable { var files: [RemoteFile] }

private struct SharedFile: Identifiable { let url: URL; var id: URL { url } }

/// Telefondan PC'ye yükleme ("Gelen" klasörü) ve PC'deki "Giden" klasörünü indirme.
struct FilesView: View {
    @Environment(DeckConnection.self) private var deck
    @State private var files: [RemoteFile] = []
    @State private var loading = true
    @State private var picking = false
    @State private var progress: Double?
    @State private var uploadName = ""
    @State private var message: String?
    @State private var shared: SharedFile?
    @State private var downloading: String?
    @State private var done = 0

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Button { picking = true } label: {
                        Label("PC'ye dosya gönder", systemImage: "arrow.up.doc.fill")
                    }
                    .disabled(progress != nil)
                    if let progress {
                        VStack(alignment: .leading, spacing: 6) {
                            Text(uploadName).font(.subheadline).lineLimit(1)
                            ProgressView(value: progress)
                        }
                    }
                    if let message {
                        Text(message).font(.footnote).foregroundStyle(.secondary)
                    }
                } footer: {
                    Text("Gönderilenler PC'de İndirilenler › MacroDeck › Gelen klasörüne düşer.")
                }

                Section {
                    if loading {
                        ProgressView().frame(maxWidth: .infinity)
                    } else if files.isEmpty {
                        Text("PC'deki Giden klasörü boş.").foregroundStyle(.secondary)
                    }
                    ForEach(files) { file in
                        Button { Task { await download(file) } } label: {
                            HStack {
                                Image(systemName: "doc").foregroundStyle(Brand.accent)
                                VStack(alignment: .leading) {
                                    Text(file.name).lineLimit(1).foregroundStyle(.primary)
                                    Text(ByteCountFormatter.string(fromByteCount: Int64(file.size), countStyle: .file))
                                        .font(.caption).foregroundStyle(.secondary)
                                }
                                Spacer()
                                if downloading == file.name { ProgressView() } else {
                                    Image(systemName: "arrow.down.circle").foregroundStyle(.secondary)
                                }
                            }
                        }
                        .disabled(downloading != nil)
                    }
                } header: {
                    Text("PC'den al")
                } footer: {
                    Text("PC'de İndirilenler › MacroDeck › Giden klasörüne koyduğun dosyalar burada listelenir.")
                }
            }
            .navigationTitle("Dosya")
            .refreshable { await reload() }
            .task { await reload() }
            .safeAreaInset(edge: .top) { ConnectionBanner() }
            .fileImporter(isPresented: $picking, allowedContentTypes: [.item]) { result in
                if case .success(let url) = result { Task { await upload(url) } }
            }
            .sheet(item: $shared) { item in ShareSheet(url: item.url) }
            .sensoryFeedback(.success, trigger: done)
        }
    }

    private func reload() async {
        defer { loading = false }
        guard let url = deck.restURL("/api/files"),
              let (data, _) = try? await URLSession.shared.data(from: url),
              let list = try? JSONDecoder().decode(FileList.self, from: data) else { return }
        files = list.files
    }

    private func upload(_ source: URL) async {
        let scoped = source.startAccessingSecurityScopedResource()
        defer { if scoped { source.stopAccessingSecurityScopedResource() } }
        guard let url = deck.restURL("/api/files/upload", items: [URLQueryItem(name: "name", value: source.lastPathComponent)]) else { return }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 3600
        uploadName = source.lastPathComponent
        message = nil
        progress = 0
        defer { progress = nil }
        let tracker = UploadTracker { fraction in Task { @MainActor in progress = fraction } }
        do {
            let (_, response) = try await URLSession.shared.upload(for: request, fromFile: source, delegate: tracker)
            let code = (response as? HTTPURLResponse)?.statusCode ?? 0
            switch code {
            case 200: message = "\(source.lastPathComponent) gönderildi."; done += 1
            case 413: message = "Dosya çok büyük (en fazla 2 GB)."
            case 403: message = "PIN reddedildi."
            default: message = "Gönderilemedi (\(code))."
            }
        } catch {
            message = "Gönderilemedi: bağlantı kesildi."
        }
    }

    private func download(_ file: RemoteFile) async {
        guard let remote = deck.restURL("/api/files/" + (file.name.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? file.name)) else { return }
        downloading = file.name
        defer { downloading = nil }
        do {
            let (temp, response) = try await URLSession.shared.download(from: remote)
            guard (response as? HTTPURLResponse)?.statusCode == 200 else { message = "İndirilemedi."; return }
            let folder = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
            try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
            let target = folder.appendingPathComponent(file.name)
            try FileManager.default.moveItem(at: temp, to: target)
            shared = SharedFile(url: target)
        } catch {
            message = "İndirilemedi: bağlantı kesildi."
        }
    }
}

private final class UploadTracker: NSObject, URLSessionTaskDelegate {
    let onProgress: (Double) -> Void
    init(onProgress: @escaping (Double) -> Void) { self.onProgress = onProgress }

    func urlSession(_ session: URLSession, task: URLSessionTask, didSendBodyData bytesSent: Int64,
                    totalBytesSent: Int64, totalBytesExpectedToSend: Int64) {
        guard totalBytesExpectedToSend > 0 else { return }
        onProgress(Double(totalBytesSent) / Double(totalBytesExpectedToSend))
    }
}

private struct ShareSheet: UIViewControllerRepresentable {
    let url: URL
    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: [url], applicationActivities: nil)
    }
    func updateUIViewController(_ controller: UIActivityViewController, context: Context) {}
}
