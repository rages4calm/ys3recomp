"""Authored orchestration, refusal and frozen-import tests; no game inputs."""
import copy
import hashlib
import importlib.util
import json
import os
import py_compile
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parent.parent

def module(name):
    spec = importlib.util.spec_from_file_location('consumer_' + name, ROOT/'scripts'/ (name+'.py'))
    value = importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

ADAPTER=module('paused_write_adapter')
LOADER=module('diagnostic_tools')
ARCHIVE=module('archive_closed_journal')

class Client:
    def __init__(self):
        self._journal=types.SimpleNamespace(_stream=types.SimpleNamespace(closed=False),_failed=False);self._next_id=1;self.writes=0;self.memory=bytearray(8192)
        self.status=dict(ok=True,paused=True,local_paused=False,frame=10,ticks=20,
            host=dict(pc=0x2200,native_steps=100,interpreter_steps=2,
                debug_memory=dict(write_enabled=True,write_requests=0,bytes_changed=0),
                cpu=dict(mpr=[255,248,128,129,130,131,132,0],physical_pc=0x1f0200,
                    instruction_physical=list(range(0x1f0200,0x1f0207)),
                    instruction_bytes=[0]*7,instruction_generations=[5]*7)))
    def call(self,cmd):
        assert cmd=='status'
        result=copy.deepcopy(self.status);result['id']=self._next_id;self._next_id+=1;return result
    def read_memory(self,address,length):
        self._next_id+=1;return bytes(self.memory[address-0x1f0000:address-0x1f0000+length])
    def write_memory(self,address,data,expected):
        self.writes+=1;identity=self._next_id;self._next_id+=1
        at=address-0x1f0000;assert self.memory[at:at+len(data)]==expected
        self.memory[at:at+len(data)]=data
        return dict(id=identity,ok=True,address=address,length=len(data))

