import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from deck.core import State
from deck.http import make_server

class FakeMac:
    apps=[]
    def __init__(self): self.executions=[]
    def shortcut(self,key,modifiers): self.executions.append((key,modifiers))
    def write_clipboard(self,text): self.clipboard=text
    def icon(self,app): return None
    def resolve_session_window(self,source): raise ValueError('매핑 미확인')

class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.mac=FakeMac()
        self.state=State(Path(self.temp.name)/'config.json',[])
        self.server=make_server('127.0.0.1',0,self.state,self.mac,'test-code')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.host=f'127.0.0.1:{self.server.server_port}';self.cookie=''
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
    def request(self,path,body=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=2)
        base={'Host':self.host,'Origin':'http://'+self.host,'Content-Type':'application/json','Cookie':self.cookie}
        base.update(headers or {})
        raw=json.dumps(body) if body is not None else None
        conn.request('POST' if body is not None else 'GET',path,raw,base)
        response=conn.getresponse();data=response.read();result=(response.status,data,response.getheader('Set-Cookie'))
        conn.close();return result
    def pair(self):
        status,data,cookie=self.request('/api/pair',{'code':'test-code'})
        self.assertEqual(status,200);self.cookie=cookie.split(';')[0]
        self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Strict',cookie)
    def test_task_alias_auth_and_session_mapping(self):
        from deck.ai import Sessions
        self.state.ai=Sessions();self.state.ai.event('test:task','test',1,'idle');self.state.ai.register(0,'test:task')
        body={'slot':0,'session':'test:task','alias':'시험 별칭'}
        self.assertEqual(self.request('/api/ai/task',body)[0],401)
        self.pair();self.assertEqual(self.request('/api/ai/task',body)[0],200)
        self.assertEqual(self.state.ai.snapshot()['slots'][0]['taskName'],'시험 별칭')
        self.assertEqual(self.request('/api/ai/task',{**body,'session':'changed'})[0],400)
        self.assertEqual(self.mac.executions,[])
    def test_ai_auth_revision_and_one_shot(self):
        from deck.ai import Sessions
        self.state.ai=Sessions()
        for path in ['/api/ai/detail?slot=0','/api/weather/search?q=Seoul']:
            self.assertEqual(self.request(path)[0],401)
        self.assertEqual(self.request('/api/ai/reply',{'key':'enter'})[0],401)
        self.pair();self.state.ai.event('claude:explicit-test','claude',1,'input-required',replySupported=True)
        self.state.ai.register(0,'claude:explicit-test')
        self.assertEqual(self.request('/api/ai/detail?slot=0')[0],400)
        self.state.ai.bind(0,{'pid':999999,'windowId':999999})
        self.mac.resolve_session_window=lambda source:{'pid':999999,'windowId':999999}
        self.mac.capture_registered=lambda mapping:{'image':'fake-test-only'}
        self.mac.reply_registered=lambda mapping,key:self.mac.executions.append(key) or {'status':'accepted'}
        detail=json.loads(self.request('/api/ai/detail?slot=0')[1])
        body={'slot':0,'revision':detail['revision'],'nonce':detail['nonce'],'key':'enter','requestId':'testaireply0000001'}
        self.assertEqual(self.request('/api/ai/reply',{**body,'text':'forbidden'})[0],400)
        body['requestId']='testaireply0000002'
        self.assertEqual(self.request('/api/ai/reply',body)[0],200)
        self.assertEqual(self.request('/api/ai/reply',body)[0],409)
        body['requestId']='testaireply0000003';self.assertEqual(self.request('/api/ai/reply',body)[0],400)
        self.assertEqual(self.mac.executions,['enter'])

    def test_auth_and_origin_guards(self):
        self.assertEqual(self.request('/api/state')[0],401)
        self.assertEqual(self.request('/api/pair',{'code':'test-code'},{'Origin':'http://evil.test'})[0],403)
        self.assertEqual(self.request('/api/state',headers={'Host':'evil.test'})[0],403)
        self.pair();self.assertEqual(self.request('/api/state')[0],200)
        self.assertEqual(self.request('/api/buttons',{'buttons':[]},{'Origin':''})[0],403)
        self.assertEqual(self.request('/api/buttons',{'buttons':[]},{'Content-Type':'text/plain'})[0],415)
    def test_rate_limit_and_bad_input(self):
        for _ in range(10): self.assertEqual(self.request('/api/pair',{'code':'bad'})[0],401)
        self.assertEqual(self.request('/api/pair',{'code':'test-code'})[0],429)
    def test_one_shot_and_logout(self):
        self.pair()
        body={'id':'copy','requestId':'a'*24}
        self.assertEqual(self.request('/api/run',body)[0],200)
        self.assertEqual(self.request('/api/run',body)[0],409)
        self.assertEqual(self.mac.executions,[('c',['command'])])
        self.assertEqual(self.request('/api/run',{'id':'copy','requestId':[]})[0],400)
        self.assertEqual(self.request('/api/logout',{})[0],200)
        self.assertEqual(self.request('/api/state')[0],401)
    def test_clipboard_and_config_roundtrip(self):
        self.pair()
        self.assertEqual(self.request('/api/clipboard',{'action':'enabled','enabled':True})[0],200)
        self.state.clipboard.observe('baseline'); self.state.clipboard.observe('안녕하세요')
        data=json.loads(self.request('/api/clipboard')[1]);item=data['items'][0]
        self.assertEqual(self.request('/api/clipboard',{'action':'copy','id':item['id']})[0],200)
        self.assertEqual(self.mac.clipboard,'안녕하세요')
        self.assertEqual(self.request('/api/clipboard',{'action':'delete','id':item['id']})[0],200)
        self.assertEqual(json.loads(self.request('/api/clipboard')[1])['items'],[])
        self.assertEqual(self.request('/api/buttons',{'buttons':[]})[0],200)
        self.assertEqual(json.loads(self.request('/api/state')[1])['buttons'],[])
    def test_non_object_and_oversized_payload(self):
        self.pair()
        self.assertEqual(self.request('/api/run',[])[0],400)
        self.assertEqual(self.request('/api/run',{}, {'Content-Length':'300000'})[0],413)

    def test_restore_invalidates_old_clipboard_poll(self):
        self.pair()
        clip=self.state.clipboard
        clip.set_enabled(True);clip.observe('baseline');clip.observe('retained')
        retained=clip.snapshot()['items'][0]['id']
        clip.observe('deleted secret');clip.delete(clip.snapshot()['items'][0]['id'])
        old_generation=clip.generation
        self.assertEqual(self.request('/api/clipboard',{'action':'copy','id':retained})[0],200)
        clip.observe('deleted secret',old_generation)
        self.assertEqual([i['text'] for i in clip.snapshot()['items']],['retained'])

    def test_macro_batch_failed_dispatch_is_not_retried(self):
        self.pair()
        def partial(urls):
            self.mac.executions.append(urls[0]);raise RuntimeError('second URL failed')
        self.mac.open_urls=partial
        self.state.save_buttons([dict(id='urls',label='urls',kind='urls',urls=['https://example.com/one','https://example.com/two'])])
        request={'id':'urls','requestId':'batchrequest00000001'}
        self.assertEqual(self.request('/api/run',request)[0],503)
        self.assertEqual(self.request('/api/run',request)[0],409)
        self.assertEqual(self.mac.executions,['https://example.com/one'])

    def test_trash_gate_at_http_boundary(self):
        self.pair();self.state.save_buttons([dict(id='trash',label='trash',kind='trash')])
        self.mac.empty_trash=lambda:self.mac.executions.append('fake-trash')
        first={'id':'trash','requestId':'firstclick00000001'}
        data=json.loads(self.request('/api/run',first)[1]);self.assertTrue(data['confirmationRequired'])
        self.assertEqual(self.mac.executions,[])
        self.assertEqual(self.request('/api/run',first)[0],409)
        second={'id':'trash','requestId':'secondclick0000001','confirmationId':data['confirmationId']}
        self.assertEqual(self.request('/api/run',second)[0],200)
        self.assertEqual(self.request('/api/run',second)[0],409)
        second['requestId']='thirdclick00000001'
        self.assertEqual(self.request('/api/run',second)[0],400)
        self.assertEqual(self.mac.executions,['fake-trash'])

    def test_authenticated_diagnostics_and_text_dispatch(self):
        self.assertEqual(self.request('/api/diagnostics')[0],401)
        self.pair();self.state.save_buttons([dict(id='text',label='macro',kind='text',text='Hello\n한글 🙂',enter=True)])
        self.mac.type_text=lambda text,enter:self.mac.executions.append((text,enter))
        request={'id':'text','requestId':'textclick000000001'}
        self.assertEqual(self.request('/api/run',request)[0],200)
        self.assertEqual(self.request('/api/run',request)[0],409)
        self.assertEqual(self.mac.executions,[('Hello\n한글 🙂',True)])


    def test_system_auth_validation_readback_and_no_replay(self):
        self.assertEqual(self.request('/api/system')[0],401)
        self.pair()
        self.mac.system_status=lambda:{'volume':{'supported':True,'value':40}}
        self.mac.system_control=lambda body:self.mac.executions.append(body) or {'status':'verified','system':{'volume':{'value':50}}}
        self.assertEqual(json.loads(self.request('/api/system')[1])['volume']['value'],40)
        request={'action':'volume_set','value':50,'requestId':'volume000000000001'}
        result=self.request('/api/system',request)
        self.assertEqual(result[0],200);self.assertEqual(json.loads(result[1])['system']['volume']['value'],50)
        self.assertEqual(self.request('/api/system',request)[0],409)
        self.assertEqual(len(self.mac.executions),1)
        self.assertEqual(self.request('/api/system',dict(request,requestId='volume000000000002',value=200))[0],400)
        self.assertEqual(len(self.mac.executions),1)
