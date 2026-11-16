import json,tempfile,unittest,sqlite3,time
from pathlib import Path
from unittest.mock import patch
from deck.ai import Sessions
from deck.sources import CodexRollouts

class DiscoveryTests(unittest.TestCase):
    def test_global_metadata_rename_exact_registration_and_no_body(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);root=base/'sessions';root.mkdir()
            db=sqlite3.connect(base/'state_5.sqlite');db.execute('CREATE TABLE threads(id TEXT,rollout_path TEXT,cwd TEXT,title TEXT,name TEXT,updated_at INTEGER,archived INTEGER)')
            for i in range(35):
                path=root/f'{i}.jsonl';path.write_text(json.dumps({'type':'session_meta','payload':{'id':str(i),'cwd':f'/projects/p{i%3}'}})+'\n'+json.dumps({'type':'event_msg','timestamp':'2026-11-15T00:00:00Z','payload':{'type':'task_complete','last_agent_message':'PRIVATE RESPONSE'}})+'\n')
                db.execute('INSERT INTO threads VALUES(?,?,?,?,?,?,0)',(str(i),str(path),f'/projects/p{i%3}','같은 제목','',int(time.time())+i))
            db.commit();s=Sessions();a=CodexRollouts(s,root,'/unrelated');a.poll();snap=s.snapshot()
            self.assertEqual(len(snap['sources']),35);self.assertEqual(len(snap['slots']),12)
            self.assertNotIn('PRIVATE RESPONSE',json.dumps(s.tasks));self.assertEqual(len({r['cwd'] for r in snap['sources']}),3)
            s.register(0,'codex:0');self.assertEqual(s.slots[0],'codex:0')
            with self.assertRaises(ValueError):s.register(1,'codex:0')
            db.execute("UPDATE threads SET name='새 작업명' WHERE id='0'");db.commit();a.poll()
            row=next(r for r in s.snapshot()['sources'] if r['id']=='codex:0');self.assertEqual(row['taskName'],'새 작업명');self.assertEqual(row['registeredSlot'],0)
            self.assertNotIn('PRIVATE RESPONSE',json.dumps(s.snapshot()['sources']))
            a.LIMIT=2;a.poll();self.assertTrue(s.snapshot()['discovery']['truncated']);self.assertIn('codex:0',{r['id'] for r in s.snapshot()['sources']})
            db.close()
    def test_metadata_does_not_refresh_lifecycle_or_proof(self):
        now=[0];s=Sessions(clock=lambda:now[0]);s.discover([{'id':'codex:s','title':'title','cwd':'/a','updatedAt':100}])
        s.event('codex:s','codex',1,'idle',eventAt=100);s.register(0,'codex:s');now[0]=31
        s.discover([{'id':'codex:s','title':'renamed','cwd':'/a','updatedAt':200}]);row=s.snapshot()['sources'][0]
        self.assertEqual(row['state'],'offline');self.assertEqual(row['taskName'],'renamed');self.assertEqual(row['stateChangedAt'],100)
    def test_fallback_all_projects_and_missing_title(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'test.jsonl';path.write_text(json.dumps({'type':'session_meta','payload':{'id':'stable-id','cwd':'/other/project'}})+'\n')
            s=Sessions();CodexRollouts(s,directory,'/current').poll();row=s.snapshot()['sources'][0]
            self.assertIn('project',row['taskName']);self.assertEqual(row['state'],'offline');s.register(0,row['id'])

    def test_index_path_identity_mismatch_never_adopts_other_session(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'sessions';root.mkdir();path=root/'r.jsonl'
            path.write_text(json.dumps({'type':'session_meta','payload':{'id':'different','cwd':'/test'}})+'\n'+json.dumps({'type':'event_msg','payload':{'type':'task_started'}})+'\n')
            s=Sessions();a=CodexRollouts(s,root)
            with patch.object(a,'catalog',return_value=([{'id':'codex:expected','path':path,'cwd':'/test','title':'test','updatedAt':100}],1,'test index')):a.poll()
            self.assertFalse(s.sources);self.assertEqual(s.snapshot()['sources'][0]['state'],'offline')
