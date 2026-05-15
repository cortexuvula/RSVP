# macOS code signing & notarization — setup

The release workflow (`.github/workflows/release.yml`) signs the `RSVP Reader.app` bundle with your Developer ID Application certificate, submits it to Apple's notary service, staples the ticket, packages the app into a drag-to-Applications DMG, and then signs and notarizes the DMG itself. This document is the one-time setup to make that work.

You need to add **six GitHub Actions secrets** to the repo: three for the certificate, three for notarization.

---

## 1. Prepare the `.p12` certificate bundle

Your existing `Certificates.p12` at `~/Documents/Development/Keys-Certificates/ahugo72 Dev Certs & Keys/Certificates.p12` already contains the Developer ID Application cert + private key. Confirm it can decrypt — open it in Keychain Access and you'll be prompted for the password it was exported with. **That password is the value of `MACOS_CERTIFICATE_P12_PASSWORD` below.**

If you've forgotten the password, re-export from Keychain Access:

1. Open **Keychain Access** → "login" keychain → "My Certificates"
2. Find "Developer ID Application: …" — it should have a disclosure arrow showing the private key beneath it
3. Right-click → **Export…** → save as `.p12` and set a fresh password
4. Use that fresh password for `MACOS_CERTIFICATE_P12_PASSWORD`

Then base64-encode the `.p12` (GitHub secrets are text-only):

```sh
base64 -i ~/Documents/Development/Keys-Certificates/ahugo72\ Dev\ Certs\ \&\ Keys/Certificates.p12 | pbcopy
```

That copies the encoded blob to your clipboard. Paste it as the value of `MACOS_CERTIFICATE_P12_BASE64` in step 4.

---

## 2. Find your signing identity string

You need the exact string `codesign` will look for. Run:

```sh
security find-identity -v -p codesigning
```

Look for a line like:

```
1) ABCDEF1234567890ABCDEF1234567890ABCDEFGH "Developer ID Application: Andre Hugo (XXXXXXXXXX)"
```

Copy the part in quotes — `Developer ID Application: Andre Hugo (XXXXXXXXXX)`. That goes into `MACOS_SIGNING_IDENTITY`. The 10-character code in parentheses is your **Team ID** — note it down, you need it for notarization too.

---

## 3. Create an app-specific password for notarization

Apple's notary service won't accept your regular Apple ID password — you need an app-specific password.

1. Sign in at <https://appleid.apple.com>
2. **Sign-In and Security** → **App-Specific Passwords** → **Generate an app-specific password**
3. Label it something like `RSVP Reader notarization CI`
4. Copy the generated password (format: `xxxx-xxxx-xxxx-xxxx`). You'll only see it once.

That value goes into `MACOS_NOTARY_PASSWORD`.

---

## 4. Add the six secrets to GitHub

Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**. Add each of:

| Secret name | Value |
| --- | --- |
| `MACOS_CERTIFICATE_P12_BASE64` | base64 blob from step 1 |
| `MACOS_CERTIFICATE_P12_PASSWORD` | the password used to export the `.p12` |
| `MACOS_KEYCHAIN_PASSWORD` | any random string — used to lock the temporary CI keychain. Generate with `openssl rand -base64 24` |
| `MACOS_SIGNING_IDENTITY` | e.g. `Developer ID Application: Andre Hugo (XXXXXXXXXX)` |
| `MACOS_NOTARY_APPLE_ID` | your Apple ID email (the one tied to the developer account) |
| `MACOS_NOTARY_TEAM_ID` | the 10-character Team ID from step 2 |
| `MACOS_NOTARY_PASSWORD` | the app-specific password from step 3 |

---

## 5. Trigger a release

```sh
git tag v0.1.0
git push --tags
```

The workflow fires on any tag matching `v*`. Watch the macOS job in the Actions tab — the steps to look for are **Import signing certificate into keychain**, **Codesign app bundle**, **Notarize and staple**, **Build DMG**, **Codesign DMG**, and **Notarize and staple DMG**.

Typical timings on the `macos-latest` runner:

- Signing: a few seconds
- Notarization: 1–5 minutes (occasionally longer when Apple's queue is busy)

If notarization fails, the `notarytool submit` output prints a submission ID. To get the detailed log, run from a Mac with `xcrun`:

```sh
xcrun notarytool log <submission-id> \
  --apple-id <your-apple-id> \
  --team-id <your-team-id> \
  --password <app-specific-password>
```

The log will tell you which binary in the bundle failed (most common cause: a nested `.dylib` that wasn't signed with the hardened runtime, but the workflow's `--deep --options runtime` handles that).

---

## 6. Verify the released artifact

Download `RSVP-Reader-macOS.dmg` from the GitHub release on any Mac and run:

```sh
# Verify the DMG itself is signed and notarized
spctl -a -vvv -t open --context context:primary-signature RSVP-Reader-macOS.dmg

# Mount, then verify the .app inside
hdiutil attach RSVP-Reader-macOS.dmg
spctl -a -vvv -t exec "/Volumes/RSVP Reader/RSVP Reader.app"
hdiutil detach "/Volumes/RSVP Reader"
```

Expected output for each:

```
…: accepted
source=Notarized Developer ID
```

That confirms Gatekeeper will let it open without the "unidentified developer" warning.

---

## Notes on the entitlements file

`packaging/macos/entitlements.plist` enables the hardened runtime exceptions that PyInstaller-bundled apps need:

- `allow-jit` and `allow-unsigned-executable-memory` — Python's interpreter can JIT and load code at runtime
- `disable-library-validation` — PyInstaller loads its own bundled dylibs (PyQt6, etc.) which aren't co-signed by Apple
- `allow-dyld-environment-variables` — PyInstaller's bootloader uses `DYLD_*` vars

It also declares two app capabilities:

- `network.client` — for fetching URLs (the document loader supports loading from a URL)
- `files.user-selected.read-only` — for the file open dialog

These are the minimum entitlements that let notarization pass while keeping the security posture as tight as PyInstaller allows. If you ever sandbox the app or move to a non-PyInstaller bundler (e.g. `briefcase`), revisit this file.

---

## What about the `developerID_installer.cer`?

That's for signing `.pkg` installers. You're shipping a `.app` inside a `.dmg`, both signed with the Developer ID Application cert, so it's not used by this workflow. If you ever switch to a `.pkg` installer (e.g. via `pkgbuild` / `productbuild`), you'd add a `productsign --sign "Developer ID Installer: …"` step and add a second signing identity secret.
