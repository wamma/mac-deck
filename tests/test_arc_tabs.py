import json,subprocess,unittest
from unittest.mock import patch
from deck.arc import read_tabs
from tests.test_http import HTTPTests

class ArcAdapterTests(unittest.TestCase):
    def test_fields_are_structured_domain_only_and_errors_classified(self):
        payload={'status':'ok','windows':[{'id':'w','tabs':[{'id':'t','title':'quotes " 한글\ntext','url':'https://example.com/private?q=secret'}]}]}
        with patch('deck.arc.subprocess.run',return_value=subprocess.CompletedProcess([],0,json.dumps(payload).encode(),b'')) as run:
            result=read_tabs();self.assertEqual(result['windows'][0]['tabs'][0]['domain'],'example.com');self.assertNotIn('secret',json.dumps(result));self.assertNotIn('url',result['windows'][0]['tabs'][0]);self.assertEqual(run.call_args.kwargs['timeout'],8)
            self.assertNotIn('secret',str(run.call_args.args))
        for code,status in [(-1743,'permission'),(-1712,'timeout'),(-600,'not_running'),(-1728,'unavailable'),(-1700,'error')]:
            with patch('deck.arc.subprocess.run',return_value=subprocess.CompletedProcess([],0,json.dumps({'status':'error','code':code}).encode(),b'PRIVATE')):self.assertEqual(read_tabs()['status'],status)
        with patch('deck.arc.subprocess.run',side_effect=subprocess.TimeoutExpired('osascript',8)):self.assertEqual(read_tabs()['status'],'timeout')
        with patch('deck.arc.subprocess.run',return_value=subprocess.CompletedProcess([],0,b'{"status":"not_running"}',b'')):self.assertEqual(read_tabs()['status'],'not_running')

class ArcHTTPTests(HTTPTests):
    def test_arc_authenticated_origin_host_and_readonly(self):
        calls=[];self.mac.arc_tabs=lambda:calls.append(True) or {'status':'ok','windows':[]}
        self.assertEqual(self.request('/api/arc/tabs')[0],401);self.assertFalse(calls)
        self.pair()
        self.assertEqual(self.request('/api/arc/tabs',headers={'Origin':'http://evil.test'})[0],403)
        self.assertEqual(self.request('/api/arc/tabs',headers={'Host':'evil.test'})[0],403);self.assertFalse(calls)
        status,raw,_=self.request('/api/arc/tabs');body=json.loads(raw);self.assertEqual(status,200);self.assertEqual(body['status'],'ok');self.assertEqual(len(calls),1)
        self.assertEqual(self.request('/api/arc/tabs',{})[0],404);self.assertEqual(len(calls),1)
        for state in ['permission','timeout']:
            self.mac.arc_tabs=lambda:{'status':state,'windows':[],'message':'Synthetic '+state}
            self.assertEqual(json.loads(self.request('/api/arc/tabs')[1])['status'],state)
