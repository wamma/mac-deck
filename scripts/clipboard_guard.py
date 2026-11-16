"""Test-only memory guardian and temporary production collector pause. Never logs bytes."""
import http.cookiejar,json,re,subprocess,urllib.request,os

class ClipboardGuard:
    def __init__(self):
        self.process=subprocess.Popen(['swift','scripts/clipboard_guard.swift'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
        self.snapshot=self._read()
    def _read(self):
        line=self.process.stdout.readline()
        result=json.loads(line) if line else {'ok':False,'reason':'Clipboard guard exited'}
        if not result['ok']:raise RuntimeError(result.get('reason','Clipboard verification failed'))
        return result
    def command(self,command,text=None):
        self.process.stdin.write(json.dumps({'command':command,**({'text':text} if text is not None else {})})+'\n');self.process.stdin.flush()
        return self._read()
    def close(self):
        if self.process.poll() is None:self.process.stdin.close();self.process.wait(timeout=5)

class CollectorPause:
    def __init__(self):
        # Existing server's code stays in memory, never in evidence or shell arguments.
        code=os.environ.get('DECK_CODE')
        if not code:raise RuntimeError('Set DECK_CODE for an explicitly chosen isolated test server')
        self.client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.request('/api/pair',{'code':code})
        self.before=self.request('/api/clipboard');self.paused=False
    def request(self,path,body=None):
        root=os.environ['DECK_TEST_URL']
        request=urllib.request.Request(root+path,data=json.dumps(body).encode() if body is not None else None,headers={'Origin':root,'Content-Type':'application/json'})
        with self.client.open(request,timeout=5) as response:return json.load(response)
    def pause(self):
        if self.before['enabled']:self.request('/api/clipboard',{'action':'enabled','enabled':False});self.paused=True
        if self.request('/api/clipboard')['enabled']:raise RuntimeError('Collector could not be paused')
    def restore(self):
        if self.paused:self.request('/api/clipboard',{'action':'enabled','enabled':True})
        after=self.request('/api/clipboard')
        return {'originalEnabled':self.before['enabled'],'enabledRestored':after['enabled']==self.before['enabled'],'existingHistoryUnchanged':after['items']==self.before['items']}
