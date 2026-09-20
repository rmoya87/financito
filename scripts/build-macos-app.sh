#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/dist/macos"
APP="$DIST/Financito.app"
CONTENTS="$APP/Contents"
RES="$CONTENTS/Resources/financito"
BUNDLE_ID="${FINANCITO_BUNDLE_ID:-com.rmoya87.financito}"
VERSION="${FINANCITO_VERSION:-0.2.0}"

[[ "$(uname -s)" == "Darwin" ]] || { echo "Este empaquetado debe ejecutarse en macOS." >&2; exit 1; }
command -v xcrun >/dev/null || { echo "Faltan Xcode Command Line Tools." >&2; exit 1; }
command -v npm >/dev/null || { echo "Falta Node/npm para construir la interfaz." >&2; exit 1; }

rm -rf "$APP"
mkdir -p "$CONTENTS/MacOS" "$RES/apps/web" "$RES/scripts"

(
  cd "$ROOT/apps/web"
  npm install --no-package-lock --no-audit --no-fund
  npm run build
)
cp -R "$ROOT/apps/api" "$RES/apps/api"
cp -R "$ROOT/apps/web/out" "$RES/apps/web/out"
cp "$ROOT/scripts/macos-app-runtime.sh" "$RES/scripts/macos-app-runtime.sh"

cat > "$CONTENTS/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleDevelopmentRegion</key><string>es</string>
<key>CFBundleExecutable</key><string>Financito</string>
<key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
<key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
<key>CFBundleName</key><string>Financito</string>
<key>CFBundleDisplayName</key><string>Financito</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleShortVersionString</key><string>$VERSION</string>
<key>CFBundleVersion</key><string>$VERSION</string>
<key>LSMinimumSystemVersion</key><string>13.0</string>
<key>LSUIElement</key><true/>
</dict></plist>
PLIST

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cat > "$TMP/Launcher.swift" <<'SWIFT'
import Foundation
import Darwin

guard let resources = Bundle.main.resourceURL else { exit(2) }
let script = resources.appendingPathComponent("financito/scripts/macos-app-runtime.sh")
let process = Process()
process.executableURL = URL(fileURLWithPath: "/bin/bash")
process.arguments = [script.path]
do {
    try process.run()
    process.waitUntilExit()
    exit(process.terminationStatus)
} catch {
    fputs("Unable to start Financito: \(error)\n", stderr)
    exit(3)
}
SWIFT
xcrun swiftc -O "$TMP/Launcher.swift" -o "$CONTENTS/MacOS/Financito"
chmod 755 "$CONTENTS/MacOS/Financito"
plutil -lint "$CONTENTS/Info.plist"
echo "$APP"
