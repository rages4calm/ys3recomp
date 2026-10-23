"""Bind a private Ys III module to the shared upstream consumer contract."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('tool-root', 'inputs', 'module', 'out'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--expected-revision', help='explicit clean development tool commit')
    args = parser.parse_args()
    tool = args.tool_root.resolve(strict=True)
    verification = [sys.executable, str(ROOT/'scripts/verify_tool.py'), '--tool-root', str(tool)]
    if args.expected_revision:
        verification += ['--expected-revision', args.expected_revision]
    json.loads(subprocess.check_output(verification, text=True))
    env = dict(os.environ, PYTHONPATH=str(tool), PYTHONDONTWRITEBYTECODE='1')
    identity = json.loads(subprocess.check_output([sys.executable, '-m', 'pcerecomp.project',
                          'identity', str(tool)], env=env, text=True))
    inputs = json.loads(args.inputs.read_text())
    route = json.loads(Path(inputs['route']).read_text())
    command = route['initial_command']
    boot = Path(command[1])
    if not boot.is_absolute():
        boot = Path(inputs['evidence_root'])/boot
    module = args.module.resolve(strict=True)
    manifest = module.with_name('module.json')
    quote = lambda value: json.dumps(str(value), ensure_ascii=True)
    def asset(name, path, digest):
        path = Path(path).resolve(strict=True)
        if sha(path) != digest:
            raise ValueError('input changed while preparing descriptor: '+name)
        return [f'[{name}]', f'path = {quote(path.as_posix())}', f'sha256 = {quote(digest)}', '']
    lines = ['schema = 1', 'name = "ys3-native"', '', '[tool]',
             f'path = {quote(tool.as_posix())}', f'revision = {quote(identity["revision"])}',
             f'source_sha256 = {quote(identity["source_sha256"])}', 'runtime_abi = 12', '']
    lines += asset('module.source', module, sha(module))
    lines += asset('module.manifest', manifest, sha(manifest))
    manifest_config = json.loads((ROOT/'toolchain.json').read_text())
    lines += asset('payload', boot, manifest_config['inputs']['boot_payload']['sha256'])[:-1]
    lines += [f'physical_load = {int(command[2], 0)}', f'pc = {int(command[3], 0)}',
              f'mpr = {json.dumps([int(v) for v in command[4].split(",")])}', '']
    region = 'japan' if json.loads((Path(inputs['evidence_root'])/'.local/boss-check/attempt8/run.json').read_text())['joypad']['japanese'] else 'usa'
    lines += ['[runtime]', 'tier = "hybrid"', 'video = "continuous"',
              'cd_unknown_status = "gear-good"', 'joypad = 2', f'region = {quote(region)}',
              'multitap = "off"', '', '[limits]', f'steps = {int(command[5])}',
              f'ticks = {int(command[6])}', 'wall_seconds = 600', '']
    for flag, value in inputs['inputs'].items():
        lines += asset(flag[2:].replace('-', '_'), value['path'], value['sha256'])
    with args.out.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write('\n'.join(lines))
    result = subprocess.check_output([sys.executable, '-m', 'pcerecomp.project', 'verify',
                                      str(args.out.resolve())], env=env, text=True)
    print(result)


if __name__ == '__main__':
    main()
