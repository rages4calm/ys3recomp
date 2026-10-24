"""Prepare a private, hash-bound USA Super System Card reset descriptor.

This is separate from the retained snapshot/IPL descriptor generator. Firmware,
disc, captures and generated modules are caller-owned read-only private inputs.
No host, build, firmware patch, BRAM image or save installation is performed.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
USA_BIOS_SHA256 = 'cadac2725711b3c442bcf237b02f5a5210c96f17625c35fa58f009e0ed39e4db'
ABI = 17
WAV_FRAME_LIMIT = 441000
SELECTION = {'profile': 'raw', 'sample_rate': 44100, 'timing': 'gear'}
RUNTIME = {'tier': 'hybrid', 'video': 'continuous', 'cd_unknown_status': 'gear-good',
           'joypad': 2, 'region': 'usa', 'multitap': 'off', 'audio': 'on'}
AUDIO_DEFAULT_FIELDS = {'audio_profile': 'raw', 'audio_rate': 44100}
ASSETS = ('bios', 'toc', 'disc', 'libchdr')


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _keys(value, required, label):
    if not isinstance(value, dict) or set(value) != set(required):
        raise ValueError(label + ' has missing or unsupported fields')


def _integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(label + ' requires a bounded integer')
    return value


def _digest(value, label, length=64):
    if type(value) is not str or re.fullmatch('[0-9a-f]{' + str(length) + '}', value) is None:
        raise ValueError(label + ' requires an exact lowercase digest')
    return value


def _file(base, entry, label):
    _keys(entry, {'path', 'sha256'}, label)
    if type(entry['path']) is not str or not entry['path'] or '\0' in entry['path']:
        raise ValueError(label + ' requires an explicit path')
    raw = Path(entry['path'])
    raw = raw if raw.is_absolute() else base / raw
    if raw.is_symlink():
        raise ValueError(label + ' cannot be a symlink')
    path = raw.resolve(strict=True)
    if not stat.S_ISREG(path.stat().st_mode) or sha256(path) != _digest(entry['sha256'], label):
        raise ValueError(label + ' hash mismatch or nonregular input')
    return path


def expected_boot_metadata(bios_path):
    """Authenticate the selected clean US card and derive, never override, PC."""
    path = Path(bios_path)
    if not path.is_file() or path.stat().st_size != 262144:
        raise ValueError('reset firmware requires exactly 256 KiB')
    if sha256(path) != USA_BIOS_SHA256:
        raise ValueError('reset firmware is not the selected clean USA System Card')
    with path.open('rb') as stream:
        stream.seek(0x1FFE)
        vector = stream.read(2)
    return {'mode': 'system-card-reset', 'profile': 'super',
            'initialization': 'gear-deterministic-zero-v1', 'vector_physical': 8190,
            'pc': vector[0] | (vector[1] << 8), 'a': 0, 'x': 0, 'y': 0, 'sp': 0,
            'p': 4, 'clock_divisor': 12, 'ticks': 0, 'cycles': 0, 'mpr': [0] * 8,
            'bram': 'blank-unformatted'}


def validate_boot_metadata(value, bios_path):
    """Return exact initial metadata after authentic hash/vector/type checks."""
    expected = expected_boot_metadata(bios_path)
    _keys(value, expected, 'reset boot metadata')
    for key, wanted in expected.items():
        actual = value[key]
        if type(actual) is not type(wanted) or actual != wanted:
            raise ValueError('reset boot metadata mismatch: ' + key)
    if any(type(bank) is not int for bank in value['mpr']):
        raise ValueError('reset boot MPR values must be integer bytes')
    return copy.deepcopy(expected)


def _module_files(base, config):
    _keys(config, {'source', 'manifest'}, 'module')
    files = {'module_source': _file(base, config['source'], 'module.source'),
             'module_manifest': _file(base, config['manifest'], 'module.manifest')}
    if files['module_source'].suffix != '.cpp' or files['module_manifest'].stat().st_size > 64 * 1024 * 1024:
        raise ValueError('module source or manifest bound is invalid')
    manifest = json.loads(files['module_manifest'].read_text(encoding='utf-8'))
    if not isinstance(manifest, dict):
        raise ValueError('module manifest must be an object')
    _integer(manifest.get('schema'), 1, 1, 'module schema')
    _integer(manifest.get('runtime_abi'), ABI, ABI, 'module ABI')
    _integer(manifest.get('native_instructions_emitted'), 1, 1000000, 'positive module identities')
    if 'capture_runtime_abi' in manifest:
        _integer(manifest['capture_runtime_abi'], ABI, ABI, 'reset source capture ABI')
    # The official API also supports a legacy one-source authored CFG module.
    if not {'translation_units', 'generated_headers'} & manifest.keys():
        return files
    seen, units = set(), []
    folder = files['module_manifest'].parent
    for field, suffix, minimum, maximum, prefix in (
            ('translation_units', '.cpp', 1, 512, 'module_unit'),
            ('generated_headers', '.hpp', 0, 256, 'module_header')):
        entries = manifest.get(field)
        if not isinstance(entries, list) or not minimum <= len(entries) <= maximum:
            raise ValueError('module artifact list bound: ' + field)
        for entry in entries:
            _keys(entry, {'file', 'sha256'}, 'module artifact')
            name = entry['file']
            if (type(name) is not str or not 1 <= len(name) <= 128
                    or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name) is None
                    or not name.endswith(suffix)
                    or name.split('.', 1)[0].upper() in {'CON', 'PRN', 'AUX', 'NUL',
                        *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}
                    or name.casefold() in seen):
                raise ValueError('module artifact requires a unique portable basename')
            seen.add(name.casefold())
            path = _file(folder, {'path': name, 'sha256': entry['sha256']}, 'module artifact')
            if path.parent != folder:
                raise ValueError('module artifact escapes its manifest folder')
            files[prefix + ':' + name] = path
            if field == 'translation_units': units.append(path)
    if files['module_source'] not in units:
        raise ValueError('module source is absent from translation_units')
    return files


def validate_reset_descriptor(config, descriptor_path):
    """Rehash all reset/media/module bindings; return JSON-safe validation data.

    This checks the narrow consumer recipe, not Git cleanliness. Callers must
    independently verify the declared exact toolkit checkout; prepare() does.
    """
    _keys(config, {'schema', 'name', 'tool', 'module', 'boot', 'runtime', 'limits', *ASSETS}, 'reset descriptor')
    _integer(config['schema'], 1, 1, 'descriptor schema')
    if type(config['name']) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', config['name']) is None:
        raise ValueError('invalid descriptor name')
    _keys(config['boot'], {'mode', 'profile'}, 'boot')
    if config['boot'] != {'mode': 'system-card-reset', 'profile': 'super'}:
        raise ValueError('only explicit Super System Card reset boot is selected')
    runtime = config['runtime']
    if (not isinstance(runtime, dict) or not set(RUNTIME) <= set(runtime)
            or not set(runtime) <= set(RUNTIME) | set(AUDIO_DEFAULT_FIELDS)):
        raise ValueError('reset runtime has missing or unsupported fields')
    for key, value in (RUNTIME | {key: value for key, value in AUDIO_DEFAULT_FIELDS.items() if key in runtime}).items():
        if type(config['runtime'][key]) is not type(value) or config['runtime'][key] != value:
            raise ValueError('reset runtime differs at ' + key)
    _keys(config['limits'], {'steps', 'ticks', 'wall_seconds'}, 'limits')
    _integer(config['limits']['steps'], 1, 20000000000, 'steps')
    _integer(config['limits']['ticks'], 1, (1 << 64) - 1, 'ticks')
    _integer(config['limits']['wall_seconds'], 1, 600, 'wall_seconds')
    tool = config['tool']
    _keys(tool, {'path', 'revision', 'source_sha256', 'runtime_abi'}, 'tool')
    _digest(tool['revision'], 'tool revision', 40)
    _digest(tool['source_sha256'], 'tool source')
    _integer(tool['runtime_abi'], ABI, ABI, 'tool ABI')
    if type(tool['path']) is not str or not tool['path'] or '\0' in tool['path']:
        raise ValueError('tool requires an explicit path')
    base = Path(descriptor_path).resolve().parent
    files = _module_files(base, config['module'])
    for name in ASSETS: files[name] = _file(base, config[name], name)
    boot = expected_boot_metadata(files['bios'])
    return {'files': {name: str(path) for name, path in files.items()},
            'identities': {name: sha256(path) for name, path in files.items()},
            'boot': boot, 'audio_selection': dict(SELECTION), 'wav_frame_limit': WAV_FRAME_LIMIT,
            'tool': dict(tool, path=str((base / tool['path']).resolve()))}


def load_reference(launch_path, receipt_path):
    """Select the frozen reset reference only; no mutable media discovery."""
    launch_path, receipt_path = Path(launch_path).resolve(strict=True), Path(receipt_path).resolve(strict=True)
    if launch_path.stat().st_size > 65536 or receipt_path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('reference JSON exceeds its finite bound')
    launch = json.loads(launch_path.read_text(encoding='utf-8'))
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    _keys(launch, {'argv', 'inputs', 'source'}, 'reference launch')
    _keys(launch['source'], {'revision', 'source_sha256', 'source_files'}, 'reference source')
    _digest(launch['source']['revision'], 'reference revision', 40)
    _digest(launch['source']['source_sha256'], 'reference source SHA256')
    _integer(launch['source']['source_files'], 1, 4096, 'reference source file count')
    argv = launch['argv']
    if (not isinstance(argv, list) or len(argv) < 7 or len(argv) > 100
            or any(type(item) is not str or not item or '\0' in item for item in argv)
            or argv[1:3] != ['--system-card-reset', 'super'] or argv[6] != 'hybrid'):
        raise ValueError('reference must be the explicit Super reset command, without payload/IPL overrides')
    fixed = {'--dev-port': '0', '--dev-start-paused': 'on', '--video-output': 'continuous',
             '--audio-output': 'on', '--audio-frames': str(WAV_FRAME_LIMIT), '--cd-unknown-status': 'gear-good'}
    required = set(fixed) | {'--audio-out', '--wall-seconds', '--toc', '--disc', '--libchdr'}
    optional = {'--dev-memory-write': 'off', '--joypad': '2', '--joypad-region': 'usa', '--multitap': 'off'}
    tail, options = argv[7:], {}
    if len(tail) % 2: raise ValueError('reference options require exact flag/value pairs')
    for flag, value in zip(tail[::2], tail[1::2]):
        if flag not in required | set(optional) or flag in options:
            raise ValueError('forbidden or duplicate reference option: ' + flag)
        options[flag] = value
    if not required <= options.keys() or any(options[key] != value for key, value in fixed.items()):
        raise ValueError('reference default raw44100 Gear/reset selection differs')
    if any(options[key] != value for key, value in optional.items() if key in options):
        raise ValueError('reference has an unsupported host/input override')
    try: limits = {'steps': int(argv[4]), 'ticks': int(argv[5]), 'wall_seconds': int(options['--wall-seconds'])}
    except ValueError as error: raise ValueError('reference limits must be decimal integers') from error
    limits_bounds = {'steps': 20000000000, 'ticks': (1 << 64) - 1, 'wall_seconds': 600}
    for name, maximum in limits_bounds.items(): _integer(limits[name], 1, maximum, name)
    paths = {'bios': argv[3], **{name: options['--' + name] for name in ASSETS if name != 'bios'}}
    if not isinstance(launch['inputs'], dict) or set(launch['inputs']) != set(paths.values()):
        raise ValueError('reference must hash exactly the four explicit original assets')
    assets = {}
    for name, path in paths.items():
        entry = {'path': path, 'sha256': launch['inputs'][path]}
        resolved = _file(launch_path.parent, entry, 'reference ' + name)
        assets[name] = dict(entry, path=str(resolved))
    states = receipt.get('states')
    if (receipt.get('error') is not None or receipt.get('child_stopped') is not True
            or type(receipt.get('returncode')) is not int or receipt['returncode'] != 0
            or not isinstance(states, list) or not 1 <= len(states) <= 10000):
        raise ValueError('reference requires a completed, stopped, successful observation')
    unchanged = receipt.get('inputs_unchanged')
    if not isinstance(unchanged, dict) or set(unchanged) != set(launch['inputs']) or any(value is not True for value in unchanged.values()):
        raise ValueError('reference original-input closeout is incomplete')
    first = states[0]
    if first.get('paused') is not True or type(first.get('frame')) is not int or first['frame'] != 0 or type(first.get('ticks')) is not int or first['ticks'] != 0:
        raise ValueError('reference must expose paused reset before its first instruction')
    boot = validate_boot_metadata(first['host']['boot'], assets['bios']['path'])
    debug = first['host'].get('debug_memory')
    wanted_debug = {'write_enabled': False, 'write_requests': 0, 'bytes_changed': 0}
    if (not isinstance(debug, dict) or set(debug) != set(wanted_debug)
            or any(type(debug[key]) is not type(value) or debug[key] != value for key, value in wanted_debug.items())):
        raise ValueError('reference cannot contain development writes')
    return {'assets': assets, 'limits': limits, 'boot': boot, 'audio_selection': dict(SELECTION),
            'wav_frame_limit': WAV_FRAME_LIMIT, 'reference_source': launch['source'],
            'bindings': {str(launch_path): sha256(launch_path), str(receipt_path): sha256(receipt_path)}}


def descriptor_text(reference, module, tool_root, identity):
    module = Path(module).resolve(strict=True)
    manifest = module.with_name('module.json')
    quote = lambda value: json.dumps(str(value), ensure_ascii=True)
    lines = ['schema = 1', 'name = "ys3-reset-native"', '', '[tool]',
             'path = ' + quote(Path(tool_root).resolve().as_posix()),
             'revision = ' + quote(identity['revision']), 'source_sha256 = ' + quote(identity['source_sha256']),
             'runtime_abi = 17', '', '[boot]', 'mode = "system-card-reset"', 'profile = "super"', '']
    entries = {'module.source': {'path': str(module), 'sha256': sha256(module)},
               'module.manifest': {'path': str(manifest), 'sha256': sha256(manifest)}, **reference['assets']}
    for name, item in entries.items():
        lines += ['[' + name + ']', 'path = ' + quote(Path(item['path']).as_posix()), 'sha256 = ' + quote(item['sha256']), '']
    lines += ['[runtime]'] + [key + ' = ' + (str(value) if type(value) is int else quote(value)) for key, value in (RUNTIME | AUDIO_DEFAULT_FIELDS).items()]
    lines += ['', '[limits]'] + [key + ' = ' + str(value) for key, value in reference['limits'].items()]
    return '\n'.join(lines) + '\n'


def verify_identity(tool_root, revision, abi, source_sha256):
    _digest(revision, 'expected revision', 40); _digest(source_sha256, 'expected source')
    _integer(abi, ABI, ABI, 'expected ABI')
    command = [sys.executable, str(ROOT / 'scripts/verify_tool.py'), '--tool-root', str(tool_root),
               '--expected-revision', revision, '--expected-abi', str(abi), '--expected-source-sha256', source_sha256]
    result = json.loads(subprocess.check_output(command, text=True, timeout=60))
    source = result['shared_source_identity']
    if (result['revision'] != revision or result['runtime_abi'] != ABI or result['tracked_source_clean'] is not True
            or source['revision'] != revision or source['source_sha256'] != source_sha256):
        raise ValueError('verified toolkit identity differs from explicit reset pin')
    return result


def prepare(tool_root, reference_launch, reference_receipt, module, out, *, expected_revision, expected_abi, expected_source_sha256):
    """Verify and write a new descriptor, then invoke official verify; no build."""
    out = Path(out).resolve()
    if out.exists() or out.is_symlink(): raise ValueError('reset descriptor output must be new')
    tool_root = Path(tool_root).resolve(strict=True)
    identity = verify_identity(tool_root, expected_revision, expected_abi, expected_source_sha256)
    reference = load_reference(reference_launch, reference_receipt)
    text = descriptor_text(reference, module, tool_root, identity['shared_source_identity'])
    checked = validate_reset_descriptor(tomllib.loads(text), out)
    with out.open('x', encoding='utf-8', newline='\n') as stream: stream.write(text)
    env = dict(os.environ, PYTHONPATH=str(tool_root), PYTHONSAFEPATH='1', PYTHONDONTWRITEBYTECODE='1')
    official = json.loads(subprocess.check_output([sys.executable, '-m', 'pcerecomp.project', 'verify', str(out)],
                                                 cwd=tool_root, env=env, text=True, timeout=60))
    if (official.get('verified') is not True or official.get('revision_override') is not False
            or official['descriptor_sha256'] != sha256(out) or official['files'] != checked['identities']
            or official['tool'] != identity['shared_source_identity']):
        raise ValueError('official reset descriptor binding differs')
    for path, digest in reference['bindings'].items():
        if sha256(path) != digest: raise ValueError('reset reference changed during preparation')
    if checked != validate_reset_descriptor(tomllib.loads(out.read_text(encoding='utf-8')), out):
        raise ValueError('reset assets/module changed during preparation')
    if identity != verify_identity(tool_root, expected_revision, expected_abi, expected_source_sha256):
        raise ValueError('reset toolkit changed during preparation')
    return {'prepared': True, 'descriptor': str(out), 'descriptor_sha256': sha256(out),
            'tool_identity': identity, 'validation': checked, 'official_verification': official,
            'reference_bindings': reference['bindings'], 'reference_source': reference['reference_source'],
            'scope': 'Official reset descriptor verification only; no build or host execution.'}


class _Once(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if getattr(namespace, self.dest, None) is not None:
            parser.error(option_string + ' may be supplied only once')
        setattr(namespace, self.dest, values)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    for name in ('tool-root', 'reference-launch', 'reference-receipt', 'module', 'out'):
        parser.add_argument('--' + name, type=Path, required=True, action=_Once)
    parser.add_argument('--expected-revision', action=_Once)
    parser.add_argument('--expected-abi', type=int, choices=(ABI,), action=_Once)
    parser.add_argument('--expected-source-sha256', action=_Once)
    return parser


def main():
    parser = build_parser(); args = parser.parse_args()
    supplied = (args.expected_revision, args.expected_abi, args.expected_source_sha256)
    if any(value is not None for value in supplied) and not all(value is not None for value in supplied):
        parser.error('development reset verification requires revision, ABI17 and source SHA256 together')
    if all(value is None for value in supplied):
        pin = json.loads((ROOT / 'toolchain.json').read_text(encoding='utf-8'))['tool']
        if pin['runtime_abi'] != ABI:
            parser.error('public pin is not ABI17; supply all three explicit verified identity arguments')
        supplied = pin['revision'], pin['runtime_abi'], pin['source_sha256']
    result = prepare(args.tool_root, args.reference_launch, args.reference_receipt, args.module, args.out,
                     expected_revision=supplied[0], expected_abi=supplied[1], expected_source_sha256=supplied[2])
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
