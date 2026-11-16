"""Mac-local pairing windows and memory-only device sessions."""
import secrets
import threading
import time


class AccessControl:
    def __init__(self,code=None,pairing_seconds=0,clock=time.monotonic):
        self.lock=threading.RLock();self.clock=clock;self.sessions={};self.code=code or secrets.token_hex(6)
        self.pairing_until=clock()+pairing_seconds
    def open_pairing(self,seconds=120):
        with self.lock:
            self.code=secrets.token_hex(6);self.pairing_until=self.clock()+seconds
            return self.code
    def pairing_open(self):return self.clock()<self.pairing_until
    def close_pairing(self):
        with self.lock:self.pairing_until=0
    def devices(self):
        with self.lock:
            now=self.clock()
            return [{'id':v['id'],'name':v['name'],'secondsRemaining':max(0,int(v['expires']-now))} for v in self.sessions.values() if v['expires']>now]
    def revoke(self,ident):
        with self.lock:
            matches=[token for token,value in self.sessions.items() if value['id']==ident]
            for token in matches:self.sessions.pop(token)
            return bool(matches)


def console(access,stop,stream,output):
    """Only the process's local stdin; never available over HTTP."""
    for line in stream:
        if stop.is_set():break
        words=line.strip().split()
        if words==['p']:
            code=access.open_pairing();print('Pairing open for 120 seconds · 접속 코드: '+code,file=output,flush=True)
        elif words==['close']:
            access.close_pairing();print('Pairing closed; existing devices remain connected.',file=output,flush=True)
        elif words==['list']:
            for device in access.devices():print(device['id'],device['name'],str(device['secondsRemaining'])+'s',file=output,flush=True)
            print('End of connected devices.',file=output,flush=True)
        elif len(words)==2 and words[0]=='revoke':print('Device revoked. Later requests are blocked; already admitted work cannot be cancelled.' if access.revoke(words[1]) else 'No matching device.',file=output,flush=True)
        else:print('Local commands: p | close | list | revoke DEVICE_ID',file=output,flush=True)
