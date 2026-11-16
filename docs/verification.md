# Reproducible verification

Run from this checkout on macOS with Python 3.11+, Swift Command Line Tools, Node.js and the test dependencies described in README. No running user server is required.

```sh
python3 -m unittest discover -s tests
node --check web/app.js
zsh -n start.command
npm ci
npx playwright install chromium webkit
npm run test:browser
```

Python tests use temporary directories, synthetic providers and isolated ports. Startup integration launches fixture servers, tests replacement/protected other checkouts and refuses forced termination. The native target tests compile safe test entry points; clipboard-guard tests use a uniquely named test pasteboard, not the user's general pasteboard. No real Mac app activation, permission probe, approval key or provider model request is part of the public release run.

`tests.test_public_security` exercises real verified loopback TLS, rejection of an untrusted certificate and incorrect scheme/Origin, cookie flags, local pairing windows/revocation, connection limits, expensive-query single-flight and cross-checkout replacement refusal. Deterministic barriers cover revoke/expiry after authentication but before command admission and confirm an already admitted OS fixture can finish without holding the authentication lock.

The browser smoke test intercepts every request and uses synthetic names only. It covers pairing guidance/device name, four modes, no command execution from mode changes, HTTP/TLS guidance and mobile overflow. It is desktop Chromium with touch/mobile viewport, not a physical Android/iPad or mobile certificate-trust test. Screenshot paths are caller supplied; generated evidence belongs in ignored `artifacts/`.

Historical browser verifiers are retained for targeted regressions. Use `PLAYWRIGHT_MODULE` or the installed `playwright` package, optional `CHROME_PATH`, and explicit output folders. `DECK_TEST_URL` selects a dedicated fixture server where needed. **Do not run live verifier scripts against an active user's server.** Scripts such as `verify_native.py`, `verify_web_text.py`, `verify_claude_terminal.py`, installation helpers and clipboard helpers are explicit live/manual tools with their own target requirements; they are not required to start the app. Never insert a production pairing code into source or evidence. `DECK_CODE` is an ephemeral environment input for explicitly selected live tests only.

Public preparation does not repeat or claim earlier private live evidence. Actual Claude usage delivery, terminal/window mapping and responses, supported-screen brightness, mobile IME, physical-device LAN/TLS trust and panel power behavior remain separate manual checks. A completed response is not a completed user project; missing signals are not completion.

No private history, operating config, user screenshot, pairing code or conversation evidence is included. Licensing remains an owner decision before publication.
