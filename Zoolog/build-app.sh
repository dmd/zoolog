#!/bin/bash
set -euo pipefail

APP_NAME="Zoolog"
BUILD_DIR=".build"
APP_BUNDLE="$BUILD_DIR/$APP_NAME.app"

swift build

rm -rf "$APP_BUNDLE"
mkdir -p "$APP_BUNDLE/Contents/MacOS"
mkdir -p "$APP_BUNDLE/Contents/Resources"

cp "$BUILD_DIR/debug/$APP_NAME" "$APP_BUNDLE/Contents/MacOS/$APP_NAME"

cat > "$APP_BUNDLE/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>Zoolog</string>
    <key>CFBundleDisplayName</key>
    <string>Zoolog</string>
    <key>CFBundleIdentifier</key>
    <string>com.dashare.zoolog</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleExecutable</key>
    <string>Zoolog</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>14.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSPhotoLibraryUsageDescription</key>
    <string>Zoolog displays photos from your library alongside journal entries.</string>
</dict>
</plist>
PLIST

codesign --force --sign - "$APP_BUNDLE"

echo "Built $APP_BUNDLE"
echo "Run with: open $APP_BUNDLE"
