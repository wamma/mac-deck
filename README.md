# Mac Deck

Use a phone or tablet browser as a local Mac control panel: app switching, custom buttons, shortcuts, text and URL macros, system controls, clipboard history, AI activity and read-only Arc tabs.

**A paired device can control your Mac and read the enabled metadata/clipboard history.** This is not an Internet-facing service or a multi-user authorization system. Keep it on a trusted private network. Feature availability is documented in [the feature map](docs/feature-parity.md), including previously unverified provider and physical-device behavior.

## Requirements

- macOS, Python 3.11 or newer, Xcode Command Line Tools (`xcode-select --install` if not installed).
- The Swift helper builds locally on first start. Missing build tools or OS permissions produce a diagnostic; permissions are never reset automatically.
- Optional: Arc, Orca, Codex or Claude. Missing optional tools do not prevent the app controls/server from starting. Usage or activity then reports unavailable/no signal, never invented values.
- Node.js and Playwright are only required for browser tests, not normal use.

## First start: Mac only

```sh
python3 server.py
# Equivalent launcher (arguments are forwarded):
./start.command
```

The default bind is **127.0.0.1**. This is intentionally **Mac-only**; a phone cannot connect to that address. Open the loopback URL printed in this terminal on the Mac. Keep the terminal open. Type `p` followed by Enter **in the running server console** to display a fresh code and allow pairing for 120 seconds. Enter a device name and the code in the browser.

No special restart flag is needed: starting again replaces only a verified same-user server with the same canonical script and data directory on a conflicting endpoint. An unrelated/private checkout is never killed. If another checkout owns the port, choose `--port 8766` and use that printed port. Restart loses memory-only clipboard history, disables collection and expires old cookies. Use console pairing/session controls instead of restarting just to add or remove a device.

## Phone/tablet over LAN: TLS

Obtain a certificate/key outside this repository. Its SAN must cover the exact hostname or IP you will open, and the device must trust its issuing CA. See [certificate setup and verification](docs/tls.md) for a local CA example, external certificates and mobile trust steps.

```sh
python3 server.py --host 0.0.0.0 \
  --tls-cert "$DECK_CERT_DIR/server.crt" --tls-key "$DECK_CERT_DIR/server.key" \
  --allowed-host "$DECK_NAME"
# Or use ./start.command with those same arguments.
```

Open `https://<your-certificate-hostname>:8765` on the phone, on the same private network, with no certificate error. In the Mac console type `p`, then pair within the window. Guest/client-isolated Wi-Fi can block device-to-device connections. Do not bypass certificate warnings; fix the name, expiry or trust chain first.

### Explicit HTTP compatibility mode

```sh
python3 server.py --host 0.0.0.0 --allow-insecure-http
```

This mode is **unencrypted**: network observers can obtain pairing codes, session cookies, clipboard content and command traffic. Same Wi-Fi alone is not a security guarantee. It retains the original LAN HTTP functionality for environments where the user explicitly accepts this risk. It is not presented as equivalent to TLS. Never forward the port to the Internet. `X-Forwarded-*` headers cannot enable TLS or change the accepted Origin.

## Local connection management

These commands run in the server's own terminal, without restart or clipboard loss. They are not HTTP endpoints.

| Command | Effect |
|---|---|
| `p` | Rotate the pairing code and open a 120-second window; existing sessions remain connected |
| `close` | Close pairing immediately; existing sessions remain connected |
| `list` | Show connected device IDs, user-entered names and remaining session lifetime |
| `revoke DEVICE_ID` | Revoke one session; later requests are denied |
| Ctrl+C | Stop the server normally |

Pairing is closed by default. A scripted local start can explicitly use `--pairing-seconds 120`. Sessions expire after twelve hours or restart; browser logout removes that session. A request authenticated earlier is checked again at mutation/command admission. Revocation **does not cancel already admitted OS work**, even if that work finishes after revocation. Closing a browser tab alone is not revocation. All paired sessions have the same full control scope.

## Controls and data

Four modes: apps, system, AI work and text/sites. Short tap executes; in edit mode short tap edits and long press reorders. Verified app activation updates the target without a success toast; unverified activation/errors remain visible. System support is read from the Mac; unsupported brightness hardware is explicitly marked. Shortcuts/text go to the verified active target, not a browser-selected invisible window. Trash requires a server-side second confirmation within three seconds.

Clipboard collection is OFF by default, memory-only, and captures text only after enabled. Never enable it on an untrusted shared session. Settings and order live under `.deck-data`; keep that directory private. Do not commit it or include it in a bug report. Native permissions, app selection and displayed metadata may reveal local activity to paired devices.

AI work shows up to twelve actual Orca activities in recent activity order, with no automatic manual-slot registration. Automatic details are read-only. Optional manual slots retain window verification and one-shot replies. Exact logical session/window mapping, actual Claude usage and physical-device behavior retain their documented limitations. Codex discovery may expose other project titles to paired clients; do not pair untrusted devices. No cloud summarizer is used.

Arc's panel opens only after verified activation of the actual Arc bundle ID. It reads running Arc windows/tabs, shows titles/domains, and supports local search/manual refresh. No active-tab guessing, selection, close or new-tab action. Weather requires an explicit location and uses Open-Meteo. Provider credentials are not copied into this repository.

Thirty-second web power saving shows a black overlay and stops that client's polling. The first input only wakes the UI. This is not OS screen-off, automatic unlocking or a battery-saving percentage guarantee.

## Development and release review

```sh
python3 -m unittest discover -s tests
npm ci
npx playwright install chromium webkit
npm run test:browser
```

Tests use temporary fixtures and ports; see [verification](docs/verification.md) before any optional live Mac test. Do not run live test scripts against a working user's server. `PLAYWRIGHT_MODULE`, `CHROME_PATH`, `DECK_TEST_URL` and explicit output directories replace machine-specific paths. Private artifacts belong in ignored `artifacts/`, never in tracked docs.

This distribution starts from a new Git root with no imported private history. Security controls reduce specific risks; they do not constitute a security audit or guarantee. See [security boundaries](docs/security.md). **A public license has not been selected.** No additional reuse license is granted. The owner may add a license later.
