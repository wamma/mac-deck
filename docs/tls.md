# TLS and certificate trust

The server uses Python's TLS server context, a TLS 1.2 minimum and a supplied certificate chain/private key. Certificates stay outside the checkout. The scheme used for Origin and Secure cookies comes from that context, never from proxy headers. Direct TLS is supported; a reverse-proxy deployment is not configured by trusting forwarded headers.

## Externally managed certificate

Use your existing certificate management process. Supply the leaf plus intermediate chain as `server.crt`, and its matching key as `server.key`. The SAN must match the exact address the device visits. The server does not issue, renew or upload certificates. Protect private keys and renew before expiry. A publicly trusted certificate normally requires a domain you control; do not request a public certificate for a made-up private hostname.

## Local CA example (user-run, not automatically installed)

Choose `DECK_NAME` as a hostname that actually resolves to your Mac from the device, and `DECK_LAN_IP` as your current LAN IPv4 address. A `.local` hostname may use mDNS on your network. Keep this directory outside Git. The values below are variables to fill in, not hidden defaults.

```sh
umask 077
export DECK_CERT_DIR="$HOME/mac-deck-certs"
mkdir -p "$DECK_CERT_DIR"
# Set DECK_NAME and DECK_LAN_IP to your own reachable hostname/IP before continuing.
: "${DECK_NAME:?Set your reachable Mac hostname}"
: "${DECK_LAN_IP:?Set your current LAN IP}"
cat > "$DECK_CERT_DIR/ca.cnf" <<'EOF_CA'
[req]
distinguished_name=dn
x509_extensions=ca
prompt=no
[dn]
CN=Mac Deck Local CA
[ca]
basicConstraints=critical,CA:TRUE
keyUsage=critical,keyCertSign,cRLSign
subjectKeyIdentifier=hash
EOF_CA
openssl req -x509 -newkey rsa:3072 -nodes -days 365 \
  -config "$DECK_CERT_DIR/ca.cnf" \
  -keyout "$DECK_CERT_DIR/ca.key" -out "$DECK_CERT_DIR/ca.crt"
openssl req -new -newkey rsa:2048 -nodes -subj "/CN=$DECK_NAME" \
  -keyout "$DECK_CERT_DIR/server.key" -out "$DECK_CERT_DIR/server.csr"
cat > "$DECK_CERT_DIR/server.ext" <<EOF_EXT
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:$DECK_NAME,IP:$DECK_LAN_IP
EOF_EXT
openssl x509 -req -in "$DECK_CERT_DIR/server.csr" \
  -CA "$DECK_CERT_DIR/ca.crt" -CAkey "$DECK_CERT_DIR/ca.key" -CAcreateserial \
  -days 365 -sha256 -extfile "$DECK_CERT_DIR/server.ext" -out "$DECK_CERT_DIR/server.crt"
openssl verify -CAfile "$DECK_CERT_DIR/ca.crt" "$DECK_CERT_DIR/server.crt"
python3 server.py --host 0.0.0.0 \
  --tls-cert "$DECK_CERT_DIR/server.crt" --tls-key "$DECK_CERT_DIR/server.key" \
  --allowed-host "$DECK_NAME"
```

A local CA grants trust authority, not merely trust in one page. Keep `ca.key` private/offline where practical. Transfer **only the public CA certificate**, never a key, to devices you own through a trusted channel. Check the fingerprint before installing:

```sh
openssl x509 -in "$DECK_CERT_DIR/ca.crt" -noout -fingerprint -sha256
curl --cacert "$DECK_CERT_DIR/ca.crt" "https://$DECK_NAME:8765/"
```

Do not use `curl -k`, disabled browser certificate checks, or click through browser warnings as a successful verification. A direct self-signed leaf may be handled differently across devices; the example uses a CA-signed leaf with SAN. If the IP changes, use the matching hostname or reissue the leaf with the new SAN.

## Mobile trust (manual, device-specific)

- iOS/iPadOS: installing a profile does not automatically grant SSL trust. After verifying the CA, follow Apple's certificate trust settings procedure; do not trust unknown certificates. [Apple's instructions](https://support.apple.com/en-us/102390).
- Android: install the user CA through the device's certificate/credential settings after verifying it. Menus and user-CA behavior vary by vendor, OS and browser; some apps do not trust user CAs. [Google's instructions](https://support.google.com/pixelphone/answer/2844832?hl=en). Galaxy/Samsung Internet trust has not been verified for this public candidate.

The automated tests establish real loopback TLS handshakes with an explicit fixture trust root, rejection with default untrusted roots, and HTTPS Origin/Secure-cookie behavior. They do **not** establish physical-device certificate installation, mDNS reachability, external CA issuance or router configuration. No such system settings were changed during preparation. [Python SSL reference](https://docs.python.org/3/library/ssl.html).
