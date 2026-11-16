import tempfile,unittest
from pathlib import Path
from deck.core import defaults,State,preferred_app_order

NAMES=['Arc','Orca','Safari','System Settings','Finder','KakaoTalk','Notes','Claude','zoom.us']
APPS=[{'id':'id'+str(i),'name':n} for i,n in enumerate(NAMES)]+[{'id':'chrome','name':'Google Chrome'},{'id':'extra','name':'Extra'}]
class AppOrderTests(unittest.TestCase):
    def test_defaults_installed_only_in_requested_order(self):
        self.assertEqual([b['app'] for b in defaults(APPS) if b['kind']=='app'],['id'+str(i) for i in range(9)])
        missing=[a for a in APPS if a['name']!='zoom.us'];self.assertEqual(len([b for b in defaults(missing) if b['kind']=='app']),8)
    def test_reorder_preserves_other_positions_labels_ids_and_extra_order(self):
        app=lambda id,app,label:{'id':id,'kind':'app','app':app,'label':label}
        buttons=[app('mine7','id7','내 Claude'),{'id':'save','kind':'shortcut','key':'s','modifiers':['command'],'label':'저장'},app('chrome-tile','chrome','크롬'),app('extra-tile','extra','추가'),app('mine0','id0','내 Arc')]
        result,missing=preferred_app_order(buttons,APPS)
        self.assertEqual(result[1],buttons[1]);self.assertEqual([b['app'] for b in result if b['kind']=='app'],['id'+str(i) for i in range(9)]+['extra'])
        self.assertEqual(next(b for b in result if b.get('app')=='id0')['id'],'mine0');self.assertEqual(next(b for b in result if b.get('app')=='id7')['label'],'내 Claude');self.assertFalse(missing)
        again,_=preferred_app_order(result,APPS);self.assertEqual(again,result)
    def test_chrome_replacement_and_user_edit_survives_reload(self):
        old=[{'id':'chrome-tile','kind':'app','app':'chrome','label':'크롬'}];ordered,_=preferred_app_order(old,APPS)
        self.assertEqual(ordered[0]['id'],'chrome-tile');self.assertEqual(ordered[0]['label'],'Arc')
        with tempfile.TemporaryDirectory() as root:
            state=State(Path(root)/'buttons.json',APPS);state.save_buttons(list(reversed(ordered)));self.assertEqual(State(state.path,APPS).buttons,list(reversed(ordered)))

    def test_legacy_chrome_label_on_existing_arc_is_corrected(self):
        old=[{'id':'keep-id','kind':'app','app':'id0','label':'크롬'}]
        result,_=preferred_app_order(old,APPS);self.assertEqual(result[0]['id'],'keep-id');self.assertEqual(result[0]['label'],'Arc')
