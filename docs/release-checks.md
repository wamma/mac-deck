# Local release-candidate checks

This is a new Git root, with no imported commit history or configured remote. The repository owner reviews this candidate before creating/uploading a public repository. No license has been selected.

## Executed checks

- Python suite: **124 tests passed** in 37.119 seconds. Includes eight public-security tests. A focused public-security + HTTP run passed twenty tests in 9.716 seconds.
- Revoke/expiry: deterministic thread barriers for all three command endpoints; zero fake native executions after revocation before admission. Settings admission rejects a revoked session. An already admitted blocked OS fixture finishes after revocation and does not hold the authentication lock.
- TLS: actual loopback TLS handshake with explicit test trust, untrusted-certificate rejection, wrong scheme/Origin rejection and Secure-cookie verification. The documented local CA/leaf recipe was separately executed in a temporary directory; certificate chain/hostname verification and server TLS-context loading passed. No real certificates were issued or trust settings installed.
- All JavaScript files passed `node --check`; `start.command` passed `zsh -n`; the complete Swift helper compiled to a temporary binary without execution.
- Chromium mobile/touch 393px: fully intercepted synthetic HTTP/HTTPS pairing, device-name submission, four modes, no horizontal overflow and zero native command requests. Two final PNGs were opened for visual review outside the repository. This does not verify physical-device TLS or LAN.
- Ignore protection checked for local app metadata, local Claude settings, runtime data, environment files, certificate/key files, node modules and generated evidence.
- Source inventory records every retained implementation/test/script file; no required source file was omitted. Machine-specific test dependency/output paths were made configurable.

The full suite emitted Python ResourceWarnings for unclosed SQLite connections in existing discovery fixtures; it completed with no failures. These warnings are not presented as a clean resource-leak audit. Installer success messages during the suite came from temporary test fixtures, not actual project/home settings changes.

## Privacy review

A tracked-file scan checked personal home/volume paths, private network addresses, terminal handles, key material headers, email patterns and known private identifying strings. The only email-pattern hit was a deliberate `example.com` URL credential-rejection fixture; no personal email was included. Runtime directories, original evidence/photos and private Git history were excluded. Generic synthetic session labels in tests remain intentionally. This pattern scan is a release check, not proof that arbitrary future contributions are safe.

No operational server, user clipboard/app, provider session or external project settings were accessed for release testing. Private source identity/status was checked read-only. No remote creation, upload or push was performed.

## Still unverified / owner decisions

- No reuse license is selected; source publication does not add one. The owner may choose a license later.
- Physical iPad/Galaxy/Samsung Internet certificate trust, LAN reachability and IME behavior.
- Actual Claude usage delivery; actual AI terminal/window capture and approval response under the required permissions.
- Real supported-display brightness and OS capture selection; actual battery savings are not claimed.
- Historical live verifier scripts are preserved but not executed against a user's server. Their evidence must never be committed.
- Same-network HTTP compatibility is explicitly unencrypted; paired clients retain full control. Revoking a session does not undo work already admitted.

See [feature coverage](feature-parity.md), [source inventory](source-inventory.json), [security boundaries](security.md) and [reproduction instructions](verification.md).
