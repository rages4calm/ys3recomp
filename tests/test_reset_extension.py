"""Authored closed-recipe guards; no owner inputs, code emission or host runs."""
import contextlib,copy,io,json
from pathlib import Path
import subprocess,tempfile,unittest
from unittest.mock import patch
from scripts import replay_reset_extension as e
from tests.test_reset_replay import status,latency_fixture


def identity(revision):
    source,files=e.TOOLS[revision]
    return {'revision':revision,'runtime_abi':17,'tracked_source_clean':True,
            'shared_source_identity':{'revision':revision,'source_sha256':source,'source_files':files}}


def fixture():
    plan={'actions':[],'deferred_terminal_action':{'source_index':114,'action':['quit']}}
    observations=[{'phase':'prefix','state':status(0,True)}];frame=0
    for index in range(1,105):
        delta=140 if index<=100 else 170;frame+=delta;plan['actions'].append(['advance',str(delta)])
        observations.append({'phase':'prefix','state':status(frame,True,native=index*3)})
        if index<=10:plan['actions'].append(['capture'])
    prior=copy.deepcopy(observations[-1]['state']);observations.append({'phase':'boundary','state':copy.deepcopy(prior)})
    immediate=copy.deepcopy(prior);observations.append({'phase':'extension-input-status','state':immediate})
    advanced=status(14690,True,native=315,interpreted=3);advanced['host']['buttons'][0]=8
    observations.append({'phase':'extension','state':advanced})
    observations.append({'phase':'extension-capture-status','state':copy.deepcopy(advanced)})
    observations.append({'phase':'terminal-proof','state':copy.deepcopy(advanced)})
    requests=[{'binding':{'path':'authored-request','sha256':'a'*64},'value':value}for value in (
        {'id':1,'op':'advance','mask':8,'frames':10},{'id':2,'op':'capture'},{'id':3,'op':'finish'})]
    receipt={'schema':1,'kind':'ys3-reset-interactive-discovery','passed':True,'natural_quit':True,'child_stopped':True,
             'exit_code':0,'memory_edits':0,'prefix_plan':plan,'requests':requests,
             'states':[x['state']for x in observations],'prefix_boundary':{'status':observations[104]['state'],'fresh_status':observations[105]['state']}}
    receipt['images']=[{'phase':phase}for phase in ['prefix']*10+['boundary']+['extension']*2]
    receipt['actions']=e.expected_action_journal(plan,requests)
    return receipt,observations


class InputObservationTests(unittest.TestCase):
    def test_prior_or_requested_raw_mask_is_valid_only_without_any_guest_change(self):
        previous=status(10,True,native=10);previous['host']['buttons'][0]=1
        for mask in (1,0):
            immediate=copy.deepcopy(previous);immediate['id']=99;immediate['host']['buttons'][0]=mask
            snapshot=copy.deepcopy(immediate);proof=e.validate_input_status(previous,immediate,0)
            self.assertFalse(proof['guest_time_advanced']);self.assertEqual(proof['observed_buttons'][0],mask)
            self.assertEqual(immediate,snapshot)

    def test_input_status_rejects_other_mask_clock_source_pcm_tiers_and_unknown_fields(self):
        previous=status(10,True,native=10)
        mutations=(lambda s:s['host']['buttons'].__setitem__(0,2),lambda s:s.update(ticks=s['ticks']+1),
                   lambda s:s['host']['cpu']['instruction_generations'].__setitem__(0,2),
                   lambda s:s['host']['audio_output'].update(pcm_hash=123),lambda s:s['host'].update(native_steps=11),
                   lambda s:s['host'].update(unknown_future=1))
        for mutate in mutations:
            value=copy.deepcopy(previous)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):mutate(value);e.validate_input_status(previous,value,1)

    def test_postadvance_requires_exact_frame_and_settled_requested_mask(self):
        previous=status(10,True,native=10);after=status(12,True,native=20);after['host']['buttons'][0]=8
        self.assertEqual(e.validate_advance(previous,after,8,2)['total'],20)
        for mask,frames in ((0,2),(8,1),(True,2),(8,2.0)):
            with self.subTest(mask=mask,frames=frames),self.assertRaises(ValueError):e.validate_advance(previous,after,mask,frames)

    def test_settled_crossrun_allows_only_conserved_native_redistribution(self):
        old=status(12,True,native=10,interpreted=10);new=status(12,True,native=20)
        result=e.compare_state(new,old,phase='extension');self.assertEqual(result['classification'],'settled')
        new['host']['buttons'][0]=1
        with self.assertRaises(ValueError):e.compare_state(new,old,phase='extension')

    def test_input_phase_requires_own_previous_context_and_does_not_hide_settled_masks(self):
        previous=status(12,True,native=10);raw=copy.deepcopy(previous);raw['host']['buttons'][0]=1
        result=e.compare_state(raw,previous,phase='extension-input-status',previous_settled=previous,requested_mask=1)
        self.assertEqual(result['classification'],'input-intent-status')
        with self.assertRaises(ValueError):e.compare_state(raw,previous,phase='extension-input-status')
        with self.assertRaises(ValueError):e.compare_state(raw,previous,phase='prefix')


