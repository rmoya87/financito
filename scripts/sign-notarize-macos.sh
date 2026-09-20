#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="${1:-$ROOT/dist/macos/Financito.app}"
IDENTITY="${APPLE_SIGNING_IDENTITY:-}"
[[ -d "$APP" ]] || { echo "No existe $APP" >&2; exit 1; }
[[ -n "$IDENTITY" ]] || { echo "Define APPLE_SIGNING_IDENTITY (Developer ID Application: ...)." >&2; exit 1; }
command -v xcrun >/dev/null || { echo "Falta Xcode/notarytool." >&2; exit 1; }

xattr -cr "$APP"
codesign --force --deep --options runtime --timestamp --sign "$IDENTITY" "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"

ZIP="${APP%.app}.zip"
rm -f "$ZIP"
ditto -c -k --keepParent "$APP" "$ZIP"

if [[ -n "${APPLE_NOTARY_PROFILE:-}" ]]; then
  xcrun notarytool submit "$ZIP" --keychain-profile "$APPLE_NOTARY_PROFILE" --wait
elif [[ -n "${APPLE_API_KEY_PATH:-}" && -n "${APPLE_API_KEY_ID:-}" && -n "${APPLE_API_ISSUER_ID:-}" ]]; then
  xcrun notarytool submit "$ZIP" --key "$APPLE_API_KEY_PATH" --key-id "$APPLE_API_KEY_ID" --issuer "$APPLE_API_ISSUER_ID" --wait
else
  echo "Configura APPLE_NOTARY_PROFILE o APPLE_API_KEY_PATH/APPLE_API_KEY_ID/APPLE_API_ISSUER_ID." >&2
  exit 1
fi

xcrun stapler staple "$APP"
xcrun stapler validate "$APP"
spctl --assess --type execute --verbose=4 "$APP"
rm -f "$ZIP"
ditto -c -k --keepParent "$APP" "$ZIP"
echo "$ZIP"
