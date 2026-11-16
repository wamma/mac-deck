"""Only compile/run extracted pure message classification; never execute DeckBridge or AppleEvents."""
import subprocess,tempfile,unittest
from pathlib import Path

class TerminalErrorTests(unittest.TestCase):
    def test_appleevent_messages_and_context_without_native_operations(self):
        source=Path('native/DeckBridge.swift').read_text()
        self.assertTrue('func terminalFailureMessage(' in source,'Missing pure Terminal error classifier')
        pure=source.split('func terminalFailureMessage(',1)[1].split('\nfunc terminalTTY()',1)[0]
        pure='func terminalFailureMessage('+pure
        harness='''
let denied=terminalFailureMessage(errorNumber:-1743)
assert(denied.contains("-1743") && denied.contains("허용되지"))
assert(denied.contains("시스템 설정 → 개인정보 보호 및 보안 → 자동화"))
assert(denied.contains("서버를 실행한 앱") && denied.contains("Terminal 제어"))
assert(!denied.contains("Orca"))
let timed=terminalFailureMessage(errorNumber:-1712)
assert(timed.contains("-1712") && timed.contains("자동화 요청 창 또는 Terminal 응답"))
assert(!timed.contains("허용되지"))
for code in [-1728,-1719] {assert(terminalFailureMessage(errorNumber:code).contains("창 또는 선택 탭"))}
assert(terminalFailureMessage(wrongApp:true).contains("전면"))
assert(terminalFailureMessage(missingWindow:true).contains("창 또는 선택 탭"))
for message in [denied,timed,terminalFailureMessage(errorNumber:-999),terminalFailureMessage(),terminalFailureMessage(wrongApp:true),terminalFailureMessage(missingWindow:true)] {
 assert(message.contains("등록 창 확인"))
 assert(!message.contains("손쉬운 사용") && !message.contains("화면 기록"))
}
print("PASS: denied / timeout / missing window / wrong app / unknown; pure strings only")
'''
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'messages.swift';path.write_text(pure+harness)
            result=subprocess.run(['swift',str(path)],capture_output=True,text=True,check=True,timeout=15)
            self.assertIn('pure strings only',result.stdout)
