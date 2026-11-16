import tempfile
import unittest
from pathlib import Path
from scripts.verify_native import verify_document,wait_for_saved_text

class NativeVerifierTests(unittest.TestCase):
    def test_changed_document_sends_no_input(self):
        with tempfile.TemporaryDirectory(prefix='mac-deck-native-') as folder:
            path=Path(folder)/'Deck-Safe-Verification.txt';path.write_text('')
            expected={'pid':123,'windowId':456,'documentURL':path.resolve().as_uri()}
            class Fake:
                def diagnostics(self):return {'pid':123,'windowId':456,'bundleId':'com.apple.TextEdit','focusedWindowReadable':True,'documentURL':'file:///tmp/other-document.txt'}
                def type_text(self,*a,**k):raise AssertionError('must not type')
                def shortcut(self,*a,**k):raise AssertionError('must not save')
            self.assertIn('blocked',verify_document(Fake(),path,expected))
    def test_nonempty_document_rejected(self):
        with tempfile.TemporaryDirectory(prefix='mac-deck-native-') as folder:
            path=Path(folder)/'Deck-Safe-Verification.txt';path.write_text('existing')
            with self.assertRaises(ValueError):verify_document(None,path,{})

    def test_delayed_file_save_is_observed_without_repeating_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.txt';path.write_text('');now=[0.]
            def sleep(seconds):
                now[0]+=seconds
                if now[0]>=1.2:path.write_text('saved\n')
            saved,elapsed=wait_for_saved_text(path,'saved\n',clock=lambda:now[0],sleep=sleep)
            self.assertEqual(saved,'saved\n');self.assertGreaterEqual(elapsed,1.2)
    def test_save_wait_is_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.txt';path.write_text('');now=[0.]
            saved,elapsed=wait_for_saved_text(path,'expected',timeout=.3,clock=lambda:now[0],sleep=lambda s:now.__setitem__(0,now[0]+s))
            self.assertEqual(saved,'');self.assertGreaterEqual(elapsed,.3);self.assertLess(elapsed,.5)
