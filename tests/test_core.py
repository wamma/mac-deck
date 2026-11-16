import json
import tempfile
import unittest
from pathlib import Path
from deck.core import State, Clipboard, validate_button
from deck.macos import shortcut_script

APPS = [{'id': 'finder', 'name': 'Finder', 'path': '/System/Library/CoreServices/Finder.app'}]

class CoreTests(unittest.TestCase):
    def test_shortcuts_reject_code_and_bad_types(self):
        for key, mods in [('a" & do shell script "x', ['command']), ('a', ['evil']), ('a', 'command'), ('', []), (None, [])]:
            with self.assertRaises(ValueError):
                shortcut_script(key, mods)
        self.assertIn('key code 36', shortcut_script('enter', []))
        self.assertIn('command down', shortcut_script('c', ['command']))

    def test_buttons_only_allow_known_apps(self):
        with self.assertRaises(ValueError):
            validate_button({'id':'x', 'label':'x', 'kind':'app', 'app':'/bin/sh'}, APPS)
        for value in [None, {}, {'id':'x','label':'x','kind':'shell'}]:
            with self.assertRaises(ValueError): validate_button(value, APPS)

    def test_app_field_malformed_types_are_validation_errors(self):
        for app in [[],{},None,123]:
            with self.assertRaises(ValueError):
                validate_button({'id':'a','label':'앱','kind':'app','app':app},APPS)

    def test_unicode_settings_persist_and_invalid_updates_are_atomic(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'config.json'
            state = State(path, APPS)
            button = {'id':'abc', 'label':'한글 앱 ✨','kind':'app','app':'finder'}
            state.save_buttons([button])
            self.assertEqual(State(path, APPS).snapshot()['buttons'][0]['label'], '한글 앱 ✨')
            with self.assertRaises(ValueError): state.save_buttons([button, button])
            self.assertEqual(len(state.snapshot()['buttons']), 1)
            self.assertEqual(len(json.loads(path.read_text())['buttons']),1)

    def test_clipboard_opt_in_baseline_and_pause(self):
        clip = Clipboard()
        clip.observe('before')
        self.assertEqual(clip.snapshot()['items'], [])
        clip.set_enabled(True)
        clip.observe('before') # first sample is baseline, not a new copy
        clip.observe('한글 복사')
        self.assertEqual(clip.snapshot()['items'][0]['text'], '한글 복사')
        clip.set_enabled(False)
        clip.observe('secret')
        clip.set_enabled(True)
        clip.observe('secret')
        self.assertEqual(len(clip.snapshot()['items']), 1)

    def test_clipboard_cap_dedupe_and_delete_does_not_resurrect(self):
        clip = Clipboard(); clip.set_enabled(True); clip.observe('baseline')
        for i in range(105): clip.observe(str(i))
        self.assertEqual(len(clip.snapshot()['items']),100)
        clip.observe('104')
        self.assertEqual(len(clip.snapshot()['items']),100)
        top = clip.snapshot()['items'][0]
        clip.delete(top['id']); clip.observe('104')
        self.assertEqual(len(clip.snapshot()['items']),99)
        clip.delete(None); clip.observe('104')
        self.assertEqual(clip.snapshot()['items'],[])
        clip.observe('x'*100_001)
        self.assertEqual(clip.snapshot()['items'],[])

if __name__ == '__main__': unittest.main()
