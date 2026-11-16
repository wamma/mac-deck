import json,tempfile,unittest
from pathlib import Path
from deck.ai import Sessions

class TaskMetadataTests(unittest.TestCase):
    def test_times_completion_alias_persist_without_heartbeat_rewriting(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'slots.json';now=[10.];s=Sessions(path,clock=lambda:now[0])
            s.event('codex:s','codex',1,'working',eventAt=1700000000,providerTitle='작업 제목');s.register(0,'codex:s')
            s.set_alias(0,'codex:s','내 작업')
            s.event('codex:s','codex',2,'completed',eventAt=1700000010,providerTitle='작업 제목',completionPreview='실제 최종 응답')
            s.event('codex:s','codex',3,'working',eventAt=1700000020,providerTitle='작업 제목')
            now[0]+=20;s.heartbeat('codex:s');row=s.snapshot()['slots'][0]
            self.assertEqual(row['taskName'],'내 작업');self.assertEqual(row['stateChangedAt'],1700000020)
            self.assertEqual(row['lastCompleted']['at'],1700000010);self.assertEqual(row['lastCompleted']['preview'],'실제 최종 응답')
            now[0]+=31;row=s.snapshot()['slots'][0];self.assertEqual(row['state'],'offline');self.assertEqual(row['lastCompleted']['at'],1700000010)
            restored=Sessions(path);row=restored.snapshot()['slots'][0];self.assertEqual(row['state'],'offline');self.assertEqual(row['taskName'],'내 작업');self.assertEqual(row['stateChangedAt'],1700000020)
            restored.event('codex:s','codex',1,'working',eventAt=1600000000);self.assertEqual(restored.snapshot()['slots'][0]['stateChangedAt'],1700000020)
    def test_minimum_fields_missing_time_no_invented_result_and_alias_race(self):
        s=Sessions();s.event('claude:x','claude',1,'completed',providerTitle='x'*100,completionPreview='y'*1000);s.register(0,'claude:x')
        row=s.snapshot()['slots'][0];self.assertIsNone(row['stateChangedAt']);self.assertIsNone(row['lastCompleted'])
        s.event('claude:x','claude',2,'completed',eventAt=1700000010,completionPreview='y'*1000,stateTimeSource='hook-received')
        row=s.snapshot()['slots'][0];self.assertLessEqual(len(row['lastCompleted']['preview']),240);self.assertEqual(row['stateTimeSource'],'hook-received')
        with self.assertRaises(ValueError):s.set_alias(0,'other','wrong')
        with self.assertRaises(ValueError):s.set_alias(0,'claude:x','x'*81)
        s.set_alias(0,'claude:x','<script>literal</script>');self.assertEqual(s.snapshot()['slots'][0]['taskName'],'<script>literal</script>')
        s.event('claude:x','claude',1,'completed',eventAt=1800000000,completionPreview='OUT OF ORDER')
        self.assertNotIn('OUT OF ORDER',json.dumps(s.snapshot()))

class ProviderTaskTests(unittest.TestCase):
    def test_codex_only_title_and_final_excerpt(self):
        from deck.sources import CodexRollouts
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'sessions';root.mkdir()
            (root.parent/'session_index.jsonl').write_text(json.dumps({'id':'test','thread_name':'시험 작업'})+'\n')
            rows=[{'type':'session_meta','payload':{'id':'test','cwd':'/test'}},{'type':'event_msg','timestamp':'2026-11-14T01:00:00Z','payload':{'type':'task_complete','last_agent_message':'결과 '*200,'prompt':'DO NOT COLLECT'}}]
            (root/'test.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            s=Sessions();s.discover([{'id':'codex:test','title':'시험 작업','cwd':'/test'}]);s.register(0,'codex:test');CodexRollouts(s,root,'/test').poll();row=s.snapshot()['slots'][0]
            self.assertEqual(row['taskName'],'시험 작업');self.assertEqual(row['lastCompleted']['at'],1794618000);self.assertEqual(len(row['lastCompleted']['preview']),240)
            self.assertNotIn('DO NOT COLLECT',json.dumps(s.snapshot()))
    def test_claude_statusline_does_not_change_hook_time(self):
        import io,sys
        from unittest.mock import patch
        from scripts import claude_bridge
        with tempfile.TemporaryDirectory() as directory:
            def send(mode,data,now):
                with patch.object(sys,'argv',['bridge',mode,'--data-dir',directory]),patch.object(sys,'stdin',io.TextIOWrapper(io.BytesIO(json.dumps(data).encode()))),patch.object(claude_bridge,'process_identity',return_value=None),patch.object(claude_bridge.time,'time',return_value=now),patch('builtins.print'):
                    claude_bridge.main()
            send('hook',{'session_id':'synthetic','hook_event_name':'Stop','last_assistant_message':'허용 결과','transcript':'PRIVATE'},100)
            send('statusline',{'session_id':'synthetic'},200)
            data=json.loads(next((Path(directory)/'claude-events').glob('*.json')).read_text())
            self.assertEqual(data['stateChangedAt'],100);self.assertEqual(data['lastCompletedAt'],100);self.assertEqual(data['completionPreview'],'허용 결과');self.assertNotIn('PRIVATE',json.dumps(data))
