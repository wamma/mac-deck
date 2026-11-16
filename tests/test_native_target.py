"""Compile the pure target predicate, never main/input dispatch or native UI operations."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from deck.macos import Mac

class TargetTests(unittest.TestCase):
    def test_expected_identity_forwarded_to_both_input_operations(self):
        mac=Mac.__new__(Mac);seen=[];mac.bridge=lambda p:seen.append(p)
        target={'pid':123,'windowId':456,'documentURL':'file:///tmp/unique-test.txt'}
        mac.type_text('safe',True,expected=target);mac.shortcut('s',['command'],expected=target)
        self.assertEqual([p['expected'] for p in seen],[target,target])

    @unittest.skipUnless(shutil.which('swiftc') and Path('/System/Library/Frameworks/AppKit.framework').exists(),'macOS Swift required')
    def test_native_fixed_target_rejects_pid_window_document_races(self):
        source=(Path(__file__).resolve().parents[1]/'native/DeckBridge.swift').read_text()
        pure=source.split('\ndo {\n    let data=')[0]
        harness=r'''
let data="{\"pid\":123,\"windowId\":456,\"documentURL\":\"file:///tmp/deck-unique.txt\"}".data(using:.utf8)!
let expected=try! JSONSerialization.jsonObject(with:data) as! [String:Any]
let base: [String:Any] = ["pid":123,"windowId":UInt32(456),"documentURL":"file:///tmp/deck-unique.txt"]
assert(matchesExpected(base,expected))
for (key,value) in [("pid",124 as Any),("windowId",UInt32(457) as Any),("documentURL","file:///tmp/other.txt" as Any)] {
 var changed=base;changed[key]=value;assert(!matchesExpected(changed,expected))
}
assert(!matchesExpected(base,[:]))
var missing=expected;missing["windowId"]=0;assert(!matchesExpected(base,missing))
let session: [String:Any] = ["sessionId":"session-1","question":"question-1","requireQuestion":true]
let proof: [String:Any] = ["session":"session-1","question":"question-1","state":"input-required","updatedAt":100.0]
assert(matchesSessionProof(session,proof,101))
assert(!matchesSessionProof(session,proof,130))
assert(!matchesSessionProof(session,proof,98))
for (key,value) in [("session","other"),("question","new-question"),("state","working")] {
 var changed=proof;changed[key]=value;assert(!matchesSessionProof(session,changed,101))
}
assert(!matchesSessionProof([:],proof,101))
print("fixed-target predicate PASS; no native input called")
'''
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'check.swift';file.write_text(pure+harness);binary=Path(tmp)/'check'
            subprocess.run(['swiftc',str(file),'-o',str(binary)],check=True,capture_output=True,timeout=30)
            output=subprocess.check_output([str(binary)],timeout=5).decode()
            self.assertIn('predicate PASS',output)

    def test_failed_capture_guard_never_calls_screencapture(self):
        from unittest.mock import patch
        mac=Mac.__new__(Mac)
        def deny(payload):raise RuntimeError('locked or missing permission')
        mac.bridge=deny
        with patch('deck.macos.subprocess.run') as execute:
            with self.assertRaises(RuntimeError):mac.capture_registered({'pid':1,'windowId':2})
            execute.assert_not_called()
