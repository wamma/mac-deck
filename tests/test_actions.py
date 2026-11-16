import json
import tempfile
import unittest
from pathlib import Path
from deck.core import State, validate_button
from deck.actions import TrashConfirmation, execute_button

class FakeMac:
    def __init__(self): self.events=[]
    def type_text(self,text,enter): self.events.append(('text',text,enter)); return {'status':'sent','message':'전송됨'}
    def open_urls(self,urls): self.events.append(('urls',urls));return {'status':'accepted','message':'요청됨'}
    def empty_trash(self): self.events.append(('trash',));return {'status':'accepted','message':'요청됨'}

class ActionTests(unittest.TestCase):
    def test_unicode_multiline_macro_is_data(self):
        b=validate_button({'id':'m','label':'한글','kind':'text','text':'한글\n" & do shell script "ignored\n🙂','enter':True},[])
        mac=FakeMac();execute_button(b,mac,[])
        self.assertEqual(mac.events,[('text','한글\n" & do shell script "ignored\n🙂',True)])
        for text,enter in [('',True),('x'*1001,True),('x','true'),('\x00',False)]:
            with self.assertRaises(ValueError):validate_button(dict(id='x',label='x',kind='text',text=text,enter=enter),[])

    def test_url_validation_and_order(self):
        good=['https://example.com/a?q=hello','http://127.0.0.1:8765/검증']
        b=validate_button(dict(id='u',label='url',kind='urls',urls=good),[])
        mac=FakeMac();execute_button(b,mac,[]);self.assertEqual(mac.events,[('urls',good)])
        for urls in [[],['file:///etc/passwd'],['javascript:alert(1)'],['https://user:pass@example.com'],['https://x\ny.com'],['https://'],['https://example.com:bad'],['https://example.com']*11,'https://example.com']:
            with self.assertRaises(ValueError):validate_button(dict(id='u',label='u',kind='urls',urls=urls),[])

    def test_trash_two_distinct_requests_with_expiry_and_session_binding(self):
        now=[100.0];gate=TrashConfirmation(clock=lambda:now[0]);mac=FakeMac()
        first=gate.check('session-a','trash',None)
        self.assertTrue(first['confirmationRequired']);self.assertEqual(mac.events,[])
        with self.assertRaises(ValueError):gate.check('session-b','trash',first['confirmationId'])
        now[0]=103.01
        with self.assertRaises(ValueError):gate.check('session-a','trash',first['confirmationId'])
        second=gate.check('session-a','trash',None)
        self.assertIsNone(gate.check('session-a','trash',second['confirmationId']))
        execute_button(dict(kind='trash'),mac,[]);self.assertEqual(mac.events,[('trash',)])
        with self.assertRaises(ValueError):gate.check('session-a','trash',second['confirmationId'])

    def test_sound_preferences_persist_independently_of_button_edits(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'config.json';state=State(path,[])
            state.save_preferences({'macSound':True});state.save_buttons([])
            self.assertTrue(State(path,[]).snapshot()['preferences']['macSound'])
            with self.assertRaises(ValueError):state.save_preferences({'macSound':'true'})

    def test_physical_key_mapping_covers_alphanumeric(self):
        from deck.macos import Mac
        mac=Mac.__new__(Mac);mac.bridge=lambda payload:payload
        expected={'a':0,'m':46,'t':17,'y':16,'0':29,'1':18,'9':25,'enter':36,'up':126}
        for key,code in expected.items():self.assertEqual(mac.shortcut(key,[])['code'],code)
        for key in 'abcdefghijklmnopqrstuvwxyz0123456789':self.assertIsInstance(mac.shortcut(key,[])['code'],int)

    def test_maximum_unicode_macro_and_over_limit(self):
        text='🙂'*1000
        button=validate_button(dict(id='long',label='long',kind='text',text=text,enter=True),[])
        mac=FakeMac();execute_button(button,mac,[])
        self.assertEqual(mac.events,[('text',text,True)])
        with self.assertRaises(ValueError):validate_button(dict(button,text=text+'🙂'),[])

    def test_native_action_never_builds_after_source_change(self):
        from deck.macos import Mac
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'bridge.swift';source.write_text('changed')
            mac=Mac.__new__(Mac);mac.bridge_error=None;mac.bridge_source=source;mac.bridge_version=0
            with patch('deck.macos.subprocess.run') as run:
                with self.assertRaises(RuntimeError):mac.bridge({'action':'text','text':'must not send','enter':False})
                run.assert_not_called()

    def test_native_text_is_payload_and_urls_are_argv(self):
        from deck.macos import Mac
        from unittest.mock import patch
        mac=Mac.__new__(Mac);payloads=[];mac.bridge=lambda payload:payloads.append(payload)
        text='한글\n" & do shell script "no\n$(literal)'
        mac.type_text(text,True)
        self.assertEqual(payloads,[{'action':'text','text':text,'enter':True}])
        with patch('deck.macos.run') as run:
            mac.open_urls(['https://example.com/one','http://127.0.0.1/two'])
            self.assertEqual([call.args[0] for call in run.call_args_list],[['/usr/bin/open','https://example.com/one'],['/usr/bin/open','http://127.0.0.1/two']])
            run.reset_mock()
            with self.assertRaises(ValueError):mac.open_urls(['https://example.com','file:///bad'])
            run.assert_not_called()
