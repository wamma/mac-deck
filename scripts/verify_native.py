"""Explicit safe-document native check; never operates the trash or user documents."""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit,unquote
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deck.macos import Mac

TEST_TEXT='MAC DECK safe test\n한글 줄바꿈 🙂\n"quoted" & $literal'

def matches_document(diagnostic,expected,path):
    document=urlsplit(diagnostic.get('documentURL',''))
    return (diagnostic.get('bundleId')=='com.apple.TextEdit' and diagnostic.get('focusedWindowReadable')
            and diagnostic.get('pid')==expected['pid'] and diagnostic.get('windowId')==expected['windowId']
            and document.scheme=='file' and document.netloc in {'','localhost'}
            and Path(unquote(document.path)).resolve()==path.resolve()
            and expected['documentURL']==path.resolve().as_uri())

def wait_for_saved_text(path,expected,timeout=5,clock=time.monotonic,sleep=time.sleep):
    start=clock()
    while True:
        saved=path.read_text().replace('\r\n','\n')
        elapsed=clock()-start
        if saved==expected or elapsed>=timeout:return saved,elapsed
        sleep(.1)

def verify_document(mac,path,expected):
    """An already-prepared, empty, uniquely named test document; never adopt a new foreground."""
    if not path.parent.name.startswith('mac-deck-native-') or path.name!='Deck-Safe-Verification.txt' or path.read_text()!='':
        raise ValueError('Only a new empty dedicated test document is allowed.')
    report={'textInput':'not attempted','shortcut':'not attempted','expected':expected,'testDocument':str(path)}
    diagnostic=mac.diagnostics()
    if not matches_document(diagnostic,expected,path):
        report['blocked']='Fixed PID/window/canonical document mismatch before input. No keys sent.';return report
    before=mac.read_clipboard()
    try:
        report['dispatch']=mac.type_text(TEST_TEXT,True,expected=expected);time.sleep(.5)
        if not matches_document(mac.diagnostics(),expected,path):
            report['blocked']='Fixed target changed before save. Save not sent.';return report
        report['saveDispatch']=mac.shortcut('s',['command'],expected=expected)
        saved,elapsed=wait_for_saved_text(path,TEST_TEXT+'\n');report['saveObservedAfterSeconds']=round(elapsed,3)
        report['savedBeforeClose']=saved==TEST_TEXT+'\n'
        report['savedSHA256']=hashlib.sha256(saved.encode()).hexdigest()
        report['expectedSHA256']=hashlib.sha256((TEST_TEXT+'\n').encode()).hexdigest()
        report['textInput']='PASS' if saved==TEST_TEXT+'\n' else 'FAIL: saved text differs'
        report['shortcut']='PASS' if report['textInput']=='PASS' else 'not verified'
    except RuntimeError as error:report['blocked']=str(error)
    finally:report['clipboardTextUnchanged']=mac.read_clipboard()==before
    return report

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepared',type=Path);args=parser.parse_args();mac=Mac('.deck-data')
    if args.prepared:
        prepared=json.loads(args.prepared.read_text());path=Path(prepared['testDocument']);expected=prepared['expected']
        report=verify_document(mac,path,expected)
    else:
        folder=Path(tempfile.mkdtemp(prefix='mac-deck-native-'));path=folder/'Deck-Safe-Verification.txt';path.write_text('')
        subprocess.run(['/usr/bin/open','-a','TextEdit',str(path)],check=True)
        app=next(a for a in mac.apps if a['name']=='TextEdit');activation=mac.open_app(app['path']);diagnostic=mac.diagnostics()
        expected={'pid':diagnostic['pid'],'windowId':diagnostic.get('windowId',0),'documentURL':path.resolve().as_uri()}
        report=verify_document(mac,path,expected);report['activation']=activation
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
