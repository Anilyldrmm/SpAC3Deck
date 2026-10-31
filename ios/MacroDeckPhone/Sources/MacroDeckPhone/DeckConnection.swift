import Foundation
import Observation
import UIKit

enum DeckError: LocalizedError {
    case badPIN
    case tooManyAttempts
    case unreachable
    case server(Int)

    var errorDescription: String? {
        switch self {
        case .badPIN: return "PIN yanlış."
        case .tooManyAttempts: return "Çok fazla deneme. Biraz bekleyip tekrar dene."
        case .unreachable: return "PC'ye ulaşılamıyor. MacroDeck'in açık olduğunu ve adresi kontrol et."
        case .server(let code): return "Sunucu hata verdi (\(code))."
        }
    }

    /// Tekrar denemenin anlamsız olduğu hatalar (PIN yanlış gibi).
    var isFatal: Bool {
        switch self {
        case .badPIN, .tooManyAttempts: return true
        default: return false
        }
    }
}

/// PC'deki MacroDeck sunucusuyla konuşur (web arayüzüyle aynı protokol):
/// yapılandırma (REST), canlı durum ve komutlar (WebSocket).
@MainActor @Observable
final class DeckConnection {
    enum State: Equatable {
        case disconnected
        case connecting
        case connected
        case reconnecting
        case failed(String)
    }

    var state: State = .disconnected
    var config: DeckConfig?
    /// Voicemeeter / Discord canlı durumu (strip0_mute, discord_camera, ...).
    var values: [String: JSONValue] = [:]
    var pcClipboard = ""
    var serverVersion: String?
    /// Son bağlantı kopmasının saati ve nedeni (Ayarlar'da görünür; kopma teşhisi için).
    var lastDisconnect: String?
    private(set) var host = ""

    private var pin = ""
    private var fatal = false // yanlış PIN gibi: tekrar denemek anlamsız
    private var socket: URLSessionWebSocketTask?
    private var loop: Task<Void, Never>?
    private let rest: URLSession = {
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 8
        return URLSession(configuration: configuration)
    }()
    private let wsSession = URLSession(configuration: .default)

    // MARK: - Bağlantı yaşam döngüsü

    /// Kayıtlı PC'ye bağlan (uygulama açılışı / ön plana dönüş). PC'ye ulaşılamazsa vazgeçmez, PIN'i sormaz.
    func autoConnect() {
        switch state {
        case .connected, .connecting, .reconnecting:
            return
        case .disconnected, .failed:
            guard !fatal else { return }
        }
        let savedHost = UserDefaults.standard.string(forKey: "deckHost") ?? ""
        guard !savedHost.isEmpty, let savedPIN = PinStore.load() else { return }
        connect(host: savedHost, pin: savedPIN, persistent: true)
    }

    /// Arka plandan dönünce: bağlantı ölmüşse hemen yenile, canlıysa dokunma.
    func resume() {
        if state == .connected, let socket {
            socket.sendPing { error in
                if error != nil { socket.cancel(with: .goingAway, reason: nil) } // receive döngüsü yeniden bağlanır
            }
        } else {
            autoConnect()
        }
    }

    func connect(host: String, pin: String, persistent: Bool = false) {
        stop()
        self.host = host
        self.pin = pin
        fatal = false
        state = .connecting
        loop = Task { await run(persistent: persistent) }
    }

    /// Bağlanmayı bırak ama kayıtlı PIN'i silme.
    func cancel() {
        stop()
        state = .disconnected
    }

    func disconnect() {
        stop()
        config = nil
        values = [:]
        serverVersion = nil
        state = .disconnected
        PinStore.clear()
    }

    private func stop() {
        loop?.cancel()
        loop = nil
        socket?.cancel(with: .goingAway, reason: nil)
        socket = nil
    }

    private func run(persistent: Bool) async {
        var delay = 1.0
        var everConnected = persistent
        while !Task.isCancelled {
            do {
                try await loadConfig()
                guard let url = wsURL("/ws") else { throw DeckError.unreachable }
                let socket = wsSession.webSocketTask(with: url)
                self.socket = socket
                socket.resume()
                try await ping(socket)
                remember()
                state = .connected
                everConnected = true
                delay = 1
                Task { await loadVersion() }
                // iOS boşta kalan WebSocket'i kapatabiliyor; sunucu sessiz olduğu için ping at
                let keepAlive = Task {
                    while !Task.isCancelled {
                        try? await Task.sleep(nanoseconds: 20_000_000_000)
                        socket.sendPing { _ in }
                    }
                }
                defer { keepAlive.cancel() }
                while true { handle(try await socket.receive()) }
            } catch {
                if Task.isCancelled { return }
                let nsError = error as NSError
                NSLog("MacroDeck baglanti koptu: %@ %ld %@", nsError.domain, nsError.code, nsError.localizedDescription)
                lastDisconnect = "\(Date().formatted(date: .omitted, time: .standard)) · \(nsError.domain) \(nsError.code)"
                if let deckError = error as? DeckError, deckError.isFatal {
                    fail(deckError.errorDescription ?? "Bağlanılamadı.", fatal: true)
                    return
                }
                if !everConnected {
                    fail((error as? DeckError)?.errorDescription ?? DeckError.unreachable.errorDescription ?? "Bağlanılamadı.")
                    return
                }
                state = .reconnecting
                try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                delay = min(delay * 2, 8)
            }
        }
    }

