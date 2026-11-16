import hashlib,json,shlex,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from scripts.install_claude_usage import install,restore,prepare
from deck.sources import Providers
from deck.ai import Sessions

class ClaudeUsageTests(unittest.TestCase):
    def test_preview_install_delegate_restore_and_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);project=root/'project';project.mkdir();data=root/'central';home=root/'home.json';home.write_text('{}')
            settings=project/'.claude/settings.local.json';settings.parent.mkdir()
            command=shlex.join([sys.executable,'-c','import sys,hashlib; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest());print("delegate stderr",file=sys.stderr);sys.exit(7)'])
            original={'statusLine':{'type':'command','command':command,'padding':3,'refreshInterval':12},'permissions':{'allow':['Read']}};settings.write_text(json.dumps(original));before=settings.read_bytes()
            self.assertTrue(install(project,data,home_settings=home)['preview']);self.assertEqual(settings.read_bytes(),before);self.assertFalse(data.exists())
            self.assertTrue(install(project,data,True,home_settings=home)['changed']);self.assertFalse(install(project,data,True,home_settings=home)['changed'])
            installed=json.loads(settings.read_text());self.assertEqual(installed['statusLine']['padding'],3);self.assertEqual(installed['statusLine']['refreshInterval'],12)
            raw=json.dumps({'session_id':'synthetic-session','prompt':'SECRET PROMPT','last_assistant_message':'SECRET RESPONSE','rate_limits':{'five_hour':{'used_percentage':12,'resets_at':time.time()+100}}}).encode()
            run=subprocess.run(installed['statusLine']['command'],shell=True,input=raw,capture_output=True);self.assertEqual(run.returncode,7);self.assertEqual(run.stderr,b'delegate stderr\n');self.assertEqual(run.stdout.decode().strip(),hashlib.sha256(raw).hexdigest())
            payload=json.loads(next((data/'claude-usage').glob('*.json')).read_text());self.assertEqual(payload['five_hour']['used_percentage'],12);self.assertNotIn('SECRET',json.dumps(payload));self.assertNotIn('synthetic-session',json.dumps(payload));self.assertFalse((data/'claude-events').exists())
            modified={**installed,'extra':'keep'};settings.write_text(json.dumps(modified));restore(project,data,True);self.assertEqual(json.loads(settings.read_text()),{**original,'extra':'keep'})
            install(project,data,True,home_settings=home);edited=json.loads(settings.read_text());edited['statusLine']['command']='user changed';settings.write_text(json.dumps(edited))
            with self.assertRaises(ValueError):restore(project,data,True)
            self.assertEqual(json.loads(settings.read_text()),edited)
    def test_inherited_project_command_and_shared_root_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);main=root/'main';other=root/'other';main.mkdir();other.mkdir();data=root/'central';home=root/'home.json';home.write_text(json.dumps({'statusLine':{'command':'printf HOME','padding':4}}))
            (other/'.claude').mkdir();(other/'.claude/settings.json').write_text(json.dumps({'statusLine':{'command':'printf PROJECT','padding':4}}))
            with patch('scripts.install_claude_usage.settings_root',return_value=(main,[main,other])):
                report=install(other,data,home_settings=home);self.assertEqual(report['sharedWorktreeCount'],2);self.assertEqual(report['settingsPath'],str(main/'.claude/settings.local.json'))
                with self.assertRaises(ValueError):install(other,data,True,home_settings=home)
                install(other,data,True,True,home)
                installed=json.loads((main/'.claude/settings.local.json').read_text());raw=json.dumps({'session_id':'test','cwd':str(other)}).encode()
                run=subprocess.run(installed['statusLine']['command'],shell=True,input=raw,capture_output=True);self.assertEqual(run.stdout,b'PROJECT')
                with self.assertRaises(ValueError):install(other,root/'another-central',True,True,home)
                restore(other,data,True);self.assertFalse((main/'.claude/settings.local.json').exists());self.assertEqual(json.loads(home.read_text())['statusLine']['command'],'printf HOME')
    def test_usage_signal_fields_stale_and_order_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            sessions=Sessions();p=Providers(directory,sessions);self.assertEqual(p.snapshot()['usage']['claude']['status'],'no_signal')
            path=Path(directory)/'claude-usage';path.mkdir();file=path/'synthetic.json';now=time.time()
            file.write_text(json.dumps({'usageObserved':True,'usageAt':now,'projectLabel':'synthetic'}));p.poll_hooks();self.assertEqual(p.snapshot()['usage']['claude']['status'],'no_limits')
            file.write_text(json.dumps({'usageObserved':True,'usageAt':now+1,'five_hour':{'used_percentage':0}}));p.poll_hooks();self.assertEqual(p.snapshot()['usage']['claude']['windows'][0]['usedPercent'],0)
            file.write_text(json.dumps({'usageObserved':True,'usageAt':now-100,'five_hour':{'used_percentage':99}}));p.poll_hooks();self.assertEqual(p.snapshot()['usage']['claude']['windows'][0]['usedPercent'],0)
            with patch('deck.sources.time.time',return_value=now+1000):self.assertTrue(p.snapshot()['usage']['claude']['stale'])
            self.assertFalse(sessions.sources);self.assertEqual(sessions.slots,[None]*12)
    def test_collector_failure_does_not_break_delegate(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);project=root/'p';project.mkdir();home=root/'home.json';home.write_text(json.dumps({'statusLine':{'command':'printf ORIGINAL'}}));data=root/'central';install(project,data,True,home_settings=home)
            _,_,manifest,_,_=prepare(project,data,home);bad=root/'file';bad.write_text('not a directory')
            run=subprocess.run([sys.executable,'scripts/claude_usage_bridge.py','--manifest',str(manifest),'--data-dir',str(bad)],input=b'{"session_id":"test"}',capture_output=True)
            self.assertEqual(run.returncode,0);self.assertEqual(run.stdout,b'ORIGINAL')

    def test_runtime_account_config_dir_delegate_and_no_option_overwrite(self):
        from scripts.claude_usage_bridge import delegate_status
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);account=root/'account';account.mkdir();(account/'settings.json').write_text(json.dumps({'statusLine':{'command':'printf ACCOUNT'}}))
            manifest={'hadLocalStatusLine':False,'projectRoot':str(root),'homeSettings':str(root/'absent.json')}
            with patch.dict('os.environ',{'CLAUDE_CONFIG_DIR':str(account)}):self.assertEqual(delegate_status(manifest,{}).get('command'),'printf ACCOUNT')
            other=root/'worktree';other.mkdir();(other/'.claude').mkdir();(other/'.claude/settings.json').write_text(json.dumps({'statusLine':{'command':'printf WORKTREE','padding':9}}))
            with patch('scripts.install_claude_usage.settings_root',return_value=(root,[root,other])):
                report=install(other,root/'data',home_settings=root/'absent.json');self.assertEqual(report['sharedOptionVariants'],2)
                with self.assertRaises(ValueError):install(other,root/'data',True,True,root/'absent.json')
                self.assertFalse((root/'.claude/settings.local.json').exists())

    def test_project_root_subdirectories_and_override_precedence(self):
        from scripts.claude_usage_bridge import delegate_status
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);main=base/'main';linked=base/'linked';home=base/'home.json';account=base/'account';account.mkdir()
            home.write_text(json.dumps({'statusLine':{'command':'printf HOME'}}))
            (account/'settings.json').write_text(json.dumps({'statusLine':{'command':'printf ACCOUNT'}}))
            for root,label in [(main,'MAIN'),(linked,'LINKED')]:
                (root/'src/.claude').mkdir(parents=True);(root/'.claude').mkdir()
                (root/'.claude/settings.json').write_text(json.dumps({'statusLine':{'command':'printf '+label}}))
                (root/'src/.claude/settings.json').write_text(json.dumps({'statusLine':{'command':'printf WRONG'}}))
            manifest={'projectRoot':str(main),'allowedProjectRoots':[str(main),str(linked)],'hadLocalStatusLine':False,'homeSettings':str(home)}
            def payload(root):return {'cwd':str(root/'src'),'workspace':{'current_dir':str(root/'src'),'project_dir':str(root)}}
            for root,label in [(main,'MAIN'),(linked,'LINKED')]:
                self.assertEqual(delegate_status(manifest,payload(root))['command'],'printf '+label)
            local=linked/'.claude/settings.local.json';local.write_text(json.dumps({'statusLine':{'command':'printf LEGACY'}}))
            self.assertEqual(delegate_status(manifest,payload(linked))['command'],'printf LEGACY')
            self.assertEqual(delegate_status({**manifest,'hadLocalStatusLine':True,'previousLocalStatusLine':{'command':'printf MAINLOCAL'}},payload(linked))['command'],'printf MAINLOCAL')
            local.unlink();(linked/'.claude/settings.json').unlink()
            with patch.dict('os.environ',{'CLAUDE_CONFIG_DIR':str(account)}):
                self.assertEqual(delegate_status(manifest,payload(linked))['command'],'printf ACCOUNT')
            for invalid in [payload(base/'unregistered'),{'cwd':str(linked/'src'),'workspace':{'project_dir':str(main)}},{'cwd':str(main/'src')},{'workspace':{'project_dir':'relative'}}]:
                self.assertEqual(delegate_status(manifest,invalid),{})
            escape=main/'escape';escape.symlink_to(linked,target_is_directory=True)
            self.assertEqual(delegate_status(manifest,{'cwd':str(escape/'src'),'workspace':{'project_dir':str(main)}}),{})
