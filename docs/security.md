# Security boundaries

A paired client has full application control, not a read-only role. App activation, keyboard input, clipboard text, window captures, browser titles/URLs and project metadata can be sensitive. Pair only devices you trust. Do not expose the port to the Internet. Host/Origin checks are browser request defenses, not a substitute for authentication or TLS.

## Transport and admission

The default bind is loopback. Non-loopback binds require supplied TLS certificate/key or an explicit `--allow-insecure-http` choice. Direct TLS uses TLS 1.2 or newer; cookies are HttpOnly, SameSite=Strict and Secure under TLS. No forwarded header changes the scheme. Exact Host/Origin validation applies. HTTP compatibility remains unencrypted and cannot protect cookies or command contents from network observers.

Pairing is closed until a local stdin console command opens a short window. Codes rotate when reopening; existing sessions remain valid. There is no unauthenticated HTTP management endpoint. Up to 32 in-memory sessions expire after twelve hours. Console `list` and `revoke ID` do not restart the server or erase clipboard history. Device names are labels supplied by clients, not cryptographic device identities.

Authentication is rechecked at mutation admission. Commands `/api/run`, `/api/system`, `/api/ai/reply` additionally check session identity and expiry under the nonce lock immediately before registering the command. Clipboard copy rechecks after acquiring its sampling lock. Settings mutations share a pre-dispatch admission boundary. Revocation blocks requests that have not crossed their admission boundary; it cannot cancel already admitted work, roll back a settings write or retract data already returned. No authentication lock is held for a native OS call. A request may finish after the device was revoked.

## Resource limits

The HTTP server admits at most sixteen concurrent handlers, with a bounded listen backlog, socket timeouts and a twenty-second connection deadline. Excess connections are closed. A deadline closes transport; it does not interrupt an already running Python/OS action. Native helpers retain subprocess timeouts. Expensive HTTP metadata queries share a nonblocking single-flight gate and return 429 when busy; actions retain their independent one-shot execution gate. This is a small LAN service, not a denial-of-service hardened public server.

Automatic replacement verifies the same user, canonical script, data directory and conflicting endpoint using operating-system process metadata. A PID file alone is not trusted. Another checkout, including a private installation, is never stopped. Choose a different port if it occupies the requested endpoint. Failure to identify or stop a server results in an error, never force-kill.

## Data and optional integrations

Runtime configuration and provider bridges belong in ignored `.deck-data`; clipboard history and authentication are memory-only. Certificates/private keys stay outside Git. No request-body/access logging is enabled. Provider metadata is returned to authenticated clients; not all such metadata is harmless merely because it excludes conversation bodies. Weather sends the chosen coordinates to Open-Meteo. Optional provider authentication remains managed by the installed provider, not copied into the release.

No other project's settings are installed automatically. Claude integration tools are opt-in preparation tools; review their scope and existing-command delegation before any separate installation. Missing provider programs yield unavailable/no-signal, not a server-wide dependency failure or fabricated usage.

This document records controls and limits, not an independent security audit. Physical-device TLS trust, hostile-network penetration testing and OS permission/window behavior have not been established by the public fixture suite.
