#!/usr/bin/env python3
"""Usage-only statusLine tap. Preserve the delegate's stdin/stdout; never store raw input."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def read_settings(path):
    try:
        value=json.loads(Path(path).read_text())
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):return {}


def invocation_root(manifest,data):
    """Accept an exact installed project root, never search cwd ancestors for commands."""
    root=Path(manifest['projectRoot']).resolve()
    allowed={Path(p).resolve() for p in manifest.get('allowedProjectRoots',[str(root)])}
    workspace=data.get('workspace') if isinstance(data.get('workspace'),dict) else {}
    declared=workspace.get('project_dir')
    current=[p for p in [workspace.get('current_dir'),data.get('cwd')] if p is not None]
    if declared is None:
        # Legacy input can identify a root exactly, but a subfolder is ambiguous.
        declared=current[0] if current else str(root)
    if not isinstance(declared,str) or not Path(declared).is_absolute():return None
    project=Path(declared).resolve()
    if project not in allowed:return None
    for value in current:
        if not isinstance(value,str) or not Path(value).is_absolute():return None
        resolved=Path(value).resolve()
        if not resolved.is_relative_to(project):return None
        # A nested registered worktree is a different project, not a subdirectory.
        if any(other!=project and resolved.is_relative_to(other) and other.is_relative_to(project) for other in allowed):return None
    return project


def delegate_status(manifest,data):
    directory=invocation_root(manifest,data)
    if directory is None:return {}
    # Main-checkout local settings override worktree project/user settings.
    if manifest['hadLocalStatusLine']:return manifest['previousLocalStatusLine'] or {}
    candidates=[]
    if directory!=Path(manifest['projectRoot']).resolve():candidates.append(directory/'.claude/settings.local.json')
    home=Path(manifest['homeSettings'])
    if not manifest.get('homeSettingsExplicit') and os.environ.get('CLAUDE_CONFIG_DIR'):home=Path(os.environ['CLAUDE_CONFIG_DIR'])/'settings.json'
    candidates.extend([directory/'.claude/settings.json',home])
    for path in candidates:
        status=read_settings(path).get('statusLine')
        if isinstance(status,dict) and 'claude_usage_bridge.py' not in str(status.get('command','')):return status
    return {}


def collect(data,manifest,data_dir):
    ident=data.get('session_id')
    if not isinstance(ident,str) or not 1<=len(ident)<=180:return
    limits=data.get('rate_limits');limits=limits if isinstance(limits,dict) else {}
    windows={}
    for name in ['five_hour','seven_day']:
        value=limits.get(name);value=value if isinstance(value,dict) else {};pct=value.get('used_percentage');reset=value.get('resets_at')
        if type(pct) in (int,float) and math.isfinite(pct) and 0<=pct<=100:
            windows[name]={'used_percentage':pct}
            if type(reset) in (int,float) and math.isfinite(reset):windows[name]['resets_at']=reset
    directory=Path(data_dir)/'claude-usage';directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    key=manifest['projectKey']+'-'+hashlib.sha256(ident.encode()).hexdigest()
    value={'usageObserved':True,'usageAt':time.time(),'projectKey':manifest['projectKey'],'projectLabel':Path(manifest['projectRoot']).name[:80],**windows}
    path=directory/(key+'.json');tmp=directory/(key+'.'+str(os.getpid())+'.tmp');tmp.write_text(json.dumps(value));os.chmod(tmp,0o600);tmp.replace(path)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',type=Path,required=True);parser.add_argument('--data-dir',type=Path,required=True);args=parser.parse_args()
    manifest=read_settings(args.manifest);raw=sys.stdin.buffer.read(2_000_001);data={}
    if len(raw)<=2_000_000:
        try:
            parsed=json.loads(raw)
            if isinstance(parsed,dict):data=parsed
        except ValueError:pass
    try:collect(data,manifest,args.data_dir)
    except (OSError,ValueError,KeyError,TypeError):pass # collector failure must not replace the user's display
    status=delegate_status(manifest,data);command=status.get('command')
    if not isinstance(command,str) or not command:return 0
    # Only the pre-existing user's command is executed; no payload is interpolated as code.
    process=subprocess.Popen(command,shell=True,stdin=subprocess.PIPE)
    try:
        process.stdin.write(raw);shutil.copyfileobj(sys.stdin.buffer,process.stdin,65536);process.stdin.close()
    except BrokenPipeError:pass
    return process.wait()

if __name__=='__main__':sys.exit(main())
