import copy
import unittest
from unittest.mock import patch
from deck.orca_activity import activity_rows,OrcaActivity
from deck.ai import Sessions


def payload(count=1,state='working'):
    return {'ok':True,'_meta':{'runtimeId':'fixture-runtime'},'result':{'truncated':False,'worktrees':[{'worktreeId':'fixture-worktree','worktreeInstanceId':'fixture-instance','hasAttachedPty':True,'displayName':'Synthetic task','repo':'Synthetic project','agents':[{'paneKey':'pane-'+str(n),'state':state,'agentType':'codex','mainAgent':{'state':state,'stateStartedAt':100000},'updatedAt':(101+n)*1000,'prompt':'DO NOT COLLECT','lastAssistantMessage':'DO NOT COLLECT'} for n in range(count)]}]}}

class OrcaActivityTests(unittest.TestCase):
    def test_recent_order_cap_ties_and_manual_settings_unchanged(self):
        data=payload(20);rows,_=activity_rows(data,150)
        sessions=Sessions();sessions.slots[0]='manual-session';before=copy.deepcopy(sessions.slots)
        sessions.set_activity(rows);view=sessions.snapshot()['activity']
        self.assertEqual(len(view['rows']),12);self.assertEqual(view['total'],20)
        self.assertEqual([r['lastActivityAt'] for r in view['rows']],list(range(120,108,-1)))
        self.assertEqual(sessions.slots,before);self.assertFalse(sessions.sources);self.assertFalse(sessions.proofs)
        for a in data['result']['worktrees'][0]['agents']:a['updatedAt']=101000
        rows,_=activity_rows(data,150);self.assertEqual([r['id'] for r in rows],sorted(r['id'] for r in rows))
        self.assertNotIn('DO NOT COLLECT',str(rows))
    def test_under_cap_empty_completed_monitoring_and_lease_failure(self):
        clock=[0];sessions=Sessions(clock=lambda:clock[0]);rows,_=activity_rows(payload(2),150);sessions.set_activity(rows)
        self.assertEqual(len(sessions.snapshot()['activity']['rows']),2)
        sessions.activity_failed();self.assertEqual(sessions.snapshot()['activity']['status'],'degraded')
        clock[0]=31;self.assertEqual(sessions.snapshot()['activity']['rows'],[])
        data=payload(1,'done');data['result']['worktrees'][0]['agents'][0]['state']='working'
        rows,_=activity_rows(data,150);self.assertEqual(rows,[]) # monitor wrapper cannot revive done main
        sessions.set_activity(rows);self.assertEqual(sessions.snapshot()['activity']['status'],'ok')
        data=payload();data['result']['worktrees'][0]['hasAttachedPty']=False
        self.assertEqual(activity_rows(data,150)[0],[])
    def test_state_time_is_source_time_identity_survives_reorder_and_changes_with_incarnation(self):
        data=payload(2);rows,_=activity_rows(data,150);ident=rows[0]['id']
        data['result']['worktrees'][0]['agents'].reverse()
        self.assertEqual(activity_rows(data,150)[0][0]['id'],ident)
        self.assertEqual(activity_rows(data,999999)[0][0]['lastActivityAt'],102)
        data['result']['worktrees'][0]['worktreeInstanceId']='new-incarnation'
        self.assertNotEqual(activity_rows(data,150)[0][0]['id'],ident)
        data=payload(1,'waiting');self.assertEqual(activity_rows(data,119)[0][0]['state'],'working')
        self.assertEqual(activity_rows(data,120)[0][0]['state'],'input-required')
        data['result']['worktrees'][0]['agents'][0]['mainAgent']['state']='done'
        self.assertEqual(activity_rows(data,121)[0],[])
    def test_poll_failure_keeps_last_observation_without_inventing_completion(self):
        sessions=Sessions();rows,_=activity_rows(payload(),150);sessions.set_activity(rows)
        with patch('deck.orca_activity.subprocess.run',side_effect=OSError('unavailable')):OrcaActivity(sessions).poll()
        view=sessions.snapshot()['activity'];self.assertEqual(view['status'],'degraded');self.assertEqual(view['rows'][0]['state'],'working')
