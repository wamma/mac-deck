"""LAN-only JSON boundary with pairing, origin checks and bounded commands."""
import hmac
import json
import re
import secrets
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

from .access import AccessControl
from .transport import BoundedServer

from .actions import TrashConfirmation, execute_button, validate_system_command

WEB=Path(__file__).resolve().parent.parent/'web'

class HTTPError(Exception):
    def __init__(self,status,message): self.status=status; self.message=message


def make_server(host,port,state,mac,code,allowed_hosts=None,*,tls=None,access=None,max_connections=16):
    access=access or AccessControl(code,pairing_seconds=120)
    trash=TrashConfirmation();sessions=access.sessions;attempts={};auth_lock=access.lock;action_lock=threading.Lock();query_lock=threading.Lock()
    scheme='https' if tls else 'http';cookie_security='; Secure' if tls else ''
    def expensive(fn):
        if not query_lock.acquire(blocking=False):raise HTTPError(429,'Another Mac metadata query is running. Refresh manually after it finishes.')
        try:return fn()
        finally:query_lock.release()
    hosts=set(allowed_hosts or []) | {'localhost','127.0.0.1'}
    if host != '0.0.0.0': hosts.add(host)

    class Handler(BaseHTTPRequestHandler):
        server_version='LocalDeck'
        def setup(self):
            super().setup();self.connection.settimeout(10)
        def log_message(self,*args): pass
        def send_data(self,status,data,content_type='application/json; charset=utf-8',cookie=None):
            if not isinstance(data,bytes): data=json.dumps(data,ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            if cookie: self.send_header('Set-Cookie',cookie)
            self.end_headers();self.wfile.write(data)
        def guard_host(self):
            host=self.headers.get('Host','')
            try: parsed=urlsplit(scheme+'://'+host)
            except ValueError: raise HTTPError(403,'잘못된 접속 주소입니다.')
            if parsed.hostname not in hosts or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
                raise HTTPError(403,'허용되지 않은 접속 주소입니다.')
            try: port=parsed.port or (443 if tls else 80)
            except ValueError: raise HTTPError(403,'잘못된 포트입니다.')
            if port!=self.server.server_port: raise HTTPError(403,'잘못된 접속 포트입니다.')
            return host
        def authenticate(self):
            try:
                cookie=SimpleCookie();cookie.load(self.headers.get('Cookie',''))
                token=cookie['deck_session'].value if 'deck_session' in cookie else ''
            except Exception: token=''
            with auth_lock:
                now=access.clock()
                for key in list(sessions):
                    if sessions[key]['expires']<=now: del sessions[key]
                session=sessions.get(token)
                if not session: raise HTTPError(401,'접속 코드를 입력해 맥과 연결하세요.')
                return token,session
        def authorize_current(self,token,session):
            with auth_lock:
                if sessions.get(token) is not session or session['expires']<=access.clock():
                    raise HTTPError(401,'Device session revoked or expired. This request was not admitted.')
        def read_json(self):
            if self.headers.get('Content-Type','').split(';')[0].strip()!='application/json':
                raise HTTPError(415,'JSON 요청만 허용됩니다.')
            if self.headers.get('Transfer-Encoding'): raise HTTPError(400,'지원하지 않는 요청입니다.')
            try: size=int(self.headers.get('Content-Length','-1'))
            except ValueError: raise HTTPError(400,'잘못된 요청 크기입니다.')
            if size<0: raise HTTPError(411,'요청 크기가 필요합니다.')
            if size>262144: raise HTTPError(413,'요청이 너무 큽니다.')
            try: body=json.loads(self.rfile.read(size))
            except (ValueError,UnicodeDecodeError): raise HTTPError(400,'잘못된 JSON입니다.')
            if not isinstance(body,dict): raise HTTPError(400,'객체 형식의 요청이 필요합니다.')
            return body
        def do_GET(self): self.handle_request(False)
        def do_POST(self): self.handle_request(True)
        def handle_request(self,mutation):
            try:
                host=self.guard_host();url=urlsplit(self.path);path=url.path
                if self.headers.get('Origin') and self.headers.get('Origin')!=scheme+'://'+host:raise HTTPError(403,'Origin mismatch')
                if mutation:
                    if self.headers.get('Origin')!=scheme+'://'+host: raise HTTPError(403,'이 화면에서 보낸 요청만 실행할 수 있습니다.')
                    body=self.read_json()
                    if path=='/api/pair':
                        with auth_lock:
                            now=access.clock();ip=self.client_address[0]
                            if not access.pairing_open():raise HTTPError(403,'Pairing is closed. Type p in the Mac server console to open it for 120 seconds.')
                            # A global bound prevents unbounded address/session allocation.
                            for addr in list(attempts):
                                attempts[addr]=[t for t in attempts[addr] if t>now-60]
                                if not attempts[addr]: del attempts[addr]
                            recent=attempts.setdefault(ip,[])
                            if len(recent)>=10 or sum(map(len,attempts.values()))>=100:
                                raise HTTPError(429,'접속 시도가 많습니다. 1분 후 다시 시도하세요.')
                            recent.append(now)
                            supplied=body.get('code')
                            if not isinstance(supplied,str) or not hmac.compare_digest(supplied.encode(),access.code.encode()):
                                raise HTTPError(401,'접속 코드가 일치하지 않습니다.')
                            for token in list(sessions):
                                if sessions[token]['expires']<=now: del sessions[token]
                            if len(sessions)>=32: raise HTTPError(429,'연결된 기기가 너무 많습니다. 서버를 재시작하세요.')
                            name=body.get('deviceName','Browser')
                            if not isinstance(name,str):raise HTTPError(400,'Invalid device name')
                            name=''.join(c for c in name if c.isprintable())[:40].strip() or 'Browser'
                            token=secrets.token_urlsafe(32);sessions[token]={'id':secrets.token_hex(8),'name':name,'expires':now+43200,'seen':{}}
                        return self.send_data(200,{'ok':True},cookie=f'deck_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200{cookie_security}')
                if not mutation and path in {'/','/style.css','/app.js'}:
                    file=WEB/({'/':'index.html'}.get(path,path[1:]))
                    types={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8'}
                    return self.send_data(200,file.read_bytes(),types[file.suffix])
                token,session=self.authenticate()
                if not mutation:
                    if path=='/api/arc/tabs':
                        if self.headers.get('Origin') and self.headers.get('Origin')!=scheme+'://'+host:raise HTTPError(403,'이 화면에서 보낸 요청만 조회할 수 있습니다.')
                        return self.send_data(200,expensive(mac.arc_tabs))
                    if path=='/api/state':
                        result=state.snapshot();clip=state.clipboard.snapshot()
                        if hasattr(state,'ai'):result['ai']=state.ai.snapshot();result.update(state.providers.snapshot())
                        result['clipboard']={'enabled':clip['enabled'],'count':len(clip['items']),'error':clip['error']}
                        return self.send_data(200,result)
                    if path=='/api/ai/detail':
                        def capture():
                            slot=int(parse_qs(url.query).get('slot',['-1'])[0])
                            source=state.ai.source(slot)
                            if source.get('provider')=='claude' or slot not in state.ai.mappings:
                                state.ai.bind(slot,mac.resolve_session_window(source))
                            detail=state.ai.detail(slot)
                            # Capture and recheck the exact registered target before issuing a response nonce.
                            result=mac.capture_registered(detail['mapping'])
                            return {**detail,**result}
                        return self.send_data(200,expensive(capture))
                    if path=='/api/weather/search':
                        return self.send_data(200,{'cities':expensive(lambda:state.providers.cities(parse_qs(url.query).get('q',[''])[0]))})
                    if path=='/api/system': return self.send_data(200,expensive(mac.system_status))
                    if path=='/api/diagnostics': return self.send_data(200,expensive(mac.diagnostics))
                    if path=='/api/apps': return self.send_data(200,{'apps':[{'id':a['id'],'name':a['name']} for a in mac.apps]})
                    if path=='/api/clipboard': return self.send_data(200,state.clipboard.snapshot())
                    if path=='/api/icon':
                        data=expensive(lambda:mac.icon(parse_qs(url.query).get('id',[''])[0]))
                        if data: return self.send_data(200,data,'image/png')
                        raise HTTPError(404,'아이콘이 없습니다.')
                else:
                    self.authorize_current(token,session) # Mutation admission boundary; no global lock during OS calls.
                    if path=='/api/logout':
                        with auth_lock: sessions.pop(token,None)
                        return self.send_data(200,{'ok':True},cookie='deck_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'+cookie_security)
                    if path=='/api/ai/task':
                        state.ai.set_alias(body.get('slot'),body.get('session'),body.get('alias'));return self.send_data(200,{'ok':True})
                    if path=='/api/ai/register':
                        state.ai.register(body.get('slot'),body.get('session'));return self.send_data(200,{'ok':True})
                    if path=='/api/weather':
                        state.providers.set_location(body);return self.send_data(200,{'ok':True})
                    if path=='/api/presets':
                        state.add_presets();return self.send_data(200,{'ok':True})
                    if path=='/api/preferences':
                        state.save_preferences(body);return self.send_data(200,{'ok':True})
                    if path=='/api/buttons': state.save_buttons(body.get('buttons'));return self.send_data(200,{'ok':True})
                    if path=='/api/clipboard':
                        action=body.get('action')
                        if action=='enabled': state.clipboard.set_enabled(body.get('enabled'))
                        elif action=='delete':
                            ident=body.get('id')
                            if not isinstance(ident,str): raise ValueError('삭제할 항목이 필요합니다.')
                            state.clipboard.delete(ident)
                        elif action=='clear': state.clipboard.delete(None)
                        elif action=='copy':
                            # Serialize with sampling to avoid history reappearing after copy.
                            with state.clipboard.lock:
                                self.authorize_current(token,session)
                                text=state.clipboard.get(body.get('id'));mac.write_clipboard(text)
                                state.clipboard.last=text;state.clipboard.generation+=1
                        else: raise ValueError('잘못된 클립보드 동작입니다.')
                        return self.send_data(200,{'ok':True})
                    if path in {'/api/run','/api/system','/api/ai/reply'}:
                        request_id=body.get('requestId')
                        if not isinstance(request_id,str) or not re.fullmatch('[a-zA-Z0-9_-]{16,80}',request_id): raise ValueError('실행 요청 ID가 필요합니다.')
                        button=state.button(body.get('id')) if path=='/api/run' else ({'kind':'ai','label':'AI 응답'} if path=='/api/ai/reply' else {'kind':'system','label':'시스템 제어','command':validate_system_command(body)})
                        if not action_lock.acquire(blocking=False): raise HTTPError(409,'다른 동작을 실행 중입니다. 잠시 후 다시 눌러주세요.')
                        try:
                            with auth_lock:
                                self.authorize_current(token,session)
                                if request_id in session['seen']: raise HTTPError(409,'이미 처리한 실행 요청입니다.')
                                if len(session['seen'])>=10000: raise HTTPError(429,'실행 한도에 도달했습니다. 다시 연결하세요.')
                                session['seen'][request_id]=time.monotonic()
                            result=None
                            if button['kind']=='ai':
                                if set(body)-{'slot','revision','key','nonce','requestId'}:raise ValueError('추가 키·자유 텍스트는 허용되지 않습니다.')
                                mapping=state.ai.consume_reply(body.get('slot'),body.get('revision'),body.get('key'),body.get('nonce'))
                                result=mac.reply_registered(mapping,body['key'])
                            if button['kind']=='trash': result=trash.check(token,button['id'],body.get('confirmationId'))
                            if result is None: result=mac.system_control(button['command']) if button['kind']=='system' else execute_button(button,mac,mac.apps)
                        finally: action_lock.release()
                        return self.send_data(200,{'ok':True,'label':button['label'],**result})
                raise HTTPError(404,'요청을 찾을 수 없습니다.')
            except HTTPError as exc: self.send_data(exc.status,{'error':exc.message})
            except ValueError as exc: self.send_data(400,{'error':str(exc)})
            except (RuntimeError,OSError) as exc:
                if isinstance(exc,(BrokenPipeError,ConnectionResetError)): return
                self.send_data(503,{'error':str(exc) if isinstance(exc,RuntimeError) else '맥의 파일이나 서비스에 접근할 수 없습니다.'})
    server=BoundedServer((host,port),Handler,context=tls,max_connections=max_connections)
    server.access=access
    server.daemon_threads=True
    return server
