"""Explicit real web/native check. Isolated config; fixed target only in this runner."""
import argparse, base64, hashlib, json, secrets, subprocess, sys, tempfile, threading, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deck.core import State
from deck.http import make_server
from deck.macos import Mac
from scripts.verify_native import TEST_TEXT, matches_document, wait_for_saved_text

class PinnedMac(Mac):
    def pin(self,expected,clipboard=None):
        if expected.get('pid',0)<=0 or expected.get('windowId',0)<=0:raise ValueError('Positive fixed PID and window ID required')
        self.fixed=dict(expected);self.calls=[];self.clipboard_guard=clipboard
    def type_text(self,text,enter,expected=None):
        self.calls.append('text')
        return super().type_text(text,enter,expected=dict(self.fixed))
    def shortcut(self,key,modifiers,expected=None):
        allowed={('s',('command',)):'save'}
        if self.clipboard_guard:allowed.update({('a',('command',)):'select',('c',('command',)):'copy',('right',()):'end-selection',('v',('command',)):'paste'})
        action=allowed.get((key,tuple(modifiers)))
        if not action:raise RuntimeError('Only explicit test keys are allowed')
        if action=='copy':self.clipboard_guard.command('arm')
        if self.clipboard_guard and action in {'paste','save'}:self.clipboard_guard.command('check')
        self.calls.append(action)
        result=super().shortcut(key,modifiers,expected=dict(self.fixed))
        if action=='paste':self.clipboard_guard.command('check')
        if action=='copy':
            time.sleep(.15)
            self.copy_proof=self.clipboard_guard.command('copied',TEST_TEXT+'\n')
        return result

def await_document_target(mac,path,pid,timeout=3,clock=time.monotonic,sleep=time.sleep):
    """Wait only for this dedicated document's CG ID; never send keys or adopt another document."""
    start=clock()
    while True:
        d=mac.diagnostics();expected={'pid':pid,'windowId':d.get('windowId',0),'documentURL':path.resolve().as_uri()}
        if not matches_document(d,expected,path):raise RuntimeError('Dedicated document identity changed during preparation')
        if expected['windowId']>0:return expected
        if clock()-start>=timeout:raise RuntimeError('Dedicated document CGWindowID not ready; no input sent')
        sleep(.1)

