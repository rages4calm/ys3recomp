"""Open the privately selected qualified native build or its generated sources."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import tomllib
import uuid

if __package__:
    from .package_checks import packaged_environment, verify_package
    from .replay_route import validate_project_binding
else:
    from package_checks import packaged_environment, verify_package
    from replay_route import validate_project_binding

ROOT = Path(__file__).resolve().parents[1]
SELECTION = ROOT / '.local/launcher/selection.json'
METADATA_LIMIT = 16 * 1024 * 1024
REPLAY_RECEIPT_LIMIT = 128 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path, *, size_limit=METADATA_LIMIT):
    require(Path(path).stat().st_size <= size_limit, 'Metadata exceeds its size bound')
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def load_replay_receipt(path):
    """Long finite routes retain every state; other metadata keeps its small cap."""
    return load(path, size_limit=REPLAY_RECEIPT_LIMIT)


def bound(path, digest, graph=None):
    path = (ROOT / path).resolve(strict=True)
    require(path.is_file() and sha(path) == digest, 'Selected file changed: ' + str(path))
    if graph is not None:
        require(graph.get(str(path)) == digest, 'File is absent from the selected qualification: ' + str(path))
    return path


def shared(arguments, environment):
    return json.loads(subprocess.check_output(arguments, cwd=ROOT, env=environment,
                                              text=True, timeout=120))


def receipt_contract(receipt, qualification=None):
    """Decode retained receipt layouts without changing their bindings."""
    require(receipt.get('passed') is True and type(receipt.get('exit_code')) is int
            and receipt['exit_code'] == 0, 'Selected route did not pass with a clean exit')
    if 'cut_policy' in receipt:
        require(receipt['cut_policy'] == 'explicit-milestones'
                and all(receipt.get(k) is True for k in
                        ('explicit_manifest_quit', 'natural_quit', 'child_stopped')),
                'Selected sparse scenario did not close naturally at explicit milestones')
        require(receipt.get('reference') is False
                and type(receipt.get('native')) is int and receipt['native'] > 0
                and type(receipt.get('interpreted')) is int and receipt['interpreted'] == 0,
                'Selected sparse scenario is not native execution')
        require(type(qualification) is dict and qualification.get('native_qualified') is True,
                'Sparse scenario requires its native qualification')
        package = receipt.get('package_after')
        require(type(package) is dict and bool(package)
                and receipt.get('package_before') == package
                and qualification.get('current_package') == package,
                'Sparse scenario package differs from its qualification')
        identity = qualification.get('tool')
        require(type(identity) is dict, 'Missing qualified toolkit identity')
        if set(identity) == {'revision', 'runtime_abi', 'shared_source_identity', 'tracked_source_clean'}:
            require(identity['tracked_source_clean'] is True
                    and type(identity['runtime_abi']) is int and identity['runtime_abi'] > 0,
                    'Invalid qualified toolkit verification')
            source = identity['shared_source_identity']
            require(type(source) is dict and identity['revision'] == source.get('revision'),
                    'Qualified toolkit revisions disagree')
        else:
            source = identity
        require(set(source) == {'revision', 'source_sha256', 'source_files'}
                and type(source['revision']) is str and re.fullmatch('[0-9a-f]{40}', source['revision'])
                and type(source['source_sha256']) is str and re.fullmatch('[0-9a-f]{64}', source['source_sha256'])
                and type(source['source_files']) is int and source['source_files'] > 0,
                'Invalid qualified toolkit source identity')
        def scenario_artifact(name):
            path = receipt.get(name)
            require(type(path) is str and bool(path) and '\0' not in path,
                    'Invalid sparse scenario artifact: ' + name)
            inputs = receipt.get('input_bindings')
            require(type(inputs) is dict, 'Missing sparse scenario input bindings')
            digest = inputs.get(path)
            require(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest),
                    'Missing sparse scenario artifact digest: ' + name)
            return path, digest
        return (scenario_artifact('project_descriptor'), scenario_artifact('project_build_receipt'),
                identity, package)
    if receipt.get('kind') == 'ys3-reset-extension-replay':
        require(receipt.get('child_stopped') is True and receipt.get('natural_quit') is True,
                'Selected extension did not close naturally')
        def artifact(name):
            entry = receipt[name]
            require(type(entry) is dict and set(entry) == {'path', 'sha256'},
                    'Unexpected extension artifact binding: ' + name)
            require(type(entry['path']) is str and bool(entry['path']) and '\0' not in entry['path'],
                    'Invalid extension artifact path: ' + name)
            require(type(entry['sha256']) is str and re.fullmatch('[0-9a-f]{64}', entry['sha256']),
                    'Invalid extension artifact digest: ' + name)
            return entry['path'], entry['sha256']
        descriptor, built = artifact('project_descriptor'), artifact('project_build_receipt')
        require(receipt['tool_identity_before'] == receipt['tool_identity_after'],
                'Qualified extension toolkit changed')
        require(receipt['package_before'] == receipt['package_after'],
                'Qualified extension package changed')
        return descriptor, built, receipt['tool_identity_after'], receipt['package_after']
    return ((receipt['project_descriptor'], receipt['project_descriptor_sha256']),
            (str(Path(receipt['project_build']) / 'build-receipt.json'),
             receipt['project_build_receipt_sha256']),
            receipt['tool_identity'], receipt['desktop_contract']['package_after'])


def tree_members(directory):
    directory = Path(directory)
    require(directory.is_dir() and not directory.is_symlink() and not directory.is_junction(),
            'Verification tree is missing or linked')
    rows = []
    for path in directory.rglob('*'):
        if '__pycache__' in path.parts:
            continue
        require(not path.is_symlink() and not path.is_junction(), 'Linked verification input')
        rows.append([path.relative_to(directory).as_posix(), path.is_dir()])
    return sorted(rows)


def recheck_inputs(snapshot):
    for path, digest in snapshot['raw_bindings'].items():
        require(sha(path) == digest, 'Verified input changed before launch: ' + path)
    for directory, members in snapshot['trees'].items():
        require(tree_members(directory) == members, 'Verified artifact membership changed: ' + directory)


def verified_launch(tool, descriptor, binary, selected, environment):
    """Use one official verification object for binding and command derivation."""
    code = '''import json,sys
from pathlib import Path
sys.path[:0]=[sys.argv[1],sys.argv[2]]
from scripts.verify_tool import verify as verify_tool
from scripts.play_local import sha,tree_members
from pcerecomp import project
tool,descriptor,binary=map(Path,sys.argv[2:5])
expected=json.loads(sys.argv[5])
actual=verify_tool(tool,expected['revision'],expected['runtime_abi'])
p=project.verify(descriptor)
actual['shared_source_identity']=p['tool_identity']
if actual!=expected:raise ValueError('Selected clean toolkit identity differs from its qualification')
command=project.command_for(p,binary)
raw={str(path):p['identities'][name] for name,path in p['files'].items()}
raw[str(descriptor)]=p['descriptor_sha256']
directories=[tool/name for name in ('runtime','pcerecomp','cmake','scripts') if (tool/name).is_dir()]
directories.append(Path(p['files']['module_source']).parent)
trees={str(path):tree_members(path) for path in directories}
for directory in directories[:-1]:
 for path in directory.rglob('*'):
  if path.is_file() and '__pycache__' not in path.parts and path.suffix in ('.py','.cpp','.hpp','.h','.cmake'):raw[str(path)]=sha(path)
raw[str(tool/'CMakeLists.txt')]=sha(tool/'CMakeLists.txt')
if project.source_identity(tool)!=p['tool_identity']:raise ValueError('Toolkit changed during command derivation')
if verify_tool(tool,expected['revision'],expected['runtime_abi'])!={k:v for k,v in actual.items() if k!='shared_source_identity'}:raise ValueError('Toolkit verification changed')
print(json.dumps(dict(tool=actual,verification=dict(schema=1,verified=True,**project._binding(p)),command=command,raw_bindings=raw,trees=trees)))
'''
    with tempfile.TemporaryDirectory(prefix='ys3-launch-source-') as prefix:
        require(not any(Path(prefix).iterdir()), 'Source-only import prefix must start empty')
        return shared([sys.executable, '-I', '-B', '-X', 'pycache_prefix=' + prefix,
                       '-c', code, str(ROOT), str(tool), str(descriptor), str(binary),
                       json.dumps(selected)], environment)


def prepare():
    config = load(SELECTION)
    require(config.get('schema') == 1, 'Unknown private launcher selection schema')
    qualification_digest = config['qualification']['digest']
    qfile = bound(**config['qualification'])
    qualification = load(qfile)
    require(qualification.get('result') == 'pass' or qualification.get('passed') is True,
            'Selected qualification did not pass')
    graph = qualification['evidence_sha256']
    receipt_path = bound(**config['replay_receipt'], graph=graph)
    receipt = load_replay_receipt(receipt_path)
    descriptor_binding, build_binding, selected, qualified_package = receipt_contract(receipt, qualification)
    descriptor = bound(*descriptor_binding, graph=graph)
    built_path = bound(*build_binding, graph=graph)
    built = load(built_path)
    config = tomllib.loads(descriptor.read_text(encoding='utf-8'))
    tool = (descriptor.parent / config['tool']['path']).resolve(strict=True)
    if 'cut_policy' in receipt:
        source = selected.get('shared_source_identity', selected)
        expected = dict(revision=source['revision'], runtime_abi=config['tool']['runtime_abi'],
                        shared_source_identity=source, tracked_source_clean=True)
        require(set(selected) == set(source) or selected == expected,
                'Qualified toolkit differs from the bound descriptor ABI')
        selected = expected
    environment = dict(os.environ, PYTHONPATH=str(tool), PYTHONSAFEPATH='1', PYTHONDONTWRITEBYTECODE='1')
    plan = verified_launch(tool, descriptor, Path(built['binary']), selected, environment)
    require(plan['tool'] == selected, 'Selected clean toolkit identity differs from its qualified receipt')
    validate_project_binding(built, plan['verification'])
    package = verify_package(built, built['binary'])
    require(package == qualified_package, 'Qualified desktop package changed')
    for name, digest in package['output_files'].items():
        bound(Path(package['binary']).parent / name, digest, graph)
    command = plan['command']
    require(command.count('--wall-seconds') == 1, 'Unexpected shared manual host wall-limit contract')
    position = command.index('--wall-seconds')
    del command[position:position + 2]
    forbidden = {'--dev-port', '--dev-start-paused', '--dev-memory-write', '--code-capture',
                 '--capture-limit', '--code-capture-start-frame', '--audio-out', '--audio-frames',
                 '--frame-out', '--window-capture', '--hidden', '--unthrottled'}
    require(not any(str(value).split('=', 1)[0] in forbidden for value in command),
            'Manual command unexpectedly requests development controls or output captures')
    module = (descriptor.parent / config['module']['source']['path']).resolve(strict=True)
    require(module.is_file(), 'Selected generated native module is missing')
    environment, isolation = packaged_environment(package['binary'], environment)
    bound(qfile, qualification_digest)
    bound(receipt_path, qualification['evidence_sha256'][str(receipt_path)])
    bound(descriptor, descriptor_binding[1], graph)
    bound(built_path, build_binding[1], graph)
    recheck_inputs(plan)
    require(verify_package(built, built['binary']) == package,
            'Verified desktop package changed before launch')
    return selected, module, package, command, environment, isolation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--info', action='store_true', help='verify readiness and print paths without launching')
    mode.add_argument('--native-files', action='store_true', help='open the qualified generated-source folder')
    args = parser.parse_args()
    try:
        selected, module, package, command, environment, isolation = prepare()
        print('Selected native runtime ABI:', selected['runtime_abi'])
        print('Native source folder:', module.parent)
        print('Executable:', package['binary'])
        print('Controls: Arrows move; Z = I; X = II; Shift = Select; Enter = Run;')
        print('          Space = Pause; F11 = Fullscreen; Esc = Exit.')
        print('Controller: D-pad/left stick = Move; A/Cross = Jump; B/Circle = Attack;')
        print('            Back/Select = Command menu; Start = Run. Connect before or during play.')
        print('            Keep the game window focused to receive controller input.')
        print('Guest saves are volatile; closing the game discards this session\'s save changes.')
        print('Direct manual host: visible, paced; guest step/tick limits remain; no 10-minute wall timeout.')
        if args.info:
            print('Readiness verified. No game or folder was opened.')
            return 0
        if args.native_files:
            os.startfile(module.parent)
            return 0
        session = ROOT / '.local/play-sessions' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8])
        cwd = session / 'cwd'
        cwd.mkdir(parents=True, exist_ok=False)
        print('Private session logs:', session)
        record = {'kind': 'direct-manual-host', 'shared_project_run_used': False,
                  'tool': selected, 'command': command, 'package': package, 'environment': isolation,
                  'guest_saves': 'volatile', 'working_directory_initially_empty': not any(cwd.iterdir())}
        with (session / 'stdout.log').open('xb') as out, (session / 'stderr.log').open('xb') as err:
            result = subprocess.run(command, cwd=cwd, env=environment, stdout=out, stderr=err)
        record['exit_code'] = result.returncode
        (session / 'session.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
        return result.returncode
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print('Preparation required:', error, file=sys.stderr)
        print('See docs/DEVELOPMENT.md for the qualified local build/input setup. Nothing was downloaded or built.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