class ClosedRecipeTests(unittest.TestCase):
    def test_complete_literal114_prefix_and_terminalquit_are_explicit(self):
        value,rows=fixture();self.assertEqual(e.closed_recipe(value,rows),value['requests'])
        self.assertEqual(value['actions'][114],{'phase':'boundary','action':['status'],'frame_before':14680})
        self.assertEqual(value['actions'][-1]['action'],['quit'])

    def test_missing_final_state_extra_action_bad_control_and_nonclosed_recipe_reject(self):
        mutations=(lambda v,r:v['actions'].append({'phase':'terminal','action':['status'],'frame_before':14690}),
                   lambda v,r:r.pop(),lambda v,r:v['states'].pop(),lambda v,r:v.update(natural_quit=False),
                   lambda v,r:v.update(memory_edits=False),lambda v,r:v['requests'][-1]['value'].update(op='capture'),
                   lambda v,r:v['requests'][0]['value'].update(frames=10.0),
                   lambda v,r:v['requests'][0]['value'].update(memory_write='forbidden'),
                   lambda v,r:v['prefix_plan']['actions'].append(['quit']))
        for mutate in mutations:
            value,rows=fixture()
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):mutate(value,rows);e.closed_recipe(value,rows)

    def test_raw_phase_journal_cannot_silently_relabel_input_or_omit_boundary(self):
        for index,phase in ((105,'extension'),(106,'extension')):
            value,rows=fixture();rows[index]['phase']=phase
            with self.subTest(index=index),self.assertRaises(ValueError):e.closed_recipe(value,rows)


class ExactPrefixVisibilityTests(unittest.TestCase):
    def test_only_witnessed_candidate_prior1_vs_selected0_returns_explicit_view(self):
        reference,released,previous,following,options=latency_fixture();actual=copy.deepcopy(previous)
        view,annotation=e.selected_prefix_status_view(reference,actual,released,previous,
            reference_sha256=options['reference_sha256'],state_index=54,action_index=58,action=['input','0'],
            next_reference_state=following,witness=options['bridge'])
        self.assertEqual(actual['host']['buttons'][0],1);self.assertEqual(view['host']['buttons'][0],0)
        self.assertEqual(annotation['actual_state'],actual);self.assertEqual(annotation['selected_state'],released)
        self.assertIsNone(annotation['next_confirmation'])
        next_actual=copy.deepcopy(following);next_actual['host']['audio_output']=status(following['frame'],True)['host']['audio_output']
        from tests.test_reset_replay import pcm
        next_actual['host']['audio_output']=pcm(following['ticks'],True)
        confirmed=e.reset.confirm_input_status_bridge(annotation,following,next_actual,state_index=55,action_index=59,action=['advance','2'])
        self.assertTrue(confirmed['next_confirmation']['strict_guest_match'])

    def test_selected_prefix_variant_rejects_other_clock_action_hash_source_pcm_and_tier(self):
        for mutate in (lambda a,o:a.update(frame=11661),lambda a,o:o.update(action_index=57),
                       lambda a,o:o.update(reference_sha256='c'*64),
                       lambda a,o:a['host']['cpu']['instruction_generations'].__setitem__(0,2),
                       lambda a,o:a['host']['audio_output'].update(pcm_hash=123),
                       lambda a,o:a['host'].update(native_steps=1)):
            reference,released,previous,following,options=latency_fixture();actual=copy.deepcopy(previous)
            kwargs={'reference_sha256':options['reference_sha256'],'state_index':54,'action_index':58,'action':['input','0'],
                    'next_reference_state':following,'witness':options['bridge']}
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):
                mutate(actual,kwargs);e.selected_prefix_status_view(reference,actual,released,previous,**kwargs)