    private func fail(_ message: String, fatal: Bool = false) {
        self.fatal = fatal
        config = nil
        state = .failed(message)
    }

    private func remember() {
        UserDefaults.standard.set(host, forKey: "deckHost")
        PinStore.save(pin)
    }

    private func ping(_ socket: URLSessionWebSocketTask) async throws {
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            socket.sendPing { error in
                if let error { continuation.resume(throwing: error) } else { continuation.resume() }
            }
        }
    }

    // MARK: - Adresler

    private func components(scheme: String, path: String, items: [URLQueryItem]) -> URL? {
        var parts = URLComponents()
        parts.scheme = scheme
        let pieces = host.trimmingCharacters(in: .whitespaces).split(separator: ":", maxSplits: 1)
        guard let name = pieces.first else { return nil }
        parts.host = String(name)
        parts.port = pieces.count > 1 ? Int(pieces[1]) : 8765
        parts.path = path
        parts.queryItems = [URLQueryItem(name: "token", value: pin)] + items
        return parts.url
    }

    func restURL(_ path: String, items: [URLQueryItem] = []) -> URL? {
        components(scheme: "http", path: path, items: items)
    }

    func wsURL(_ path: String, items: [URLQueryItem] = []) -> URL? {
        components(scheme: "ws", path: path, items: items)
    }

    // MARK: - REST

    func loadConfig() async throws {
        guard let url = restURL("/api/config") else { throw DeckError.unreachable }
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await rest.data(from: url)
        } catch {
            if Task.isCancelled { throw CancellationError() }
            throw DeckError.unreachable
        }
        switch (response as? HTTPURLResponse)?.statusCode ?? 0 {
        case 200: break
        case 403: throw DeckError.badPIN
        case 429: throw DeckError.tooManyAttempts
        case let code: throw DeckError.server(code)
        }
        config = try JSONDecoder().decode(DeckConfig.self, from: data)
    }

    private func loadVersion() async {
        guard let url = restURL("/api/version"),
              let (data, _) = try? await rest.data(from: url),
              let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return }
        serverVersion = object["version"] as? String
    }

    // MARK: - Gelen mesajlar

    private func handle(_ message: URLSessionWebSocketTask.Message) {
        guard case .string(let text) = message,
              let data = text.data(using: .utf8),
              let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = object["type"] as? String else { return }
        switch type {
        case "state":
            if let diff = object["data"] as? [String: Any] {
                for (key, value) in diff { values[key] = Self.json(value) }
            }
        case "clipboard":
            guard let clip = object["text"] as? String else { return }
            pcClipboard = clip
            if UserDefaults.standard.bool(forKey: "autoCopy") { UIPasteboard.general.string = clip }
        case "reload":
            Task { try? await loadConfig() }
        default:
            break
        }
    }

    private static func json(_ value: Any) -> JSONValue {
        if let number = value as? NSNumber {
            if CFGetTypeID(number) == CFBooleanGetTypeID() { return .bool(number.boolValue) }
            return .number(number.doubleValue)
        }
        if let string = value as? String { return .string(string) }
        return .null
    }

    // MARK: - Giden komutlar

    private func send(_ payload: [String: Any]) {
        guard let socket,
              let data = try? JSONSerialization.data(withJSONObject: payload),
              let text = String(data: data, encoding: .utf8) else { return }
        socket.send(.string(text)) { _ in }
    }

    /// Deck butonu: press / release / set (sürgü değeri).
    func sendEvent(page: String, button: String, event: String, value: Double? = nil) {
        var payload: [String: Any] = ["page": page, "button_id": button, "event": event]
        if let value { payload["value"] = value }
        send(payload)
    }

    func move(dx: Double, dy: Double) { send(["type": "input", "kind": "move", "dx": dx, "dy": dy]) }
    func click(_ button: String = "left") { send(["type": "input", "kind": "click", "button": button]) }
    func mouseButton(_ button: String, down: Bool) { send(["type": "input", "kind": "button", "button": button, "down": down]) }
    func scroll(_ steps: Int) { send(["type": "input", "kind": "scroll", "dy": steps]) }
    func type(_ text: String) { send(["type": "input", "kind": "text", "text": text]) }
    func key(_ name: String) { send(["type": "input", "kind": "key", "key": name]) }
    func sendClipboard(_ text: String) { send(["type": "clipboard", "text": text]) }
}
