"""Archive one explicitly closed, consumer-owned wire journal; retain originals."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import types


def parse_closure(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate closure field')
            result[key] = value
        return result
    def reject_constant(value):
        raise ValueError('Nonfinite closure token: ' + value)
    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError('Nonfinite closure number')
        return result
    return json.loads(raw, object_pairs_hook=unique, parse_constant=reject_constant, parse_float=finite_float)


def archive_closed(source, destination, *, closure, expected_sha256, archive, audit):
    """Closure is caller-owned process evidence, not inferred from journal EOF.

    Use only after actual wait(0), client close and closed file handles. The
    caller authenticates closure to this exact journal. No historical receipt
    is edited; the returned supplemental manifest preserves both identities.
    """
    if (type(closure) is not dict or set(closure) != {'journal', 'exit_code', 'client_closed', 'streams_closed'}
            or type(closure['exit_code']) is not int or closure['exit_code'] != 0
            or closure['client_closed'] is not True or closure['streams_closed'] is not True
            or Path(closure['journal']).resolve(strict=True) != Path(source).resolve(strict=True)):
        raise ValueError('Exact closed-client/process/journal evidence required')
    metadata = archive.archive_wire_journal(source, destination, expected_sha256=expected_sha256, offline=True)
    streamed = audit.audit_wire_journal(destination, encoding='gzip', expected_sha256=expected_sha256,
                                        expected_storage_sha256=metadata['archive_sha256'])
    return dict(closure=closure, raw=dict(path=str(Path(source).resolve()), sha256=expected_sha256),
                gzip=dict(path=str(Path(destination).resolve()), sha256=metadata['archive_sha256'], encoding='gzip'),
                archive=metadata, streaming_audit=streamed)


def main():
    # Execute the adjacent authored loader source, never a timestamp-valid pyc.
    path = Path(__file__).with_name('diagnostic_tools.py')
    loader = types.ModuleType('consumer_diagnostic_loader')
    loader.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), loader.__dict__)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--closure', type=Path, required=True)
    parser.add_argument('--closure-sha256', required=True)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    raw = args.closure.read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.closure_sha256:
        raise ValueError('Closure receipt hash differs')
    closure = parse_closure(raw)
    helpers = loader.load_diagnostics()
    result = archive_closed(args.source, args.destination, closure=closure, expected_sha256=args.sha256,
                            archive=helpers['dev_journal_archive'], audit=helpers['dev_journal_audit'])
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
