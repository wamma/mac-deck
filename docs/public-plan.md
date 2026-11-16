# Public distribution plan

1. Export only tracked source into a new directory and initialize a new Git root; do not copy history, runtime data, screenshots or private evidence.
2. Retain all feature implementations and replace personal verification records with portable reproduction instructions.
3. Bind loopback by default. LAN requires TLS with externally managed certificates, or an explicit insecure HTTP compatibility flag. Determine Origin/cookie policy from actual TLS configuration, never forwarded headers.
4. Bound HTTP workers, socket/handshake deadlines and expensive reads. Keep existing command serialization and one-shot protections.
5. Pair only during a Mac-side explicitly opened time window. Support named browser sessions, local list/revoke commands and client logout. No cloud identity service or persistent bearer secrets.
6. Use isolated fixtures/ports for feature, TLS, CSRF, pairing expiry, revocation and concurrency checks; document remaining limitations honestly. No live user app, clipboard, provider or private server operations.
7. Run a tracked-file privacy scan and give the reviewer the local root, commit, feature map and results. No remote is configured or pushed by the implementer.
