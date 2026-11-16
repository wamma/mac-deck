#!/usr/bin/env python3
"""Run: python3 server.py. Keep this terminal open while using the iPad."""
import argparse
import secrets
import signal
import socket
import subprocess
import threading
import sys
import ipaddress
from pathlib import Path
from deck.core import State, clipboard_worker, metrics_worker
from deck.macos import Mac
from deck.http import make_server
from deck.ai import Sessions
from deck.sources import Providers
from deck.access import AccessControl, console
from deck.transport import tls_context
from deck.startup import startup_lock, replace_existing


def local_addresses():
    addresses={'127.0.0.1'}
    try:
        output=subprocess.check_output(['/sbin/ifconfig'],text=True)
        import re
        addresses.update(re.findall(r'\binet (\d+\.\d+\.\d+\.\d+)',output))
    except (OSError,subprocess.CalledProcessError): pass
    return sorted(addresses)


def main():
    parser=argparse.ArgumentParser(description='아이패드용 맥 스트림덱')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--tls-cert',type=Path)
    parser.add_argument('--tls-key',type=Path)
    parser.add_argument('--allow-insecure-http',action='store_true')
    parser.add_argument('--pairing-seconds',type=int,default=0,choices=range(0,601),metavar='0..600')
    parser.add_argument('--allowed-host',action='append',default=[])
    parser.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parent/'.deck-data')
    args=parser.parse_args()
    if bool(args.tls_cert)!=bool(args.tls_key):parser.error('Provide both --tls-cert and --tls-key')
    try:loopback=ipaddress.ip_address(socket.gethostbyname(args.host)).is_loopback
    except (ValueError,OSError):parser.error('Cannot resolve bind host')
    if not loopback and not args.tls_cert and not args.allow_insecure_http:
        parser.error('LAN requires --tls-cert CERT --tls-key KEY, or explicit --allow-insecure-http. No server was stopped.')
    try:tls=tls_context(args.tls_cert,args.tls_key) if args.tls_cert else None
    except (OSError,ValueError):parser.error('Cannot load TLS certificate/key. No server was stopped.')
    access=AccessControl(pairing_seconds=args.pairing_seconds)
    args.data_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
    stop=threading.Event()
    for sig in (signal.SIGINT,signal.SIGTERM):
        signal.signal(sig,lambda *_:stop.set())
    server=None;serving=False
    try:
        with startup_lock(args.data_dir,args.port):
            replaced=replace_existing(Path(__file__),args.data_dir,args.host,args.port)
            if replaced:print('기존 Stream Deck 정상 종료 완료 · 메모리 수집 기록과 이전 접속 코드는 유지되지 않습니다.',flush=True)
            mac=Mac(args.data_dir);state=State(args.data_dir/'buttons.json',mac.apps)
            state.ai=Sessions(args.data_dir/'ai-slots.json');state.providers=Providers(args.data_dir,state.ai)
            code=access.code
            addresses=local_addresses()
            hostnames={socket.gethostname(),socket.gethostname().split('.')[0]+'.local'}
            server=make_server(args.host,args.port,state,mac,code,set(addresses)|hostnames|set(args.allowed_host),tls=tls,access=access)
            threading.Thread(target=state.providers.run,args=(stop,state),daemon=True).start()
            for target in [clipboard_worker,metrics_worker]:
                threading.Thread(target=target,args=(state,mac,stop),daemon=True).start()
            threading.Thread(target=server.serve_forever,daemon=True).start();serving=True
            print('\nMAC DECK · '+('LOCAL ONLY: phones cannot connect to this loopback address.' if loopback else 'LAN access enabled.'),flush=True)
            print('LAN TLS: python3 server.py --host 0.0.0.0 --tls-cert CERT_FILE --tls-key KEY_FILE --allowed-host MAC_HOSTNAME',flush=True)
            print('LAN HTTP compatibility (unencrypted): python3 server.py --host 0.0.0.0 --allow-insecure-http',flush=True)
            if not tls:print('WARNING: HTTP is unencrypted. Paired devices can control this Mac. Do not expose to the Internet.',flush=True)
            display_addresses=sorted(set(addresses if args.host=='0.0.0.0' else [args.host])|set(args.allowed_host))
            if tls:print('Use only an address covered by the certificate SAN and trusted by your device.',flush=True)
            for address in display_addresses:
                print(f"  {'https' if tls else 'http'}://{address}:{server.server_port}",flush=True)
            if access.pairing_open():print('Pairing open · 접속 코드: '+access.code,flush=True)
            print('Clipboard collection OFF. Local commands: p (pair 120s), close, list, revoke DEVICE_ID. Ctrl+C stops server.',flush=True)
            threading.Thread(target=console,args=(access,stop,sys.stdin,sys.stdout),daemon=True).start()

        stop.wait()
    except (OSError,RuntimeError,subprocess.TimeoutExpired) as exc:
        parser.exit(1,f'서버를 시작하지 못했습니다: {exc}\n확인되지 않은 프로세스는 종료하지 않습니다. 다른 저장소/서버가 이 포트를 사용하면 --port 8766으로 별도 실행하세요.\n')
    finally:
        stop.set()
        if server is not None:
            if serving:server.shutdown()
            server.server_close()

if __name__=='__main__': main()
