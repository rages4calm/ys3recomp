"""Bounded ABI17 System Card reset replay with private raw evidence and capture.

This is consumer TCP supervision around the official verify/build/command APIs.
Inputs are immutable, BRAM starts unformatted and remains process-local, and
memory-write access is disabled. No payload/IPL or CPU mapping override exists.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import time
import zlib

from . import audio15_contract as audio
from .compat16_contract import validate_cd_unknown
from . import package_checks
from .replay_route import BoundedChild

ROOT = Path(__file__).resolve().parents[1]
TOOL = {'revision':'bb3b695b782352bdfacd8db877f2a843bd1242f1',
        'source_sha256':'5d3551481d1245d8cec9011d0f390ad0b464720c2d1f37a0fce601d0888e7a0d',
        'source_files':54,'runtime_abi':17}
SELECTED = {'profile':'raw','sample_rate':44100,'timing':'gear'}
WAV_LIMIT = 441000
U64 = (1 << 64)-1
STATUS_FIELDS = {'id','ok','frame','ticks','paused','local_paused','host'}
HOST_FIELDS = {'boot','debug_memory','pc','native_steps','interpreter_steps','irq_entries',
               'rti_steps','sectors_read','read_errors','unknown_commands','adpcm_dma_bytes',
               'buttons','cpu','cd_control','scsi','cd_unknown','cd_audio','adpcm',
               'audio_output','vdc','raster','interrupts'}
BOOT_FIELDS = {'mode','profile','initialization','vector_physical','pc','a','x','y','sp','p',
               'clock_divisor','ticks','cycles','mpr','bram'}
TIER_FIELDS = {'native_steps','interpreter_steps','native_block_steps','interpreter_block_steps','guard_misses'}
DESKTOP_FIELDS = {'presented','polls','focus_losses','gamepad_connections','resize_events',
                  'pacing_resets','keyboard_events','gamepad_events','input_pulses',
                  'unmapped_key_down','last_unmapped_scancode'}
RUNNER_FIELDS = {'scope','boot','stop','pc','a','x','y','sp','p','ticks','cycles','clock_divisor',
                 'native_steps','interpreter_steps','native_block_steps','interpreter_block_steps','block_bytes',
                 'irq_entries','irq_vector','rti_steps','irq_mask','irq_requests','input_events_applied',
                 'guard_misses','mpr_latch','mpr','instruction_bytes','cd_control','scsi','cd_unknown',
                 'cd_audio','adpcm','audio_output','joypad','toc','vdc','raster','video_output','development'}


def require(ok, label):
    if not ok:
        raise ValueError(label)


def integer(value, maximum=U64, minimum=0, label='integer'):
    require(type(value) is int and minimum <= value <= maximum, label+' outside bounds')
    return value


def keys(value, expected, label):
    require(isinstance(value,dict) and set(value)==set(expected), label+' fields differ')


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def strict_json(path, limit=32*1024*1024):
    def unique(pairs):
        result={}
        for key,value in pairs:
            require(key not in result,'Duplicate JSON key')
            result[key]=value
        return result
    raw=Path(path).read_bytes()
    require(len(raw)<=limit,'JSON exceeds bound')
    return json.loads(raw,object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def binding(path):
    path=Path(path).resolve(strict=True)
    return {'path':str(path),'sha256':sha256(path)}


def check_binding(value):
    keys(value,{'path','sha256'},'artifact binding')
    require(isinstance(value['sha256'],str) and re.fullmatch('[0-9a-f]{64}',value['sha256']),
            'Exact SHA256 required')
    path=Path(value['path']).resolve(strict=True)
    require(path.is_file() and sha256(path)==value['sha256'],'Bound artifact changed')
    return path


def png_identity(path):
    """Validate the shared encoder's bounded RGB8/filter-zero PNG and decode RGB."""
    path=Path(path);raw=path.read_bytes()
    require(len(raw)<=16*1024*1024 and raw[:8]==b'\x89PNG\r\n\x1a\n','PNG extent/signature')
    offset=8;image=None;compressed=bytearray();ended=False
    while offset<len(raw):
        require(offset+12<=len(raw),'Truncated PNG chunk')
        size=struct.unpack_from('>I',raw,offset)[0];kind=raw[offset+4:offset+8]
        require(offset+size+12<=len(raw),'PNG chunk extent')
        data=raw[offset+8:offset+8+size]
        crc=struct.unpack_from('>I',raw,offset+8+size)[0]
        require(zlib.crc32(kind+data)&0xffffffff==crc,'PNG CRC mismatch')
        if kind==b'IHDR':
            require(image is None and offset==8 and size==13,'PNG IHDR')
            width,height,depth,color,compression,filtering,interlace=struct.unpack('>IIBBBBB',data)
            require(1<=width<=1024 and 1<=height<=512 and (depth,color,compression,filtering,interlace)==(8,2,0,0,0),
                    'Shared RGB8 PNG profile required')
            image=(width,height)
        elif kind==b'IDAT':
            require(image is not None and not ended,'PNG IDAT order')
            compressed.extend(data)
        elif kind==b'IEND':
            require(size==0 and image is not None,'PNG IEND');ended=True
        else:
            require(kind[0]&32,'Unknown critical PNG chunk')
        offset+=size+12
        if ended:
            require(offset==len(raw),'PNG trailing bytes');break
    require(ended and compressed,'PNG incomplete')
    width,height=image;extent=height*(width*3+1)
    decoder=zlib.decompressobj();pixels=decoder.decompress(bytes(compressed),extent+1)
    require(len(pixels)==extent and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,
            'PNG decompressed extent')
    stride=width*3+1
    require(all(pixels[y*stride]==0 for y in range(height)),'Shared filter-zero PNG profile required')
    rgb=b''.join(pixels[y*stride+1:(y+1)*stride] for y in range(height))
    return {'width':width,'height':height,'rgb_sha256':hashlib.sha256(rgb).hexdigest(),
            'png_sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}


def validate_boot_shape(value):
    keys(value,BOOT_FIELDS,'reset boot')
    expected={'mode':'system-card-reset','profile':'super','initialization':'gear-deterministic-zero-v1',
              'vector_physical':8190,'a':0,'x':0,'y':0,'sp':0,'p':4,'clock_divisor':12,
              'ticks':0,'cycles':0,'mpr':[0]*8,'bram':'blank-unformatted'}
    for key,wanted in expected.items():
        require(type(value[key]) is type(wanted) and value[key]==wanted,'Reset initialization '+key)
    require(all(type(v)is int for v in value['mpr']),'Reset MPR byte types')
    integer(value['pc'],65535,label='reset PC')
    return copy.deepcopy(value)


def _tree(value):
    if type(value)is int:integer(value)
    elif isinstance(value,dict):
        require(len(value)<=128,'Diagnostic object extent')
        for item in value.values():_tree(item)
    elif isinstance(value,list):
        require(len(value)<=4096,'Diagnostic array extent')
        for item in value:_tree(item)
    else:require(value is None or type(value)in(bool,str),'Diagnostic value type')


def _status_source(value):
    keys(value,STATUS_FIELDS,'status');require(value['ok']is True and value['paused']is True
                                             and value['local_paused']is False,'Paused TCP status required')
    integer(value['id'],(1<<53)-1,1,'TCP ID');integer(value['frame']);integer(value['ticks'])
    host=value['host'];keys(host,HOST_FIELDS,'status host');_tree(host)
    keys(host['debug_memory'],{'write_enabled','write_requests','bytes_changed'},'debug memory')
    require(host['debug_memory']=={'write_enabled':False,'write_requests':0,'bytes_changed':0}
            and type(host['debug_memory']['write_enabled'])is bool
            and type(host['debug_memory']['write_requests'])is int
            and type(host['debug_memory']['bytes_changed'])is int,'Zero assists required')
    validate_boot_shape(host['boot'])
    cpu=host['cpu'];keys(cpu,{'a','x','y','sp','p','clock_divisor','mpr_latch','irq_sampled','irq_vector',
                             'mpr','physical_pc','instruction_bytes','instruction_physical','instruction_generations'},'CPU')
    integer(host['pc'],65535);require(len(cpu['mpr'])==8,'All8 MPRs required')
    for bank in cpu['mpr']:integer(bank,255)
    for key in ('a','x','y','sp','p','mpr_latch','irq_sampled'):integer(cpu[key],255)
    integer(cpu['irq_vector'],65535);require(cpu['clock_divisor']in(3,12),'CPU clock divisor')
    require(cpu['physical_pc']==(cpu['mpr'][host['pc']>>13]<<13)|(host['pc']&8191),'Mapped PC identity')
    integer(cpu['physical_pc'],0x1fffff)
    for name in ('instruction_bytes','instruction_physical','instruction_generations'):
        require(isinstance(cpu[name],list)and len(cpu[name])==7,'Full7byte source identity')
    for i,address in enumerate(cpu['instruction_physical']):
        pc=(host['pc']+i)&65535
        integer(address,0x1fffff)
        require(address==(cpu['mpr'][pc>>13]<<13)|(pc&8191),'Mapped fetch identity')
        if cpu['instruction_bytes'][i]is not None:integer(cpu['instruction_bytes'][i],255)
        integer(cpu['instruction_generations'][i])
    require(host['buttons'] and len(host['buttons'])==5,'Five controller masks')
    for mask in host['buttons']:integer(mask,4095)
    for name in ('scsi','adpcm','raster'):
        require(host[name]['master_ticks']==value['ticks'],'Guest clock '+name)
    require(host['raster']['frames']==value['frame'],'Published frame identity')
    require(host['cd_control']['bram_seeded']is False,'Implicit unformatted BRAM required')
    validate_cd_unknown(host['cd_unknown'],host['unknown_commands'],observed_ticks=value['ticks'])
    for name in ('native_steps','interpreter_steps'):integer(host[name])
    return host


def normalize_status(value, *, desktop, project_tiers=False):
    """Keep every guest/source field; validate before removing transport/drain phase."""
    require(type(desktop)is bool and type(project_tiers)is bool,'Explicit normalization modes')
    _status_source(value);result=copy.deepcopy(value);result.pop('id')
    validator=audio.validate_desktop if desktop else audio.validate_headless
    pcm=validator(result['host']['audio_output'],SELECTED,WAV_LIMIT,allow_pending=True)
    require(pcm['frames']==value['ticks']*44100//21477273,'Gear source clock identity')
    # Checkpoints may precede the host WAV drain; settled runner/WAV stays exact.
    pcm.pop('wav_frames');pcm.pop('wav_truncated');result['host']['audio_output']=pcm
    if project_tiers:
        for field in ('native_steps','interpreter_steps'):result['host'].pop(field)
    return result


def validate_initial_status(value, expected_boot):
    host=_status_source(value)
    require(value['frame']==value['ticks']==0 and host['boot']==expected_boot,'Fresh reset frame0')
    require(host['native_steps']==host['interpreter_steps']==0 and host['buttons']==[0]*5,'Zero retired reset baseline')
    require(host['pc']==expected_boot['pc'] and host['cpu']['mpr']==[0]*8,'Reset vector/allMPR baseline')
    for field in ('a','x','y','sp','p','clock_divisor'):
        require(host['cpu'][field]==expected_boot[field],'Reset CPU '+field)
    return copy.deepcopy(value)


def validate_input_status_bridge(value, reference_sha256):
    """An explicit private witness selects the one audited paused input snapshot."""
    keys(value,{'schema','reference_sha256','audit','case'},'input-status bridge')
    require(type(value['schema'])is int and value['schema']==1
            and isinstance(reference_sha256,str)and re.fullmatch('[0-9a-f]{64}',reference_sha256)
            and value['reference_sha256']==reference_sha256,'Bridge exact reference binding')
    case={'state_index':54,'action_index':58,'frame':11660,'ticks':4185881703,
          'previous_mask':1,'requested_mask':0,'reference_mask':1,'actual_mask':0,
          'next_state_index':55,'next_action_index':59,'next_frame':11662,'next_advance':2}
    keys(value['case'],case,'input-status case')
    require(all(type(value['case'][k])is int and value['case'][k]==v for k,v in case.items()),
            'Only the documented neutral-clock release snapshot is eligible')
    keys(value['audit'],{'path','sha256'},'bridge audit binding')
    require(isinstance(value['audit']['sha256'],str)and re.fullmatch('[0-9a-f]{64}',value['audit']['sha256']),
            'Audited witness SHA256 required')
    return copy.deepcopy(value)


def input_status_latency_bridge(reference_state, actual_state, previous_actual_state, *,
                                reference_sha256, state_index, action_index, action,
                                next_reference_state, bridge):
    """Return the precise comparison view and retain all three unmodified states."""
    validate_input_status_bridge(bridge,reference_sha256);case=bridge['case']
    require(type(state_index)is int and state_index==case['state_index']
            and type(action_index)is int and action_index==case['action_index']
            and action==['input','0'],'Exact audited release action/index required')
    for state in (reference_state,actual_state,previous_actual_state):
        require(state['frame']==case['frame']and state['ticks']==case['ticks'],'Exact paused release clock')
    require(reference_state['host']['buttons']==previous_actual_state['host']['buttons']==[1,0,0,0,0]
            and actual_state['host']['buttons']==[0]*5,'Exact previous/requested/observed release masks')
    old=normalize_status(reference_state,desktop=False,project_tiers=True)
    actual=normalize_status(actual_state,desktop=True,project_tiers=True)
    old['host']['buttons']=[0]*5
    require(old==actual,'Release exception cannot change CPU/source/device/CD/PCM fields')
    previous=normalize_status(previous_actual_state,desktop=True)
    previous['host']['buttons']=[0]*5
    require(previous==normalize_status(actual_state,desktop=True),'No guest execution during release snapshot')
    require(next_reference_state['frame']==case['next_frame']
            and next_reference_state['ticks']>case['ticks']and next_reference_state['host']['buttons']==[0]*5,
            'Strict next advancing released reference is required')
    view=copy.deepcopy(reference_state);view['host']['buttons']=[0]*5
    annotation={'kind':'audited-input-status-latency','reference_sha256':reference_sha256,
                'case':copy.deepcopy(case),'action':copy.deepcopy(action),
                'reference_state':copy.deepcopy(reference_state),'actual_state':copy.deepcopy(actual_state),
                'previous_actual_state':copy.deepcopy(previous_actual_state),'next_confirmation':None}
    return view,annotation


def confirm_input_status_bridge(annotation, reference_state, actual_state, *, state_index, action_index, action):
    case=annotation['case']
    require(annotation['next_confirmation']is None and state_index==case['next_state_index']
            and action_index==case['next_action_index']and action==['advance','2']
            and actual_state['frame']==reference_state['frame']==case['next_frame']
            and actual_state['ticks']==reference_state['ticks']>case['ticks']
            and actual_state['host']['buttons']==reference_state['host']['buttons']==[0]*5,
            'Exact subsequent advancing zero-input checkpoint required')
    require(normalize_status(actual_state,desktop=True,project_tiers=True)
            ==normalize_status(reference_state,desktop=False,project_tiers=True),'Subsequent checkpoint must match strictly')
    result=copy.deepcopy(annotation)
    result['next_confirmation']={'state_index':state_index,'action_index':action_index,'action':copy.deepcopy(action),
                                 'reference_state':copy.deepcopy(reference_state),'actual_state':copy.deepcopy(actual_state),
                                 'strict_guest_match':True}
    return result


def validate_capture_contract(value, runner, capture=None):
    keys(value,{'schema','runtime_abi','path','sha256','bytes','start_frame','capacity','start_proof',
                'capture','observations','window'},'reset capture contract')
    require(value['schema']==1 and type(value['schema'])is int and value['runtime_abi']==17
            and type(value['runtime_abi'])is int and value['start_frame']==0
            and type(value['start_frame'])is int and value['capacity']==65536,'Actual17 reset0 capture required')
    require(isinstance(value['path'],str) and value['path'] and isinstance(value['sha256'],str)
            and re.fullmatch('[0-9a-f]{64}',value['sha256']),'Capture artifact binding required')
    integer(value['bytes'],32*1024*1024,1,'Capture byte extent')
    proof=value['start_proof'];keys(proof,{'status_before','status','retired_instructions','vector_readback','fetch_readback'},'reset proof')
    boot=proof['status_before']['host']['boot']
    validate_initial_status(proof['status_before'],boot);validate_initial_status(proof['status'],boot)
    require(normalize_status(proof['status_before'],desktop=True)
            ==normalize_status(proof['status'],desktop=True),'No instructions during reset proof')
    require(proof['retired_instructions']==0 and type(proof['retired_instructions'])is int,'Reset capture origin0')
    vector=proof['vector_readback'];keys(vector,{'address','expected','observed'},'vector readback')
    require(type(vector['address'])is int and vector['address']==8190
            and isinstance(vector['expected'],str) and re.fullmatch('[0-9a-f]{4}',vector['expected'])
            and vector['expected']==vector['observed']
            and len(bytes.fromhex(vector['expected']))==2
            and int.from_bytes(bytes.fromhex(vector['observed']),'little')==boot['pc'],'Actual BIOS reset vector readback')
    reads=proof['fetch_readback'];require(isinstance(reads,list)and len(reads)==7,'Fresh reset fetch readback')
    cpu=proof['status']['host']['cpu']
    for i,row in enumerate(reads):
        keys(row,{'address','expected','observed'},'fetch readback')
        integer(row['address'],0x1fffff);integer(row['expected'],255);integer(row['observed'],255)
        require(row['address']==cpu['instruction_physical'][i]
                and row['expected']==row['observed']==cpu['instruction_bytes'][i], 'Initial source byte readback')
    header=value['capture'];keys(header,{'schema','runtime_abi','capacity','dropped_instructions',
                                       'unreadable_instructions','retired_instructions','complete'},'capture header')
    require(header['schema']==1 and header['runtime_abi']==17 and header['capacity']==65536
            and header['complete']is True and header['dropped_instructions']==header['unreadable_instructions']==0,
            'Complete lossless65536 actualABI17 capture')
    for name in set(header)-{'complete'}:integer(header[name])
    total=integer(runner['native_steps'])+integer(runner['interpreter_steps'])
    require(header['retired_instructions']==total and total>0,'Whole reset execution retirement conservation')
    window={'requested_start_frame':0,'started':True,'actual_start_frame':0,'actual_start_ticks':0,
            'native_steps_before':0,'interpreter_steps_before':0}
    keys(value['window'],window,'Capture window')
    for key,wanted in window.items():require(type(value['window'][key])is type(wanted),'Capture window type')
    require(value['window']==runner.get('code_capture_window')==window,'Exact before-first-instruction capture window')
    require(type(value['observations'])is int and 1<=value['observations']<=65536,'Capture identity count')
    if capture is not None:
        require({k:v for k,v in capture.items()if k!='observations'}==header
                and len(capture['observations'])==value['observations'],'Raw capture metadata exact')
        require(sum(x['native_hits']+x['interpreted_hits']for x in capture['observations'])==total,
                'Per-source retirement conservation')
        require(sum(x['native_hits']for x in capture['observations'])==runner['native_steps']
                and sum(x['interpreted_hits']for x in capture['observations'])==runner['interpreter_steps'],
                'Each execution tier conserves retired source hits')
    return copy.deepcopy(value)


def normalize_runner(value, *, desktop, project_tiers=False, capture_contract=None):
    require(type(desktop)is bool and type(project_tiers)is bool,'Explicit runner modes')
    keys(value,RUNNER_FIELDS|({'desktop'}if desktop else set())
         |({'code_capture_window'}if capture_contract is not None else set()),'runner')
    result=copy.deepcopy(value);_tree(result);validate_boot_shape(result['boot'])
    require(result['scope']=='System Card reset-vector boot; deterministic reference initialization; not hardware power-on certification',
            'Declared deterministic reset scope required')
    require(result['stop']=='dev_quit','Natural TCP quit runner required')
    for name in ('pc','a','x','y','sp','p','ticks','cycles','clock_divisor','block_bytes','irq_entries','irq_vector',
                 'rti_steps','irq_mask','irq_requests','input_events_applied','mpr_latch'):
        integer(result[name])
    for name in ('a','x','y','sp','p','mpr_latch'):integer(result[name],255)
    integer(result['pc'],65535);integer(result['irq_vector'],65535)
    require(result['clock_divisor']in(3,12),'Runner clock divisor')
    require(isinstance(result['mpr'],list)and len(result['mpr'])==8,'Runner all8 MPRs')
    for bank in result['mpr']:integer(bank,255)
    require(isinstance(result['instruction_bytes'],list)and len(result['instruction_bytes'])==7,'Runner full7byte fetch')
    for byte in result['instruction_bytes']:
        if byte is not None:integer(byte,255)
    for name in ('scsi','adpcm','raster'):require(result[name]['master_ticks']==result['ticks'],'Final guest clock '+name)
    development=result['development']
    keys(development,{'enabled','port','memory_write_enabled','memory_write_requests','memory_bytes_changed'},'development')
    require(development['enabled']is True and development['memory_write_enabled']is False
            and development['memory_write_requests']==development['memory_bytes_changed']==0,'Zero writes at natural exit')
    integer(development['memory_write_requests']);integer(development['memory_bytes_changed'])
    integer(development['port'],65535,1,'TCP port');development.pop('port')
    validator=audio.validate_desktop if desktop else audio.validate_headless
    result['audio_output']=validator(result['audio_output'],SELECTED,WAV_LIMIT,allow_pending=False)
    require(result['audio_output']['frames']==result['ticks']*44100//21477273,'Final Gear clock')
    validate_cd_unknown(result['cd_unknown'],result['scsi']['unknown_commands'],observed_ticks=result['ticks'])
    for field in TIER_FIELDS:integer(result[field])
    require(result['cd_control']['bram_seeded']is False,'No initial BRAM seed')
    if desktop:
        host=result.pop('desktop');keys(host,DESKTOP_FIELDS,'desktop presentation')
        for field in host:integer(host[field])
        require(host['presented']==result['raster']['frames'],'Presented frame endpoint')
        require(all(host[k]==0 for k in ('focus_losses','keyboard_events','gamepad_events','input_pulses',
                                        'unmapped_key_down','last_unmapped_scancode')),'No unrecorded physical input')
    else:require('desktop'not in result,'Headless reference has no desktop telemetry')
    if capture_contract is not None:
        validate_capture_contract(capture_contract,value);result.pop('code_capture_window')
    else:require('code_capture_window'not in result,'Unvalidated capture window')
    if project_tiers:
        for field in TIER_FIELDS:result.pop(field)
    return result


def route_plan(reference, stop_after_frame=None):
    if stop_after_frame is not None:
        route_plan(reference)  # Validate the complete declared recipe before selecting a prefix.
    keys(reference,{'error','states','actions','images','inputs_unchanged','child_stopped','returncode'},'reference receipt')
    require(reference['error']is None and reference['child_stopped']is True and reference['returncode']==0,
            'Completed reference required')
    require(type(reference['returncode'])is int and isinstance(reference['inputs_unchanged'],dict)
            and reference['inputs_unchanged'] and all(v is True for v in reference['inputs_unchanged'].values()),
            'Unchanged reference inputs required')
    actions=reference['actions'];require(isinstance(actions,list)and 1<=len(actions)<=4096,'Bounded ordinary action route')
    frame=0;state_indices=[0];image_indices=[];selected=[];state_index=0;image_index=0;quit_seen=False
    if stop_after_frame is not None:integer(stop_after_frame,1000000,1,'stop frame')
    for index,action in enumerate(actions):
        require(isinstance(action,list)and action and all(type(v)is str for v in action),'Raw action words')
        name=action[0];require(name in ('advance','input','capture','status','quit'),'Only ordinary read/control actions')
        require(len(action)==(2 if name in('advance','input')else 1),'Action arity')
        require(not quit_seen,'Actions after quit forbidden')
        if name in('advance','input'):
            require(re.fullmatch('0|[1-9][0-9]*',action[1]),'Canonical decimal action value')
            integer(int(action[1]),600 if name=='advance'else 255,1 if name=='advance'else 0,'action value')
        if name=='advance':frame+=int(action[1])
        if name in('advance','input','status'):
            state_index+=1;state_indices.append(state_index)
            require(state_index<len(reference['states'])and reference['states'][state_index]['frame']==frame,
                    'Reference state/action frame alignment')
        elif name=='capture':
            require(image_index<len(reference['images'])and reference['images'][image_index]['frame']==frame,
                    'Reference image/action alignment')
            image_indices.append(image_index);image_index+=1
        elif name=='quit':quit_seen=True
        selected.append(copy.deepcopy(action))
        if stop_after_frame is not None and name=='advance'and frame==stop_after_frame:
            break
    full=stop_after_frame is None
    require((full and quit_seen and state_index+1==len(reference['states'])and image_index==len(reference['images']))
            or(not full and frame==stop_after_frame and selected[-1][0]=='advance'), 'Exact complete route or paused prefix required')
    return {'full_reference_route':full,'stop_after_frame':None if full else frame,
            'source_action_count':len(selected),'expected_state_indices':state_indices,
            'expected_image_indices':image_indices,'actions':selected,'frames':frame}


def boot_prefix_plan(reference):
    """A declared neutral timeline equivalent to the first reference advance600."""
    original=route_plan(reference,600)
    require(original['actions']==[['advance','600']] and original['expected_state_indices']==[0,1],
            'Boot visual prefix requires initial neutral advance600')
    require(reference['states'][0]['host']['buttons']==[0]*5
            and reference['states'][1]['host']['buttons']==[0]*5,'Neutral boot prefix required')
    return {**original,'source_actions':original['actions'],'source_action_count':1,
            'actions':[['advance','120'],['capture'],['advance','480'],['capture']],
            'expected_state_indices':[0,None,1],'expected_image_indices':[],
            'neutral_timeline':{'port':0,'mask':0,'frames':600,'splits':[120,480]},
            'prefix_visual_bridge':True}


def replay_actions(client, plan, on_action, on_state, on_image):
    for action in plan['actions']:
        on_action(copy.deepcopy(action))  # Persist raw journal before any RPC/comparison.
        name=action[0]
        if name=='advance':on_state(client.advance(int(action[1])))
        elif name=='input':
            client.call('set_input',port=0,mask=int(action[1]));on_state(client.call('status'))
        elif name=='status':on_state(client.call('status'))
        elif name=='capture':on_image(*client.capture('guest'))
        elif name=='quit':client.call('quit');return True
    return False


def load_shared(tool):
    name='_ys3_verified_reset17'
    package=tool/'pcerecomp'
    if name in sys.modules:
        require(Path(sys.modules[name].__file__).resolve()==package/'__init__.py','Shared package collision')
    else:
        spec=importlib.util.spec_from_file_location(name,package/'__init__.py',submodule_search_locations=[str(package)])
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    project=importlib.import_module(name+'.project');capture=importlib.import_module(name+'.capture')
    spec=importlib.util.spec_from_file_location('_ys3_reset_dev_client',tool/'scripts/dev_client.py')
    client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)
    return project,capture,client


def verify_tool(tool):
    command=[sys.executable,'-B',str(ROOT/'scripts/verify_tool.py'),'--tool-root',str(tool),
             '--expected-revision',TOOL['revision'],'--expected-abi','17',
             '--expected-source-sha256',TOOL['source_sha256']]
    value=json.loads(subprocess.check_output(command,cwd=ROOT,text=True,timeout=60))
    require(value['revision']==TOOL['revision'] and value['runtime_abi']==17
            and value['tracked_source_clean']is True and value['shared_source_identity']==
            {k:TOOL[k]for k in ('revision','source_sha256','source_files')},'Exact clean reviewed ABI17 tool required')
    return value


def reset_command(project_api, project, binary, out):
    command=project_api.command_for(project,binary,dev_port=0,start_paused=True,memory_write=False,
                                    code_capture=out/'observed-code.json',capture_limit=65536)
    extra={'--audio-out':str(out/'audio.wav'),'--audio-frames':str(WAV_LIMIT),
           '--code-capture-start-frame':'0','--hidden':'on','--unthrottled':'on'}
    require(command[:4]==[str(binary),'--system-card-reset','super',str(project['files']['bios'])],
            'Official reset-only command header')
    require(command[4:7]==[str(project['config']['limits']['steps']),str(project['config']['limits']['ticks']),'hybrid'],
            'Official guest limits/tier')
    options={}
    require((len(command)-7)%2==0,'Option/value pairs required')
    for name,value in zip(command[7::2],command[8::2]):
        require(name.startswith('--') and '='not in name and name not in options,'Duplicate/malformed reset option')
        options[name]=value
    expected={'--video-output':'continuous','--cd-unknown-status':'gear-good','--joypad':'2',
              '--joypad-region':'usa','--multitap':'off','--wall-seconds':str(project['config']['limits']['wall_seconds']),
              '--audio-output':'on','--dev-port':'0','--dev-start-paused':'on','--dev-memory-write':'off',
              '--code-capture':str((out/'observed-code.json').resolve()),'--capture-limit':'65536'}
    for role in ('toc','disc','libchdr'):expected['--'+role]=str(project['files'][role])
    for field,flag in (('audio_profile','--audio-profile'),('audio_rate','--audio-rate')):
        if field in project['config']['runtime']:expected[flag]=str(project['config']['runtime'][field])
    require(options==expected,'Unexpected boot/payload/mapping/seed/input/audio override')
    require(not set(options)&set(extra),'Capture/audio/output option collision')
    for name,value in extra.items():command.extend((name,value))
    return command


class ResetChild(BoundedChild):
    def __init__(self,command,cwd,out,env,seconds):
        self.phase_seconds=seconds
        super().__init__(command,cwd,out,env=env)
        self.deadline=time.monotonic()+seconds
    def _watch(self):
        while not self.done.wait(0.1):
            if self.process.poll()is not None:return
            if time.monotonic()>=self.deadline:self.failure=str(self.phase_seconds)+'-second reset watchdog exceeded'
            if self.failure:self.stop();return


def protected_inputs(document):
    names=set(document)&{'protected_inputs','protected_originals'}
    require(len(names)==1,'One declared protected-original list required')
    rows=document[next(iter(names))];require(isinstance(rows,list)and len(rows)==7,'Seven immutable originals required')
    result=[];seen=set()
    for row in rows:
        keys(row,{'path','sha256','bytes'},'protected original')
        path=Path(row['path']).resolve(strict=True);require(path not in seen,'Duplicate protected original')
        seen.add(path);check_binding({'path':str(path),'sha256':row['sha256']})
        require(type(row['bytes'])is int and path.stat().st_size==row['bytes'],'Original size differs')
        result.append({'path':str(path),'sha256':sha256(path),'bytes':path.stat().st_size})
    return result


def run(args):
    from .prepare_reset_descriptor import validate_reset_descriptor,validate_boot_metadata
    tool=args.tool_root.resolve(strict=True);descriptor=args.descriptor.resolve(strict=True)
    build=args.build_dir.resolve(strict=True);out=args.out.resolve()
    require(out.is_relative_to(ROOT/'.local') and not out.exists()and not out.is_symlink(),'Fresh private .local output required')
    integer(args.wall_seconds,600,1,'watchdog seconds')
    launch_path=check_binding({'path':str(args.reference_launch),'sha256':args.reference_launch_sha256})
    reference_path=check_binding({'path':str(args.reference_receipt),'sha256':args.reference_receipt_sha256})
    launch,reference=strict_json(launch_path),strict_json(reference_path)
    bridge=None;bridge_binding=None
    if args.input_status_bridge is not None:
        require(args.input_status_bridge_sha256 is not None,'Explicit input bridge SHA256 required')
        bridge_path=check_binding({'path':str(args.input_status_bridge),'sha256':args.input_status_bridge_sha256})
        bridge=validate_input_status_bridge(strict_json(bridge_path),args.reference_receipt_sha256)
        audit=strict_json(check_binding(bridge['audit']))
        require(audit['result']=='pass'and audit['deferred_button_status_snapshots']==[
                {'action':58,'state':54,'frame':11660,'requested_mask':0,'observed_mask':1,'guest_time_advanced':False}],
                'Exact previously audited deferred input snapshot required')
        bridge_binding=binding(bridge_path)
    else:require(args.input_status_bridge_sha256 is None,'Bridge SHA256 requires explicit witness')
    plan=route_plan(reference,args.stop_after_frame)
    prefix_images=None;prefix_binding=None
    if args.prefix_images is not None:
        require(args.stop_after_frame==600 and args.prefix_images_sha256 is not None,
                'Visual bridge requires explicit600 prefix and reference SHA256')
        prefix_path=check_binding({'path':str(args.prefix_images),'sha256':args.prefix_images_sha256})
        prefix_document=strict_json(prefix_path)
        require(prefix_document['error']is None and prefix_document['child_stopped']is True,
                'Completed menu image reference required')
        prefix_images=prefix_document['images'];require(len(prefix_images)==2
                and [i['frame']for i in prefix_images]==[120,600],'Exact120/600 menu image reference')
        prefix_binding={'receipt':binding(prefix_path),'images':[binding(i['path'])for i in prefix_images]}
        for image in prefix_images:
            decoded=png_identity(image['path'])
            require(all(decoded[k]==image[k]for k in ('width','height','rgb_sha256')),'Decoded menu PNG identity')
        plan=boot_prefix_plan(reference)
    else:require(args.prefix_images_sha256 is None,'Prefix image SHA requires explicit reference')
    before=verify_tool(tool);project_api,capture_api,client_api=load_shared(tool)
    config=__import__('tomllib').loads(descriptor.read_text(encoding='utf-8'))
    selected=validate_reset_descriptor(config,descriptor)
    require(Path(selected['tool']['path']).resolve()==tool,'Descriptor tool root differs')
    verified=project_api.verify(descriptor);built=strict_json(build/'build-receipt.json')
    shared_binding=project_api._binding(verified)
    require(built['binding']==shared_binding,'Official selected build binding differs')
    verification={'schema':1,'verified':True,**shared_binding}
    binary=Path(built['binary']).resolve(strict=True);package=package_checks.verify_package(built,binary)
    expected_boot=selected['boot'];bios=Path(selected['files']['bios'])
    for state in reference['states']:normalize_status(state,desktop=False)
    validate_initial_status(reference['states'][0],expected_boot)
    validate_boot_metadata(reference['states'][0]['host']['boot'],bios)
    require(set(launch['inputs'])=={str(verified['files'][role])for role in ('bios','toc','disc','libchdr')},
            'Exact reset reference media paths required')
    for path,expected in launch['inputs'].items():check_binding({'path':path,'sha256':expected})
    for role in ('bios','toc','disc','libchdr'):
        require(launch['inputs'][str(verified['files'][role])]==verified['identities'][role],'Reference asset differs')
    originals=protected_inputs(strict_json(args.protected_inputs))
    reference_files={'launch':binding(launch_path),'receipt':binding(reference_path),
                     'runner':binding(reference_path.parent/'run.stdout'),'wav':binding(reference_path.parent/'audio.wav')}
    reference_runner=strict_json(reference_files['runner']['path']);normalize_runner(reference_runner,desktop=False)
    for image in reference['images']:
        actual=png_identity(image['path'])
        require(all(actual[k]==image[k]for k in ('width','height','rgb_sha256')),'Reference PNG decoded identity')
    require(not out.is_relative_to(Path(selected['files']['module_source']).parent),'Output may not contaminate source module')
    out.mkdir(parents=True,exist_ok=False);cwd=out/'cwd';cwd.mkdir()
    command=reset_command(project_api,verified,binary,out)
    environment,isolation=package_checks.packaged_environment(binary)
    environment.update(PYTHONDONTWRITEBYTECODE='1',PYTHONSAFEPATH='1',PYTHONPATH=str(tool))
    receipt={'schema':1,'kind':'ys3-reset-replay','passed':False,'error':None,'states':[],'actions':[],'images':[],
             'reference':reference_files,'reference_source':launch.get('source'),'route_plan':plan,
             'prefix_image_reference':prefix_binding,
             'input_status_bridge':bridge_binding,'input_status_bridge_witness':bridge,'input_status_annotations':[],
             'initial_boot':expected_boot,'tool_identity':before,'tool_identity_before':before,
             'tool_identity_after':None,'project_descriptor':str(descriptor),'project_descriptor_sha256':sha256(descriptor),
             'project_build':str(build),'project_build_receipt':binding(build/'build-receipt.json'),
             'project_build_receipt_sha256':sha256(build/'build-receipt.json'),
             'project_verification_before':verification,'project_verification_after':None,
             'protected_inputs_before':originals,'protected_inputs_after':None,
             'asset_hashes_before':verified['identities'],'asset_hashes_after':None,
             'command':command,'shared_project_run_used':False,'execution_mode':'shared-verify-command-consumer-tcp',
             'desktop_contract':{'packaged':True,'package_before':package,'package_after':None,'environment':isolation,
                                 'working_directory':str(cwd),'working_directory_initially_empty':True,
                                 'hidden':True,'unthrottled':True},
             'natural_quit':False,'child_stopped':False,'exit_code':None,'raw_files':{}}
    (out/'launch.json').open('x',encoding='utf-8').write(json.dumps(receipt,indent=2)+'\n')
    child=None;client=None;problem=None;state_stream=(out/'states.jsonl').open('x',encoding='utf-8')
    action_stream=(out/'actions.jsonl').open('x',encoding='utf-8')
    try:
        child=ResetChild(command,cwd,out,environment,args.wall_seconds)
        require(child.ready.wait(15)and child.process.poll()is None and not child.failure,'TCP startup failed')
        receipt['desktop_contract']['loaded_sdl_before']=package_checks.inspect_loaded_sdl(child.process.pid,binary.parent/'SDL3.dll',binary)
        with client_api.DevClient(child.port,timeout=90)as client:
            def on_state(state):
                receipt['states'].append(state);state_stream.write(json.dumps(state,separators=(',',':'))+'\n');state_stream.flush()
                index=plan['expected_state_indices'][len(receipt['states'])-1]
                if index is None:
                    normalize_status(state,desktop=True)
                    require(state['frame']==120 and state['host']['buttons']==[0]*5,'Explicit neutral120 checkpoint')
                    if args.require_zero_native:require(state['host']['native_steps']==0,'Baseline native work')
                    return
                expected=reference['states'][index]
                actual_guest=normalize_status(state,desktop=True,project_tiers=True)
                if receipt['input_status_annotations']and index==55:
                    receipt['input_status_annotations'][0]=confirm_input_status_bridge(
                        receipt['input_status_annotations'][0],expected,state,state_index=index,
                        action_index=len(receipt['actions'])-1,action=receipt['actions'][-1])
                if actual_guest!=normalize_status(expected,desktop=False,project_tiers=True)and bridge is not None:
                    expected,annotation=input_status_latency_bridge(expected,state,receipt['states'][-2],
                        reference_sha256=args.reference_receipt_sha256,state_index=index,
                        action_index=len(receipt['actions'])-1,action=receipt['actions'][-1],
                        next_reference_state=reference['states'][index+1],bridge=bridge)
                    require(not receipt['input_status_annotations'],'Only one audited snapshot exception')
                    receipt['input_status_annotations'].append(annotation)
                require(actual_guest==normalize_status(expected,desktop=False,project_tiers=True),'Reset reference state mismatch at'+str(index))
                require(sum(state['host'][k]for k in ('native_steps','interpreter_steps'))
                        ==sum(expected['host'][k]for k in ('native_steps','interpreter_steps')),'Retirement total differs')
                if args.require_zero_native:require(state['host']['native_steps']==0,'Baseline must execute zero native work')
            def finish_status():
                if 'final_status'not in receipt:
                    state=client.call('status');receipt['final_status']=state
                    require(normalize_status(state,desktop=True)==normalize_status(receipt['states'][-1],desktop=True),
                            'Guest moved at final paused boundary')
                    receipt['desktop_contract']['loaded_sdl_final']=package_checks.inspect_loaded_sdl(child.process.pid,binary.parent/'SDL3.dll',binary)
            def on_action(action):
                receipt['actions'].append(action);action_stream.write(json.dumps(action)+'\n');action_stream.flush()
                if action[0]=='quit':finish_status()
            def on_image(metadata,rgb):
                image_index=len(receipt['images'])
                expected=(prefix_images[image_index]if prefix_images is not None
                          else reference['images'][plan['expected_image_indices'][image_index]])
                path=out/f'frame-{metadata["frame"]}-{image_index}.png';client_api.write_capture(path,metadata,rgb)
                decoded=png_identity(path);image={'path':str(path),**metadata,**{k:v for k,v in decoded.items()if k not in('width','height')}}
                receipt['images'].append(image)
                require(all(image[k]==expected[k]for k in ('width','height','frame','ticks','frame_ticks','source','rgb_sha256')),
                        'Reset image mismatch at'+str(image_index))
            initial=client.call('status');on_state(initial);validate_initial_status(initial,expected_boot)
            vector=bios.read_bytes()[8190:8192];vector_observed=client.read_memory(8190,2)
            reads=[]
            for address,expected in zip(initial['host']['cpu']['instruction_physical'],initial['host']['cpu']['instruction_bytes']):
                observed=client.read_memory(address,1)[0];reads.append({'address':address,'expected':expected,'observed':observed})
                require(observed==expected,'Fresh reset ROM fetch differs')
            proof={'status_before':initial,'status':client.call('status'),'retired_instructions':0,
                   'vector_readback':{'address':8190,'expected':vector.hex(),'observed':vector_observed.hex()},
                   'fetch_readback':reads}
            receipt['start_proof']=proof
            require(vector==vector_observed and normalize_status(initial,desktop=True)==normalize_status(proof['status'],desktop=True),
                    'Reset vector/proof moved before first instruction')
            receipt['natural_quit']=replay_actions(client,plan,on_action,on_state,on_image)
            if not receipt['natural_quit']:
                finish_status();client.call('quit');receipt['natural_quit']=True
            child.process.wait(timeout=15)
            require(child.process.returncode==0 and not child.failure,'Natural reset host exit failed')
        require(len(receipt['states'])==len(plan['expected_state_indices'])
                and len(receipt['images'])==(2 if prefix_images is not None else len(plan['expected_image_indices']))
                and receipt['actions']==plan['actions'],'Every selected reference action/state/image required')
        require(all(a['next_confirmation']is not None for a in receipt['input_status_annotations']),
                'Missing subsequent strict input release confirmation')
    except BaseException as error:
        problem=error;receipt['error']=repr(error)
        if client is not None and child is not None and child.process.poll()is None:
            try:client.call('quit')
            except Exception:pass
    finally:
        if child is not None:
            child.close();receipt['child_stopped']=child.process.poll()is not None
            receipt['exit_code']=child.process.returncode;receipt['supervisor_failure']=child.failure
        state_stream.close();action_stream.close()
        try:
            receipt['protected_inputs_after']=protected_inputs(strict_json(args.protected_inputs))
            require(receipt['protected_inputs_after']==originals,'Protected originals changed')
            after=project_api.verify(descriptor);receipt['asset_hashes_after']=after['identities']
            receipt['project_verification_after']={'schema':1,'verified':True,**project_api._binding(after)}
            require(receipt['project_verification_after']==verification,'Official bindings changed during execution')
            receipt['desktop_contract']['package_after']=package_checks.verify_package(built,binary)
            require(receipt['desktop_contract']['package_after']==package,'Package changed')
            receipt['desktop_contract']['working_directory_finally_empty']=not any(cwd.iterdir())
            require(receipt['desktop_contract']['working_directory_finally_empty'],'Private cwd acquired files')
            receipt['tool_identity_after']=verify_tool(tool);require(receipt['tool_identity_after']==before,'Tool changed')
            for value in reference_files.values():check_binding(value)
            if bridge_binding is not None:check_binding(bridge_binding);check_binding(bridge['audit'])
            if prefix_binding is not None:
                check_binding(prefix_binding['receipt'])
                for value in prefix_binding['images']:check_binding(value)
            if problem is None:
                runner=strict_json(out/'run.stdout');receipt['runner']=runner
                raw,capture_hash=capture_api.load_capture(out/'observed-code.json')
                contract={'schema':1,'runtime_abi':17,'path':str(out/'observed-code.json'),'sha256':capture_hash,
                          'bytes':(out/'observed-code.json').stat().st_size,'start_frame':0,'capacity':65536,
                          'start_proof':receipt['start_proof'],'capture':{k:v for k,v in raw.items()if k!='observations'},
                          'observations':len(raw['observations']),'window':runner['code_capture_window']}
                receipt['capture_contract']=validate_capture_contract(contract,runner,raw)
                actual=normalize_runner(runner,desktop=True,project_tiers=True,capture_contract=contract)
                require(all(runner[k]==receipt['final_status']['host'][k]for k in ('native_steps','interpreter_steps')),
                        'Final paused runner tier counts differ')
                require(runner['ticks']==receipt['final_status']['ticks']
                        and runner['raster']['frames']==receipt['final_status']['frame'],'Final paused runner endpoint differs')
                receipt['boot_validation']=project_api._boot_provenance(verified,runner)
                require(receipt['boot_validation']=={'valid':True},'Shared reset provenance rejected')
                if plan['full_reference_route']:
                    require(actual==normalize_runner(reference_runner,desktop=False,project_tiers=True),'Final reset guest/source/device/PCM mismatch')
                    require(sha256(out/'audio.wav')==reference_files['wav']['sha256'],'Final bounded WAV differs')
                if args.require_zero_native:require(runner['native_steps']==0,'Baseline runner native work is nonzero')
                require(receipt['natural_quit']and receipt['exit_code']==0 and receipt['child_stopped'],'Owned process closure')
                receipt['passed']=True
        except BaseException as error:
            if problem is None:problem=error;receipt['error']=repr(error)
        for role,name in (('stdout','run.stdout'),('stderr','run.stderr'),('wav','audio.wav'),('states','states.jsonl'),('actions','actions.jsonl')):
            if (out/name).is_file():receipt['raw_files'][role]=binding(out/name)
        (out/'receipt.json').open('x',encoding='utf-8').write(json.dumps(receipt,indent=2)+'\n')
    if problem is not None:raise problem
    return receipt


class Once(argparse.Action):
    def __call__(self,parser,namespace,value,option_string=None):
        seen=getattr(namespace,'_reset_seen',set())
        if self.dest in seen:parser.error('duplicate option: '+str(option_string))
        seen.add(self.dest);namespace._reset_seen=seen;setattr(namespace,self.dest,value)


def argument_parser():
    parser=argparse.ArgumentParser(description=__doc__)
    for flag in ('descriptor','build-dir','reference-launch','reference-receipt','protected-inputs','out'):
        parser.add_argument('--'+flag,type=Path,required=True,action=Once)
    for flag in ('reference-launch-sha256','reference-receipt-sha256'):
        parser.add_argument('--'+flag,required=True,action=Once)
    parser.add_argument('--tool-root',type=Path,default=ROOT/'.deps/pcenginerecomp-abi17',action=Once)
    parser.add_argument('--stop-after-frame',type=int,action=Once)
    parser.add_argument('--prefix-images',type=Path,action=Once,
                        help='Bounded menu image receipt for explicit neutral120/600 prefix only')
    parser.add_argument('--prefix-images-sha256',action=Once)
    parser.add_argument('--input-status-bridge',type=Path,action=Once)
    parser.add_argument('--input-status-bridge-sha256',action=Once)
    parser.add_argument('--wall-seconds',type=int,default=600,action=Once)
    parser.add_argument('--require-zero-native',action='store_true')
    return parser


def main():
    result=run(argument_parser().parse_args())
    print(json.dumps({'passed':result['passed'],'frames':result['states'][-1]['frame'],
                      'states':len(result['states']),'actions':len(result['actions']),
                      'images':len(result['images']),'native':result['runner']['native_steps'],
                      'interpreted':result['runner']['interpreter_steps']}))


if __name__=='__main__':main()
