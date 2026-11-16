"""Validated deck configuration and ephemeral clipboard history."""
import copy
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path
from .macos import shortcut_script
from .actions import validate_urls


def validate_button(button, apps):
    if not isinstance(button,dict): raise ValueError('잘못된 버튼입니다.')
    ident,label,kind=button.get('id'),button.get('label'),button.get('kind')
    if not isinstance(ident,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',ident): raise ValueError('잘못된 버튼 ID입니다.')
    if not isinstance(label,str) or not 1<=len(label.strip())<=60: raise ValueError('이름은 1~60자로 입력하세요.')
    result={'id':ident,'label':label.strip(),'kind':kind}
    if kind=='app':
        if not isinstance(button.get('app'),str) or button['app'] not in {a['id'] for a in apps}: raise ValueError('설치된 앱을 선택하세요.')
        result['app']=button['app']
    elif kind=='shortcut':
        shortcut_script(button.get('key'),button.get('modifiers'))
        result.update(key=button['key'],modifiers=button['modifiers'])
    elif kind=='text':
        text,enter=button.get('text'),button.get('enter',False)
        if not isinstance(text,str) or not 1<=len(text)<=1000 or any(ord(c)<32 and c not in '\n\r\t' for c in text) or type(enter) is not bool:
            raise ValueError('텍스트는 1~1000자이며 Enter 설정은 참/거짓이어야 합니다.')
        result.update(text=text,enter=enter)
    elif kind=='urls': result['urls']=validate_urls(button.get('urls'))
    elif kind=='trash': pass
    else: raise ValueError('지원하지 않는 버튼 종류입니다.')
    return result


PREFERRED_APPS=[('Arc','Arc'),('Orca','Orca'),('Safari','Safari'),('System Settings','설정'),('Finder','Finder'),('KakaoTalk','카카오톡'),('Notes','메모'),('Claude','Claude'),('zoom.us','Zoom')]


def preferred_app_order(buttons,apps):
    """Explicit one-time ordering only; never invoked when loading saved settings."""
    result=[];used=set();missing=[]
    installed={a['name'].casefold():a for a in apps}
    chrome=installed.get('google chrome');arc=installed.get('arc')
    old_apps=[b for b in buttons if b['kind']=='app']
    for name,label in PREFERRED_APPS:
        app=installed.get(name.casefold())
        if not app:missing.append(label);continue
        old=next((b for b in old_apps if b['app']==app['id'] and b['id'] not in used),None)
        if old:
            button=copy.deepcopy(old)
            if name=='Arc' and button['label'].strip().casefold() in {'크롬','chrome','google chrome'}:button['label']='Arc'
        else:
            replacement=next((b for b in old_apps if name=='Arc' and chrome and b['app']==chrome['id']),None)
            ident=replacement['id'] if replacement else 'app-'+app['id']
            if ident in {b['id'] for b in buttons} and not replacement:ident='app-'+uuid.uuid4().hex
            button=dict(id=ident,label=label,kind='app',app=app['id'])
        used.add(button['id']);result.append(button)
    result.extend(copy.deepcopy(b) for b in old_apps if b['id'] not in used and not (arc and chrome and b['app']==chrome['id']))
    if len(result)<len(old_apps):raise ValueError('앱 중복 제거가 다른 모드 위치를 바꿀 수 있어 자동 저장하지 않았습니다.')
    ordered=iter(result);merged=[next(ordered) if b['kind']=='app' else copy.deepcopy(b) for b in buttons];merged.extend(ordered)
    return merged,missing


def defaults(apps):
    shortcuts=[('capture','화면 캡처','4',['command','shift','control']),
               ('paste','붙여넣기','v',['command']),('copy','복사','c',['command']),
               ('select','전체 선택','a',['command']),('undo','실행 취소','z',['command']),
               ('find','찾기','f',['command']),('save','저장','s',['command']),
               ('switch','앱 전환','tab',['command']),('spotlight','Spotlight','space',['command'])]
    buttons=[dict(id=i,label=l,kind='shortcut',key=k,modifiers=m) for i,l,k,m in shortcuts]
    for name,label in PREFERRED_APPS:
        app=next((a for a in apps if a['name'].casefold()==name.casefold()),None)
        if app:buttons.append(dict(id='app-'+app['id'],label=label,kind='app',app=app['id']))
    return buttons


class Clipboard:
    def __init__(self):
        self.lock=threading.RLock(); self.enabled=False; self.items=[]; self.last=None
        self.generation=0; self.error=None

    def set_enabled(self,enabled):
        if type(enabled) is not bool: raise ValueError('수집 상태가 잘못되었습니다.')
        with self.lock:
            if self.enabled != enabled:
                self.enabled=enabled; self.last=None; self.generation+=1; self.error=None

    def observe(self,text,generation=None):
        with self.lock:
            if not self.enabled or (generation is not None and generation!=self.generation): return
            if self.last is None: self.last=text; return
            if text==self.last: return
            self.last=text
            if not isinstance(text,str) or not text.strip() or len(text)>100_000: return
            self.items=[item for item in self.items if item['text']!=text]
            self.items.insert(0,{'id':uuid.uuid4().hex,'text':text,'time':time.time()})
            del self.items[100:]

    def delete(self,ident):
        with self.lock:
            self.items=[] if ident is None else [i for i in self.items if i['id']!=ident]
            # Invalidate an already-running poll without resetting last-seen text.
            self.generation+=1

    def get(self,ident):
        with self.lock:
            item=next((i for i in self.items if i['id']==ident),None)
            if item is None: raise ValueError('기록이 삭제되었거나 더 이상 없습니다.')
            return item['text']

    def snapshot(self):
        with self.lock: return {'enabled':self.enabled,'items':copy.deepcopy(self.items),'error':self.error}


class State:
    def __init__(self,config_path,apps):
        self.path=Path(config_path); self.apps=apps; self.lock=threading.RLock()
        self.clipboard=Clipboard(); self.metrics={}; self.config_warning=None
        self.buttons=defaults(apps); self.preferences={'macSound':False}
        if self.path.exists():
            try:
                config=json.loads(self.path.read_text()); saved=config['buttons']
                self.preferences=self._preferences(config.get('preferences',{'macSound':False}))
                # Keep missing app buttons visible, so uninstalling never destroys user layout.
                known=apps + [{'id':b.get('app')} for b in saved if isinstance(b,dict) and isinstance(b.get('app'),str)]
                self.buttons=self._validated(saved,known)
            except (OSError,ValueError,KeyError,TypeError):
                self.config_warning='저장된 설정을 읽지 못해 기본 버튼을 표시합니다. 원본 파일은 유지됩니다.'

    def _validated(self,buttons,apps):
        if not isinstance(buttons,list) or len(buttons)>100: raise ValueError('버튼은 최대 100개입니다.')
        result=[validate_button(b,apps) for b in buttons]
        if len({b['id'] for b in result})!=len(result): raise ValueError('버튼 ID가 중복되었습니다.')
        return result

    def save_buttons(self,buttons):
        with self.lock:
            # Existing missing apps may be retained or removed, never newly registered.
            known=self.apps+[{'id':b['app']} for b in self.buttons if b['kind']=='app']
            result=self._validated(buttons,known)
            self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            temp=self.path.with_suffix('.tmp')
            temp.write_text(json.dumps({'buttons':result,'preferences':self.preferences},ensure_ascii=False,indent=2))
            os.chmod(temp,0o600); temp.replace(self.path)
            self.buttons=result; self.config_warning=None

    @staticmethod
    def _preferences(value):
        if not isinstance(value,dict) or set(value)!={'macSound'} or type(value['macSound']) is not bool:
            raise ValueError('잘못된 알림음 설정입니다.')
        return dict(value)

    def add_presets(self):
        with self.lock:
            presets=[{'id':'preset-'+ident,'label':label,'kind':'text','text':value,'enter':False}
                     for ident,label,value in [('ok','ok','ok'),('clear','/clear','/clear'),('continue','keep going','keep going'),('log','Log','Log')]]
            existing={b['id'] for b in self.buttons}
            self.save_buttons(self.buttons+[b for b in presets if b['id'] not in existing])

    def save_preferences(self,value):
        with self.lock:
            previous=self.preferences;self.preferences=self._preferences(value)
            try: self.save_buttons(self.buttons)
            except Exception:
                self.preferences=previous
                raise

    def snapshot(self):
        with self.lock:
            return {'preferences':dict(self.preferences),'buttons':copy.deepcopy(self.buttons),'metrics':copy.deepcopy(self.metrics),'warning':self.config_warning}

    def button(self,ident):
        with self.lock:
            button=next((b for b in self.buttons if b['id']==ident),None)
            if button is None: raise ValueError('버튼을 찾을 수 없습니다.')
            return copy.deepcopy(button)


def clipboard_worker(state,mac,stop):
    while not stop.wait(.8):
        with state.clipboard.lock:
            if not state.clipboard.enabled: continue
            generation=state.clipboard.generation
        try:
            text=mac.read_clipboard()
            state.clipboard.observe(text,generation)
            with state.clipboard.lock: state.clipboard.error=None
        except (RuntimeError,OSError):
            with state.clipboard.lock: state.clipboard.error='맥 클립보드를 읽지 못했습니다.'


def metrics_worker(state,mac,stop):
    while not stop.is_set():
        metrics=mac.status()
        with state.lock: state.metrics=metrics
        stop.wait(5)
