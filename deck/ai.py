"""Bounded, revisioned AI state. Only bounded task titles and final-response excerpts; no conversations."""
import copy
import json
import math
import os
import secrets
import threading
import time
from pathlib import Path

STATES={'working','idle','completed','input-required','ended'}

class Sessions:
    def __init__(self,path=None,clock=time.monotonic):
        self.clock=clock;self.lock=threading.RLock();self.sources={};self.slots=[None]*12
        self.mappings={};self.proofs={};self.notifications=[];self.epoch=secrets.token_hex(12)
        self.path=Path(path) if path else None
        self.tasks={};self.catalog={};self.discoveryInfo={}
        self.activity_rows=[];self.activity_seen=None;self.activity_error=False;self.activity_truncated=False
        self.task_path=self.path.with_name("ai-tasks.json") if self.path else None
        if self.task_path and self.task_path.exists():
            try:self.tasks=json.loads(self.task_path.read_text())
            except (OSError,ValueError):pass
        if self.path and self.path.exists():
            try:
                saved=json.loads(self.path.read_text())
                if len(saved)==12 and all(x is None or isinstance(x,str) and len(x)<180 for x in saved): self.slots=saved
            except (OSError,ValueError,TypeError):pass
    def set_activity(self,rows,truncated=False):
        with self.lock:
            self.activity_rows=copy.deepcopy(rows);self.activity_seen=self.clock();self.activity_error=False;self.activity_truncated=truncated
    def activity_failed(self):
        with self.lock:self.activity_error=True
    def activity_snapshot(self):
        age=None if self.activity_seen is None else self.clock()-self.activity_seen
        expired=age is None or age>30
        return {'rows':[] if expired else copy.deepcopy(self.activity_rows[:12]),'status':'no_signal' if expired else 'degraded' if self.activity_error else 'ok','age':age,'total':0 if expired else len(self.activity_rows),'truncated':self.activity_truncated,'source':'Orca CLI agent metadata','scope':'Orca가 보고한 주 agent 활동 · 창/논리 세션 연결 미확인'}
    def discover(self,records,**info):
        # Metadata discovery never refreshes a lifecycle lease or manufactures a state.
        with self.lock:
            self.catalog={r['id']:{'title':' '.join(str(r.get('title') or '').split())[:80],'cwd':str(r.get('cwd') or '')[:1024],'updatedAt':r.get('updatedAt')} for r in records if isinstance(r.get('id'),str) and len(r['id'])<=180}
            self.discoveryInfo=info
    def _source_row(self,ident):
        item=self.sources.get(ident);meta=self.catalog.get(ident,{})
        row={'id':ident,'provider':item['provider'] if item else 'codex','label':item['label'] if item else 'Codex · '+ident[-8:],'source':item['source'] if item else '로컬 세션 인덱스','state':self._tick(item) if item else 'offline',**self._task(ident)}
        row.pop('lastCompleted',None)
        row.update(cwd=meta.get('cwd',''),project=Path(meta.get('cwd') or '').name or '프로젝트 미제공',updatedAt=meta.get('updatedAt'),registeredSlot=self.slots.index(ident) if ident in self.slots else None,stateObserved=item is not None)
        return row
    def event(self,ident,provider,sequence,state,**metadata):
        if not isinstance(ident,str) or len(ident)>180 or provider not in {'codex','claude','test'} or type(sequence) is not int or state not in STATES: return False
        with self.lock:
            old=self.sources.get(ident)
            initial=old is None
            if old and sequence<=old['sequence']:return False
            if not old and len(self.sources)>=100:
                removable=[i for i in self.sources.values() if i['id'] not in self.slots and (i['state']=='ended' or self.clock()-i['seen']>30)]
                if not removable:return False
                removed=min(removable,key=lambda i:i['seen'])['id'];self.sources.pop(removed);self.tasks.pop(removed,None)
            now=self.clock();old=old or {'revision':0,'state':None,'pending':None,'transition':None}
            changed=old['state']!=state or (state=='input-required' and old.get('question')!=metadata.get('question'))
            item={**old,'id':ident,'provider':provider,'sequence':sequence,'state':state,'seen':now,
                  'revision':old['revision']+int(changed),'label':str(metadata.get('label',provider))[:80],
                  'source':str(metadata.get('source',''))[:120], 'replySupported':bool(metadata.get('replySupported',False)), 'process':metadata.get('process'),'question':metadata.get('question'),'proofPath':metadata.get('proofPath')}
            if changed:
                item['pending']=now if state=='input-required' else None
                item['transition']=None
                item['notify']=not (initial and metadata.get('baseline',False))
                self.proofs={k:v for k,v in self.proofs.items() if v['session']!=ident}
            self.sources[ident]=item
            self._task_event(ident,state,changed,metadata)
            self._tick(item)
            return True
    def _save_tasks(self):
        if not self.task_path:return
        self.task_path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        saved={i:self.tasks[i] for i in self.slots if i in self.tasks}
        tmp=self.task_path.with_suffix('.tmp');tmp.write_text(json.dumps(saved));os.chmod(tmp,0o600);tmp.replace(self.task_path)
    def _task_event(self,ident,state,changed,metadata):
        task=self.tasks.setdefault(ident,{})
        before=copy.deepcopy(task)
        title=metadata.get('providerTitle')
        if isinstance(title,str) and title.strip():task['providerTitle']=' '.join(title.split())[:80]
        at=metadata.get('eventAt')
        valid=lambda v:type(v) in (int,float) and math.isfinite(v) and v>0
        if valid(at) and (changed or not task.get('stateChangedAt')) and at>=task.get('stateChangedAt',0):
            task.update(stateChangedAt=at,stateTimeSource=metadata.get('stateTimeSource','provider-event'))
        completed=metadata.get('lastCompletedAt',at if state=='completed' else None)
        if valid(completed) and completed>=(task.get('lastCompleted') or {}).get('at',0):
            preview=metadata.get('completionPreview')
            task['lastCompleted']={'at':completed,'title':task.get('alias') or task.get('providerTitle'),'preview':' '.join(preview.split())[:240] if isinstance(preview,str) else None,'timeSource':metadata.get('stateTimeSource','provider-event')}
        if task!=before and ident in self.slots:self._save_tasks()
    def set_alias(self,slot,ident,alias):
        with self.lock:
            if type(slot) is not int or not 0<=slot<12 or not ident or self.slots[slot]!=ident:raise ValueError('세션이 바뀌었습니다. 다시 확인하세요.')
            if not isinstance(alias,str) or len(alias)>80:raise ValueError('작업 이름은 80자 이내입니다.')
            self.tasks.setdefault(ident,{})['alias']=' '.join(alias.split());self._save_tasks()
    def _task(self,ident):
        task=self.tasks.get(ident,{})
        meta=self.catalog.get(ident,{})
        fallback=(Path(meta.get('cwd') or '').name or '프로젝트 미제공')+' · Codex · '+str(ident)[-8:] if meta else '이름 없는 작업'
        return {'taskName':task.get('alias') or meta.get('title') or task.get('providerTitle') or fallback,'alias':task.get('alias',''),'stateChangedAt':task.get('stateChangedAt'),'stateTimeSource':task.get('stateTimeSource'),'lastCompleted':copy.deepcopy(task.get('lastCompleted'))}
    def heartbeat(self,ident):
        with self.lock:
            if ident in self.sources and self.sources[ident]['state']!='ended':self.sources[ident]['seen']=self.clock()
    def _tick(self,item):
        now=self.clock()
        if now-item['seen']>30 or item['state']=='ended':
            item['pending']=None;item['transition']=None
            return 'offline'
        if item['state']=='input-required':
            if item['pending'] is None:return 'offline' # expired wait never revives silently
            if item['provider']=='codex' and now-item['pending']<20:return 'working'
            if item['transition'] is None:
                item['transition']=self.epoch+':'+secrets.token_hex(12)
                item['revision']+=1
                if item.get('notify',True) and item['id'] in self.slots:self.notifications.append(item['transition'])
            return 'input-required'
        return item['state']
    def register(self,slot,ident):
        if type(slot) is not int or not 0<=slot<12:raise ValueError('슬롯은 1~12입니다.')
        with self.lock:
            if ident is not None and ident not in self.sources and ident not in self.catalog:raise ValueError('실제 관찰된 세션을 선택하세요.')
            if ident is not None and ident in self.slots and self.slots[slot]!=ident:raise ValueError('이미 등록한 세션입니다.')
            self.slots[slot]=ident;self._save_tasks();self.mappings.pop(slot,None);self.proofs.pop(slot,None)
            if self.path:
                self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(self.slots));os.chmod(tmp,0o600);tmp.replace(self.path)
    def source(self,slot):
        if type(slot) is not int or not 0<=slot<12:raise ValueError('잘못된 슬롯입니다.')
        with self.lock:return copy.deepcopy(self.sources.get(self.slots[slot],{}))
    def bind(self,slot,mapping):
        # Called only by a source adapter that proves logical-session -> native-window mapping.
        with self.lock:
            self.mappings[slot]=copy.deepcopy(mapping);self.proofs.pop(slot,None)
            self.sources[self.slots[slot]]['revision']+=1
    def _slot(self,n):
        ident=self.slots[n];item=self.sources.get(ident)
        if not item:return {**self._task(ident),'slot':n,'id':ident,'state':'offline' if ident else 'unregistered','revision':0,'transition':None}
        state=self._tick(item)
        return {**self._task(ident),'slot':n,**{k:item[k] for k in ['id','provider','label','revision','source','transition','replySupported']},'state':state,'age':round(self.clock()-item['seen'],1),'mapped':n in self.mappings}
    def snapshot(self):
        with self.lock:
            slots=[self._slot(n) for n in range(12)]
            sources=[self._source_row(ident) for ident in self.catalog.keys()|self.sources.keys()]
            sources.sort(key=lambda r:(r['state']=='offline',-(r.get('updatedAt') or r.get('stateChangedAt') or 0),r['id']))
            return {'epoch':self.epoch,'slots':slots,'sources':sources,'discovery':self.discoveryInfo,'activity':self.activity_snapshot()}
    def drain_notifications(self):
        with self.lock:
            result=self.notifications[:];self.notifications.clear();return result
    def detail(self,slot):
        if type(slot) is not int or not 0<=slot<12:raise ValueError('잘못된 슬롯입니다.')
        with self.lock:
            row=self._slot(slot);mapping=self.mappings.get(slot)
            if not mapping:raise ValueError('이 세션과 실제 창의 연결을 증명할 수 없습니다. 다른 창을 대신 표시하지 않습니다.')
            if row['state'] in {'offline','unregistered'}:raise ValueError('세션 신호가 만료되었습니다.')
            nonce=secrets.token_urlsafe(24)
            self.proofs[slot]={'session':row['id'],'revision':row['revision'],'nonce':nonce,'expires':self.clock()+10}
            return {**row,'mapping':copy.deepcopy(mapping),'nonce':nonce}
    def consume_reply(self,slot,revision,key,nonce=None):
        if type(slot) is not int or not 0<=slot<12 or key not in {'up','down','enter'}:raise ValueError('Up / Down / Enter만 허용됩니다.')
        with self.lock:
            row=self._slot(slot);proof=self.proofs.get(slot)
            if not row.get('replySupported') or row['state']!='input-required' or row['revision']!=revision or not proof or proof['revision']!=revision or proof['session']!=row['id'] or proof['nonce']!=nonce or self.clock()>=proof['expires']:
                raise ValueError('질문·세션이 바뀌었거나 화면 확인이 만료되었습니다. 다시 확인하세요.')
            self.proofs.pop(slot)
            return copy.deepcopy(self.mappings[slot])
