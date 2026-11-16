import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from deck.ai import Sessions
from deck.core import State
from deck.sources import Providers,window_usage,CodexRollouts

class SourceTests(unittest.TestCase):
    def test_presets_preserve_old_and_repeat(self):
        with tempfile.TemporaryDirectory() as root:
            state=State(Path(root)/'config.json',[]);state.save_buttons([{'id':'mine','kind':'text','text':'한글\nhello','enter':True,'label':'mine'}]);before=state.snapshot()['buttons']
            restored=State(state.path,[]);self.assertEqual(restored.buttons,before)
            restored.add_presets();restored.add_presets()
            self.assertEqual(restored.buttons[:1],before);self.assertEqual(len(restored.buttons),5)
            restored.buttons[1]['text']='custom';restored.save_buttons(restored.buttons);restored.add_presets();self.assertEqual(restored.buttons[1]['text'],'custom')
    def test_weather_validation_cache_error_and_generation(self):
        with tempfile.TemporaryDirectory() as root:
            p=Providers(root,Sessions())
            for bad in [None,{}, {'name':'x','latitude':float('nan'),'longitude':0},{'name':'x','latitude':91,'longitude':0},{'name':'x','latitude':0,'longitude':True}]:
                with self.assertRaises(ValueError):p.validate_location(bad)
            p.location={'name':'시험 위치','latitude':0,'longitude':0}
            with patch.object(p,'get_json',return_value={'current':{'temperature_2m':12,'weather_code':0,'time':'2026-11-14T00:00'}}):p.fetch_weather()
            self.assertEqual(p.snapshot()['weather']['temperature'],12)
            with patch.object(p,'get_json',side_effect=TimeoutError):p.fetch_weather()
            self.assertEqual(p.weather['status'],'error');self.assertEqual(p.weather['temperature'],12)
            p.weather['updatedAt']=time.time()-901;self.assertTrue(p.snapshot()['weather']['stale'])
    def test_usage_is_only_official_percent(self):
        self.assertIsNone(window_usage({'tokens':1000}));self.assertIsNone(window_usage({'usedPercent':float('inf')}));self.assertIsNone(window_usage({'usedPercent':True}))
        self.assertEqual(window_usage({'usedPercent':12,'windowDurationMins':300})['minutes'],300)
    def test_rollout_lifecycle_no_text_or_approval_guess(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'rollout.jsonl';cwd='/test'
            rows=[{'type':'session_meta','payload':{'id':'real-id','cwd':cwd}}, {'type':'event_msg','payload':{'type':'task_started'}},{'type':'event_msg','payload':{'type':'agent_message','message':'sensitive approval request'}}]
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows));s=Sessions();adapter=CodexRollouts(s,root,cwd);adapter.poll();s.register(0,'codex:real-id')
            self.assertEqual(s.snapshot()['slots'][0]['state'],'working');self.assertNotIn('sensitive',json.dumps(s.snapshot()))
            with path.open('a') as f:f.write(json.dumps({'type':'event_msg','payload':{'type':'task_complete'}})+'\n')
            adapter.poll();self.assertEqual(s.snapshot()['slots'][0]['state'],'completed')
    def test_partial_line_awaits_completion(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'r.jsonl';p.write_text(json.dumps({'type':'session_meta','payload':{'id':'s','cwd':'/test'}})+'\n'+ '{"type":"event_msg",')
            s=Sessions();a=CodexRollouts(s,root,'/test');a.poll();self.assertFalse(s.sources)
            with p.open('a') as f:f.write('"payload":{"type":"task_started"}}\n')
            a.poll();self.assertIn('codex:s',s.sources)
    def test_other_projects_do_not_hide_current_session(self):
        import os
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'current.jsonl';p.write_text(json.dumps({'type':'session_meta','payload':{'id':'current','cwd':'/test'}})+'\n'+json.dumps({'type':'event_msg','payload':{'type':'task_started'}})+'\n');os.utime(p,(1,1))
            for n in range(25):(Path(root)/f'other{n}.jsonl').write_text(json.dumps({'type':'session_meta','payload':{'id':str(n),'cwd':'/other'}})+'\n')
            s=Sessions()
            with patch('deck.sources.subprocess.run') as run:
                run.return_value.stdout='';adapter=CodexRollouts(s,root,'/test');adapter.poll();self.assertIn('codex:current',{r['id'] for r in s.snapshot()['sources']});adapter.poll()
            self.assertIn('codex:current',s.sources)
    def test_ended_sessions_do_not_exhaust_capacity(self):
        s=Sessions()
        for n in range(100):s.event('codex:'+str(n),'codex',1,'ended')
        self.assertTrue(s.event('codex:new','codex',1,'working'));self.assertEqual(len(s.sources),100)
    def test_install_preserves_project_statusline_and_idempotence(self):
        from scripts.install_claude_bridge import install
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);(root/'.claude').mkdir();(root/'.claude/settings.json').write_text(json.dumps({'statusLine':{'type':'command','command':'printf project'}}))
            local=root/'.claude/settings.local.json';local.write_text(json.dumps({'permissions':{'allow':['Read']}}));install(root);first=json.loads(local.read_text());install(root)
            self.assertEqual(first,json.loads(local.read_text()));self.assertEqual(first['permissions'],{'allow':['Read']})
            self.assertEqual(json.loads((root/'.deck-data/claude-statusline-previous.json').read_text())['command'],'printf project')
    def test_slow_rollout_does_not_block_hook_or_ttl_loop(self):
        import threading
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as root:
            p=Providers(root,Sessions());stop=threading.Event();entered=threading.Event();release=threading.Event();hooks=threading.Event()
            def slow():entered.set();release.wait(2)
            def hook():hooks.set();stop.set()
            with patch('deck.sources.OrcaActivity.run'),patch.object(p.rollouts,'poll',side_effect=slow),patch.object(p,'poll_hooks',side_effect=hook),patch.object(p,'update_usage'),patch.object(p,'fetch_weather'):
                worker=threading.Thread(target=p.run,args=(stop,SimpleNamespace(preferences={'macSound':False})));worker.start()
                try:
                    self.assertTrue(entered.wait(1));self.assertTrue(hooks.wait(.5));self.assertFalse(release.is_set())
                finally:release.set();worker.join(2)
                self.assertFalse(worker.is_alive())
