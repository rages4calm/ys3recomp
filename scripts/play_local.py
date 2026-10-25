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


def receipt_contract(receipt):
    """Decode the two retained receipt layouts without changing their bindings."""
    require(receipt.get('passed') is True and type(receipt.get('exit_code')) is int
            and receipt['exit_code'] == 0, 'Selected route did not pass with a clean exit')
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
    descriptor_binding, build_binding, selected, qualified_package = receipt_contract(receipt)
    descriptor = bound(*descriptor_binding, graph=graph)
    built_path = bound(*build_binding, graph=graph)
    built = load(built_path)
    config = tomllib.loads(descriptor.read_text(encoding='utf-8'))
    tool = (descriptor.parent / config['tool']['path']).resolve(strict=True)
    source = selected['shared_source_identity']
    checked = shared([sys.executable, str(ROOT / 'scripts/verify_tool.py'), '--tool-root', str(tool),
        '--expected-revision', selected['revision'], '--expected-abi', str(selected['runtime_abi']),
        '--expected-source-sha256', source['source_sha256']], os.environ.copy())
    require(checked == selected, 'Selected clean toolkit identity differs from its qualified receipt')
    environment = dict(os.environ, PYTHONPATH=str(tool), PYTHONSAFEPATH='1', PYTHONDONTWRITEBYTECODE='1')
    verification = shared([sys.executable, '-m', 'pcerecomp.project', 'verify', str(descriptor)], environment)
    validate_project_binding(built, verification)
    package = verify_package(built, built['binary'])
    require(package == qualified_package, 'Qualified desktop package changed')
    for name, digest in package['output_files'].items():
        bound(Path(package['binary']).parent / name, digest, graph)
    code = ('import json,sys; from pathlib import Path; from pcerecomp.project import verify,command_for; '
            'p=verify(Path(sys.argv[1])); print(json.dumps(command_for(p,Path(sys.argv[2]))))')
    command = shared([sys.executable, '-c', code, str(descriptor), package['binary']], environment)
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
