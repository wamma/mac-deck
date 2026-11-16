import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from deck.startup import invocation, replace_existing

ROOT=Path(__file__).resolve().parent.parent


@unittest.skipUnless(sys.platform=='darwin','macOS process inspection')
class StartupIntegration(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.processes=[];self.logs=[]
        (self.root/'sitecustomize.py').write_text('''
import os,signal
from deck import macos,core,sources
class TestMac:
    def __init__(self,*args):self.apps=[]
class TestProviders:
    def __init__(self,*args):pass
    def run(self,stop,state):stop.wait()
macos.Mac=TestMac
sources.Providers=TestProviders
core.clipboard_worker=lambda state,mac,stop:stop.wait()
core.metrics_worker=lambda state,mac,stop:stop.wait()
if os.environ.get('DECK_TEST_IGNORE_INT'):
    original=signal.signal
    def configure(sig,handler):return original(sig,signal.SIG_IGN if sig==signal.SIGINT else handler)
    signal.signal=configure
''')
        self.env={**os.environ,'PYTHONPATH':str(self.root)+os.pathsep+str(ROOT)}
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));self.port=sock.getsockname()[1]
    def tearDown(self):
        for process in self.processes:
            if process.poll() is None:process.terminate()
            process.wait(timeout=5)
        for log in self.logs:log.close()
        self.temp.cleanup()
    def launch(self,data='data',ignore=False,script=None):
        log=tempfile.TemporaryFile(mode='w+');self.logs.append(log)
        env={**self.env}
        if ignore:env['DECK_TEST_IGNORE_INT']='1'
        proc=subprocess.Popen([sys.executable,str(script or ROOT/'server.py'),'--host','127.0.0.1','--port',str(self.port),'--data-dir',str(self.root/data),'--pairing-seconds','120'],stdout=log,stderr=log,env=env)
        self.processes.append(proc);return proc,log
    def output(self,log):
        log.flush();log.seek(0);return log.read()
    def ready(self,proc,log):
        deadline=time.monotonic()+12
        while time.monotonic()<deadline:
            text=self.output(log)
            if re.search(r'접속 코드: ([a-f0-9]{12})',text):return re.search(r'접속 코드: ([a-f0-9]{12})',text).group(1)
            if proc.poll() is not None:self.fail('server exited before ready (output omitted to avoid pairing code)')
            time.sleep(.05)
        self.fail('startup timeout')
    def test_first_launch_replacement_config_code_and_concurrent_starts(self):
        data=self.root/'data';data.mkdir();(data/'buttons.json').write_text(json.dumps({'buttons':[],'preferences':{'macSound':False}}))
        first,log=self.launch();code=self.ready(first,log)
        config=self.root/'data/buttons.json';original=config.read_bytes()
        second,log2=self.launch();code2=self.ready(second,log2)
        self.assertEqual(first.wait(timeout=5),0);self.assertNotEqual(first.pid,second.pid);self.assertNotEqual(code,code2)
        self.assertEqual(config.read_bytes(),original)
        self.assertIn('정상 종료 완료',self.output(log2))
        # Real simultaneous entrants serialize through the same startup lock.
        third,log3=self.launch();fourth,log4=self.launch()
        self.ready(third,log3);self.ready(fourth,log4)
        deadline=time.monotonic()+4
        while time.monotonic()<deadline and sum(p.poll() is None for p in [second,third,fourth])!=1:time.sleep(.1)
        self.assertEqual(sum(p.poll() is None for p in [second,third,fourth]),1)
        self.assertEqual(config.read_bytes(),original)
    def test_other_data_and_other_script_are_not_signalled(self):
        first,log=self.launch();self.ready(first,log)
        other,otherlog=self.launch('other');self.assertEqual(other.wait(timeout=5),1);self.assertIsNone(first.poll())
        first.terminate();first.wait(timeout=5)
        foreign=self.root/'server.py';foreign.write_text((ROOT/'server.py').read_text())
        different,log=self.launch(script=foreign);self.ready(different,log)
        candidate,candidatelog=self.launch();self.assertEqual(candidate.wait(timeout=5),1);self.assertIsNone(different.poll())
    def test_foreign_listener_is_not_signalled(self):
        log=tempfile.TemporaryFile(mode='w+');self.logs.append(log)
        foreign=subprocess.Popen([sys.executable,'-m','http.server',str(self.port),'--bind','127.0.0.1'],stdout=log,stderr=log)
        self.processes.append(foreign)
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            try:
                with socket.create_connection(('127.0.0.1',self.port),timeout=.1):break
            except OSError:time.sleep(.05)
        candidate,candidatelog=self.launch();self.assertEqual(candidate.wait(timeout=5),1);self.assertIsNone(foreign.poll())
    def test_shutdown_failure_does_not_force_kill(self):
        first,log=self.launch(ignore=True);self.ready(first,log)
        second,log2=self.launch();self.assertEqual(second.wait(timeout=12),1);self.assertIsNone(first.poll())
        self.assertIn('강제 종료하지 않았습니다',self.output(log2))
    def test_legacy_without_metadata_ctrl_c_path(self):
        # Legacy entrypoint catches KeyboardInterrupt; no ownership metadata required.
        script=self.root/'legacy.py'
        script.write_text('''import argparse\nfrom http.server import HTTPServer,BaseHTTPRequestHandler\np=argparse.ArgumentParser();p.add_argument('--host');p.add_argument('--port',type=int);p.add_argument('--data-dir');p.add_argument('--pairing-seconds');a=p.parse_args()\ns=HTTPServer((a.host,a.port),BaseHTTPRequestHandler)\nprint('ready',flush=True)\ntry:s.serve_forever()\nexcept KeyboardInterrupt:pass\nfinally:s.server_close()\n''')
        proc,log=self.launch(script=script)
        deadline=time.monotonic()+3
        while 'ready' not in self.output(log) and time.monotonic()<deadline:time.sleep(.05)
        self.assertTrue(replace_existing(script,self.root/'data','127.0.0.1',self.port))
        self.assertEqual(proc.wait(timeout=3),0)


class StartupIdentityTests(unittest.TestCase):
    def test_exact_args_and_changed_identity_never_signal(self):
        root=ROOT.resolve();identity=('uid start','/usr/bin/python3',('python3','server.py','--data-dir','data'),'{}'.format(root))
        self.assertEqual(invocation(identity)[:2],(root/'server.py',root/'data'))
        with patch('deck.startup.available',return_value=False),patch('deck.startup.conflicting_listeners',return_value={123}),patch('deck.startup.process_identity',side_effect=[identity,('changed',*identity[1:])]),patch('deck.startup.os.kill') as kill:
            with self.assertRaises(RuntimeError):replace_existing(root/'server.py',root/'data','0.0.0.0',8765)
            kill.assert_not_called()
    def test_already_gone_is_safe(self):
        with patch('deck.startup.available',side_effect=[False,True]),patch('deck.startup.conflicting_listeners',return_value={123}),patch('deck.startup.process_identity',return_value=None),patch('deck.startup.os.kill') as kill:
            self.assertFalse(replace_existing(ROOT/'server.py',ROOT/'data','0.0.0.0',8765));kill.assert_not_called()
