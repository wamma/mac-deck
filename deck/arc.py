"""Arc tabs metadata; no activation, user script interpolation, persistence or raw errors."""
import json
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

BUNDLE_ID='company.thebrowser.Browser'
MESSAGES={
    'not_running':'Arc가 실행 중이 아닙니다. 앱을 실행한 뒤 다시 확인하세요.',
    'permission':'Arc 자동화 읽기가 허용되지 않았습니다. 시스템 설정 → 개인정보 보호 및 보안 → 자동화에서 서버 실행 앱의 Arc 제어를 확인하세요.',
    'timeout':'Arc 탭 조회 시간이 초과되었습니다. 맥의 자동화 요청 창 또는 Arc 응답을 확인한 뒤 직접 새로고침하세요.',
    'unavailable':'조회 중 Arc 창 또는 탭이 바뀌었습니다. 직접 새로고침하세요.',
    'error':'Arc 탭 목록을 읽지 못했습니다. 활성 탭을 추측하거나 다른 창으로 대체하지 않습니다.'}


def read_tabs():
    try:
        result=subprocess.run(['/usr/bin/osascript','-l','JavaScript',str(Path(__file__).resolve().parent.parent/'native/ArcTabs.js')],capture_output=True,timeout=8)
        if result.returncode:return failure('error')
        data=json.loads(result.stdout)
        if data.get('status')=='not_running':return failure('not_running')
        if data.get('status')!='ok':return failure({-1743:'permission',-1712:'timeout',-600:'not_running',-1728:'unavailable'}.get(data.get('code'),'error'))
        windows=[]
        for window in data['windows']:
            tabs=[]
            for tab in window['tabs']:
                try:domain=urlsplit(tab['url']).hostname or '도메인 없음'
                except ValueError:domain='도메인 없음'
                tabs.append({'id':str(tab['id']),'title':str(tab['title'])[:512],'domain':domain[:253]})
            windows.append({'id':str(window['id']),'tabs':tabs})
        return {'status':'ok','windows':windows,'truncated':bool(data.get('truncated')),'bundleId':BUNDLE_ID}
    except subprocess.TimeoutExpired:return failure('timeout')
    except (OSError,ValueError,TypeError,KeyError):return failure('error')


def failure(status):return {'status':status,'windows':[],'message':MESSAGES[status],'bundleId':BUNDLE_ID}