def command(*args):return subprocess.check_output(args,text=True).strip()
def clipboard_count():return int(command('/usr/bin/osascript','-l','JavaScript','-e','ObjC.import("AppKit"); $.NSPasteboard.generalPasteboard.changeCount'))
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('screenshot_folder',type=Path)
    parser.add_argument('--clipboard',action='store_true')
    parser.add_argument('--evidence',type=Path)
    args=parser.parse_args();clipboard_mode=args.clipboard
    phase='4-6' if clipboard_mode else '4-5'
    Path('artifacts').mkdir(exist_ok=True)
    evidence_path=args.evidence or Path(f'artifacts/phase{phase}-evidence.json')
    if args.evidence and evidence_path.exists():parser.error('Explicit evidence output already exists; refusing to overwrite')
    guardian=None;collector=None
    folder=args.screenshot_folder;folder.mkdir(parents=True,exist_ok=True)
    mac=PinnedMac('.deck-data');initial=mac.diagnostics()
    report={'result':'BLOCKED','initial':{k:initial.get(k) for k in ['pid','bundleId','accessibilityTrusted','focusedWindowReadable']},'scope':'Real UI/HTTP/actions/Mac/native with test-only fixed expected; isolated copied config, no mocked responses'}
    path=None;expected=None;server=None;before_clip=mac.read_clipboard();before_count=clipboard_count()
    production=Path('.deck-data/buttons.json');production_bytes=production.read_bytes()
    try:
        if clipboard_mode:
            from scripts.clipboard_guard import ClipboardGuard,CollectorPause
            guardian=ClipboardGuard();report['memorySnapshotComplete']=guardian.snapshot['snapshotComplete']
            collector=CollectorPause();collector.pause()
        if not initial.get('accessibilityTrusted') or (not clipboard_mode and not initial.get('focusedWindowReadable')) or initial.get('bundleId') in {'com.apple.loginwindow','com.apple.ScreenSaver.Engine'}:raise RuntimeError('Initial safety gate failed (see diagnostic flags); no test document opened')
        directory=Path(tempfile.mkdtemp(prefix='mac-deck-native-'));path=directory/'Deck-Safe-Verification.txt';path.write_text(TEST_TEXT+'\n' if clipboard_mode else '')
        command('/usr/bin/open','-a','TextEdit',str(path))
        app=next(a for a in mac.apps if a['name']=='TextEdit');activation=mac.open_app(app['path'])
        expected=await_document_target(mac,path,activation['pid'])
        mac.pin(expected,guardian);report.update(expected=expected,testDocument=str(path))
        command('/usr/bin/open','-b',initial['bundleId'])
        config=directory/'buttons.json';config.write_bytes(production_bytes);state=State(config,mac.apps);before=state.snapshot()
        code=secrets.token_hex(6);server=make_server('127.0.0.1',0,state,mac,code)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        private=directory/'control.json';private.write_text(json.dumps({'root':f'http://127.0.0.1:{server.server_port}','code':code,'text':TEST_TEXT,'expected':expected,'config':str(config),'result':str(directory/'ui.json'),'clipboardMode':clipboard_mode}));private.chmod(0o600)
        try:
            run=subprocess.run(['node','scripts/verify_web_text.mjs',str(private)],capture_output=True,text=True,timeout=70)
            if (directory/'ui.json').exists():report['ui']=json.loads((directory/'ui.json').read_text())
            if run.returncode:raise RuntimeError('UI check failed: '+run.stderr[-1600:])
            wanted=(TEST_TEXT+'\n')*(2 if clipboard_mode else 1)
            expected_calls=['select','copy','end-selection','paste','save'] if clipboard_mode else ['text','save']
            saved,elapsed=wait_for_saved_text(path,wanted);report.update(savedBeforeClose=saved==wanted,saveObservedAfterSeconds=round(elapsed,3),savedSHA256=hashlib.sha256(saved.encode()).hexdigest(),expectedSHA256=hashlib.sha256(wanted.encode()).hexdigest(),inputCalls=mac.calls)
            if saved!=wanted or mac.calls!=expected_calls:raise RuntimeError('Saved text or one-shot counts differ')
            capture=mac.capture_registered(expected);png=folder/f'macOS_TextEdit_phase{phase}_saved_{time.time_ns()}.png';data=base64.b64decode(capture['image'].split(',')[1]);png.write_bytes(data)
            report['screenshot']={'path':str(png),'sha256':hashlib.sha256(data).hexdigest(),'width':int.from_bytes(data[16:20],'big'),'height':int.from_bytes(data[20:24],'big')};report['result']='PASS'
        finally:
            private.unlink(missing_ok=True)
            state.save_buttons(before['buttons']);report['copiedButtonsPreferencesRestored']=state.snapshot()['buttons']==before['buttons'] and state.preferences==before['preferences']
    except Exception as error:report['error']=str(error)
    finally:
        if server:server.shutdown();server.server_close()
        report['inputCalls']=getattr(mac,'calls',[])
        if guardian:
            try:
                report['copyProof']=getattr(mac,'copy_proof',None)
                report['clipboardRestoration']=guardian.command('restore')
            except Exception as error:report['clipboardRestoration']={'ok':False,'reason':str(error)};report['result']='BLOCKED'
            finally:guardian.close()
        if collector:
            try:report['collector']=collector.restore()
            except Exception:report['collector']={'enabledRestored':False,'existingHistoryUnchanged':False};report['result']='BLOCKED'
        report['clipboardTextUnchanged']=before_clip==mac.read_clipboard();report['clipboardChangeCountUnchanged']=before_count==clipboard_count()
        report['productionConfigBytesUnchanged']=production.read_bytes()==production_bytes
        if expected:
            try:report['closeTestDocument']=Mac.shortcut(mac,'w',['command'],expected=expected)
            except RuntimeError as error:report['closeError']=str(error)
        if initial.get('bundleId'):
            command('/usr/bin/open','-b',initial['bundleId']);restored=mac.diagnostics();report['foregroundRestored']=restored.get('pid')==initial.get('pid') and restored.get('bundleId')==initial.get('bundleId')
        checks=['productionConfigBytesUnchanged','foregroundRestored']+([] if clipboard_mode else ['clipboardTextUnchanged','clipboardChangeCountUnchanged'])
        if not all(report.get(k,False) for k in checks):report['result']='FAIL'
        if clipboard_mode and collector and not all(report['collector'][k] for k in ['enabledRestored','existingHistoryUnchanged']):report['result']='FAIL'
        evidence_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report.get(k) for k in ['result','error','savedBeforeClose','inputCalls','clipboardChangeCountUnchanged','foregroundRestored']},ensure_ascii=False))
    return 0 if report['result']=='PASS' else 1
if __name__=='__main__':sys.exit(main())
