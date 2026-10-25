"""Bound opening-plan input observations; raw states are never modified.

An acknowledged input intent need not have appeared in the immediately following
paused snapshot. Only controller zero at a literal input action receives a
comparison view. Subsequent settled observations retain their full meaning.
"""
from __future__ import annotations

import copy
from . import replay_reset as reset
from . import replay_reset_extension as extension


def input_ack(value, action_index, mask):
    """Validate the actual command/response pair, not a fabricated applied ACK."""
    reset.keys(value, {'action_index', 'command', 'port', 'mask', 'response'}, 'input ACK record')
    reset.integer(value['action_index'], label='input action index')
    reset.integer(value['port'], 4, label='input port')
    reset.integer(value['mask'], 255, label='input mask')
    reset.require(value['action_index'] == action_index and value['command'] == 'set_input'
                  and value['port'] == 0 and value['mask'] == mask, 'ACK must bind the literal input intent')
    response = value['response']
    reset.keys(response, {'id', 'ok'}, 'set_input response')
    reset.integer(response['id'], label='input response id')
    reset.require(response['ok'] is True, 'Successful set_input response required')
    return copy.deepcopy(value)


def input_view(previous, raw, mask, *, desktop):
    """Validate this run's paused state before changing one copied controller."""
    reset.integer(mask, 255, label='literal input mask')
    if desktop:
        proof = extension.validate_input_status(previous, raw, mask)
    else:
        before = reset.normalize_status(previous, desktop=False)
        after = reset.normalize_status(raw, desktop=False)
        prior = before['host']['buttons']
        reset.require(after['host']['buttons'] in (prior, [mask, 0, 0, 0, 0]),
                      'Headless immediate input must be prior or requested')
        observed = copy.deepcopy(after['host']['buttons'])
        after['host']['buttons'][0] = prior[0]
        reset.require(before == after, 'Headless input cannot advance or alter guest/source/CD/PCM')
        proof = {'classification': 'input-intent-status', 'previous_buttons': copy.deepcopy(prior),
                 'requested_buttons': [mask, 0, 0, 0, 0], 'observed_buttons': observed,
                 'guest_time_advanced': False, 'static_guest_source_pcm': True}
    view = copy.deepcopy(raw)
    view['host']['buttons'][0] = mask
    return view, proof


class PrefixInputCheck:
    """Compare the complete bound opening through the unchanged prefix checker.

    Historical receipts bind their literal action journals, not retained input
    ACKs. Fresh executions must supply each real ACK. This difference is explicit
    in the returned evidence and never presented as historical ACK verification.
    """
    def __init__(self, reference_binding, selected_binding, witness, *, actions):
        self.reference_binding = copy.deepcopy(reference_binding)
        self.selected_binding = copy.deepcopy(selected_binding)
        reference = reset.strict_json(reset.check_binding(reference_binding))
        selected = reset.strict_json(reset.check_binding(selected_binding), 128 * 1024 * 1024)
        plan = reset.route_plan(reference)
        reset.require(plan['actions'][-1] == ['quit'] and actions == plan['actions'][:-1],
                      'Literal bound opening actions with only terminal quit deferred required')
        reset.require(len(actions) == 114 and len(reference['states']) == 105
                      and len(reference['images']) == 10 and plan['frames'] == 14680,
                      'Exact original opening dimensions required')
        self.actions = copy.deepcopy(actions)
        self.positions = [(-1, None)] + [(i, a) for i, a in enumerate(actions)
                                           if a[0] in ('advance', 'input', 'status')]
        reset.require(len(selected['states']) >= 105, 'Complete selected opening required')
        reset.require(selected['actions'] == reference['actions'], 'Selected literal opening plan must match the bound reference')
        self.diagnostics = {'reference': [], 'selected': [], 'actual': []}
        reference = copy.deepcopy(reference)
        selected = copy.deepcopy(selected)
        for name, value, desktop in (('reference', reference, False), ('selected', selected, True)):
            raw_states = copy.deepcopy(value['states'][:105])
            for index, raw in enumerate(raw_states):
                view, proof = self._view(raw_states[:index], raw, index, desktop=desktop)
                value['states'][index] = view
                if proof is not None:
                    self.diagnostics[name].append(proof)
        self.checker = extension.PrefixCheck(reference, selected, witness, reference_binding['sha256'])
        self.raw_states = []
        self.acks = []

    def _view(self, previous_states, raw, index, *, desktop):
        reset.normalize_status(raw, desktop=desktop)
        ai, action = self.positions[index]
        if action is not None and action[0] == 'input':
            view, proof = input_view(previous_states[-1], raw, int(action[1]), desktop=desktop)
            return view, {'state_index': index, 'action_index': ai, **proof}
        held = 0
        for words in self.actions[:ai + 1]:
            if words[0] == 'input':
                held = int(words[1])
        reset.require(raw['host']['buttons'] == [held, 0, 0, 0, 0],
                      'Settled opening controller must equal the literal held intent')
        if action is not None and action[0] == 'status':
            reset.require(reset.normalize_status(previous_states[-1], desktop=desktop)
                          == reset.normalize_status(raw, desktop=desktop), 'Paused status cannot change guest state')
        return copy.deepcopy(raw), None

    def state(self, raw, action_index, action, *, ack=None):
        index = len(self.raw_states)
        reset.require(index < len(self.positions), 'No extra opening state')
        reset.require(type(action_index) is int and (action_index, action) == self.positions[index],
                      'State must occupy its exact bound literal action position')
        view, proof = self._view(self.raw_states, raw, index, desktop=True)
        if proof is not None:
            self.acks.append(input_ack(ack, action_index, int(action[1])))
            self.diagnostics['actual'].append(proof)
        else:
            reset.require(ack is None, 'ACK only belongs to a literal input action')
        self.raw_states.append(copy.deepcopy(raw))
        return self.checker.state(view, action_index, action)

    def finish(self):
        boundary = self.checker.finish()
        return {**boundary, 'input_observation_contract': {
            'schema': 1, 'kind': 'bound-opening-input-intent',
            'reference': self.reference_binding, 'selected': self.selected_binding,
            'historical_ack_retained': False, 'actual_input_acks': copy.deepcopy(self.acks),
            'observations': copy.deepcopy(self.diagnostics),
            'projection': 'controller zero only at validated literal input-status positions',
            'raw_states_unchanged': True}}
