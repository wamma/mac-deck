import unittest
from unittest.mock import patch
from deck.macos import Mac
from deck.actions import validate_system_command

class SystemTests(unittest.TestCase):
    def test_supported_commands_and_strict_values(self):
        for action in ['volume_up','volume_down','mute_toggle','brightness_up','brightness_down']:
            self.assertEqual(validate_system_command({'action':action}),{'action':action})
        self.assertEqual(validate_system_command({'action':'volume_set','value':42}),{'action':'volume_set','value':42})
        for body in [{'action':'shell'},{'action':'volume_set','value':101},{'action':'volume_set','value':True},{'action':'brightness_set','value':-1},{'action':'volume_set','value':'50'}]:
            with self.assertRaises(ValueError):validate_system_command(body)

    def test_system_boundary_uses_structured_payload(self):
        mac=Mac.__new__(Mac);seen=[];mac.bridge=lambda p:seen.append(p) or {'status':'verified','value':51}
        result=mac.system_control({'action':'volume_set','value':51})
        self.assertEqual(result['status'],'verified');self.assertEqual(seen,[{'action':'system','operation':'volume_set','value':51}])
        with self.assertRaises(ValueError):mac.system_control({'action':'volume_set','value':'x'})
        self.assertEqual(len(seen),1)


    def test_old_config_load_preserves_buttons_and_preferences(self):
        import tempfile,json
        from pathlib import Path
        from deck.core import State
        buttons=[{'id':'b','label':'복사','kind':'shortcut','key':'c','modifiers':['command']},{'id':'a','label':'붙여넣기','kind':'shortcut','key':'v','modifiers':['command']}]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'buttons.json';raw=json.dumps({'buttons':buttons});path.write_text(raw)
            state=State(path,[])
            self.assertEqual(state.snapshot()['buttons'],buttons);self.assertEqual(state.snapshot()['preferences'],{'macSound':False});self.assertEqual(path.read_text(),raw)
            state.save_preferences({'macSound':True});self.assertEqual(State(path,[]).snapshot()['buttons'],buttons)


    def test_system_verifier_can_pin_device_without_changing_product_policy(self):
        mac=Mac.__new__(Mac);mac.bridge=lambda p:p
        self.assertEqual(mac.system_control({'action':'volume_set','value':45},expected_id=81)['expectedIdentity'],81)
        self.assertNotIn('expectedIdentity',mac.system_control({'action':'volume_set','value':45}))
