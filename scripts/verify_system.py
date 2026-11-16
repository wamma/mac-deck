"""Small real system adjustments with readback and restoration; no input/trash."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deck.macos import Mac
mac=Mac('.deck-data');before=mac.system_status();report={'before':before,'checks':[]}
try:
    for kind,identity in [('volume','deviceId'),('brightness','displayId')]:
        info=before[kind]
        if not info.get('supported'):
            report['checks'].append({'kind':kind,'result':'unsupported; no write attempted'});continue
        current=mac.system_status()[kind]
        if current.get(identity)!=info[identity]:raise RuntimeError('Device changed; abort')
        value=info['value']+1 if info['value']<100 else info['value']-1
        result=mac.system_control({'action':kind+'_set','value':value},expected_id=info[identity])
        report['checks'].append({'kind':kind,'requested':value,'result':result})
        mac.system_control({'action':kind+'_set','value':info['value']},expected_id=info[identity])
    if before['volume'].get('muteSupported'):
        result=mac.system_control({'action':'mute_toggle'},expected_id=before['volume']['deviceId']);report['checks'].append({'kind':'mute','result':result})
finally:
    for kind,identity in [('volume','deviceId'),('brightness','displayId')]:
        current=mac.system_status()[kind];original=before[kind]
        if current.get(identity)!=original.get(identity):
            report['checks'].append({'kind':kind,'restore':'device changed; original device needs manual check'});continue
        if original.get('supported') and current.get('value')!=original['value']:
            mac.system_control({'action':kind+'_set','value':original['value']},expected_id=original[identity])
        if kind=='volume' and original.get('muteSupported') and current.get('muted')!=original['muted']:
            mac.system_control({'action':'mute_toggle'},expected_id=original[identity])
    report['after']=mac.system_status()
    report['restored']=report['after']==before
    print(json.dumps(report,ensure_ascii=False,indent=2))