class AssistTests(unittest.TestCase):
    def setUp(self):
        self.client=Client();self.records=[];self.footprint={0x1f0200};self.epoch=dict(live=dict(window=dict(
            current_frame=10,current_ticks=20,current_native_steps=100,current_interpreter_steps=2)),prefix=dict(sha256='a'*64))
        self.observer=types.SimpleNamespace(validate_paused_observation=Mock())
        self.writer=types.SimpleNamespace(WORK_RAM_MIRRORS='work-ram-mirrors-v1',validate_paused_write=Mock(return_value={'checked':True}))
        self.authorize=Mock(return_value={'fresh_title_policy':'authored'})
        self.persist=lambda name,data:self.records.append((name,data))
    def adapter(self):
        return ADAPTER.PausedWRAMAssist(self.client,observation=self.observer,writes=self.writer,
            persist=self.persist,authorize=self.authorize,source_snapshot=lambda:(self.footprint,self.epoch))
    def apply(self,adapter=None,**kw):
        return (adapter or self.adapter()).apply(**dict(address=0x1f0500,expected=b'\0',data=b'\1',**kw))
    def test_same_wram_code_bank_is_allowed_with_typed_relation(self):
        self.apply();self.assertEqual(self.client.writes,1)
        args=self.writer.validate_paused_write.call_args.kwargs
        self.assertEqual(args['memory_before'][0x500],0);self.assertEqual(args['memory_after'][0x500],1)
        self.assertEqual(args['request']['id'],args['acknowledgement']['id'])
        self.assertEqual([name for name,_ in self.records],['preflight-raw','intent','ack','after-raw','proof'])
    def test_all_aliases_excluded_before_send(self):
        for bank in range(248,252):
            self.footprint={(bank<<13)|0x500}
            with self.assertRaisesRegex(ValueError,'aliases'):self.apply()
        self.assertEqual(self.client.writes,0)
    def test_current_fetch_excluded_even_when_not_in_catalogue(self):
        self.footprint={1}
        with self.assertRaisesRegex(ValueError,'aliases'):
            self.adapter().apply(address=0x1f0200,expected=b'\0',data=b'\1')
        self.assertEqual(self.client.writes,0)
    def test_no_raw_journal_refuses_before_any_request(self):
        self.client._journal=None
        with self.assertRaisesRegex(ValueError,'journal'):self.apply()
        self.assertEqual(self.client._next_id,1);self.assertEqual(self.client.writes,0)
    def test_stale_epoch_refuses_zero_writes(self):
        self.epoch['live']['window']['current_ticks']=19
        with self.assertRaisesRegex(ValueError,'source epoch'):self.apply()
        self.assertEqual(self.client.writes,0)
    def test_bool_epoch_refuses_zero_writes(self):
        self.epoch['live']['window']['current_interpreter_steps']=True
        with self.assertRaisesRegex(ValueError,'source epoch'):self.apply()
        self.assertEqual(self.client.writes,0)
    def test_authority_refusal_cannot_send(self):
        self.authorize.side_effect=ValueError('title refuses')
        with self.assertRaisesRegex(ValueError,'title refuses'):self.apply()
        self.assertEqual(self.client.writes,0)
    def test_no_delivery_when_intent_persistence_fails(self):
        def persist(name,value):
            if name=='intent':raise OSError('disk failure')
        self.persist=persist;a=self.adapter()
        with self.assertRaises(OSError):self.apply(a)
        with self.assertRaisesRegex(ValueError,'consumed'):self.apply(a)
        self.assertEqual(self.client.writes,0)
    def test_uncertain_send_never_retried(self):
        original=self.client.write_memory
        def uncertain(*args):original(*args);raise OSError('lost ACK')
        self.client.write_memory=uncertain;a=self.adapter()
        with self.assertRaises(OSError):self.apply(a)
        with self.assertRaisesRegex(ValueError,'consumed'):self.apply(a)
        self.assertEqual(self.client.writes,1)
    def test_typed_effect_failure_preserves_after_and_poison(self):
        self.writer.validate_paused_write.side_effect=ValueError('unrelated changed state');a=self.adapter()
        with self.assertRaisesRegex(ValueError,'unrelated'):self.apply(a)
        self.assertEqual(self.records[-1][0],'after-raw')
        with self.assertRaisesRegex(ValueError,'consumed'):self.apply(a)
        self.assertEqual(self.client.writes,1)
    def test_generation_overflow_refuses_before_send(self):
        self.client.status['host']['cpu']['instruction_generations']=[ADAPTER.U64]*7
        with self.assertRaises(ValueError):self.apply()
        self.assertEqual(self.client.writes,0)
    def test_inconsistent_same_bank_generation_refuses_before_send(self):
        self.client.status['host']['cpu']['instruction_generations'][-1]=6
        with self.assertRaisesRegex(ValueError,'inconsistent generations'):self.apply()
        self.assertEqual(self.client.writes,0)
    def test_wrong_expected_refuses(self):
        self.client.memory[0x500]=3
        with self.assertRaisesRegex(ValueError,'expected literal'):self.apply()
        self.assertEqual(self.client.writes,0)
    def test_capability_cannot_repeat_success(self):
        a=self.adapter();self.apply(a)
        with self.assertRaisesRegex(ValueError,'consumed'):self.apply(a)
        self.assertEqual(self.client.writes,1)

