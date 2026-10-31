import Foundation

/// Configurator'daki Lucide simgelerinin (SVG) SF Symbols karşılıkları.
/// iOS SVG çizemediği için uzak simge adı buradan çevrilir.
enum Icons {
    private static let lucideToSymbol: [String: String] = [
        "disc": "opticaldisc", "gamepad-2": "gamecontroller", "globe": "globe",
        "headphone-off": "headphones", "keyboard": "keyboard", "log-in": "arrow.right.circle",
        "log-out": "rectangle.portrait.and.arrow.right", "mic-off": "mic.slash", "play": "play.fill",
        "rocket": "paperplane.fill", "screen-share": "display", "screen-share-off": "xmark.rectangle",
        "shuffle": "shuffle", "skip-back": "backward.fill", "skip-forward": "forward.fill",
        "sliders-horizontal": "slider.horizontal.3", "speaker": "speaker.wave.2", "timer": "timer",
        "video-off": "video.slash", "volume-1": "speaker.wave.1", "volume-2": "speaker.wave.2",
        "volume-x": "speaker.slash", "workflow": "point.3.connected.trianglepath.dotted",
        "star": "star", "flag": "flag", "bookmark": "bookmark", "zap": "bolt", "heart": "heart",
        "circle": "circle", "square": "square", "triangle": "triangle", "hexagon": "hexagon",
        "sparkles": "sparkles", "target": "target", "flame": "flame", "snowflake": "snowflake",
        "sun": "sun.max", "moon": "moon", "bell": "bell", "thumbs-up": "hand.thumbsup",
        "music": "music.note", "camera": "camera", "settings": "gearshape",
    ]

    private static let fallback = "square.grid.2x2"

    /// "https://api.iconify.design/lucide/moon.svg?color=..." -> "moon" -> SF Symbol
    static func symbol(forURL urlString: String) -> String {
        guard let url = URL(string: urlString) else { return fallback }
        let name = url.deletingPathExtension().lastPathComponent
        return lucideToSymbol[name] ?? fallback
    }

    /// Simgesi olmayan butonlar için eyleme göre varsayılan.
    static func symbol(forAction action: String) -> String {
        switch action {
        case "hotkey", "hotkey_hold": return "keyboard"
        case "open_url": return "globe"
        case "launch_app": return "app.badge"
        case "steam_launch": return "gamecontroller"
        case "play_sound": return "speaker.wave.2"
        case "macro": return "point.3.connected.trianglepath.dotted"
        default: return fallback
        }
    }
}
