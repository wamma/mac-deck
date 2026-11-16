"""Dedicated Terminal trial: one Claude print session, zero messages, metadata only."""
import json,os,subprocess,sys,threading,time
from pathlib import Path
control=Path(sys.argv[1]);config=json.loads(control.read_text());directory=control.parent
os.chdir(config['cwd'])
print('\033[2J\033[H'+config['marker']+'\nDedicated Claude SessionStart capture trial. No prompts or approvals.',flush=True)
(directory/'ready.json').write_text(json.dumps({'pid':os.getpid(),'tty':os.ttyname(0)}))
while not (directory/'go').exists():
    if (directory/'stop').exists():sys.exit(0)
    time.sleep(.05)
args=[config['claude'],'--print','--input-format','stream-json','--output-format','stream-json','--verbose','--include-hook-events','--no-session-persistence','--session-id',config['id'],'--tools','','--permission-prompts','none','--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--setting-sources','project,local','--no-chrome']
child=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
(directory/'child.json').write_text(json.dumps({'pid':child.pid}))
events=[]
def observe():
    for line in child.stdout:
        try:data=json.loads(line)
        except ValueError:continue
        if data.get('type')=='system' and data.get('subtype') in {'hook_started','hook_response'}:
            event={k:data.get(k) for k in ['subtype','hook_event']};events.append(event)
            print('Official hook: '+str(event['hook_event'])+' / '+str(event['subtype']),flush=True)
reader=threading.Thread(target=observe,daemon=True);reader.start()
while child.poll() is None and not (directory/'stop').exists():time.sleep(.05)
child.stdin.close()
try:code=child.wait(timeout=10)
except subprocess.TimeoutExpired:
    child.terminate()
    try:code=child.wait(timeout=3)
    except subprocess.TimeoutExpired:child.kill();code=child.wait()
reader.join(timeout=1)
(directory/'ended.json').write_text(json.dumps({'exitCode':code,'hookEvents':events}))
print('Dedicated trial ended. No user messages sent.',flush=True)
