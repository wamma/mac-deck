"""Whole-action dispatch and short-lived, session-bound trash confirmation."""
import secrets
import time
from urllib.parse import urlsplit


def validate_urls(urls):
    if not isinstance(urls,list) or not 1 <= len(urls) <= 10:
        raise ValueError('URL은 1~10개를 입력하세요.')
    for url in urls:
        if not isinstance(url,str) or len(url)>4096 or any(c.isspace() or ord(c)<32 or ord(c)==127 for c in url):
            raise ValueError('URL에 공백이나 제어 문자를 넣을 수 없습니다.')
        try:
            parsed=urlsplit(url)
            valid=parsed.scheme in {'http','https'} and parsed.hostname and not parsed.username and not parsed.password
            parsed.port
        except ValueError: valid=False
        if not valid: raise ValueError('사용자 정보가 없는 http/https 주소를 입력하세요.')
    return list(urls)


class TrashConfirmation:
    def __init__(self,clock=time.monotonic): self.clock=clock; self.pending={}
    def check(self,session,button,confirmation):
        now=self.clock();key=(session,button)
        self.pending={k:v for k,v in self.pending.items() if v[1]>=now}
        if confirmation is None:
            nonce=secrets.token_urlsafe(24);self.pending[key]=(nonce,now+3)
            return {'status':'confirmation','confirmationRequired':True,'confirmationId':nonce,'expiresIn':3,
                    'message':'3초 안에 다시 누르면 맥의 휴지통을 비웁니다.'}
        entry=self.pending.pop(key,None)
        if not isinstance(confirmation,str) or not entry or not secrets.compare_digest(entry[0],confirmation):
            raise ValueError('휴지통 확인이 만료되었거나 일치하지 않습니다. 다시 시작하세요.')
        return None


def execute_button(button,mac,apps):
    kind=button['kind']
    if kind=='app':
        app=next((a for a in apps if a['id']==button['app']),None)
        if not app: raise ValueError('앱이 설치되어 있지 않습니다. 버튼을 편집하세요.')
        result=mac.open_app(app['path'])
    elif kind=='shortcut': result=mac.shortcut(button['key'],button['modifiers'])
    elif kind=='text': result=mac.type_text(button['text'],button['enter'])
    elif kind=='urls': result=mac.open_urls(validate_urls(button['urls']))
    elif kind=='trash': result=mac.empty_trash()
    else: raise ValueError('지원하지 않는 동작입니다.')
    return result or {'status':'accepted','message':'맥에 명령을 전달했습니다. 결과는 확인되지 않았습니다.'}


def validate_system_command(body):
    action=body.get('action')
    if action not in {'volume_up','volume_down','volume_set','mute_toggle','brightness_up','brightness_down','brightness_set'}:
        raise ValueError('지원하지 않는 시스템 동작입니다.')
    result={'action':action}
    if action.endswith('_set'):
        value=body.get('value')
        if type(value) is not int or not 0<=value<=100: raise ValueError('설정 값은 0~100 정수여야 합니다.')
        result['value']=value
    return result
