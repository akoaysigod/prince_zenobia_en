// swift-tools-version:5.10
import PackageDescription

let package = Package(
    name: "TranslationStudio",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(name: "TranslationStudio", path: "Sources/TranslationStudio"),
    ]
)
