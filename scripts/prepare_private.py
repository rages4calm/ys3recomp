"""Verify the retained qualified inputs and prepare a private consumer batch.

No input bytes are copied. Generated output is written only to a new batch.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def prepare(evidence_root, tool_root, output):
    evidence_root = Path(evidence_root).resolve(strict=True)
    tool_root = Path(tool_root).resolve(strict=True)
    sys.path.insert(0, str(ROOT / 'scripts'))
    # CLI verification is the shared build gate; it also checks the source ABI.
    subprocess.run([sys.executable, str(ROOT/'scripts/verify_tool.py'),
                    '--tool-root', str(tool_root)], check=True)
    receipt_path = evidence_root/'.local/ys3/with-bios/execution-boss.json'
    receipt = json.loads(receipt_path.read_text())
    verified = []
    for name, expected in receipt['protected_inputs'].items():
        path = Path(name)
        if not path.is_absolute():
            path = evidence_root/path
        actual = sha(path)
        if actual != expected['expected'] or actual != expected['actual']:
            raise ValueError('protected input hash mismatch: ' + str(path))
        verified.append({'path': str(path.resolve()), 'sha256': actual,
                         'bytes': path.stat().st_size})
    for field in ('source_route', 'source_final_run', 'desktop_replay', 'reference'):
        item = receipt[field]
        path = evidence_root/item['path']
        if path.stat().st_size != item['bytes'] or sha(path) != item['sha256']:
            raise ValueError('qualified linked receipt changed: ' + field)
    route = evidence_root/receipt['source_route']['path']
    command = json.loads(route.read_text())['initial_command']
    inputs = {}
    for flag in ('--bios', '--disc', '--toc', '--libchdr', '--input-script', '--bram'):
        path = Path(command[command.index(flag)+1])
        if not path.is_absolute():
            path = evidence_root/path
        inputs[flag] = {'path': str(path.resolve()), 'sha256': sha(path),
                        'bytes': path.stat().st_size}
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    config = {'schema': 1, 'evidence_root': str(evidence_root),
              'tool_root': str(tool_root), 'route': str(route.resolve()),
              'qualified_receipt': {'path': str(receipt_path), 'sha256': sha(receipt_path)},
              'inputs': inputs, 'protected_inputs': verified,
              'budget_bytes': 1073741824,
              'scope': 'Consumer scratch only; upstream active checkout is read-only.'}
    (out/'inputs.json').write_text(json.dumps(config, indent=2)+'\n')
    env = dict(os.environ, PYTHONPATH=str(tool_root), PYTHONDONTWRITEBYTECODE='1')
    subprocess.run([sys.executable, '-m', 'pcerecomp', 'emit',
                    str(evidence_root/'.local/ys3/with-bios/snapshot.toml'),
                    '--out', str(out/'native-baseline'), '--limit', '1024'],
                   cwd=out, env=env, check=True)
    print('Verified inputs and emitted pinned baseline:', out)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-root', required=True)
    parser.add_argument('--tool-root', default=str(ROOT/'.deps/pcenginerecomp'))
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    prepare(args.evidence_root, args.tool_root, args.out)
