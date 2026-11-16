"""Small macOS boundary. User values are never interpolated into shell commands."""
import hashlib
import json
import os
import plistlib
import re
import subprocess
from pathlib import Path

KEY_CODES = {'enter':36,'tab':48,'space':49,'backspace':51,'escape':53,'delete':117,
             'left':123,'right':124,'down':125,'up':126,'home':115,'end':119,
             'pageup':116,'pagedown':121}
KEY_CODES.update(dict(zip(('f'+str(i) for i in range(1,13)), (122,120,99,118,96,97,98,100,101,109,103,111))))
MODIFIERS = {'command','option','control','shift'}

def shortcut_script(key, modifiers):
    if not isinstance(key,str) or not (re.fullmatch('[a-z0-9]',key) or key in KEY_CODES):
        raise ValueError('키는 영문 한 글자, 숫자 또는 지원하는 특수 키를 선택하세요.')
    if not isinstance(modifiers,list) or len(modifiers)>4 or any(not isinstance(m,str) or m not in MODIFIERS for m in modifiers):
        raise ValueError('잘못된 보조 키입니다.')
    if len(set(modifiers)) != len(modifiers): raise ValueError('보조 키가 중복되었습니다.')
    action = f'key code {KEY_CODES[key]}' if key in KEY_CODES else f'keystroke "{key}"'
    if modifiers: action += ' using {' + ', '.join(m+' down' for m in modifiers) + '}'
    return 'tell application "System Events" to '+action


def run(args, **kwargs):
    try:
        return subprocess.run(args, check=True, capture_output=True, timeout=8, **kwargs).stdout
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('맥의 응답 시간이 초과되었습니다. 권한 요청 창을 확인하세요.') from exc
    except subprocess.CalledProcessError as exc:
        if args[0] == '/usr/bin/osascript':
            raise RuntimeError('키를 전송하지 못했습니다. 시스템 설정 → 개인정보 보호 및 보안 → 손쉬운 사용에서 서버를 실행한 Terminal 또는 Orca를 허용하세요. 자동화 권한 요청도 확인하세요.') from exc
        raise RuntimeError('맥에서 작업을 실행하지 못했습니다. 앱 설치와 실행 상태를 확인하세요.') from exc


