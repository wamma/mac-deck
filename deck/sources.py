"""Read-only providers. Only allowlisted metadata crosses the adapter boundary."""
import datetime
import json
import math
import os
from pathlib import Path
import selectors
import shutil
import sqlite3
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from .orca_activity import OrcaActivity


def window_usage(value,pct='usedPercent',period=None):
    if not isinstance(value,dict):return None
    used=value.get(pct);minutes=period if period is not None else value.get('windowDurationMins')
    reset=value.get('resetsAt',value.get('resets_at'))
    if type(used) not in (float,int) or not math.isfinite(used) or not 0<=used<=100:return None
    return {'usedPercent':used,'minutes':minutes,'resetsAt':reset if type(reset) in (int,float) and math.isfinite(reset) else None}


def codex_usage():
    executable=shutil.which('codex')
    if not executable:raise RuntimeError('Codex CLI 설치가 필요합니다.')
    p=subprocess.Popen([executable,'app-server'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    selector=selectors.DefaultSelector();selector.register(p.stdout,selectors.EVENT_READ)
    def send(value):p.stdin.write((json.dumps(value)+'\n').encode());p.stdin.flush()
    try:
        send({'id':1,'method':'initialize','params':{'clientInfo':{'name':'mac_deck','version':'1.0'},'capabilities':{'experimentalApi':True}}})
        deadline=time.monotonic()+15;buffer=b''
        while time.monotonic()<deadline:
            if not selector.select(.5):continue
            chunk=os.read(p.stdout.fileno(),65536)
            if not chunk:break
            buffer+=chunk
            if len(buffer)>2_000_000:raise RuntimeError('사용량 응답이 너무 큽니다.')
            while b'\n' in buffer:
                line,buffer=buffer.split(b'\n',1);message=json.loads(line)
                if message.get('id')==1:
                    if 'error' in message:raise RuntimeError('Codex 사용량 인터페이스 초기화 실패')
                    send({'method':'initialized'});send({'id':2,'method':'account/rateLimits/read','params':{'excludeResetCreditDetails':True}})
                if message.get('id')==2:
                    if 'error' in message:raise RuntimeError('Codex CLI에서 ChatGPT 계정 로그인 및 사용량 조회 지원 여부를 확인하세요.')
                    rates=message.get('result',{}).get('rateLimits',{})
                    windows=[v for key in ['primary','secondary'] if (v:=window_usage(rates.get(key)))]
                    return {'source':'Codex account/rateLimits/read','status':'ok' if windows else 'unsupported','windows':windows,'updatedAt':time.time()}
        raise RuntimeError('Codex 사용량 조회 시간 초과')
    finally:
        selector.close();p.terminate()
        try:p.wait(timeout=3)
        except subprocess.TimeoutExpired:p.kill();p.wait()


def event_time(value):
    try:
        result=float(value) if type(value) in (int,float) else datetime.datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
        return result if math.isfinite(result) and result>0 else None
    except (ValueError,TypeError,AttributeError):return None


class CodexRollouts:
    """Global metadata discovery, bounded lifecycle reads. Never infer Orca window identity."""
    LIMIT=2000
    BATCH=24
    READ_LIMIT=1_000_000
    def __init__(self,sessions,root=None,cwd=None):
        self.sessions=sessions;self.root=Path(root or Path.home()/'.codex/sessions').resolve();self.cwd=str(Path(cwd or Path.cwd()).resolve());self.files={};self.headers={};self.last_stats={}
    def catalog(self):
        titles={}
        try:
            with (self.root.parent/'session_index.jsonl').open('rb') as index:
                size=index.seek(0,2);index.seek(max(0,size-1_000_000))
                if size>1_000_000:index.readline()
                for line in index:
                    try:
                        row=json.loads(line)
                        if isinstance(row.get('thread_name'),str):titles[row.get('id')]=row['thread_name'][:80]
                    except (ValueError,TypeError):pass
        except OSError:pass
        databases=sorted(self.root.parent.glob('state_*.sqlite'),key=lambda p:p.stat().st_mtime,reverse=True)
        for database in databases[:1]:
            try:
                with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True,timeout=.2) as conn:
                    cols={r[1] for r in conn.execute('PRAGMA table_info(threads)')}
                    if not {'id','rollout_path','cwd','title','updated_at'}.issubset(cols):break
                    name="substr(name,1,80)" if 'name' in cols else 'NULL'
                    fields=f"id,rollout_path,cwd,substr(title,1,80),{name},updated_at"
                    count=conn.execute('SELECT count(*) FROM threads').fetchone()[0]
                    rows=conn.execute(f'SELECT {fields} FROM threads ORDER BY updated_at DESC LIMIT ?', (self.LIMIT,)).fetchall()
                    registered=[i[6:] for i in self.sessions.slots if i and i.startswith('codex:')]
                    if registered:rows+=conn.execute(f"SELECT {fields} FROM threads WHERE id IN ({','.join('?' for _ in registered)})",registered).fetchall()
                records={}
                for ident,path,cwd,title,name,updated in rows:
                    path=Path(path)
                    if not path.is_absolute() or not path.resolve().is_relative_to(self.root.resolve()):continue
                    records['codex:'+ident]={'id':'codex:'+ident,'path':path,'cwd':cwd,'title':name or titles.get(ident) or title or '', 'updatedAt':event_time(updated)}
                return list(records.values()),count,'Codex threads metadata (read-only SQLite)'
            except (sqlite3.Error,OSError,ValueError,TypeError):pass
        # Older installs/tests: inspect only each rollout's session_meta header, never conversation fields.
        paths=sorted(self.root.glob('**/*.jsonl'),key=lambda p:p.stat().st_mtime,reverse=True);records=[]
        for path in paths[:self.LIMIT]:
            stat=path.stat();cached=self.headers.get(path)
            if not cached or cached[0]!=stat.st_ino:
                try:
                    with path.open('rb') as stream:data=json.loads(stream.readline(self.READ_LIMIT))
                    meta=data.get('payload',{}) if data.get('type')=='session_meta' else {}
                    if not isinstance(meta.get('id'),str):continue
                    cached=(stat.st_ino,meta['id'],str(meta.get('cwd') or ''));self.headers[path]=cached
                except (ValueError,OSError):continue
            _,ident,cwd=cached
            records.append({'id':'codex:'+ident,'path':path,'cwd':cwd,'title':titles.get(ident,''),'updatedAt':stat.st_mtime})
        return records,len(paths),'rollout session_meta fallback'
    def poll(self):
        started=time.monotonic();records,total,source=self.catalog()
        paths={r['path'] for r in records};self.files={p:c for p,c in self.files.items() if p in paths};self.headers={p:c for p,c in self.headers.items() if p in paths}
        self.sessions.discover(records,total=total,listed=len(records),truncated=total>len(records),source=source,stateBatch=self.BATCH)
        candidates=[]
        for record in records:
            try:stat=record['path'].stat()
            except OSError:continue
            record={**record,'stat':stat};cursor=self.files.get(record['path'])
            registered=record['id'] in self.sessions.slots
            if time.time()-stat.st_mtime<20:self.sessions.heartbeat(record['id'])
            if registered or not cursor or cursor['inode']!=stat.st_ino or cursor['offset']!=stat.st_size:candidates.append(record)
        candidates.sort(key=lambda r:(r['id'] not in self.sessions.slots,-r['stat'].st_mtime))
        unregistered=0;reads=0;bytes_read=0;liveness=0
        for record in candidates:
            ident,path,stat=record['id'],record['path'],record['stat'];registered=ident in self.sessions.slots
            if not registered:
                if unregistered>=self.BATCH:continue
                unregistered+=1
            cursor=self.files.get(path)
            if not cursor or cursor.get('id')!=ident or cursor['inode']!=stat.st_ino or cursor['offset']>stat.st_size:
                try:
                    with path.open('rb') as header_stream:header=json.loads(header_stream.readline(self.READ_LIMIT))
                    if header.get('type')!='session_meta' or 'codex:'+str(header.get('payload',{}).get('id'))!=ident:continue
                except (ValueError,OSError):continue
                cursor={'offset':0,'inode':stat.st_ino,'id':ident}
            with path.open('rb') as stream:
                offset=max(cursor['offset'],stat.st_size-self.READ_LIMIT,0);stream.seek(offset)
                if offset>cursor['offset']:stream.readline(self.READ_LIMIT) # partial line is not an event
                for _ in range(10000):
                    line=stream.readline(self.READ_LIMIT+1);bytes_read+=len(line)
                    if not line:break
                    if not line.endswith(b'\n'):
                        if len(line)>self.READ_LIMIT:cursor['offset']=stream.tell()
                        break
                    cursor['offset']=stream.tell()
                    if b'"event_msg"' not in line:continue
                    try:data=json.loads(line)
                    except ValueError:continue
                    if data.get('type')!='event_msg':continue
                    payload=data.get('payload') or {};kind=payload.get('type');mapped={'task_started':'working','task_complete':'completed','turn_aborted':'idle'}.get(kind)
                    if mapped:
                        self.sessions.event(ident,'codex',cursor['offset'],mapped,label='Codex · '+ident[-8:],source='local rollout lifecycle · 승인 신호 미지원',providerTitle=record['title'],eventAt=event_time(payload.get('completed_at') if kind=='task_complete' else payload.get('started_at')) or event_time(data.get('timestamp')),completionPreview=payload.get('last_agent_message') if registered and kind=='task_complete' else None)
            self.files[path]=cursor;reads+=1
            fresh=time.time()-stat.st_mtime<20
            if not fresh and registered:
                # Only registered idle sessions need process-liveness probes; never N stale sessions.
                liveness+=1
                try:
                    opened=subprocess.run(['/usr/sbin/lsof','-t',str(path)],capture_output=True,text=True,timeout=.5).stdout.split()
                    for pid in opened:
                        if not pid.isdigit():continue
                        name=subprocess.run(['/bin/ps','-p',pid,'-o','comm='],capture_output=True,text=True,timeout=.5).stdout.strip()
                        if Path(name).name=='codex':fresh=True;break
                except (OSError,subprocess.TimeoutExpired):pass
            if fresh:self.sessions.heartbeat(ident)
            else:
                with self.sessions.lock:
                    if ident in self.sessions.sources:self.sessions.sources[ident]['seen']=min(self.sessions.sources[ident]['seen'],self.sessions.clock()-31)
        self.last_stats={'listed':len(records),'lifecycleReads':reads,'bytesRead':bytes_read,'livenessProbes':liveness,'seconds':round(time.monotonic()-started,4)}


class Providers:
    def __init__(self,data_dir,sessions):
        self.path=Path(data_dir);self.sessions=sessions;self.lock=threading.RLock();self.rollouts=CodexRollouts(sessions)
        self.usage={'codex':{'status':'loading','windows':[]},'claude':{'status':'no_signal','windows':[],'message':'Claude statusLine 연결 신호 없음'}}
        self.weather={'status':'unconfigured','message':'도시 또는 좌표를 설정하세요.'};self.location=None
        self.hook_sequences={};self.weather_generation=0
        try:self.location=self.validate_location(json.loads((self.path/'weather.json').read_text()))
        except (OSError,ValueError,TypeError):pass
    @staticmethod
    def validate_location(value):
        if not isinstance(value,dict):raise ValueError('위치를 입력하세요.')
        lat,lon=value.get('latitude'),value.get('longitude');name=value.get('name')
        if type(lat) not in (int,float) or type(lon) not in (int,float) or not math.isfinite(lat) or not math.isfinite(lon) or not -90<=lat<=90 or not -180<=lon<=180 or not isinstance(name,str) or not 1<=len(name.strip())<=80:raise ValueError('도시 이름과 올바른 위도·경도가 필요합니다.')
        return {'name':name.strip(),'latitude':lat,'longitude':lon}
    def set_location(self,value):
        location=self.validate_location(value)
        with self.lock:
            tmp=self.path/'weather.tmp';tmp.write_text(json.dumps(location));os.chmod(tmp,0o600);tmp.replace(self.path/'weather.json')
            self.location=location;self.weather_generation+=1;self.weather={'status':'loading'}
        threading.Thread(target=self.fetch_weather,daemon=True).start()
    @staticmethod
    def get_json(url):
        with urllib.request.urlopen(url,timeout=6) as response:
            data=response.read(200001)
            if len(data)>200000:raise ValueError('응답 크기 초과')
            return json.loads(data)
    def cities(self,name):
        if not isinstance(name,str) or not 2<=len(name.strip())<=80:raise ValueError('도시 이름을 2~80자로 입력하세요.')
        data=self.get_json('https://geocoding-api.open-meteo.com/v1/search?'+urllib.parse.urlencode({'name':name.strip(),'count':5,'language':'ko','format':'json'}))
        return [{'name':str(v['name'])+', '+str(v.get('country','')),'latitude':v['latitude'],'longitude':v['longitude']} for v in data.get('results',[])[:5]]
    def fetch_weather(self):
        with self.lock:location=self.location;generation=self.weather_generation
        if not location:return
        try:
            url='https://api.open-meteo.com/v1/forecast?'+urllib.parse.urlencode({k:location[k] for k in ['latitude','longitude']}|{'current':'temperature_2m,weather_code','timezone':'UTC'})
            data=self.get_json(url)['current'];temperature=data.get('temperature_2m');code=data.get('weather_code')
            if type(temperature) not in (int,float) or not math.isfinite(temperature) or type(code) is not int:raise ValueError('잘못된 날씨 응답')
            result={'status':'ok','message':None,'temperature':temperature,'code':code,'observedAt':data.get('time'),'updatedAt':time.time(),'source':'Open-Meteo'}
        except Exception:result={'status':'error','message':'날씨 조회 실패 · 잠시 후 다시 갱신합니다.'}
        with self.lock:
            if generation==self.weather_generation:
                self.weather={**self.weather,**result}
    def poll_hooks(self):
        for path in sorted((self.path/'claude-events').glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:100]:
            try:
                if path.stat().st_size>10000:continue
                data=json.loads(path.read_text());ident=data['session'];seq=data['sequence']
                if not isinstance(ident,str) or len(ident)>120 or type(seq) is not int:continue
                if seq<=self.hook_sequences.get(ident,0):continue
                self.hook_sequences[ident]=seq
                if time.time()-data['updatedAt']>30:continue
                session='claude:'+ident
                if data.get('state') in {'working','idle','completed','input-required','ended'}:
                    self.sessions.event(session,'claude',seq,data['state'],label='Claude · '+ident[-8:],source='Claude hooks / statusLine',eventAt=data.get('stateChangedAt'),stateTimeSource='hook-received',lastCompletedAt=data.get('lastCompletedAt'),completionPreview=data.get('completionPreview'),baseline=True,process=data.get('process'),question=data.get('question'),proofPath=str(self.path/'claude-processes'/(str((data.get('process') or {}).get('pid'))+'.json')),replySupported=bool(data.get('process')))
                if data.get('heartbeat'):self.sessions.heartbeat(session)
                if data.get('usageObserved'):self.accept_claude_usage(data,'Claude statusLine rate_limits')
            except (OSError,ValueError,KeyError,TypeError):continue
        self.poll_usage()
    def accept_claude_usage(self,data,source):
        at=data.get('usageAt')
        if type(at) not in (int,float) or not math.isfinite(at) or at<=0 or at>time.time()+60:return
        windows=[v for v in [window_usage(data.get('five_hour'),'used_percentage',300),window_usage(data.get('seven_day'),'used_percentage',10080)] if v]
        with self.lock:
            if at<(self.usage['claude'].get('updatedAt') or 0):return
            self.usage['claude']={'status':'ok' if windows else 'no_limits','windows':windows,'source':source,'updatedAt':at,'message':None if windows else 'statusLine 수신 · 한도 필드 미제공 (계정/첫 응답/공급원 조건 확인)'}
    def poll_usage(self):
        for path in sorted((self.path/'claude-usage').glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:100]:
            try:
                if path.stat().st_size>4096:continue
                data=json.loads(path.read_text())
                if data.get('usageObserved') is True:self.accept_claude_usage(data,'Claude statusLine · '+str(data.get('projectLabel') or '연결 프로젝트')[:80]+' · 최근 수신 세션')
            except (OSError,ValueError,TypeError):continue
    def snapshot(self):
        with self.lock:
            usage=json.loads(json.dumps(self.usage));weather={**self.weather,'location':self.location}
        for value in [*usage.values(),weather]:
            value['stale']=bool(value.get('updatedAt') and time.time()-value['updatedAt']>900)
        return {'usage':usage,'weather':weather}
    def run_rollouts(self,stop):
        # Slow filesystem/lsof inspection must not delay hook ingestion, TTLs or notifications.
        while not stop.is_set():
            try:self.rollouts.poll()
            except (OSError,ValueError):pass
            stop.wait(10)

    def run(self,stop,state):
        threading.Thread(target=self.run_rollouts,args=(stop,),daemon=True).start()
        threading.Thread(target=OrcaActivity(self.sessions).run,args=(stop,),daemon=True).start()
        next_usage=next_weather=0
        while not stop.is_set():
            try:self.poll_hooks()
            except (OSError,ValueError):pass
            self.sessions.snapshot()
            for _transition in self.sessions.drain_notifications():
                if state.preferences.get('macSound'):
                    # Consume even when disabled/failing; never replay a previous transition.
                    try:subprocess.Popen(['/usr/bin/afplay','/System/Library/Sounds/Glass.aiff'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                    except OSError:pass
            now=time.monotonic()
            if now>=next_usage:
                next_usage=now+300
                threading.Thread(target=self.update_usage,daemon=True).start()
            if now>=next_weather:
                next_weather=now+600
                threading.Thread(target=self.fetch_weather,daemon=True).start()
            stop.wait(2)
    def update_usage(self):
        try:result=codex_usage()
        except Exception:result={'status':'error','message':'Codex 사용량 조회 실패 · CLI 로그인/연결을 확인하세요.'}
        with self.lock:self.usage['codex']={**self.usage['codex'],**result}
