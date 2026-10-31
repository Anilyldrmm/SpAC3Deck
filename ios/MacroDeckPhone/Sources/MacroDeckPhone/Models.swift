import Foundation

/// Sunucudan gelen serbest biçimli değerler (buton parametreleri, durum değerleri).
enum JSONValue: Codable, Equatable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode(Double.self) {
            self = .number(value)
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else {
            self = .null // listeler (hotkey tuşları) uygulamada kullanılmıyor
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value): try container.encode(value)
        case .number(let value): try container.encode(value)
        case .bool(let value): try container.encode(value)
        case .null: try container.encodeNil()
        }
    }

    var number: Double? {
        switch self {
        case .number(let value): return value
        case .bool(let value): return value ? 1 : 0
        default: return nil
        }
    }

    var isOn: Bool {
        switch self {
        case .bool(let value): return value
        case .number(let value): return value != 0
        default: return false
        }
    }

    var text: String? {
        switch self {
        case .string(let value): return value
        case .number(let value): return String(Int(value))
        default: return nil
        }
    }
}

struct DeckConfig: Codable, Equatable {
    var pages: [Page]
    var gridColumns: Int
    var gridRows: Int
    var stackPages: Bool?

    enum CodingKeys: String, CodingKey {
        case pages
        case gridColumns = "grid_columns"
        case gridRows = "grid_rows"
        case stackPages = "stack_pages"
    }
}

struct Page: Codable, Equatable, Identifiable {
    var name: String
    var buttons: [DeckButton]
    var id: String { name }
}

struct DeckButton: Codable, Equatable, Identifiable {
    var id: String
    var label: String
    var icon: String
    var action: String
    var params: [String: JSONValue]
}

/// Butonun davranışı: web arayüzündeki data-kind ile aynı ayrım.
enum ButtonKind: Equatable {
    case plain
    case hold
    case toggle(stateKey: String, on: String, off: String)
    case gain(stateKey: String, defaultValue: Double)
}

extension DeckButton {
    private var strip: Int { Int(params["strip_index"]?.number ?? 0) }
    private var bus: Int { Int(params["bus_index"]?.number ?? 0) }
    private var defaultGain: Double { params["default_value"]?.number ?? 0 }

    var kind: ButtonKind {
        switch action {
        case "hotkey_hold":
            return .hold
        case "voicemeeter_mute":
            return .toggle(stateKey: "strip\(strip)_mute", on: "SESSİZ", off: "AÇIK")
        case "voicemeeter_bus_mute":
            return .toggle(stateKey: "bus\(bus)_mute", on: "SESSİZ", off: "AÇIK")
        case "voicemeeter_route":
            return .toggle(stateKey: "strip\(strip)_route_\(params["bus"]?.text ?? "")", on: "AÇIK", off: "KAPALI")
        case "discord_screenshare":
            return .toggle(stateKey: "discord_streaming", on: "AÇIK", off: "KAPALI")
        case "discord_stream_sound":
            return .toggle(stateKey: "discord_sound", on: "AÇIK", off: "KAPALI")
        case "discord_camera_toggle":
            return .toggle(stateKey: "discord_camera", on: "AÇIK", off: "KAPALI")
        case "voicemeeter_gain":
            return .gain(stateKey: "strip\(strip)_gain", defaultValue: defaultGain)
        case "voicemeeter_bus_gain":
            return .gain(stateKey: "bus\(bus)_gain", defaultValue: defaultGain)
        default:
            return .plain
        }
    }

    /// Steam kapağı ve yüklenen görseller butonun tamamını kaplar (web arayüzündeki has-image).
    var isImageTile: Bool {
        icon.hasPrefix("/api/icon/custom/") || icon.hasPrefix("/api/icon/steam/")
    }
}

struct RemoteFile: Decodable, Identifiable, Equatable {
    var name: String
    var size: Int
    var id: String { name }
}