class ReviewedToolTests(unittest.TestCase):
    def test_exact_two_reviewed_pairs_use_explicit_source_and_abi_without_old_global_mutation(self):
        original=copy.deepcopy(e.reset.TOOL)
        for revision in e.TOOLS:
            with patch.object(e.subprocess,'check_output',return_value=json.dumps(identity(revision)))as call:
                value=e.verify_identity(Path('authored-tool'),revision)
                command=call.call_args.args[0];self.assertIn('--expected-source-sha256',command)
                self.assertEqual(value['shared_source_identity']['source_files'],e.TOOLS[revision][1])
        self.assertEqual(e.reset.TOOL,original)

    def test_wrong_revision_dirty_float_abi_filecount_and_unknown_fields_reject(self):
        revision=next(reversed(e.TOOLS));mutations=(lambda v:v.update(tracked_source_clean=False),
            lambda v:v.update(runtime_abi=17.0),lambda v:v['shared_source_identity'].update(source_files=54),
            lambda v:v['shared_source_identity'].update(source_files=57.0),lambda v:v.update(extra=True))
        for mutate in mutations:
            value=identity(revision);mutate(value)
            with self.subTest(mutate=mutate),patch.object(e.subprocess,'check_output',return_value=json.dumps(value)),self.assertRaises(ValueError):
                e.verify_identity(Path('authored'),revision)
        with self.assertRaises(ValueError):e.verify_identity(Path('authored'),'0'*40)
        with patch.object(e.subprocess,'check_output',side_effect=subprocess.CalledProcessError(1,['verify'])),self.assertRaises(subprocess.CalledProcessError):
            e.verify_identity(Path('authored'),revision)


class EpochAndCliTests(unittest.TestCase):
    def test_explicit_original_hash_mapping_precedes_changed_live_path_without_guessing(self):
        with tempfile.TemporaryDirectory()as folder:
            root=Path(folder);original=root/'original';preserved=root/'preserved';original.write_text('new');preserved.write_text('old')
            digest=e.reset.sha256(preserved);path=root/'map.json'
            path.write_text(json.dumps({'schema':1,'mappings':[{'original':str(original),'sha256':digest,'preserved':str(preserved)}]}))
            epochs=e.epoch_map(path);self.assertEqual(e.bound({'path':str(original),'sha256':digest},epochs),preserved.resolve())
            preserved.write_text('drift')
            with self.assertRaises(ValueError):e.bound({'path':str(original),'sha256':digest},epochs)

    def test_duplicate_cli_and_undocumented_override_reject_before_launch(self):
        base=sum((['--'+name,'authored']for name in('descriptor','build-dir','tool-root','baseline-receipt','baseline-receipt-sha256','out')),[])
        self.assertIsNone(e.argument_parser().parse_args(base).expected_revision)
        for extra in (['--expected-revision','a'*40,'--expected-revision='+'b'*40],['--memory-write','on'],['--audio-rate','48000']):
            with self.subTest(extra=extra),contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):e.argument_parser().parse_args(base+extra)


if __name__=='__main__':unittest.main()
