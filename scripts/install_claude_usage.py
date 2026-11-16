#!/usr/bin/env python3
"""Preview by default; explicitly install/restore only a project-local statusLine wrapper."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent


def settings_root(project):
    project=Path(project).resolve()
    if not project.is_dir():raise ValueError('프로젝트 폴더가 없습니다.')
    result=subprocess.run(['git','-C',str(project),'worktree','list','--porcelain'],capture_output=True,text=True,timeout=3)
    worktrees=[Path(line[9:]).resolve() for line in result.stdout.splitlines() if line.startswith('worktree ')] if result.returncode==0 else []
    if not worktrees:return project,[project]
    root=worktrees[0]
    if os.name=='nt' or root==Path.home().resolve() or any(p.exists() and p.stat().st_uid!=os.getuid() for p in [root,root/'.git',root/'.claude']):return project,[project]
    return root,worktrees


def load(path):
    if not path.exists():return {}
    value=json.loads(path.read_text())
    if not isinstance(value,dict):raise ValueError('설정이 JSON object가 아닙니다.')
    return value


def atomic(path,value):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2));os.chmod(tmp,0o600);tmp.replace(path)


def effective_status(project,root,value,home):
    if 'statusLine' in value:return value['statusLine']
    paths=([project/'.claude/settings.local.json'] if project!=root else [])+[project/'.claude/settings.json',home]
    for path in paths:
        status=load(path).get('statusLine')
        if status is not None:return status
    return {}


def prepare(project,data_dir,home_settings=None):
    root,worktrees=settings_root(project)
    if Path(project).resolve() not in {Path(tree).resolve() for tree in worktrees}:raise ValueError('프로젝트/worktree 루트 경로를 지정하세요. 하위 폴더는 설치 대상으로 추측하지 않습니다.')
    path=root/'.claude/settings.local.json';value=load(path)
    key=hashlib.sha256(str(root).encode()).hexdigest();manifest=Path(data_dir).resolve()/'claude-usage-installations'/(key+'.json')
    home=Path(home_settings or Path(os.environ.get('CLAUDE_CONFIG_DIR',str(Path.home()/'.claude')))/'settings.json').resolve()
    original=value.get('statusLine');effective=effective_status(Path(project).resolve(),root,value,home)
    if effective is not None and not isinstance(effective,dict):raise ValueError('기존 statusLine 형식을 확인하세요.')
    command=shlex.join([sys.executable,str(ROOT/'scripts/claude_usage_bridge.py'),'--manifest',str(manifest),'--data-dir',str(Path(data_dir).resolve())])
    installed={**(effective or {}),'type':'command','command':command}
    # Keep the user's existing interval; add a gentle idle refresh only when absent.
    installed.setdefault('refreshInterval',30)
    record={'projectKey':key,'projectRoot':str(root),'allowedProjectRoots':[str(tree) for tree in worktrees],'settingsPath':str(path),'homeSettings':str(home),'homeSettingsExplicit':home_settings is not None,'settingsExisted':path.exists(),'hadLocalStatusLine':'statusLine' in value,'previousLocalStatusLine':original,'installedStatusLine':installed}
    return path,value,manifest,record,worktrees


def install(project,data_dir,apply=False,allow_shared_root=False,home_settings=None):
    path,value,manifest,record,worktrees=prepare(project,data_dir,home_settings)
    saved=load(manifest)
    if saved and value.get('statusLine')==saved.get('installedStatusLine'):
        return {'changed':False,'alreadyInstalled':True,'settingsPath':str(path),'sharedWorktreeCount':len(worktrees)}
    if not saved and 'claude_usage_bridge.py' in str(value.get('statusLine',{})):raise ValueError('다른 사용량 wrapper 설치가 있습니다. 중첩하지 않습니다.')
    if saved:raise ValueError('이전 설치 기록과 현재 설정이 다릅니다. 덮어쓰지 않습니다.')
    report={'changed':False,'preview':not apply,'settingsPath':str(path),'projectRoot':record['projectRoot'],'sharedWorktreeCount':len(worktrees),'delegate':'previous local statusLine' if record['hadLocalStatusLine'] else 'inherited project/user statusLine at invocation','preservedOptionKeys':sorted(k for k in record['installedStatusLine'] if k not in {'type','command'}),'refreshInterval':record['installedStatusLine'].get('refreshInterval'),'writes':['project-local statusLine only','central private delegate manifest'],'lifecycleHooksAdded':False}
    variants=set()
    for tree in worktrees:
        status=effective_status(tree,Path(record['projectRoot']),value,Path(record['homeSettings'])) or {}
        if not isinstance(status,dict):raise ValueError('공유 프로젝트 statusLine 형식이 다릅니다.')
        variants.add(json.dumps({k:v for k,v in status.items() if k not in {'command','type'}},sort_keys=True))
    report['sharedOptionVariants']=len(variants)
    if not apply:return report
    if len(variants)>1:raise ValueError('worktree별 표시 옵션이 달라 공유 루트 적용을 보류합니다.')
    if len(worktrees)>1 and not allow_shared_root:raise ValueError('공유 worktree 설정 루트입니다. 영향 범위 검수 후 --allow-shared-root가 필요합니다.')
    if load(path)!=value:raise ValueError('준비 중 설정이 바뀌었습니다. 다시 확인하세요.')
    atomic(manifest,record)
    try:atomic(path,{**value,'statusLine':record['installedStatusLine']})
    except OSError:manifest.unlink();raise
    report['changed']=True;return report


def restore(project,data_dir,apply=False):
    root,worktrees=settings_root(project);key=hashlib.sha256(str(root).encode()).hexdigest();manifest=Path(data_dir).resolve()/'claude-usage-installations'/(key+'.json');saved=load(manifest)
    if not saved:raise ValueError('이 프로젝트의 설치 기록이 없습니다.')
    path=root/'.claude/settings.local.json';value=load(path)
    if value.get('statusLine')!=saved['installedStatusLine']:raise ValueError('설치 후 statusLine이 바뀌었습니다. 사용자 변경을 덮어쓰지 않습니다.')
    if not apply:return {'preview':True,'settingsPath':str(path),'changed':False,'preservesOtherSettings':True}
    observed=json.loads(json.dumps(value))
    if saved['hadLocalStatusLine']:value['statusLine']=saved['previousLocalStatusLine']
    else:value.pop('statusLine',None)
    if load(path)!=observed:raise ValueError('복원 준비 중 설정이 바뀌었습니다.')
    if not value and not saved.get('settingsExisted',True):path.unlink()
    else:atomic(path,value)
    manifest.unlink();return {'changed':True,'settingsPath':str(path),'preservesOtherSettings':True}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--project',type=Path,required=True);parser.add_argument('--data-dir',type=Path,default=ROOT/'.deck-data');parser.add_argument('--apply',action='store_true');parser.add_argument('--restore',action='store_true');parser.add_argument('--allow-shared-root',action='store_true');args=parser.parse_args()
    try:result=restore(args.project,args.data_dir,args.apply) if args.restore else install(args.project,args.data_dir,args.apply,args.allow_shared_root)
    except (ValueError,OSError,subprocess.TimeoutExpired):parser.exit(1,'설정 검증 실패: 기존 설정을 덮어쓰지 말고 설치기록/JSON/공유루트 범위를 확인하세요.\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
