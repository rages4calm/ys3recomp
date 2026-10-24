"""Authored reset replay fixtures. No firmware, game inputs or hosts execute."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
import zlib

from scripts import replay_reset as r
from tests.test_dsp_contract import hosted


def boot():
    return {'mode':'system-card-reset','profile':'super','initialization':'gear-deterministic-zero-v1',
            'vector_physical':8190,'pc':256,'a':0,'x':0,'y':0,'sp':0,'p':4,
            'clock_divisor':12,'ticks':0,'cycles':0,'mpr':[0]*8,'bram':'blank-unformatted'}


def pcm(ticks=0,desktop=False,pending=0):
    frames=ticks*44100//21477273
    value={'enabled':True,'sample_rate':44100,'channels':2,'frames':frames,
           'psg_nonzero':0,'adpcm_nonzero':0,'cdda_nonzero':0,'mixed_nonzero':0,
           'peak':0,'pcm_hash':14695981039346656037,'discarded_frames':0,
           'wav_frames':min(frames-pending,r.WAV_LIMIT),'wav_truncated':frames-pending>r.WAV_LIMIT,
           'timing':'gear-v1'}
    return hosted(value,pending)if desktop else value


def status(frame=0,desktop=False,native=0,interpreted=0):
    ticks=frame*400000
    cpu={'a':0,'x':0,'y':0,'sp':0,'p':4,'clock_divisor':12,'mpr_latch':0,
         'irq_sampled':0,'irq_vector':0,'mpr':[0]*8,'physical_pc':256,
         'instruction_bytes':[17]*7,'instruction_physical':list(range(256,263)),
         'instruction_generations':[1]*7}
    host={'boot':boot(),'debug_memory':{'write_enabled':False,'write_requests':0,'bytes_changed':0},
          'pc':256,'native_steps':native,'interpreter_steps':interpreted,'irq_entries':0,'rti_steps':0,
          'sectors_read':0,'read_errors':0,'unknown_commands':0,'adpcm_dma_bytes':0,
          'buttons':[0]*5,'cpu':cpu,'cd_control':{'bram_seeded':False},
          'scsi':{'master_ticks':ticks},'adpcm':{'master_ticks':ticks},
          'raster':{'master_ticks':ticks,'frames':frame},'cd_audio':{'clock':19},
          'cd_unknown':{'accepted_responses':0,'opcodes':[],'last_command':[],'origin':None},
          'audio_output':pcm(ticks,desktop),'vdc':{'retained':23},'interrupts':{'retained':29}}
    return {'id':1,'ok':True,'frame':frame,'ticks':ticks,'paused':True,'local_paused':False,'host':host}


def reference():
    first=status();last=status(600,interpreted=3)
    return {'error':None,'states':[first,last],'actions':[['advance','600'],['capture'],['quit']],
            'images':[{'frame':600}],'inputs_unchanged':{'authored-input':True},
            'child_stopped':True,'returncode':0}


def contract():
    initial=status(desktop=True)
    proof={'status_before':initial,'status':dict(copy.deepcopy(initial),id=2),'retired_instructions':0,
           'vector_readback':{'address':8190,'expected':'0001','observed':'0001'},
           'fetch_readback':[{'address':256+i,'expected':17,'observed':17}for i in range(7)]}
    window={'requested_start_frame':0,'started':True,'actual_start_frame':0,'actual_start_ticks':0,
            'native_steps_before':0,'interpreter_steps_before':0}
    header={'schema':1,'runtime_abi':17,'capacity':65536,'dropped_instructions':0,
            'unreadable_instructions':0,'retired_instructions':3,'complete':True}
    value={'schema':1,'runtime_abi':17,'path':'authored-capture.json','sha256':'a'*64,'bytes':400,
           'start_frame':0,'capacity':65536,'start_proof':proof,'capture':header,
           'observations':1,'window':window}
    run={'native_steps':1,'interpreter_steps':2,'code_capture_window':copy.deepcopy(window)}
    raw={**header,'observations':[{'native_hits':1,'interpreted_hits':2}]}
    return value,run,raw


def runner(desktop=False):
    state=status(1,desktop,native=1,interpreted=2);host=state['host']
    value={k:0 for k in r.RUNNER_FIELDS}
    value.update(scope='System Card reset-vector boot; deterministic reference initialization; not hardware power-on certification',
                 boot=boot(),stop='dev_quit',pc=256,p=4,clock_divisor=12,ticks=state['ticks'],
                 native_steps=1,interpreter_steps=2,mpr=[0]*8,instruction_bytes=[17]*7,
                 development={'enabled':True,'port':12345,'memory_write_enabled':False,
                              'memory_write_requests':0,'memory_bytes_changed':0})
    for key in ('cd_control','scsi','cd_unknown','cd_audio','adpcm','audio_output','vdc','raster'):value[key]=host[key]
    for key in ('joypad','toc','video_output'):value[key]={'retained':1}
    value['scsi']['unknown_commands']=0
    if desktop:
        value['desktop']={k:0 for k in r.DESKTOP_FIELDS};value['desktop']['presented']=1
    return value


def latency_fixture():
    def timed(frame,ticks,desktop,mask):
        value=status(frame,desktop,interpreted=3)
        value['ticks']=ticks;value['host']['buttons'][0]=mask
        for name in ('scsi','adpcm','raster'):value['host'][name]['master_ticks']=ticks
        value['host']['audio_output']=pcm(ticks,desktop)
        return value
    old=timed(11660,4185881703,False,1)
    actual=timed(11660,4185881703,True,0)
    previous=timed(11660,4185881703,True,1)
    following=timed(11662,4186600000,False,0)
    bridge={'schema':1,'reference_sha256':'a'*64,'audit':{'path':'authored-audit.json','sha256':'b'*64},
            'case':{'state_index':54,'action_index':58,'frame':11660,'ticks':4185881703,
                    'previous_mask':1,'requested_mask':0,'reference_mask':1,'actual_mask':0,
                    'next_state_index':55,'next_action_index':59,'next_frame':11662,'next_advance':2}}
    options={'reference_sha256':'a'*64,'state_index':54,'action_index':58,'action':['input','0'],
             'next_reference_state':following,'bridge':bridge}
    return old,actual,previous,following,options


class ResetStatusTests(unittest.TestCase):
    def test_transport_and_validated_tiers_only_are_projected(self):
        head=status(600,interpreted=3);desk=status(600,True,native=1,interpreted=2)
        self.assertEqual(r.normalize_status(head,desktop=False,project_tiers=True),
                         r.normalize_status(desk,desktop=True,project_tiers=True))
        normalized=r.normalize_status(desk,desktop=True)
        self.assertIn('cpu',normalized['host']);self.assertIn('cd_audio',normalized['host'])
        self.assertEqual(desk['host']['audio_output']['host']['queued_frames'],0)

    def test_source_clock_mapping_generation_assists_and_extra_fields_reject_or_remain(self):
        mutations=(lambda s:s['host']['cpu']['mpr'].pop(),
                   lambda s:s['host']['cpu']['instruction_physical'].__setitem__(0,257),
                   lambda s:s['host']['cpu']['instruction_generations'].__setitem__(0,True),
                   lambda s:s['host']['debug_memory'].update(write_requests=1),
                   lambda s:s['host']['scsi'].update(master_ticks=1),
                   lambda s:s['host']['cd_control'].update(bram_seeded=True),
                   lambda s:s['host']['audio_output'].update(timing='legacy'),
                   lambda s:s['host'].update(unknown_new_field=1))
        for mutate in mutations:
            value=status()
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):
                mutate(value);r.normalize_status(value,desktop=False)
        value=status();value['host']['cd_audio']['new_clock']=31
        self.assertEqual(r.normalize_status(value,desktop=False)['host']['cd_audio']['new_clock'],31)

    def test_initial_cpu_and_vector_are_fresh_and_dynamic(self):
        value=status();self.assertEqual(r.validate_initial_status(value,boot()),value)
        value['host']['native_steps']=1
        with self.assertRaises(ValueError):r.validate_initial_status(value,boot())
        value=status();value['host']['cpu']['p']=0
        with self.assertRaises(ValueError):r.validate_initial_status(value,boot())

    def test_pcm_drain_phase_is_validated_before_checkpoint_projection(self):
        value=status(1,True);frames=value['host']['audio_output']['frames']
        value['host']['audio_output']=pcm(value['ticks'],True,pending=10)
        normalized=r.normalize_status(value,desktop=True)
        self.assertNotIn('wav_frames',normalized['host']['audio_output'])
        value['host']['audio_output']['host']['submitted_frames']=frames+1
        with self.assertRaises(ValueError):r.normalize_status(value,desktop=True)


class ResetCaptureTests(unittest.TestCase):
    def test_origin_whole_retirement_and_each_tier_are_conserved(self):
        value,run,raw=contract()
        self.assertEqual(r.validate_capture_contract(value,run,raw),value)
        raw['observations'][0].update(native_hits=2,interpreted_hits=1)
        with self.assertRaisesRegex(ValueError,'Each execution tier'):r.validate_capture_contract(value,run,raw)

    def test_capture_loss_window_type_late_start_restore_and_provenance_rejected(self):
        mutations=(lambda v:v['capture'].update(complete=False),
                   lambda v:v['capture'].update(dropped_instructions=1),
                   lambda v:v.update(runtime_abi=16),lambda v:v.update(start_frame=1),
                   lambda v:v.update(sha256='not-a-hash'),lambda v:v.update(bytes=True),
                   lambda v:v['window'].update(actual_start_ticks=False),
                   lambda v:v['start_proof']['vector_readback'].update(observed='0101'),
                   lambda v:v['start_proof']['fetch_readback'][0].update(observed=18),
                   lambda v:v['start_proof']['status']['host'].update(interpreter_steps=1))
        for mutate in mutations:
            value,run,raw=contract()
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):
                mutate(value);r.validate_capture_contract(value,run,raw)


class ResetRunnerTests(unittest.TestCase):
    def test_narrow_presentation_transport_tiers_preserve_all_guest_fields(self):
        head=runner();desk=runner(True);desk['development']['port']=23456
        desk['native_steps']=2;desk['interpreter_steps']=1
        self.assertEqual(r.normalize_runner(head,desktop=False,project_tiers=True),
                         r.normalize_runner(desk,desktop=True,project_tiers=True))
        normalized=r.normalize_runner(desk,desktop=True)
        self.assertIn('block_bytes',normalized);self.assertIn('cd_audio',normalized)
        self.assertEqual(desk['development']['port'],23456)

    def test_final_pending_pcm_physical_input_extra_fields_and_boolean_numbers_reject(self):
        mutations=(lambda v:v['desktop'].update(keyboard_events=1),
                   lambda v:v['development'].update(memory_bytes_changed=True),
                   lambda v:v.update(pc=False),lambda v:v.update(extra_field=1),
                   lambda v:v['scsi'].update(master_ticks=0),
                   lambda v:v['audio_output'].update(host={**v['audio_output']['host'],'submitted_frames':0}))
        for mutate in mutations:
            value=runner(True)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):
                mutate(value);r.normalize_runner(value,desktop=True)

    def test_capture_window_requires_validated_origin(self):
        value=runner(True);value['code_capture_window']={}
        with self.assertRaises(ValueError):r.normalize_runner(value,desktop=True)


class ResetInputLatencyTests(unittest.TestCase):
    def test_only_comparison_view_changes_and_raw_states_remain_with_pending_confirmation(self):
        old,actual,previous,following,options=latency_fixture();snapshot=copy.deepcopy((old,actual,previous))
        view,annotation=r.input_status_latency_bridge(old,actual,previous,**options)
        self.assertEqual(view['host']['buttons'],[0]*5)
        self.assertEqual((old,actual,previous),snapshot)
        self.assertEqual(annotation['reference_state'],old);self.assertEqual(annotation['actual_state'],actual)
        self.assertEqual(annotation['previous_actual_state'],previous);self.assertIsNone(annotation['next_confirmation'])
        next_actual=copy.deepcopy(following);next_actual['host']['audio_output']=pcm(following['ticks'],True)
        confirmed=r.confirm_input_status_bridge(annotation,following,next_actual,state_index=55,action_index=59,action=['advance','2'])
        self.assertTrue(confirmed['next_confirmation']['strict_guest_match'])
        self.assertIsNone(annotation['next_confirmation'])

    def test_other_index_clock_request_previous_source_pcm_and_reference_hash_reject(self):
        mutations=(lambda old,actual,previous,following,kw:kw.update(state_index=53),
                   lambda old,actual,previous,following,kw:kw.update(action_index=57),
                   lambda old,actual,previous,following,kw:kw.update(action=['input','1']),
                   lambda old,actual,previous,following,kw:kw.update(reference_sha256='c'*64),
                   lambda old,actual,previous,following,kw:actual.update(frame=11661),
                   lambda old,actual,previous,following,kw:actual.update(ticks=4185881704),
                   lambda old,actual,previous,following,kw:previous['host']['buttons'].__setitem__(0,0),
                   lambda old,actual,previous,following,kw:actual['host']['cpu']['instruction_bytes'].__setitem__(0,18),
                   lambda old,actual,previous,following,kw:actual['host']['audio_output'].update(pcm_hash=123),
                   lambda old,actual,previous,following,kw:following['host']['buttons'].__setitem__(0,1),
                   lambda old,actual,previous,following,kw:actual['host'].update(interpreter_steps=4))
        for mutate in mutations:
            old,actual,previous,following,options=latency_fixture()
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):
                mutate(old,actual,previous,following,options)
                r.input_status_latency_bridge(old,actual,previous,**options)

    def test_next_advancing_checkpoint_must_match_strictly_and_zero(self):
        old,actual,previous,following,options=latency_fixture()
        _,annotation=r.input_status_latency_bridge(old,actual,previous,**options)
        for mutate in (lambda s:s['host']['buttons'].__setitem__(0,1),
                       lambda s:s['host']['cpu']['instruction_generations'].__setitem__(0,2),
                       lambda s:s['host']['audio_output'].update(pcm_hash=123)):
            next_actual=copy.deepcopy(following);next_actual['host']['audio_output']=pcm(following['ticks'],True)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):
                mutate(next_actual);r.confirm_input_status_bridge(annotation,following,next_actual,
                    state_index=55,action_index=59,action=['advance','2'])
        next_actual=copy.deepcopy(following);next_actual['host']['audio_output']=pcm(following['ticks'],True)
        with self.assertRaises(ValueError):r.confirm_input_status_bridge(annotation,following,next_actual,
            state_index=55,action_index=59,action=['status'])


class ResetRouteTests(unittest.TestCase):
    def test_complete_literal_route_and_exact_prefix(self):
        value=reference();full=r.route_plan(value);prefix=r.route_plan(value,600)
        self.assertEqual(full['actions'],value['actions']);self.assertTrue(full['full_reference_route'])
        self.assertEqual(prefix['actions'],[['advance','600']]);self.assertEqual(prefix['expected_state_indices'],[0,1])
        with self.assertRaises(ValueError):r.route_plan(value,599)

    def test_visual_prefix_records_real_split_not_literal_reference_actions(self):
        plan=r.boot_prefix_plan(reference())
        self.assertEqual(plan['actions'],[['advance','120'],['capture'],['advance','480'],['capture']])
        self.assertEqual(plan['source_actions'],[['advance','600']])
        self.assertEqual(plan['expected_state_indices'],[0,None,1])
        self.assertEqual(plan['neutral_timeline'],{'port':0,'mask':0,'frames':600,'splits':[120,480]})
        value=reference();value['states'][1]['host']['buttons'][0]=8
        with self.assertRaises(ValueError):r.boot_prefix_plan(value)

    def test_memory_writes_noncanonical_actions_missing_states_and_changed_inputs_rejected(self):
        mutations=(lambda v:v['actions'].__setitem__(0,['memory_write','0']),
                   lambda v:v['actions'].__setitem__(0,['advance','0600']),
                   lambda v:v['actions'].__setitem__(0,['advance','601']),
                   lambda v:v['states'].pop(),lambda v:v['inputs_unchanged'].update(authored=False),
                   lambda v:v['actions'].append(['status']))
        for mutate in mutations:
            value=reference()
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):mutate(value);r.route_plan(value)

    def test_journal_precedes_rpc_and_read_only_capture(self):
        events=[]
        class Client:
            def advance(self,n):events.append(('advance',n));return 'state'
            def capture(self,source):events.append(('capture',source));return ('meta',b'rgb')
            def call(self,name,**options):events.append((name,options));return 'state'
        plan={'actions':[['advance','2'],['input','8'],['status'],['capture'],['quit']]}
        result=r.replay_actions(Client(),plan,lambda x:events.append(('journal',x)),
                                lambda x:events.append(('state',x)),lambda *x:events.append(('image',x)))
        self.assertTrue(result);self.assertEqual(events[0],('journal',['advance','2']))
        self.assertIn(('set_input',{'port':0,'mask':8}),events)
        self.assertIn(('capture','guest'),events)


class ResetArtifactsTests(unittest.TestCase):
    def png(self,rgb=b'\x01\x02\x03'):
        def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
        return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0'+rgb))+chunk(b'IEND',b'')

    def test_actual_png_decode_binds_rgb_container_and_crc(self):
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'authored.png';path.write_bytes(self.png())
            value=r.png_identity(path)
            self.assertEqual(value['rgb_sha256'],hashlib.sha256(b'\x01\x02\x03').hexdigest())
            self.assertEqual(value['png_sha256'],r.sha256(path))
            raw=bytearray(path.read_bytes());raw[-1]^=1;path.write_bytes(raw)
            with self.assertRaises(ValueError):r.png_identity(path)

    def test_strict_json_duplicates_nonfinite_and_bindings(self):
        with tempfile.TemporaryDirectory()as directory:
            path=Path(directory)/'authored.json'
            for raw in ('{"x":1,"x":2}','{"x":NaN}'):
                path.write_text(raw)
                with self.assertRaises(ValueError):r.strict_json(path)
            path.write_text('{}');value=r.binding(path);self.assertEqual(r.check_binding(value),path.resolve())
            path.write_text('{"changed":true}')
            with self.assertRaises(ValueError):r.check_binding(value)

    def test_exact_seven_originals_support_current_and_retained_list_names(self):
        with tempfile.TemporaryDirectory()as directory:
            rows=[]
            for i in range(7):
                path=Path(directory)/str(i);path.write_text('authored'+str(i))
                rows.append({**r.binding(path),'bytes':path.stat().st_size})
            for name in ('protected_inputs','protected_originals'):
                self.assertEqual(r.protected_inputs({name:rows}),rows)
            with self.assertRaises(ValueError):r.protected_inputs({'protected_originals':rows[:-1]})
            with self.assertRaises(ValueError):r.protected_inputs({'protected_originals':rows,'protected_inputs':rows})
            Path(rows[0]['path']).write_text('drift')
            with self.assertRaises(ValueError):r.protected_inputs({'protected_originals':rows})

    def test_cli_duplicate_equals_mixed_and_unknown_override_rejects(self):
        base=sum((['--'+flag,'authored']for flag in ('descriptor','build-dir','reference-launch','reference-receipt',
                 'protected-inputs','out','reference-launch-sha256','reference-receipt-sha256')),[])
        self.assertEqual(r.argument_parser().parse_args(base).wall_seconds,600)
        for extra in (['--stop-after-frame','600','--stop-after-frame=600'],['--wall-seconds=10','--wall-seconds','20'],
                      ['--dev-memory-write','on'],['--payload','authored']):
            with self.subTest(extra=extra),contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                r.argument_parser().parse_args(base+extra)


class ResetCommandTests(unittest.TestCase):
    def fixture(self,directory):
        root=Path(directory).resolve();binary=root/'authored.exe';out=root/'output'
        project={'files':{role:root/role for role in ('bios','toc','disc','libchdr')},
                 'config':{'limits':{'steps':99,'ticks':999,'wall_seconds':60},'runtime':{'audio_profile':'raw','audio_rate':44100}}}
        def command_for(project,binary,**options):
            command=[str(binary),'--system-card-reset','super',str(project['files']['bios']),'99','999','hybrid']
            flags={'--video-output':'continuous','--cd-unknown-status':'gear-good','--joypad':'2','--joypad-region':'usa',
                   '--multitap':'off','--wall-seconds':'60','--audio-output':'on','--audio-profile':'raw','--audio-rate':'44100',
                   '--dev-port':'0','--dev-start-paused':'on','--dev-memory-write':'off',
                   '--code-capture':str(options['code_capture'].resolve()),'--capture-limit':str(options['capture_limit'])}
            flags.update({'--'+role:str(project['files'][role])for role in ('toc','disc','libchdr')})
            return command+sum(([k,v]for k,v in flags.items()),[])
        return project,binary,out,command_for

    def test_official_command_only_appends_managed_reset_audio_capture(self):
        with tempfile.TemporaryDirectory()as directory:
            project,binary,out,builder=self.fixture(directory)
            command=r.reset_command(SimpleNamespace(command_for=builder),project,binary,out)
            self.assertEqual(command.count('--audio-out'),1);self.assertEqual(command.count('--code-capture-start-frame'),1)
            self.assertEqual(command[command.index('--code-capture-start-frame')+1],'0')
            self.assertNotIn('--payload',command);self.assertNotIn('--bram',command)

    def test_shared_command_output_collision_and_mapping_override_rejected(self):
        with tempfile.TemporaryDirectory()as directory:
            project,binary,out,builder=self.fixture(directory)
            for tail in (['--audio-out','authored.wav'],['--pc','256'],['--audio-timing=gear','on'],['--capture-limit','10']):
                api=SimpleNamespace(command_for=lambda *args,**kw:builder(*args,**kw)+tail)
                with self.subTest(tail=tail),self.assertRaises(ValueError):r.reset_command(api,project,binary,out)


if __name__=='__main__':unittest.main()
