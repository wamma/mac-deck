#!/usr/bin/env python3
"""Claude official hook/statusLine adapter; never persist raw stdin."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent.parent

def process_identity():
    pid=os.getppid()
    for _ in range(12):
        try:
            info=subprocess.run(['/bin/ps','-p',str(pid),'-o','ppid=,comm='],capture_output=True,text=True,timeout=1).stdout.strip().split(maxsplit=1)
            if len(info)!=2:return None
            if Path(info[1]).name=='claude':
                fingerprint=subprocess.run(['/bin/ps','-p',str(pid),'-o','lstart=,tty=,comm='],capture_output=True,text=True,timeout=1).stdout.strip()
                tty=subprocess.run(['/bin/ps','-p',str(pid),'-o','tty='],capture_output=True,text=True,timeout=1).stdout.strip()
                if tty.startswith('ttys'):return {'pid':pid,'fingerprint':fingerprint,'tty':'/dev/'+tty}
                return None
            pid=int(info[0])
            if pid<=1:return None
        except (OSError,ValueError,subprocess.TimeoutExpired):return None


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['hook','statusline']);parser.add_argument('--data-dir',type=Path,default=ROOT/'.deck-data');args=parser.parse_args()
    raw=sys.stdin.buffer.read(2_000_001)
    if len(raw)>2_000_000:return
    try:data=json.loads(raw)
    except ValueError:return
    ident=data.get('session_id')
    if not isinstance(ident,str) or len(ident)>120:return
    directory=args.data_dir/'claude-events';directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    key=hashlib.sha256(ident.encode()).hexdigest();path=directory/(key+'.json')
    with (directory/(key+'.lock')).open('a') as lock:
        os.chmod(lock.name,0o600);fcntl.flock(lock,fcntl.LOCK_EX)
        try:previous=json.loads(path.read_text())
        except (OSError,ValueError):previous={}
        value={**previous,'session':ident,'sequence':max(time.time_ns(),previous.get('sequence',0)+1),'updatedAt':time.time()}
        identity=process_identity()
        if identity:value['process']=identity
        if args.mode=='hook':
            event=data.get('hook_event_name');state={'SessionStart':'idle','UserPromptSubmit':'working','PreToolUse':'working','PermissionRequest':'input-required','PostToolUse':'working','PostToolUseFailure':'working','Stop':'completed','SessionEnd':'ended'}.get(event)
            if not state:return
            if previous.get('state')!=state:value['stateChangedAt']=value['updatedAt']
            if event=='Stop':
                value['lastCompletedAt']=value['updatedAt']
                preview=data.get('last_assistant_message')
                value['completionPreview']=' '.join(preview.split())[:240] if isinstance(preview,str) else None
            value.update(state=state,heartbeat=state!='ended')
            value['question']=str(value['sequence']) if state=='input-required' else None
        else:
            value.update(heartbeat=True,usageObserved=True,usageAt=time.time())
            rates=data.get('rate_limits') or {}
            for name in ['five_hour','seven_day']:
                source=rates.get(name) or {};value[name]={k:source[k] for k in ['used_percentage','resets_at'] if type(source.get(k)) in (int,float)}
        if identity:
            processes=args.data_dir/'claude-processes';processes.mkdir(exist_ok=True,mode=0o700)
            proof=processes/(str(identity['pid'])+'.json');proof_tmp=proof.with_suffix('.'+key+'.tmp')
            proof_tmp.write_text(json.dumps({k:value.get(k) for k in ['session','state','question','updatedAt']}));os.chmod(proof_tmp,0o600);proof_tmp.replace(proof)
        temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value));os.chmod(temp,0o600);temp.replace(path)
    if args.mode=='statusline':
        # Preserve the user's existing display command verbatim; its output only goes back to Claude.
        try:existing=json.loads((args.data_dir/'claude-statusline-previous.json').read_text())
        except (OSError,ValueError):existing={}
        if existing.get('command'):
            try:subprocess.run(existing['command'],shell=True,input=raw,timeout=4,stderr=subprocess.DEVNULL)
            except (OSError,subprocess.TimeoutExpired):pass
        else:print('Claude · Mac Deck 상태 연결')

if __name__=='__main__':main()
