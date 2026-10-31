// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "MacroDeckPhone",
    platforms: [
        .iOS(.v17),
        .macOS(.v14),
    ],
    products: [
        // xtool: tam olarak bir library product, ana uygulama
        .library(
            name: "MacroDeckPhone",
            targets: ["MacroDeckPhone"]
        ),
    ],
    targets: [
        .target(
            name: "MacroDeckPhone",
            // shortcut: Swift 5 modu, Swift 6 strict concurrency uyarilari URLSession callback'lerinde gurultu yapiyor; ihtiyac olursa v6'ya gec
            swiftSettings: [.swiftLanguageMode(.v5)]
        ),
    ]
)
