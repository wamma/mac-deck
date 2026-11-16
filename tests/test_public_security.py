import http.client
import io
import json
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from deck.access import AccessControl,console
from deck.core import State
from deck.http import make_server
from deck.transport import tls_context
from deck.startup import invocation,replace_existing
from tests.test_http import FakeMac


class PublicSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files=tempfile.TemporaryDirectory();root=Path(cls.files.name)
        cls.cert=root/'fixture.crt';cls.key=root/'fixture.key'
        cfg=root/'openssl.cnf';cfg.write_text('[req]\ndistinguished_name=dn\nx509_extensions=ext\nprompt=no\n[dn]\nCN=localhost\n[ext]\nsubjectAltName=DNS:localhost,IP:127.0.0.1\nbasicConstraints=critical,CA:TRUE\nkeyUsage=critical,digitalSignature,keyEncipherment,keyCertSign\nextendedKeyUsage=serverAuth\n')
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-config',str(cfg),'-keyout',str(cls.key),'-out',str(cls.cert)],check=True,capture_output=True)
    @classmethod
    def tearDownClass(cls):cls.files.cleanup()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.mac=FakeMac();self.state=State(Path(self.temp.name)/'config.json',[]);self.servers=[]
    def tearDown(self):
        for server in self.servers:server.shutdown();server.server_close()
        self.temp.cleanup()
    def start(self,tls=False,max_connections=16,access=None):
        server=make_server('127.0.0.1',0,self.state,self.mac,'fixture-code',tls=tls_context(self.cert,self.key) if tls else None,access=access,max_connections=max_connections)
        self.servers.append(server);threading.Thread(target=server.serve_forever,daemon=True).start();return server
    def req(self,server,path,body=None,cookie='',origin=None,tls=False,headers=None):
        scheme='https' if tls else 'http';host='localhost:'+str(server.server_port)
        conn=http.client.HTTPSConnection('localhost',server.server_port,context=ssl.create_default_context(cafile=str(self.cert)),timeout=3) if tls else http.client.HTTPConnection('localhost',server.server_port,timeout=3)
        base={'Host':host,'Origin':origin or scheme+'://'+host,'Cookie':cookie,'Content-Type':'application/json'};base.update(headers or {})
        conn.request('POST' if body is not None else 'GET',path,None if body is None else json.dumps(body),base)
        response=conn.getresponse();data=response.read();result=(response.status,response.getheader('Set-Cookie'),data);conn.close();return result
    def test_tls_verified_handshake_origin_secure_cookie_and_no_forwarded_trust(self):
        server=self.start(tls=True)
        status,cookie,_=self.req(server,'/api/pair',{'code':'fixture-code'},tls=True)
        self.assertEqual(status,200);self.assertIn('; Secure',cookie);self.assertIn('HttpOnly',cookie)
        self.assertEqual(self.req(server,'/api/state',cookie=cookie,tls=True)[0],200)
        self.assertEqual(self.req(server,'/api/pair',{'code':'fixture-code'},tls=True,origin='http://localhost:'+str(server.server_port),headers={'X-Forwarded-Proto':'https'})[0],403)
        with self.assertRaises(ssl.SSLCertVerificationError):
            conn=http.client.HTTPSConnection('localhost',server.server_port,timeout=2);conn.request('GET','/');conn.getresponse()
        with self.assertRaises((ConnectionError,OSError,http.client.HTTPException)):
            conn=http.client.HTTPConnection('localhost',server.server_port,timeout=2);conn.request('GET','/');conn.getresponse()
        plain=self.start();status,cookie,_=self.req(plain,'/api/pair',{'code':'fixture-code'},headers={'X-Forwarded-Proto':'https'})
        self.assertEqual(status,200);self.assertNotIn('; Secure',cookie)
    def test_local_pair_window_reopen_and_revoke_without_restart_or_clipboard_loss(self):
        clock=[100];access=AccessControl(clock=lambda:clock[0]);server=self.start(access=access)
        self.assertEqual(self.req(server,'/api/pair',{'code':access.code})[0],403)
        out=io.StringIO();console(access,threading.Event(),io.StringIO('p\n'),out)
        code=access.code;status,cookie,_=self.req(server,'/api/pair',{'code':code,'deviceName':'Fixture tablet'})
        self.assertEqual(status,200);device=access.devices()[0];clock[0]+=121
        self.assertEqual(self.req(server,'/api/pair',{'code':code})[0],403)
        self.assertEqual(self.req(server,'/api/state',cookie=cookie)[0],200)
        # Opening another window rotates only the code, never existing sessions/state.
        console(access,threading.Event(),io.StringIO('p\nlist\n'),io.StringIO());self.assertNotEqual(code,access.code)
        self.assertEqual(self.req(server,'/api/state',cookie=cookie)[0],200)
        console(access,threading.Event(),io.StringIO('revoke '+device['id']+'\nclose\n'),io.StringIO())
        self.assertEqual(self.req(server,'/api/state',cookie=cookie)[0],401);self.assertFalse(access.pairing_open())
        self.assertEqual(self.req(server,'/api/pairing/open',{})[0],401) # no remote management surface
    def test_expensive_arc_queries_are_single_flight(self):
        server=self.start();_,cookie,_=self.req(server,'/api/pair',{'code':'fixture-code'})
        entered=threading.Event();release=threading.Event();results=[]
        def slow():entered.set();release.wait(3);return {'status':'ok','windows':[]}
        self.mac.arc_tabs=slow
        worker=threading.Thread(target=lambda:results.append(self.req(server,'/api/arc/tabs',cookie=cookie)[0]));worker.start()
        try:
            self.assertTrue(entered.wait(1));self.assertEqual(self.req(server,'/api/arc/tabs',cookie=cookie)[0],429)
        finally:release.set();worker.join(4)
        self.assertEqual(results,[200])
    def test_connection_limit_drops_excess_and_recovers(self):
        server=self.start(max_connections=1);first=socket.create_connection(('localhost',server.server_port),timeout=1)
        deadline=time.monotonic()+1
        while server.capacity._value and time.monotonic()<deadline:time.sleep(.01)
        self.assertEqual(server.capacity._value,0)
        second=socket.create_connection(('localhost',server.server_port),timeout=1)
        try:
            try:
                second.sendall(b'GET / HTTP/1.0\r\n\r\n');self.assertEqual(second.recv(1),b'')
            except ConnectionResetError:pass # Either EOF or reset is a bounded refusal.
        finally:second.close();first.close()
        deadline=time.monotonic()+1
        while not server.capacity._value and time.monotonic()<deadline:time.sleep(.01)
        self.assertEqual(self.req(server,'/')[0],200)
    def test_cli_tls_identity_and_private_repository_protection(self):
        root=Path.cwd();identity=('uid start','/usr/bin/python3',('python3','server.py','--host','0.0.0.0','--tls-cert','fixture.crt','--tls-key','fixture.key','--allowed-host','localhost','--pairing-seconds','120'),str(root))
        self.assertEqual(invocation(identity),(root/'server.py',root/'.deck-data','0.0.0.0',8765))
        private=('uid start','/usr/bin/python3',('python3','server.py','--host','0.0.0.0'),str(Path(self.temp.name)/'private'))
        with patch('deck.startup.available',return_value=False),patch('deck.startup.conflicting_listeners',return_value={123}),patch('deck.startup.process_identity',return_value=private),patch('deck.startup.os.kill') as kill:
            with self.assertRaises(RuntimeError):replace_existing(root/'server.py',root/'.deck-data','0.0.0.0',8765)
            kill.assert_not_called()
    def test_revoke_or_expire_between_authentication_and_command_admission(self):
        import re
        original=re.fullmatch
        for path in ['/api/run','/api/system','/api/ai/reply']:
            for expire in [False,True]:
                with self.subTest(path=path,expire=expire):
                    server=self.start();_,cookie,_=self.req(server,'/api/pair',{'code':'fixture-code'})
                    entered=threading.Event();release=threading.Event();responses=[]
                    def gate(pattern,value,*args,**kwargs):
                        if value=='fixture-request-0001':entered.set();release.wait(2)
                        return original(pattern,value,*args,**kwargs)
                    body={'requestId':'fixture-request-0001',**({'id':'copy'} if path=='/api/run' else {'action':'volume_set','value':50} if path=='/api/system' else {'slot':0,'revision':1,'nonce':'fixture','key':'enter'})}
                    with patch('deck.http.re.fullmatch',side_effect=gate):
                        thread=threading.Thread(target=lambda:responses.append(self.req(server,path,body,cookie=cookie)[0]));thread.start()
                        try:
                            self.assertTrue(entered.wait(1))
                            if expire:
                                with server.access.lock:
                                    for value in server.access.sessions.values():value['expires']=0
                            else:server.access.revoke(server.access.devices()[0]['id'])
                        finally:release.set();thread.join(3)
                    self.assertEqual(responses,[401]);self.assertEqual(self.mac.executions,[])
    def test_settings_mutation_rechecks_session_after_authentication(self):
        server=self.start();_,cookie,_=self.req(server,'/api/pair',{'code':'fixture-code'})
        entered=threading.Event();release=threading.Event();responses=[];original=server.RequestHandlerClass.authenticate
        def gate(handler):
            value=original(handler);entered.set();release.wait(2);return value
        before=self.state.snapshot()['preferences']
        with patch.object(server.RequestHandlerClass,'authenticate',gate):
            thread=threading.Thread(target=lambda:responses.append(self.req(server,'/api/preferences',{'macSound':not before['macSound']},cookie=cookie)[0]));thread.start()
            try:self.assertTrue(entered.wait(1));server.access.revoke(server.access.devices()[0]['id'])
            finally:release.set();thread.join(3)
        self.assertEqual(responses,[401]);self.assertEqual(self.state.snapshot()['preferences'],before)
    def test_revoke_does_not_wait_for_or_cancel_already_admitted_os_work(self):
        server=self.start();_,cookie,_=self.req(server,'/api/pair',{'code':'fixture-code'})
        entered=threading.Event();release=threading.Event();responses=[]
        def action(command):entered.set();release.wait(2);return {'status':'verified','message':'fixture'}
        self.mac.system_control=action
        thread=threading.Thread(target=lambda:responses.append(self.req(server,'/api/system',{'action':'volume_set','value':50,'requestId':'already-admitted-0001'},cookie=cookie)[0]));thread.start()
        try:
            self.assertTrue(entered.wait(1));started=time.monotonic();self.assertTrue(server.access.revoke(server.access.devices()[0]['id']))
            self.assertLess(time.monotonic()-started,.5)
        finally:release.set();thread.join(3)
        self.assertEqual(responses,[200]);self.assertEqual(self.req(server,'/api/state',cookie=cookie)[0],401)
