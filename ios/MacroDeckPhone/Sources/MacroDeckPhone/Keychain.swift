import Foundation
import Security

/// PIN'i UserDefaults yerine Anahtar Zinciri'nde saklar.
enum Keychain {
    private static let service = "com.spac3.macrodeckphone"

    private static func query(_ account: String) -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
    }

    static func get(_ account: String) -> String? {
        var request = query(account)
        request[kSecReturnData as String] = true
        request[kSecMatchLimit as String] = kSecMatchLimitOne
        var item: CFTypeRef?
        guard SecItemCopyMatching(request as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    static func set(_ value: String, for account: String) {
        SecItemDelete(query(account) as CFDictionary)
        var request = query(account)
        request[kSecValueData as String] = Data(value.utf8)
        SecItemAdd(request as CFDictionary, nil)
    }

    static func remove(_ account: String) {
        SecItemDelete(query(account) as CFDictionary)
    }
}

/// PIN'i Anahtar Zinciri'ne yazar. Ücretsiz Apple kimliğiyle imzalanan uygulamada Anahtar Zinciri
/// bazen yazamıyor (PIN her açılışta sorulur); yazılamazsa UserDefaults'a düşer.
/// shortcut: yedek düz metin, PIN yalnız ev ağındaki bir sunucuyu açar; ücretli geliştirici hesabıyla kaldırılır.
enum PinStore {
    private static let fallbackKey = "pinFallback"

    static func save(_ pin: String) {
        Keychain.set(pin, for: "pin")
        if Keychain.get("pin") == pin {
            UserDefaults.standard.removeObject(forKey: fallbackKey)
        } else {
            UserDefaults.standard.set(pin, forKey: fallbackKey)
        }
    }

    static func load() -> String? {
        Keychain.get("pin") ?? UserDefaults.standard.string(forKey: fallbackKey)
    }

    static func clear() {
        Keychain.remove("pin")
        UserDefaults.standard.removeObject(forKey: fallbackKey)
    }
}
