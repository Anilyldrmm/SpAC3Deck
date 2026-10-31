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
/// bazen yazamıyor (PIN her açılışta sorulur); yazılamazsa uygulamaya özel, korumalı ve yedeğe
/// alınmayan bir dosyaya düşer.
/// shortcut: yedek dosya şifreli değil (yalnız iOS dosya koruması), PIN yalnız ev ağındaki sunucuyu açar;
/// ücretli geliştirici hesabı ya da sunucunun verdiği eşleşme belirteciyle kaldırılır.
enum PinStore {
    private static var fallbackURL: URL? {
        try? FileManager.default
            .url(for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
            .appendingPathComponent("pin.dat")
    }

    static func save(_ pin: String) {
        Keychain.set(pin, for: "pin")
        guard var url = fallbackURL else { return }
        if Keychain.get("pin") == pin {
            try? FileManager.default.removeItem(at: url)
            return
        }
        try? Data(pin.utf8).write(to: url, options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])
        var values = URLResourceValues()
        values.isExcludedFromBackup = true
        try? url.setResourceValues(values)
    }

    static func load() -> String? {
        if let pin = Keychain.get("pin") { return pin }
        guard let url = fallbackURL, let data = try? Data(contentsOf: url) else { return nil }
        return String(data: data, encoding: .utf8)
    }

    static func clear() {
        Keychain.remove("pin")
        if let url = fallbackURL { try? FileManager.default.removeItem(at: url) }
    }
}
