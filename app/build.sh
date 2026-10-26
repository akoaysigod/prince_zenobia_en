#!/bin/sh
# Builds "Translation Studio.app" in app/build/. Run from anywhere: sh app/build.sh
set -e
cd "$(dirname "$0")"
swift build -c release
APP="build/Translation Studio.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp .build/release/TranslationStudio "$APP/Contents/MacOS/TranslationStudio"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleName</key><string>Translation Studio</string>
	<key>CFBundleDisplayName</key><string>Translation Studio</string>
	<key>CFBundleIdentifier</key><string>local.ogrebattle.translationstudio</string>
	<key>CFBundleExecutable</key><string>TranslationStudio</string>
	<key>CFBundlePackageType</key><string>APPL</string>
	<key>CFBundleShortVersionString</key><string>1.0</string>
	<key>CFBundleVersion</key><string>1</string>
	<key>LSMinimumSystemVersion</key><string>14.0</string>
	<key>NSHighResolutionCapable</key><true/>
	<key>NSPrincipalClass</key><string>NSApplication</string>
</dict>
</plist>
PLIST
codesign --force --sign - "$APP" >/dev/null 2>&1 || true
echo "Built $(pwd)/$APP"
