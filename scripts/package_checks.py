"""Verify a Windows desktop consumer's adjacent SDL dependency and live binding."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_package(built, binary):
    binary = Path(binary).resolve(strict=True)
    if built.get('schema') != 1 or built.get('kind') != 'pce-consumer-build' or built.get('desktop') is not True:
        raise ValueError('packaged desktop requires an official desktop build receipt')
    if Path(built['binary']).resolve(strict=True) != binary or sha256(binary) != built['binary_sha256']:
        raise ValueError('packaged executable differs from official build')
    dll = binary.with_name('SDL3.dll')
    if dll.is_symlink() or not dll.is_file():
        raise ValueError('packaged SDL3.dll must be an adjacent regular file')
    files = {path.name: sha256(path) for path in sorted(binary.parent.iterdir()) if path.is_file()}
    if files != built['output_files'] or files.get('SDL3.dll') != sha256(dll):
        raise ValueError('packaged dependency/output set differs from official build')
    return {'binary': str(binary), 'binary_sha256': sha256(binary), 'dll': str(dll),
            'dll_sha256': sha256(dll), 'output_files': files, 'official_desktop_build': True}


def packaged_environment(binary, environment=None):
    """Remove every SDL search-path directory and implicit/relative fallback."""
    binary = Path(binary).resolve(strict=True)
    env = dict(os.environ if environment is None else environment)
    keys = [key for key in env if key.casefold() == 'path']
    if len(keys) != 1:
        raise ValueError('one unambiguous child PATH is required')
    key = keys[0]
    original = env[key]
    kept, removed = [], []
    for raw in original.split(os.pathsep):
        value = raw.strip().strip('"')
        path = Path(value)
        reason = None
        if not value or not path.is_absolute():
            reason = 'empty or relative fallback'
        elif path.resolve() == binary.parent or (path / 'SDL3.dll').exists():
            reason = 'packaged bin or SDL DLL search directory'
        if reason:
            removed.append({'entry': raw, 'reason': reason})
        else:
            kept.append(raw)
    if not kept:
        raise ValueError('sanitized PATH has no absolute system/tool directories')
    env[key] = os.pathsep.join(kept)
    selectors = {}
    for name in tuple(env):
        if name.upper() in ('SDL_AUDIODRIVER', 'SDL_VIDEODRIVER', 'SDL_RENDER_DRIVER'):
            selectors[name] = env.pop(name)
    return env, {'original_path': original, 'child_path': env[key], 'removed_entries': removed,
                 'removed_sdl_driver_overrides': selectors,
                 'no_sdk_or_packaged_bin_path': True,
                 'scope': 'Exact child PATH retained; live module inspection separately proves DLL selection.'}


def inspect_loaded_sdl(pid, expected_dll, expected_binary=None):
    """Read the owned paused process's actual loaded-module path through Windows."""
    if os.name != 'nt' or type(pid) is not int or pid <= 0:
        raise ValueError('live module inspection requires a Windows process ID')
    dll = Path(expected_dll).resolve(strict=True)
    binary = Path(expected_binary or dll.with_name('pce-consumer.exe')).resolve(strict=True)
    command = (
        f'$ysProcess = Get-Process -Id {pid} -ErrorAction Stop; '
        '[pscustomobject]@{pid=$ysProcess.Id; executable=$ysProcess.MainModule.FileName; '
        'sdl=@($ysProcess.Modules | Where-Object { $_.ModuleName -ieq "SDL3.dll" } | '
        'Select-Object -ExpandProperty FileName)} | ConvertTo-Json -Compress')
    output = subprocess.check_output(['powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive',
                                      '-Command', command], text=True, encoding='utf-8', timeout=15)
    value = json.loads(output)
    if value['pid'] != pid or Path(value['executable']).resolve(strict=True) != binary:
        raise ValueError('live process executable/PID differs from selected package')
    if len(value['sdl']) != 1 or Path(value['sdl'][0]).resolve(strict=True) != dll:
        raise ValueError('live SDL module did not load from adjacent packaged bin')
    return {'pid': pid, 'executable': str(binary), 'binary_sha256': sha256(binary),
            'loaded_sdl': str(dll), 'dll_sha256': sha256(dll), 'adjacent_package_loaded': True,
            'inspection': 'Windows Get-Process MainModule and Modules while guest paused'}
