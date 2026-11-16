#!/usr/bin/env python3
"""Append project-local official hooks; preserve all existing settings and statusLine."""
import argparse
import json
import os
from pathlib import Path
import shlex
import sys
ROOT=Path(__file__).resolve().parent.parent

def install(root=ROOT):
    settings=root/'.claude/settings.local.json';settings.parent.mkdir(exist_ok=True)
    value=json.loads(settings.read_text()) if settings.exists() else {}
    data=root/'.deck-data';data.mkdir(exist_ok=True,mode=0o700)
    backup=data/'claude-settings-before-bridge.json'
    if not backup.exists():backup.write_text(json.dumps(value,indent=2));os.chmod(backup,0o600)
    command=shlex.join([sys.executable,str(ROOT/'scripts/claude_bridge.py')])
    hook=command+' hook --data-dir '+shlex.quote(str(data))
    for name in ['SessionStart','UserPromptSubmit','PreToolUse','PermissionRequest','PostToolUse','PostToolUseFailure','Stop','SessionEnd']:
        entries=value.setdefault('hooks',{}).setdefault(name,[])
        if not any(h.get('command')==hook for entry in entries for h in entry.get('hooks',[])):
            entries.append({'matcher':'','hooks':[{'type':'command','command':hook,'timeout':5}]})
    status=command+' statusline --data-dir '+shlex.quote(str(data))
    if value.get('statusLine',{}).get('command')!=status:
        previous=value.get('statusLine')
        if previous is None:
            for inherited in [root/'.claude/settings.json',Path.home()/'.claude/settings.json']:
                try:previous=json.loads(inherited.read_text()).get('statusLine')
                except (OSError,ValueError):previous=None
                if previous is not None:break
            previous=previous or {}
        saved=data/'claude-statusline-previous.json';saved.write_text(json.dumps(previous));os.chmod(saved,0o600)
        value['statusLine']={**(previous or {}),'type':'command','command':status,'refreshInterval':5}
    tmp=settings.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2));os.chmod(tmp,0o600);tmp.replace(settings)
    print('Project-local Claude hook/statusLine connection installed; existing settings preserved. Backup in .deck-data.')
if __name__=='__main__':install()
