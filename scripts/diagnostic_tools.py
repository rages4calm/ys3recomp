"""Load the separately pinned diagnostic helpers without cached-source mixing.

Call in a dedicated process before contacting any guest. This authenticates
Python helpers, independently of the runtime's narrower source identity.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parent.parent
NAMES = ('dev_journal', 'dev_client', 'dev_journal_audit',
         'dev_observation', 'dev_write', 'dev_journal_archive')


def load_diagnostics(root=None, pin=None):
    if pin is None:
        pin = json.loads((ROOT / 'toolchain.json').read_text(encoding='utf-8'))['diagnostics']
    root = (ROOT / pin['checkout'] if root is None else Path(root)).resolve(strict=True)
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE)
    if Path(git('rev-parse', '--show-toplevel').decode().strip()).resolve() != root:
        raise ValueError('Diagnostic root must be the Git checkout root')
    if git('rev-parse', 'HEAD').decode().strip() != pin['revision']:
        raise ValueError('Diagnostic Git revision mismatch')
    if git('status', '--porcelain', '--untracked-files=no').strip():
        raise ValueError('Diagnostic tracked source is dirty')
    if any(line and (line[0].islower() or line[0] == 'S')
           for line in git('ls-files', '-v').decode().splitlines()):
        raise ValueError('Diagnostic index has hidden-source flags')
    expected = {'scripts/' + name + '.py' for name in NAMES}
    if set(pin['helper_sha256']) != expected:
        raise ValueError('Complete diagnostic helper closure required')
    sources = {}
    for relative, digest in pin['helper_sha256'].items():
        path = root / relative
        data = path.read_bytes()
        if (path.is_symlink() or hashlib.sha256(data).hexdigest() != digest
                or data != git('show', pin['revision'] + ':' + relative)):
            raise ValueError('Diagnostic helper differs from pinned Git bytes')
        sources[relative] = data
    directory = root / 'scripts'
    cached = sys.modules.get('scripts')
    if cached is not None and (getattr(cached, '__file__', None) is not None
            or list(getattr(cached, '__path__', ())) != [str(directory)]):
        raise ValueError('Cached scripts namespace is not the diagnostic pin')
    for name, module in list(sys.modules.items()):
        if name.startswith('scripts.'):
            relative = name.replace('.', '/') + '.py'
            if (relative not in expected or
                    Path(getattr(module, '__file__', '')).resolve() != root / relative):
                raise ValueError('Cached diagnostic helper origin mismatch')
            # Cached code could predate restored file bytes. Require a fresh process.
            raise ValueError('Diagnostic helpers already cached; use a fresh process')
    if cached is None:
        package = types.ModuleType('scripts')
        package.__path__ = [str(directory)]
        sys.modules['scripts'] = package
    # -B disables writing bytecode, not reading stale timestamp-valid caches.
    # Execute only the authenticated source bytes, in dependency order.
    result = {}
    try:
        for name in NAMES:
            fullname = 'scripts.' + name
            path = directory / (name + '.py')
            module = types.ModuleType(fullname)
            module.__file__ = str(path)
            module.__package__ = 'scripts'
            sys.modules[fullname] = module
            setattr(sys.modules['scripts'], name, module)
            exec(compile(sources['scripts/' + name + '.py'], str(path), 'exec'), module.__dict__)
            result[name] = module
    except BaseException:
        for name in NAMES:
            sys.modules.pop('scripts.' + name, None)
            if hasattr(sys.modules['scripts'], name):
                delattr(sys.modules['scripts'], name)
        if cached is None:
            sys.modules.pop('scripts', None)
        raise
    for name, module in result.items():
        if Path(module.__file__).resolve() != directory / (name + '.py'):
            raise ValueError('Loaded diagnostic helper origin mismatch')
    return result