class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.old={k:v for k,v in sys.modules.items() if k=='scripts' or k.startswith('scripts.')}
        for k in self.old:del sys.modules[k]
        self.addCleanup(self.restore)
        def git(*args):return subprocess.check_output(['git','-C',str(self.root),*args],stderr=subprocess.PIPE).decode().strip()
        self.git=git;git('init','--quiet');git('config','core.autocrlf','false');git('config','user.name','Synthetic');git('config','user.email','synthetic@example.invalid')
        (self.root/'scripts').mkdir()
        hashes={}
        for name in LOADER.NAMES:
            p=self.root/'scripts'/(name+'.py');p.write_text('AUTHORED = True\n',encoding='utf-8',newline='\n')
            hashes['scripts/'+name+'.py']=hashlib.sha256(p.read_bytes()).hexdigest()
        git('add','.');git('commit','--quiet','-m','Synthetic helper closure')
        self.pin=dict(revision=git('rev-parse','HEAD'),helper_sha256=hashes)
    def restore(self):
        for k in list(sys.modules):
            if k=='scripts' or k.startswith('scripts.'):del sys.modules[k]
        sys.modules.update(self.old)
    def test_exact_git_and_helper_closure_load(self):
        result=LOADER.load_diagnostics(self.root,self.pin)
        self.assertEqual(set(result),set(LOADER.NAMES))
        self.assertTrue(all(m.AUTHORED for m in result.values()))
    def test_wrong_cached_namespace_refused(self):
        p=types.ModuleType('scripts');p.__path__=[str(self.root/'other')];sys.modules['scripts']=p
        with self.assertRaisesRegex(ValueError,'namespace'):LOADER.load_diagnostics(self.root,self.pin)
    def test_old_cached_helper_refused(self):
        p=types.ModuleType('scripts.dev_write');p.__file__=str(self.root/'old/dev_write.py');sys.modules[p.__name__]=p
        with self.assertRaisesRegex(ValueError,'origin'):LOADER.load_diagnostics(self.root,self.pin)
    def test_cached_same_path_still_refused(self):
        p=types.ModuleType('scripts.dev_write');p.__file__=str(self.root/'scripts/dev_write.py');sys.modules[p.__name__]=p
        with self.assertRaisesRegex(ValueError,'fresh process'):LOADER.load_diagnostics(self.root,self.pin)
    def test_old_file_even_hidden_from_status_refused(self):
        self.git('update-index','--assume-unchanged','scripts/dev_write.py')
        (self.root/'scripts/dev_write.py').write_text('OLD = True\n',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'hidden-source flags'):LOADER.load_diagnostics(self.root,self.pin)
    def test_stale_timestamp_valid_bytecode_is_never_executed(self):
        path=self.root/'scripts/dev_write.py';raw=path.read_bytes();stamp=path.stat()
        path.write_bytes(raw.replace(b'True',b'None'));os.utime(path,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
        py_compile.compile(str(path),doraise=True)
        path.write_bytes(raw);os.utime(path,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
        result=LOADER.load_diagnostics(self.root,self.pin)
        self.assertIs(result['dev_write'].AUTHORED,True)
    def test_wrong_pin_refused(self):
        self.pin['revision']='0'*40
        with self.assertRaisesRegex(ValueError,'revision'):LOADER.load_diagnostics(self.root,self.pin)

class ArchiveTests(unittest.TestCase):
    def test_duplicate_or_nonfinite_closure_cli_refuses_before_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'wire';source.write_bytes(b'authored');destination=root/'wire.gz'
            closure=root/'closure.json'
            for raw in (b'{"exit_code":1,"exit_code":0}',b'{"exit_code":NaN}',b'{"exit_code":1e9999}'):
                closure.write_bytes(raw)
                run=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/archive_closed_journal.py'),str(source),str(destination),
                    '--closure',str(closure),'--closure-sha256',hashlib.sha256(raw).hexdigest(),'--sha256','a'*64],capture_output=True)
                self.assertNotEqual(run.returncode,0);self.assertFalse(destination.exists())
    def test_active_or_unrelated_closure_cannot_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'wire';path.write_bytes(b'authored')
            for closure in (None,dict(journal=str(path),exit_code=True,client_closed=True,streams_closed=True),
                            dict(journal=str(path),exit_code=0,client_closed=False,streams_closed=True)):
                archive=Mock()
                with self.assertRaises(ValueError):ARCHIVE.archive_closed(path,path.with_suffix('.gz'),closure=closure,
                    expected_sha256='a'*64,archive=archive,audit=Mock())
                archive.archive_wire_journal.assert_not_called()
    def test_keeps_raw_and_container_identities_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'wire';path.write_bytes(b'authored')
            archive=Mock();archive.archive_wire_journal.return_value={'archive_sha256':'b'*64}
            audit=Mock();audit.audit_wire_journal.return_value={'paired':True}
            result=ARCHIVE.archive_closed(path,path.with_suffix('.gz'),closure=dict(journal=str(path),exit_code=0,
                client_closed=True,streams_closed=True),expected_sha256='a'*64,archive=archive,audit=audit)
            self.assertEqual(result['raw']['sha256'],'a'*64);self.assertEqual(result['gzip']['sha256'],'b'*64)
            self.assertEqual(audit.audit_wire_journal.call_args.kwargs,dict(encoding='gzip',expected_sha256='a'*64,expected_storage_sha256='b'*64))

if __name__=='__main__':unittest.main()
