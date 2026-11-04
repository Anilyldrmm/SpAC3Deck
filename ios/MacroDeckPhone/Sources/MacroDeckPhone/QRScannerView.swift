import AVFoundation
import SwiftUI

/// PC'deki MacroDeck QR'ını okur: `http://<adres>:<port>/deck?token=<PIN>` → (adres:port, PIN).
func parseDeckQR(_ text: String) -> (host: String, pin: String)? {
    guard let url = URL(string: text), url.scheme == "http", let host = url.host, !host.isEmpty,
          let pin = URLComponents(url: url, resolvingAgainstBaseURL: false)?
              .queryItems?.first(where: { $0.name == "token" })?.value, !pin.isEmpty else { return nil }
    return ("\(host):\(url.port ?? 8765)", pin)
}

struct QRScannerView: View {
    let onScan: (String, String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var denied = false

    var body: some View {
        ZStack(alignment: .top) {
            if denied {
                Text("Kamera izni kapalı. Ayarlar > MacroDeck > Kamera'dan aç.")
                    .multilineTextAlignment(.center).padding(32).frame(maxHeight: .infinity)
            } else {
                ScannerRepresentable { text in
                    guard let (host, pin) = parseDeckQR(text) else { return false }
                    onScan(host, pin)
                    dismiss()
                    return true
                } onDenied: { denied = true }
                .ignoresSafeArea()
                Text("PC'deki MacroDeck QR kodunu okut")
                    .font(.subheadline.weight(.semibold)).padding(.horizontal, 16).padding(.vertical, 10)
                    .background(.ultraThinMaterial, in: Capsule()).padding(.top, 24)
            }
        }
        .overlay(alignment: .topTrailing) {
            Button("Kapat") { dismiss() }.padding(20)
        }
    }
}

private struct ScannerRepresentable: UIViewControllerRepresentable {
    /// true dönerse okuma kabul edildi, tarama durur.
    let onCode: (String) -> Bool
    let onDenied: () -> Void

    func makeUIViewController(context: Context) -> ScannerController {
        let controller = ScannerController()
        controller.onCode = onCode
        controller.onDenied = onDenied
        return controller
    }

    func updateUIViewController(_ controller: ScannerController, context: Context) {}
}

private final class ScannerController: UIViewController, AVCaptureMetadataOutputObjectsDelegate {
    var onCode: ((String) -> Bool)?
    var onDenied: (() -> Void)?
    private let session = AVCaptureSession()
    private var preview: AVCaptureVideoPreviewLayer?
    private var done = false

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        AVCaptureDevice.requestAccess(for: .video) { granted in
            DispatchQueue.main.async { granted ? self.start() : self.onDenied?() }
        }
    }

    private func start() {
        guard let device = AVCaptureDevice.default(for: .video),
              let input = try? AVCaptureDeviceInput(device: device),
              session.canAddInput(input) else { onDenied?(); return }
        session.addInput(input)
        let output = AVCaptureMetadataOutput()
        guard session.canAddOutput(output) else { return }
        session.addOutput(output)
        output.setMetadataObjectsDelegate(self, queue: .main)
        output.metadataObjectTypes = [.qr]
        let layer = AVCaptureVideoPreviewLayer(session: session)
        layer.videoGravity = .resizeAspectFill
        layer.frame = view.bounds
        view.layer.addSublayer(layer)
        preview = layer
        DispatchQueue.global(qos: .userInitiated).async { self.session.startRunning() }
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        preview?.frame = view.bounds
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        if session.isRunning { session.stopRunning() }
    }

    func metadataOutput(_ output: AVCaptureMetadataOutput, didOutput objects: [AVMetadataObject], from connection: AVCaptureConnection) {
        guard !done, let text = (objects.first as? AVMetadataMachineReadableCodeObject)?.stringValue else { return }
        if onCode?(text) == true { done = true; session.stopRunning() }
    }
}
