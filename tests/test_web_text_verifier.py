import unittest
from scripts.verify_web_text import PinnedMac

class PinnedWebTests(unittest.TestCase):
    def test_fixed_identity_cannot_be_replaced_by_call_or_original_dictionary(self):
        mac=PinnedMac.__new__(PinnedMac);seen=[];mac.bridge=lambda request:seen.append(request)
        target={'pid':123,'windowId':456,'documentURL':'file:///tmp/dedicated.txt'}
        mac.pin(target);target['pid']=999
        mac.type_text('safe',True,expected={'pid':999})
        mac.shortcut('s',['command'],expected={'pid':999})
        self.assertEqual([request['expected']['pid'] for request in seen],[123,123])
        self.assertEqual(mac.calls,['text','save'])
    def test_unpinned_and_unapproved_shortcut_send_no_native_input(self):
        mac=PinnedMac.__new__(PinnedMac);seen=[];mac.bridge=lambda request:seen.append(request)
        with self.assertRaises(AttributeError):mac.type_text('safe',True)
        mac.pin({'pid':123,'windowId':456,'documentURL':'file:///tmp/dedicated.txt'})
        with self.assertRaises(RuntimeError):mac.shortcut('v',['command'])
        self.assertEqual(seen,[])
    def test_clipboard_mode_only_adds_explicit_keys_and_checks_before_paste(self):
        from unittest.mock import Mock
        guard=Mock();mac=PinnedMac.__new__(PinnedMac);seen=[];mac.bridge=lambda request:seen.append(request)
        target={'pid':123,'windowId':456,'documentURL':'file:///tmp/dedicated.txt'};mac.pin(target,guard)
        mac.shortcut('a',['command']);mac.shortcut('right',[]);mac.shortcut('v',['command'])
        self.assertEqual([request['expected'] for request in seen],[target]*3)
        self.assertEqual(guard.command.call_count,2) # before and after paste
        with self.assertRaises(RuntimeError):mac.shortcut('x',['command'])
        guard.command.side_effect=RuntimeError('new clipboard owner')
        with self.assertRaises(RuntimeError):mac.shortcut('v',['command'])
        self.assertEqual(len(seen),3)
    def test_clipboard_memory_restore_and_conflict_on_unique_pasteboard(self):
        import json,subprocess
        result=subprocess.run(['swift','scripts/clipboard_guard.swift','--self-test'],capture_output=True,text=True,check=True)
        evidence=json.loads(result.stdout)
        self.assertTrue(evidence['multiItemMultiTypeBinaryRoundTrip'])
        self.assertTrue(evidence['newerCopyNotOverwritten'])
        self.assertTrue(evidence['promiseRejected'])
        self.assertFalse(evidence['generalClipboardTouched'])
    def test_zero_window_is_never_pinned_and_preparation_waits_without_input(self):
        from pathlib import Path
        from unittest.mock import Mock
        from scripts.verify_web_text import await_document_target
        path=Path('/tmp/dedicated.txt');base={'pid':123,'windowId':0,'documentURL':path.as_uri(),'bundleId':'com.apple.TextEdit','focusedWindowReadable':True}
        mac=PinnedMac.__new__(PinnedMac)
        with self.assertRaises(ValueError):mac.pin(base)
        mac.diagnostics=Mock(side_effect=[base,{**base,'windowId':456}]);sleep=Mock()
        fixed=await_document_target(mac,path,123,sleep=sleep)
        self.assertEqual(fixed['windowId'],456);sleep.assert_called_once_with(.1)
        mac.diagnostics=Mock(return_value={**base,'documentURL':'file:///tmp/other.txt'})
        with self.assertRaises(RuntimeError):await_document_target(mac,path,123)
        mac.diagnostics=Mock(return_value=base)
        with self.assertRaises(RuntimeError):await_document_target(mac,path,123,timeout=0)
