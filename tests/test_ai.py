import unittest
from deck.ai import Sessions

class SessionTests(unittest.TestCase):
    def setUp(self):
        self.now=100.; self.s=Sessions(clock=lambda:self.now)
        self.s.event('codex:s1','codex',1,'idle')
        self.s.register(0,'codex:s1')
    def test_delay_cancel_order_and_duplicate(self):
        self.s.event('codex:s1','codex',2,'input-required'); self.now+=19.999
        self.assertEqual(self.s.snapshot()['slots'][0]['state'],'working')
        self.s.event('codex:s1','codex',1,'completed')
        self.s.event('codex:s1','codex',2,'input-required');self.now+=.001
        self.assertEqual(self.s.snapshot()['slots'][0]['state'],'input-required')
        self.assertEqual(len(self.s.drain_notifications()),1)
        self.s.snapshot();self.assertEqual(self.s.drain_notifications(),[])
        self.s.event('codex:s1','codex',3,'working');self.s.event('codex:s1','codex',4,'input-required')
        self.now+=10;self.s.event('codex:s1','codex',5,'completed');self.now+=15
        self.assertEqual(self.s.snapshot()['slots'][0]['state'],'completed')
    def test_heartbeat_idle_and_expiry(self):
        self.now+=29;self.s.heartbeat('codex:s1');self.now+=29
        self.assertEqual(self.s.snapshot()['slots'][0]['state'],'idle')
        self.now+=2;self.assertEqual(self.s.snapshot()['slots'][0]['state'],'offline')
    def test_session_does_not_rebind(self):
        self.s.event('codex:s2','codex',1,'working');self.now+=31
        self.assertEqual(self.s.snapshot()['slots'][0]['state'],'offline')
        self.s.register(0,None);self.assertEqual(self.s.snapshot()['slots'][0]['state'],'unregistered')
    def test_reply_revision_expiry_one_shot(self):
        self.s.event('codex:s1','codex',2,'input-required',replySupported=True);self.now+=20
        revision=self.s.snapshot()['slots'][0]['revision']
        with self.assertRaises(ValueError):self.s.consume_reply(0,revision,'a')
        self.s.bind(0,{'pid':1,'windowId':2})
        revision=self.s.snapshot()['slots'][0]['revision']
        proof=self.s.detail(0)
        with self.assertRaises(ValueError):self.s.consume_reply(0,revision,'enter','bad')
        self.s.consume_reply(0,revision,'enter',proof['nonce'])
        with self.assertRaises(ValueError):self.s.consume_reply(0,revision,'enter',proof['nonce'])
    def test_expired_pending_never_replays_and_end_cancels(self):
        self.s.event('codex:s1','codex',2,'input-required');self.now+=31
        self.assertEqual(self.s.snapshot()['slots'][0]['state'],'offline')
        self.s.heartbeat('codex:s1');self.assertEqual(self.s.snapshot()['slots'][0]['state'],'offline')
        self.assertEqual(self.s.drain_notifications(),[])
        self.s.event('codex:s1','codex',3,'working');self.s.event('codex:s1','codex',4,'input-required');self.now+=10
        self.s.event('codex:s1','codex',5,'ended');self.now+=15;self.assertEqual(self.s.snapshot()['slots'][0]['state'],'offline')
    def test_new_question_invalidates_old_proof(self):
        self.s.event('codex:s1','codex',2,'input-required',replySupported=True);self.now+=20;self.s.bind(0,{'pid':1,'windowId':2});proof=self.s.detail(0)
        self.s.event('codex:s1','codex',3,'working');self.s.event('codex:s1','codex',4,'input-required',replySupported=True);self.now+=20
        with self.assertRaises(ValueError):self.s.consume_reply(0,proof['revision'],'enter',proof['nonce'])
    def test_detail_expiry_and_unsupported_source(self):
        self.s.event('codex:s1','codex',2,'input-required',replySupported=True);self.now+=20;self.s.bind(0,{'pid':1,'windowId':2});proof=self.s.detail(0);self.now+=10
        with self.assertRaises(ValueError):self.s.consume_reply(0,proof['revision'],'up',proof['nonce'])
        self.s.heartbeat('codex:s1');proof=self.s.detail(0);self.s.sources['codex:s1']['replySupported']=False
        with self.assertRaises(ValueError):self.s.consume_reply(0,proof['revision'],'enter',proof['nonce'])
    def test_second_question_restarts_continuous_delay(self):
        self.s.event('codex:s1','codex',2,'input-required',question='first');self.now+=19
        self.s.event('codex:s1','codex',3,'input-required',question='second');self.now+=1
        self.assertEqual(self.s.snapshot()['slots'][0]['state'],'working')
        self.now+=19;self.assertEqual(self.s.snapshot()['slots'][0]['state'],'input-required')
    def test_initial_existing_wait_does_not_replay_mac_notification(self):
        self.s.event('claude:old','claude',1,'input-required',baseline=True);self.s.register(1,'claude:old')
        self.s.snapshot();self.assertEqual(self.s.drain_notifications(),[])
        self.s.event('claude:old','claude',2,'working');self.s.event('claude:old','claude',3,'input-required',question='new')
        self.assertEqual(len(self.s.drain_notifications()),1)