class Mac:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.apps = self.list_apps()
        self.bridge_error=None
        try: self.prepare_bridge()
        except (OSError,RuntimeError,subprocess.TimeoutExpired):
            self.bridge_error='네이티브 도우미 빌드 실패. Xcode Command Line Tools를 확인한 뒤 서버를 재시작하세요.'

    def list_apps(self):
        roots = [Path('/Applications'), Path.home()/'Applications', Path('/System/Applications'), Path('/System/Library/CoreServices')]
        paths = set()
        for root in roots:
            if root.name == 'CoreServices':
                paths.add(root/'Finder.app')
            else:
                paths.update(root.glob('*.app'))
                paths.update(root.glob('*/*.app'))
        apps = []
        for path in sorted(paths):
            try:
                with (path/'Contents/Info.plist').open('rb') as file: info=plistlib.load(file)
                if info.get('LSBackgroundOnly'): continue
                apps.append({'id':hashlib.sha256(str(path).encode()).hexdigest()[:16],
                             'name':path.stem,'path':str(path),'bundleId':info.get('CFBundleIdentifier','')})
            except (OSError,plistlib.InvalidFileException): continue
        return sorted(apps,key=lambda a:a['name'].lower())

    def arc_tabs(self):
        from .arc import read_tabs
        return read_tabs()

    def open_app(self, path):
        if path not in {a['path'] for a in self.apps} or not Path(path).is_dir():
            raise ValueError('설치된 앱을 찾을 수 없습니다. 서버를 다시 시작해 목록을 갱신하세요.')
        return self.bridge({'action':'activate','path':path})

    def shortcut(self,key,modifiers,expected=None):
        shortcut_script(key,modifiers)
        letters={'a':0,'s':1,'d':2,'f':3,'h':4,'g':5,'z':6,'x':7,'c':8,'v':9,'b':11,'q':12,'w':13,'e':14,'r':15,'y':16,'t':17,'1':18,'2':19,'3':20,'4':21,'6':22,'5':23,'9':25,'7':26,'8':28,'0':29,'o':31,'u':32,'i':34,'p':35,'l':37,'j':38,'k':40,'n':45,'m':46}
        return self.bridge({'action':'shortcut','code':KEY_CODES.get(key,letters.get(key)),'modifiers':modifiers,**({'expected':expected} if expected is not None else {})})

    def prepare_bridge(self):
        self.bridge_source=Path(__file__).resolve().parent.parent/'native/DeckBridge.swift'
        self.bridge_binary=self.data_dir/'native/deck-bridge'
        source,binary=self.bridge_source,self.bridge_binary
        if not binary.exists() or binary.stat().st_mtime<source.stat().st_mtime:
            binary.parent.mkdir(parents=True,exist_ok=True)
            build=subprocess.run(['/usr/bin/swiftc',str(source),'-o',str(binary)],capture_output=True,timeout=60)
            if build.returncode: raise RuntimeError('네이티브 도우미 빌드 실패')
        self.bridge_version=source.stat().st_mtime_ns

    def bridge(self,payload):
        # Compilation happens before the server accepts requests, never after a client timeout.
        if self.bridge_error: raise RuntimeError(self.bridge_error)
        if self.bridge_source.stat().st_mtime_ns!=self.bridge_version:
            raise RuntimeError('네이티브 코드가 변경되었습니다. 서버를 재시작하세요. 명령은 실행되지 않았습니다.')
        binary=self.bridge_binary
        try:
            response=subprocess.run([str(binary)],input=json.dumps(payload).encode(),capture_output=True,timeout=8)
            result=json.loads(response.stdout)
        except (subprocess.TimeoutExpired,ValueError) as exc:
            raise RuntimeError('네이티브 응답을 확인하지 못했습니다. 일부 실행되었을 수 있어 재시도하지 않습니다.') from exc
        if response.returncode: raise RuntimeError(result.get('error','네이티브 작업 실패'))
        return result

    def resolve_session_window(self,source):
        process=source.get('process')
        if source.get('provider')!='claude' or not isinstance(process,dict):
            raise ValueError('이 세션과 실제 창의 연결을 증명할 수 없습니다. 다른 창을 대신 표시하지 않습니다.')
        result=self.bridge({'action':'terminal-target','process':process})['mapping']
        result.update(sessionProofPath=source.get('proofPath'),sessionId=source['id'].removeprefix('claude:'),question=source.get('question'))
        return result

    def capture_registered(self,mapping):
        import base64
        import tempfile
        self.bridge({'action':'check-target','expected':mapping})
        with tempfile.TemporaryDirectory(prefix='deck-window-') as directory:
            path=Path(directory)/'window.png'
            try:subprocess.run(['/usr/sbin/screencapture','-x','-l',str(mapping['windowId']),str(path)],check=True,timeout=5,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            except (subprocess.SubprocessError,OSError):raise RuntimeError('등록 창 캡처 실패 · 창 종료 또는 화면 기록 권한을 확인하세요.')
            self.bridge({'action':'check-target','expected':mapping})
            data=path.read_bytes()
            if not data.startswith(b'\x89PNG') or len(data)>12_000_000:raise RuntimeError('창 캡처를 확인하지 못했습니다.')
            return {'image':'data:image/png;base64,'+base64.b64encode(data).decode(),'capturedAt':__import__('time').time()}

    def reply_registered(self,mapping,key):
        if key not in {'up','down','enter'}:raise ValueError('허용되지 않은 응답 키입니다.')
        return self.shortcut(key,[],expected={**mapping,'requireQuestion':True})

    def diagnostics(self): return self.bridge({'action':'inspect'})

    def type_text(self,text,enter,expected=None):
        return self.bridge({'action':'text','text':text,'enter':enter,**({'expected':expected} if expected is not None else {})})

    def system_status(self): return self.bridge({'action':'system-status'})

    def system_control(self,body,expected_id=None):
        from .actions import validate_system_command
        command=validate_system_command(body)
        return self.bridge({'action':'system','operation':command['action'],**({'expectedIdentity':expected_id} if expected_id is not None else {}),**({'value':command['value']} if 'value' in command else {})})

    def open_urls(self,urls):
        from .actions import validate_urls
        for index,url in enumerate(validate_urls(urls)):
            try: run(['/usr/bin/open',url])
            except RuntimeError as exc:
                raise RuntimeError(f'{index}개 URL 접수 후 중단했습니다. 묶음을 자동 재시도하지 않습니다.') from exc
        return {'status':'accepted','count':len(urls),'message':f'{len(urls)}개 URL 열기를 맥에 요청했습니다. 페이지 로드는 확인되지 않았습니다.'}

    def empty_trash(self):
        run(['/usr/bin/osascript','-e','tell application "Finder" to empty trash'])
        return {'status':'accepted','message':'Finder가 휴지통 비우기 명령을 처리했습니다.'}


    def read_clipboard(self):
        return run(['/usr/bin/pbpaste','-Prefer','txt']).decode('utf-8', errors='replace')

    def write_clipboard(self,text):
        run(['/usr/bin/pbcopy'], input=text.encode('utf-8'))

    def icon(self,app_id):
        app = next((a for a in self.apps if a['id']==app_id),None)
        if not app: return None
        dest=self.data_dir/'icons'/(app_id+'.png')
        if dest.exists(): return dest.read_bytes()
        path=Path(app['path'])/'Contents'
        try:
            with (path/'Info.plist').open('rb') as file: info=plistlib.load(file)
            name=info.get('CFBundleIconFile','')
            # Icon paths come from installed bundles, but still stay inside Resources.
            source=path/'Resources'/Path(name).name
            if not source.suffix: source=source.with_suffix('.icns')
            if not source.is_file():
                source=next((path/'Resources').glob('*.icns'),None)
            if not source: return None
            dest.parent.mkdir(parents=True,exist_ok=True)
            run(['/usr/bin/sips','-s','format','png','-Z','96',str(source),'--out',str(dest)])
            return dest.read_bytes()
        except (OSError,ValueError,RuntimeError): return None

    def status(self):
        result={'cpu':None,'ram':None,'battery':None,'charging':False,'memory_total':None}
        try:
            # top's first sample is a real host-wide reading, refreshed in a worker.
            top=run(['/usr/bin/top','-l','1','-n','0']).decode()
            cpu=re.search(r'CPU usage: ([\d.]+)% user, ([\d.]+)% sys',top)
            if cpu: result['cpu']=round(float(cpu[1])+float(cpu[2]),1)
            total=int(run(['/usr/sbin/sysctl','-n','hw.memsize']))
            vm=run(['/usr/bin/vm_stat']).decode()
            page=int(re.search(r'page size of (\d+)',vm)[1])
            pages={k:int(v) for k,v in re.findall(r'^([^:]+):\s+(\d+)',vm,re.M)}
            used=sum(pages.get(k,0) for k in ['Pages active','Pages wired down','Pages occupied by compressor']) * page
            result['ram']=round(100*used/total)
            result['memory_total']=round(total/1024**3)
            battery=run(['/usr/bin/pmset','-g','batt']).decode()
            match=re.search(r'(\d+)%',battery)
            if match: result['battery']=int(match[1])
            result['charging']='AC Power' in battery
        except (RuntimeError,OSError,ValueError,TypeError): pass
        return result
