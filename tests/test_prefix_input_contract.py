"""Authored paused-input fixtures; no game traces, assets or hosts."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts import prefix_input_contract as contract
from scripts import replay_reset as reset
from tests.test_reset_replay import status


def fixture(desktop, *, prior=False):
    actions = [['advance', '600'], ['input', '1'], ['advance', '600'], ['input', '0']]
    actions += [['advance', '600']] * 22 + [['advance', '280']]
    actions += [['status']] * 77 + [['capture']] * 10 + [['quit']]
    frame = mask = 0
    states = [status(desktop=desktop)]
    for words in actions:
        if words[0] == 'capture' or words[0] == 'quit':
            continue
        if words[0] == 'advance':
            frame += int(words[1])
        raw = status(frame, desktop, native=frame * 10 if desktop else 0,
                     interpreted=0 if desktop else frame * 10)
        raw['host']['buttons'][0] = mask
        if words[0] == 'input':
            mask = int(words[1])
            if not prior:
                raw['host']['buttons'][0] = mask
        states.append(raw)
    return {'error': None, 'states': states, 'actions': actions,
            'images': [{'frame': frame}] * 10, 'inputs_unchanged': {'synthetic': True},
            'child_stopped': True, 'returncode': 0}


class PrefixInputContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.reference = fixture(False, prior=True)
        self.selected = fixture(True)
        self.actual = fixture(True, prior=True)
        self.ref = self.save('reference.json', self.reference)
        self.sel = self.save('selected.json', self.selected)

    def save(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value), encoding='utf-8')
        return reset.binding(path)

    def checker(self, **options):
        return contract.PrefixInputCheck(self.ref, self.sel, None,
                                        actions=options.get('actions', self.reference['actions'][:-1]))

    def feed(self, actual=None, *, mutate_ack=None):
        actual = actual or self.actual
        checker = self.checker()
        checker.state(actual['states'][0], -1, None)
        index = 0
        for ai, words in enumerate(self.reference['actions'][:-1]):
            if words[0] not in ('advance', 'input', 'status'):
                continue
            index += 1
            ack = None
            if words[0] == 'input':
                ack = {'action_index': ai, 'command': 'set_input', 'port': 0,
                       'mask': int(words[1]), 'response': {'id': ai + 10, 'ok': True}}
                if mutate_ack:
                    mutate_ack(ack)
            checker.state(actual['states'][index], ai, words, ack=ack)
        return checker.finish()

    def test_complete_prior_and_requested_variants_preserve_raw(self):
        before = copy.deepcopy(self.actual)
        result = self.feed()
        self.assertEqual(before, self.actual)
        self.assertEqual(result['frames'], 14680)
        self.assertEqual(len(result['input_observation_contract']['actual_input_acks']), 2)
        self.assertFalse(result['input_observation_contract']['historical_ack_retained'])
        self.assertEqual(len(result['input_observation_contract']['observations']['reference']), 2)
        self.feed(fixture(True))

    def test_bound_plan_change_rejected(self):
        actions = copy.deepcopy(self.reference['actions'][:-1])
        actions[1] = ['input', '2']
        with self.assertRaises(ValueError): self.checker(actions=actions)

    def test_binding_mismatch_rejected(self):
        Path(self.ref['path']).write_text('{}', encoding='utf-8')
        with self.assertRaises(ValueError): self.checker()

    def test_ack_wrong_intent_failure_and_boolean_types_rejected(self):
        for change in (lambda a: a.update(mask=2), lambda a: a.update(port=1),
                       lambda a: a.update(action_index=True),
                       lambda a: a['response'].update(ok=False),
                       lambda a: a['response'].update(id=True),
                       lambda a: a['response'].update(applied=True)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.feed(mutate_ack=change)

    def test_missing_ack_rejected(self):
        checker = self.checker()
        checker.state(self.actual['states'][0], -1, None)
        checker.state(self.actual['states'][1], 0, ['advance', '600'])
        with self.assertRaises(ValueError): checker.state(self.actual['states'][2], 1, ['input', '1'])

    def test_immediate_clock_cpu_source_audio_and_other_controller_drift_rejected(self):
        changes = (lambda s: s.update(ticks=s['ticks'] + 1),
                   lambda s: s['host']['cpu'].update(a=1),
                   lambda s: s['host']['cpu']['mpr'].__setitem__(0, 1),
                   lambda s: s['host']['cpu']['instruction_generations'].__setitem__(0, 2),
                   lambda s: s['host']['cpu']['instruction_bytes'].__setitem__(0, 18),
                   lambda s: s['host']['audio_output'].update(pcm_hash=7),
                   lambda s: s['host']['buttons'].__setitem__(1, 1),
                   lambda s: s['host']['buttons'].__setitem__(0, 2))
        for change in changes:
            raw = copy.deepcopy(self.actual); change(raw['states'][2])
            with self.subTest(change=change), self.assertRaises(ValueError): self.feed(raw)

    def test_historical_headless_and_selected_static_drift_rejected(self):
        for which in ('reference', 'selected'):
            value = copy.deepcopy(getattr(self, which)); value['states'][2]['host']['cpu']['x'] = 1
            binding = self.save(which + '-bad.json', value)
            with self.subTest(which=which), self.assertRaises(ValueError):
                contract.PrefixInputCheck(binding if which == 'reference' else self.ref,
                                          binding if which == 'selected' else self.sel, None,
                                          actions=self.reference['actions'][:-1])

    def test_settled_mask_and_noninput_drift_rejected(self):
        for index, change in ((3, lambda s: s['host']['buttons'].__setitem__(0, 0)),
                              (5, lambda s: s['host']['cpu'].update(a=2)),
                              (5, lambda s: s['host'].update(native_steps=s['host']['native_steps'] + 1))):
            raw = copy.deepcopy(self.actual); change(raw['states'][index])
            with self.subTest(index=index), self.assertRaises(ValueError): self.feed(raw)

    def test_wrong_state_action_position_rejected(self):
        checker = self.checker()
        with self.assertRaises(ValueError): checker.state(self.actual['states'][0], 0, ['status'])

    def test_input_view_changes_only_one_copied_button(self):
        before = self.actual['states'][1]; raw = self.actual['states'][2]
        view, _ = contract.input_view(before, raw, 1, desktop=True)
        expected = copy.deepcopy(raw); expected['host']['buttons'][0] = 1
        self.assertEqual(view, expected)
        self.assertEqual(raw['host']['buttons'], [0] * 5)


if __name__ == '__main__':
    unittest.main()
