"""Official Orca activity metadata only: no terminal text or project file access."""
import hashlib
import json
from pathlib import PurePath
import subprocess
import time


def activity_rows(payload,now):
    result=payload.get('result',{});runtime=payload.get('_meta',{}).get('runtimeId')
    if payload.get('ok') is not True or not isinstance(runtime,str):raise ValueError('Orca metadata unavailable')
    rows=[]
    for workspace in result.get('worktrees',[]):
        instance=workspace.get('worktreeInstanceId');wid=workspace.get('worktreeId')
        if not instance or not wid or workspace.get('isArchived') or not workspace.get('hasAttachedPty'):continue
        for agent in workspace.get('agents',[]):
            pane=agent.get('paneKey');main=agent.get('mainAgent') or {};state=main.get('state',agent.get('state'))
            # A monitoring parent whose actual main agent is done is not active work.
            if not pane or state not in {'working','waiting'}:continue
            updated=agent.get('updatedAt');started=main.get('stateStartedAt',agent.get('stateStartedAt'))
            if type(updated) not in (int,float) or not 0<updated/1000<=now+60:continue
            provider=agent.get('agentType') if agent.get('agentType') in {'claude','codex'} else 'unknown'
            waiting=state=='waiting';started=started/1000 if type(started) in (int,float) else None
            # Codex waiting does not turn red before a continuous 20-second wait.
            visible='input-required' if waiting and (provider!='codex' or started and now-started>=20) else 'working'
            ident='orca:'+hashlib.sha256(json.dumps([runtime,wid,instance,pane],separators=(',',':')).encode()).hexdigest()
            title=agent.get('taskTitle') or agent.get('displayName') or workspace.get('displayName') or PurePath(workspace.get('path') or '').name or '이름 없는 Orca 작업'
            project=workspace.get('repo') or PurePath(workspace.get('path') or '').name or '프로젝트 미제공'
            rows.append({'id':ident,'taskName':' '.join(str(title).split())[:80],'project':str(project)[:80],'provider':provider,'state':visible,'lastActivityAt':updated/1000,'stateChangedAt':started,'source':'Orca agent activity metadata','timeSource':'agent.updatedAt','readOnly':True,'waiting':waiting})
    unique={row['id']:row for row in rows}
    return sorted(unique.values(),key=lambda r:(-r['lastActivityAt'],r['id'])),bool(result.get('truncated'))


class OrcaActivity:
    def __init__(self,sessions,clock=time.time):self.sessions=sessions;self.clock=clock
    def poll(self):
        try:
            result=subprocess.run(['orca','worktree','ps','--json'],capture_output=True,text=True,timeout=4)
            if result.returncode:raise ValueError('Orca CLI failed')
            # Discard prompt/lastAssistantMessage/preview; never expose or persist raw CLI output.
            rows,truncated=activity_rows(json.loads(result.stdout),self.clock())
            self.sessions.set_activity(rows,truncated=truncated)
        except (OSError,ValueError,TypeError,subprocess.TimeoutExpired):
            self.sessions.activity_failed()
    def run(self,stop):
        while not stop.is_set():
            self.poll();stop.wait(5)
