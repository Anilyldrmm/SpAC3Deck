import Foundation
import Observation

/// PC'deki MacroDeck sunucusuna WebSocket bağlantısı (web arayüzüyle aynı protokol).
@Observable
final class DeckConnection {
    enum State: Equatable {
        case disconnected
        case connecting
        case connected
        case failed(String)
    }

    var state: State = .disconnected
    var pcClipboard = ""

    private var task: URLSessionWebSocketTask?
    private let session = URLSession(configuration: .default)

    func connect(host: String, pin: String) {
        disconnect()
        let cleaned = host.trimmingCharacters(in: .whitespaces)
        guard var parts = URLComponents(string: "ws://\(cleaned)"), parts.host != nil else {
            state = .failed("Adres geçersiz")
            return
        }
        if parts.port == nil { parts.port = 8765 }
        parts.path = "/ws"
        parts.queryItems = [URLQueryItem(name: "token", value: pin)]
        guard let url = parts.url else {
            state = .failed("Adres geçersiz")
            return
        }

        let socket = session.webSocketTask(with: url)
        task = socket
        state = .connecting
        socket.resume()
        // WebSocket'in açıldığını ve PIN'in kabul edildiğini ping ile anla
        socket.sendPing { [weak self] error in
            guard let self, socket === self.task else { return }
            DispatchQueue.main.async {
                self.state = error == nil ? .connected : .failed("Bağlanılamadı. Adres ve PIN'i kontrol et.")
            }
        }
        receive(socket)
    }

    func disconnect() {
        task?.cancel(with: .goingAway, reason: nil)
        task = nil
        state = .disconnected
    }

    private func receive(_ socket: URLSessionWebSocketTask) {
        socket.receive { [weak self] result in
            guard let self, socket === self.task else { return }
            switch result {
            case .failure:
                DispatchQueue.main.async {
                    if self.state == .connected { self.state = .failed("Bağlantı koptu") }
                }
            case .success(let message):
                if case .string(let text) = message,
                   let data = text.data(using: .utf8),
                   let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   object["type"] as? String == "clipboard",
                   let clip = object["text"] as? String {
                    DispatchQueue.main.async { self.pcClipboard = clip }
                }
                self.receive(socket)
            }
        }
    }

    private func send(_ payload: [String: Any]) {
        guard let socket = task,
              let data = try? JSONSerialization.data(withJSONObject: payload),
              let text = String(data: data, encoding: .utf8) else { return }
        socket.send(.string(text)) { _ in }
    }

    // MARK: - Fare / klavye

    func move(dx: Double, dy: Double) { send(["type": "input", "kind": "move", "dx": dx, "dy": dy]) }
    func click(_ button: String = "left") { send(["type": "input", "kind": "click", "button": button]) }
    func scroll(_ steps: Int) { send(["type": "input", "kind": "scroll", "dy": steps]) }
    func type(_ text: String) { send(["type": "input", "kind": "text", "text": text]) }
    func key(_ name: String) { send(["type": "input", "kind": "key", "key": name]) }

    // MARK: - Pano

    func sendClipboard(_ text: String) { send(["type": "clipboard", "text": text]) }
}
