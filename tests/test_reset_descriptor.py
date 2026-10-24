"""Authored reset descriptor fixtures; no owner firmware, game, build or host."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('prepare_reset_descriptor', ROOT / 'scripts/prepare_reset_descriptor.py')
RESET = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RESET)
TOOL = Path(os.environ.get('PCE_RESET_TEST_TOOL', ROOT / '.deps/pcenginerecomp-abi17'))
REVISION = 'bb3b695b782352bdfacd8db877f2a843bd1242f1'
SOURCE_SHA = '5d3551481d1245d8cec9011d0f390ad0b464720c2d1f37a0fce601d0888e7a0d'


class ResetDescriptorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='ys3-reset-descriptor-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.card = self.root / 'authored-card.pce'
        raw = bytearray(262144)
        raw[0x1FFE:0x2000] = bytes([0, 224])
        raw[-2:] = bytes([52, 18])  # Deliberately different from the real vector location.
        self.card.write_bytes(raw)
        self.firmware_policy = mock.patch.object(RESET, 'USA_BIOS_SHA256', RESET.sha256(self.card))
        self.firmware_policy.start(); self.addCleanup(self.firmware_policy.stop)
        # Only the selected authentic-BIOS digest policy is substituted. Every
        # synthetic file, hash, vector, field and official loader stays real.
        self.assets = {'bios': {'path': str(self.card), 'sha256': RESET.sha256(self.card)}}
        for name in ('toc', 'disc', 'libchdr'):
            path = self.root / ('authored-' + name)
            path.write_bytes(('authored-' + name).encode())
            self.assets[name] = {'path': str(path), 'sha256': RESET.sha256(path)}
        self.module = self.root / 'module.cpp'; self.module.write_text('// authored descriptor-only fixture\n')
        self.header = self.root / 'module.hpp'; self.header.write_text('// authored header\n')
        self.manifest_path = self.root / 'module.json'
        self.manifest = {'schema': 1, 'runtime_abi': 17, 'capture_runtime_abi': 17,
                         'native_instructions_emitted': 1,
                         'translation_units': [{'file': self.module.name, 'sha256': RESET.sha256(self.module)}],
                         'generated_headers': [{'file': self.header.name, 'sha256': RESET.sha256(self.header)}]}
        self.manifest_path.write_text(json.dumps(self.manifest))
        self.reference = {'assets': self.assets, 'limits': {'steps': 20000000000, 'ticks': 100000000000, 'wall_seconds': 600}}
        self.identity = {'revision': REVISION, 'source_sha256': SOURCE_SHA, 'source_files': 54}
        self.out = self.root / 'project.toml'
        self.config = tomllib.loads(RESET.descriptor_text(self.reference, self.module, TOOL, self.identity))
        self.launch_path, self.receipt_path = self.root / 'launch.json', self.root / 'reference.json'
        argv = ['authored-unexecuted.exe', '--system-card-reset', 'super', str(self.card),
                '20000000000', '100000000000', 'hybrid', '--dev-port', '0', '--dev-start-paused', 'on',
                '--video-output', 'continuous', '--audio-output', 'on', '--audio-out', str(self.root / 'unused.wav'),
                '--audio-frames', '441000', '--wall-seconds', '600',
                '--toc', self.assets['toc']['path'], '--disc', self.assets['disc']['path'],
                '--libchdr', self.assets['libchdr']['path'], '--cd-unknown-status', 'gear-good']
        self.launch = {'argv': argv, 'inputs': {item['path']: item['sha256'] for item in self.assets.values()}, 'source': self.identity}
        self.receipt = {'error': None, 'states': [{'frame': 0, 'ticks': 0, 'paused': True,
                         'host': {'boot': RESET.expected_boot_metadata(self.card),
                                  'debug_memory': {'write_enabled': False, 'write_requests': 0, 'bytes_changed': 0}}}],
                        'inputs_unchanged': {path: True for path in self.launch['inputs']},
                        'child_stopped': True, 'returncode': 0}
        self.write_reference()

    def write_reference(self):
        self.launch_path.write_text(json.dumps(self.launch)); self.receipt_path.write_text(json.dumps(self.receipt))

    def rewrite_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest))
        self.config['module']['manifest']['sha256'] = RESET.sha256(self.manifest_path)

    def validate(self, config=None):
        return RESET.validate_reset_descriptor(self.config if config is None else config, self.out)

    def test_default_reset_recipe_and_all_file_hashes(self):
        before = copy.deepcopy(self.config); result = self.validate()
        self.assertEqual(result['audio_selection'], {'profile': 'raw', 'sample_rate': 44100, 'timing': 'gear'})
        self.assertEqual(result['wav_frame_limit'], 441000)
        self.assertEqual(self.config['boot'], {'mode': 'system-card-reset', 'profile': 'super'})
        self.assertNotIn('audio_timing', self.config['runtime'])
        self.assertEqual(result['boot']['bram'], 'blank-unformatted')
        self.assertEqual(len(result['files']), 8)
        for role, path in result['files'].items(): self.assertEqual(result['identities'][role], RESET.sha256(path))
        self.assertEqual(self.config, before)

    def test_omitted_profile_rate_still_default_raw_gear(self):
        self.config['runtime'].pop('audio_profile'); self.config['runtime'].pop('audio_rate')
        self.assertEqual(self.validate()['audio_selection'], RESET.SELECTION)

    def test_boot_vector_is_first_bank_not_end_of_rom(self):
        boot = self.validate()['boot']
        self.assertEqual(boot['pc'], 57344); self.assertEqual(boot['vector_physical'], 8190)
        self.assertNotEqual(boot['pc'], 4660)

    def test_forbidden_payload_pc_mpr_bram_and_input_fields(self):
        for key, value in [('payload', {}), ('pc', 57344), ('mpr', [0] * 8), ('physical_load', 0),
                           ('bram', self.assets['bios']), ('input_script', self.assets['toc']), ('ipl', {})]:
            config = copy.deepcopy(self.config); config[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(config)
        for key in ('pc', 'mpr', 'bram', 'vector_physical'):
            config = copy.deepcopy(self.config); config['boot'][key] = 0
            with self.subTest(boot_key=key), self.assertRaises(ValueError): self.validate(config)

    def test_wrong_boot_mode_profile_and_unknown_fields(self):
        for key, value in [('mode', 'snapshot'), ('profile', 'standard'), ('profile', True)]:
            config = copy.deepcopy(self.config); config['boot'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): self.validate(config)

    def test_audio_selection_cannot_change_reset_reference(self):
        for key, value in [('audio', 'off'), ('audio_profile', 'filtered'), ('audio_rate', 48000),
                           ('audio_rate', 44100.0), ('audio_timing', 'gear'), ('audio_timing', 'legacy'),
                           ('joypad', True), ('tier', 'native'), ('region', 'japan')]:
            config = copy.deepcopy(self.config); config['runtime'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): self.validate(config)

    def test_wrong_firmware_hash_and_length(self):
        self.config['bios']['sha256'] = '0' * 64
        with self.assertRaises(ValueError): self.validate()
        self.config['bios']['sha256'] = RESET.sha256(self.card)
        with mock.patch.object(RESET, 'USA_BIOS_SHA256', 'f' * 64):
            with self.assertRaisesRegex(ValueError, 'clean USA'): self.validate()
        self.card.write_bytes(b'authored short card'); self.config['bios']['sha256'] = RESET.sha256(self.card)
        with self.assertRaisesRegex(ValueError, '256 KiB'): self.validate()

    def test_mismatched_firmware_vector_independent_of_hash(self):
        original = RESET.expected_boot_metadata(self.card)
        raw = bytearray(self.card.read_bytes()); raw[0x1FFE] = 1; self.card.write_bytes(raw)
        with mock.patch.object(RESET, 'USA_BIOS_SHA256', RESET.sha256(self.card)):
            with self.assertRaisesRegex(ValueError, 'pc'): RESET.validate_boot_metadata(original, self.card)

    def test_metadata_type_and_implicit_bram_policy_are_exact(self):
        boot = RESET.expected_boot_metadata(self.card)
        for key, value in [('pc', True), ('ticks', False), ('p', 0), ('clock_divisor', 3),
                           ('mpr', [False] * 8), ('bram', 'explicit-image'), ('mode', 'snapshot')]:
            mutated = copy.deepcopy(boot); mutated[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): RESET.validate_boot_metadata(mutated, self.card)
        boot['extra'] = 0
        with self.assertRaises(ValueError): RESET.validate_boot_metadata(boot, self.card)

    def test_module_header_tampering_is_bound(self):
        self.header.write_text('// changed authored header\n')
        with self.assertRaisesRegex(ValueError, 'hash'): self.validate()

    def test_module_artifact_lists_bounds_paths_and_duplicates(self):
        original = copy.deepcopy(self.manifest)
        cases = []
        value = copy.deepcopy(original); value.pop('generated_headers'); cases.append(value)
        value = copy.deepcopy(original); value['translation_units'] *= 513; cases.append(value)
        for name in ('../outside.cpp', 'CON.cpp', 'module/part.cpp', 'module.txt'):
            value = copy.deepcopy(original); value['translation_units'][0]['file'] = name; cases.append(value)
        value = copy.deepcopy(original); value['translation_units'].append({'file': 'MODULE.cpp', 'sha256': RESET.sha256(self.module)}); cases.append(value)
        value = copy.deepcopy(original); value['translation_units'][0]['file'] = 'absent.cpp'; cases.append(value)
        for value in cases:
            self.manifest = value; self.rewrite_manifest()
            with self.subTest(value=value), self.assertRaises((ValueError, OSError)): self.validate()

    def test_wrong_module_abi_count_and_capture_abi(self):
        for key, value in [('runtime_abi', 16), ('runtime_abi', True), ('schema', True),
                           ('native_instructions_emitted', 0), ('native_instructions_emitted', True), ('capture_runtime_abi', 16)]:
            self.manifest[key] = value; self.rewrite_manifest()
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): self.validate()
            self.manifest.update(schema=1, runtime_abi=17, native_instructions_emitted=1, capture_runtime_abi=17)

    def test_legacy_single_source_authored_baseline_is_bound(self):
        self.manifest.pop('translation_units'); self.manifest.pop('generated_headers'); self.rewrite_manifest()
        self.assertEqual(len(self.validate()['files']), 6)

    def test_valid_reference_requires_immutable_paused_blank_boot(self):
        reference = RESET.load_reference(self.launch_path, self.receipt_path)
        self.assertEqual(reference['boot']['pc'], 57344)
        self.assertEqual(reference['assets'], self.assets)
        self.assertEqual(len(reference['bindings']), 2)

    def test_reference_rejects_boot_payload_bram_timing_and_duplicate_overrides(self):
        original = copy.deepcopy(self.launch)
        for tail in (['--bram', 'authored.bin'], ['--payload', 'authored.bin'], ['--pc', '1'],
                     ['--mpr', '0,0,0,0,0,0,0,0'], ['--audio-timing', 'gear'],
                     ['--audio-output', 'on'], ['--dev-memory-write', 'on']):
            self.launch = copy.deepcopy(original); self.launch['argv'] += tail; self.write_reference()
            with self.subTest(tail=tail), self.assertRaises(ValueError): RESET.load_reference(self.launch_path, self.receipt_path)

    def test_reference_rejects_wrong_hash_boot_metadata_lifecycle_or_closeout(self):
        original = copy.deepcopy(self.receipt)
        variants = []
        value = copy.deepcopy(original); value['states'][0]['host']['boot']['pc'] += 1; variants.append(value)
        value = copy.deepcopy(original); value['states'][0]['ticks'] = True; variants.append(value)
        value = copy.deepcopy(original); value['states'][0]['host']['debug_memory']['write_requests'] = False; variants.append(value)
        value = copy.deepcopy(original); value['child_stopped'] = False; variants.append(value)
        value = copy.deepcopy(original); value['returncode'] = True; variants.append(value)
        value = copy.deepcopy(original); value['inputs_unchanged'][str(self.card)] = False; variants.append(value)
        for value in variants:
            self.receipt = value; self.write_reference()
            with self.subTest(value=value), self.assertRaises(ValueError): RESET.load_reference(self.launch_path, self.receipt_path)
        self.receipt = original; self.launch['inputs'][str(self.card)] = '0' * 64; self.write_reference()
        with self.assertRaises(ValueError): RESET.load_reference(self.launch_path, self.receipt_path)

    def test_schema_identity_and_limit_integer_types(self):
        for key, value in [('schema', True), ('name', '../bad')]:
            config = copy.deepcopy(self.config); config[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(config)
        for key, value in [('steps', True), ('steps', 20000000001), ('ticks', 0), ('wall_seconds', 601)]:
            config = copy.deepcopy(self.config); config['limits'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(config)
        for key, value in [('runtime_abi', 16), ('runtime_abi', True), ('revision', 'a' * 39), ('source_sha256', 'F' * 64)]:
            config = copy.deepcopy(self.config); config['tool'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(config)

    def test_output_is_exclusive_before_any_tool_verification(self):
        self.out.write_text('keep this authored file')
        with mock.patch.object(RESET, 'verify_identity') as verify:
            with self.assertRaisesRegex(ValueError, 'must be new'):
                RESET.prepare(TOOL, self.launch_path, self.receipt_path, self.module, self.out,
                              expected_revision=REVISION, expected_abi=17, expected_source_sha256=SOURCE_SHA)
            verify.assert_not_called()
        self.assertEqual(self.out.read_text(), 'keep this authored file')

    def test_cli_forbids_pc_payload_bram_and_partial_or_duplicate_pin(self):
        base = ['--tool-root', 'absent', '--reference-launch', 'absent', '--reference-receipt', 'absent',
                '--module', 'absent', '--out', 'absent']
        for extra in (['--pc', '1'], ['--payload', 'x'], ['--bram', 'x'],
                      ['--expected-revision', REVISION], ['--expected-abi', '16'],
                      ['--expected-abi', '17', '--expected-abi=17']):
            with self.subTest(extra=extra), mock.patch.object(RESET.sys, 'argv', ['prepare_reset_descriptor', *base, *extra]), \
                 mock.patch.object(RESET, 'prepare') as prepare, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as failure: RESET.main()
                self.assertEqual(failure.exception.code, 2); prepare.assert_not_called()

    @unittest.skipUnless((TOOL / 'pcerecomp/project.py').is_file(), 'optional frozen ABI17 tool unavailable')
    def test_actual_official_loader_verifies_authored_reset_and_boot_recipe(self):
        identity = RESET.verify_identity(TOOL, REVISION, 17, SOURCE_SHA)
        self.assertEqual(identity['runtime_abi'], 17)
        result = RESET.prepare(TOOL, self.launch_path, self.receipt_path, self.module, self.out,
                               expected_revision=REVISION, expected_abi=17, expected_source_sha256=SOURCE_SHA)
        self.assertTrue(result['prepared']); self.assertTrue(result['official_verification']['verified'])
        self.assertEqual(result['validation']['audio_selection'], RESET.SELECTION)
        self.assertEqual(result['validation']['boot']['pc'], 57344)
        code = ('import json,sys; from pathlib import Path; from pcerecomp.project import verify,command_for,_boot_provenance; '
                'p=verify(Path(sys.argv[1])); b=json.loads(sys.argv[2]); '
                'good=_boot_provenance(p,{"boot":b}); b["pc"]+=1; '
                'print(json.dumps({"command":command_for(p,Path("authored-not-executed.exe"),dev_port=0,start_paused=True),'
                '"good":good,"bad":_boot_provenance(p,{"boot":b})}))')
        env = dict(os.environ, PYTHONPATH=str(TOOL.resolve()), PYTHONSAFEPATH='1', PYTHONDONTWRITEBYTECODE='1')
        checked = json.loads(subprocess.check_output([sys.executable, '-c', code, str(self.out), json.dumps(result['validation']['boot'])],
                                                    cwd=TOOL, env=env, text=True, timeout=60))
        self.assertEqual(checked['command'][1:3], ['--system-card-reset', 'super'])
        self.assertNotIn('--bios', checked['command']); self.assertNotIn('--bram', checked['command'])
        self.assertNotIn('--audio-timing', checked['command'])
        self.assertTrue(checked['good']['valid']); self.assertFalse(checked['bad']['valid'])


if __name__ == '__main__':
    unittest.main()
