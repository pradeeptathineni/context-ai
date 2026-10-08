#!/usr/bin/env python3
"""Acquire and inspect a fixed wheel set without importing/installing candidate code."""
import argparse
import email
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import zipfile

WHEELS = [{'filename': 'attrs-26.1.0-py3-none-any.whl',
  'sha256': 'c647aa4a12dfbad9333ca4e71fe62ddc36f4e63b2d260a37a8b83d2f043ac309',
  'name': 'attrs',
  'version': '26.1.0',
  'requires': [],
  'license': 'MIT',
  'license_files': ['attrs-26.1.0.dist-info/licenses/LICENSE'],
  'native': [],
  'pth': [],
  'scripts': [],
  'url': 'https://files.pythonhosted.org/packages/64/b4/17d4b0b2a2dc85a6df63d1157e028ed19f90d4cd97c36717afef2bc2f395/attrs-26.1.0-py3-none-any.whl'},
 {'filename': 'hypothesis-6.168.5-cp312-cp312-macosx_10_12_x86_64.whl',
  'sha256': 'ddee1ef4bab47e315b705e42d2f4354e789973d11f9620d2df242aef4cfa42b2',
  'name': 'hypothesis',
  'version': '6.168.5',
  'requires': ["exceptiongroup>=1.0.0 ; python_full_version < '3.11'",
               'sortedcontainers>=2.1.0,<3.0.0',
               "black>=20.8b0 ; extra == 'all'",
               "click>=7.0 ; extra == 'all'",
               "crosshair-tool>=0.0.111 ; extra == 'all'",
               "django>=5.2 ; extra == 'all'",
               "dpcontracts>=0.4 ; extra == 'all'",
               "hypothesis-crosshair>=0.0.30 ; extra == 'all'",
               "lark>=0.10.1 ; extra == 'all'",
               "libcst>=0.3.16 ; extra == 'all'",
               "numpy>=1.21.6 ; extra == 'all'",
               "pandas>=1.1 ; extra == 'all'",
               "pytest>=4.6 ; extra == 'all'",
               "python-dateutil>=1.4 ; extra == 'all'",
               "pytz>=2014.1 ; extra == 'all'",
               "redis>=3.0.0 ; extra == 'all'",
               "rich>=9.0.0 ; extra == 'all'",
               "tzdata>=2026.5 ; (sys_platform == 'emscripten' and extra == 'all') or "
               "(sys_platform == 'win32' and extra == 'all')",
               "watchdog>=4.0.0 ; extra == 'all'",
               "click>=7.0 ; extra == 'cli'",
               "black>=20.8b0 ; extra == 'cli'",
               "rich>=9.0.0 ; extra == 'cli'",
               "libcst>=0.3.16 ; extra == 'codemods'",
               "hypothesis-crosshair>=0.0.30 ; extra == 'crosshair'",
               "crosshair-tool>=0.0.111 ; extra == 'crosshair'",
               "python-dateutil>=1.4 ; extra == 'dateutil'",
               "django>=5.2 ; extra == 'django'",
               "dpcontracts>=0.4 ; extra == 'dpcontracts'",
               "black>=20.8b0 ; extra == 'ghostwriter'",
               "lark>=0.10.1 ; extra == 'lark'",
               "numpy>=1.21.6 ; extra == 'numpy'",
               "pandas>=1.1 ; extra == 'pandas'",
               "pytest>=4.6 ; extra == 'pytest'",
               "pytz>=2014.1 ; extra == 'pytz'",
               "redis>=3.0.0 ; extra == 'redis'",
               "watchdog>=4.0.0 ; extra == 'watchdog'",
               "tzdata>=2026.5 ; (sys_platform == 'emscripten' and extra == 'zoneinfo') or "
               "(sys_platform == 'win32' and extra == 'zoneinfo')"],
  'license': 'MPL-2.0',
  'license_files': ['hypothesis-6.168.5.dist-info/licenses/LICENSE.txt'],
  'native': ['hypothesis/_native.cpython-312-darwin.so'],
  'pth': [],
  'scripts': ['hypothesis-6.168.5.dist-info/entry_points.txt'],
  'url': 'https://files.pythonhosted.org/packages/90/43/a04a727578cbef9f75c11fa6fbad66d13aaffc354f4f979506219814c7d4/hypothesis-6.168.5-cp312-cp312-macosx_10_12_x86_64.whl'},
 {'filename': 'jsonschema-4.26.0-py3-none-any.whl',
  'sha256': 'd489f15263b8d200f8387e64b4c3a75f06629559fb73deb8fdfb525f2dab50ce',
  'name': 'jsonschema',
  'version': '4.26.0',
  'requires': ['attrs>=22.2.0',
               'jsonschema-specifications>=2023.03.6',
               'referencing>=0.28.4',
               'rpds-py>=0.25.0',
               "fqdn; extra == 'format'",
               "idna; extra == 'format'",
               "isoduration; extra == 'format'",
               "jsonpointer>1.13; extra == 'format'",
               "rfc3339-validator; extra == 'format'",
               "rfc3987; extra == 'format'",
               "uri-template; extra == 'format'",
               "webcolors>=1.11; extra == 'format'",
               "fqdn; extra == 'format-nongpl'",
               "idna; extra == 'format-nongpl'",
               "isoduration; extra == 'format-nongpl'",
               "jsonpointer>1.13; extra == 'format-nongpl'",
               "rfc3339-validator; extra == 'format-nongpl'",
               "rfc3986-validator>0.1.0; extra == 'format-nongpl'",
               "rfc3987-syntax>=1.1.0; extra == 'format-nongpl'",
               "uri-template; extra == 'format-nongpl'",
               "webcolors>=24.6.0; extra == 'format-nongpl'"],
  'license': 'MIT',
  'license_files': ['jsonschema-4.26.0.dist-info/licenses/COPYING'],
  'native': [],
  'pth': [],
  'scripts': ['jsonschema-4.26.0.dist-info/entry_points.txt'],
  'url': 'https://files.pythonhosted.org/packages/69/90/f63fb5873511e014207a475e2bb4e8b2e570d655b00ac19a9a0ca0a385ee/jsonschema-4.26.0-py3-none-any.whl'},
 {'filename': 'jsonschema_specifications-2025.9.1-py3-none-any.whl',
  'sha256': '98802fee3a11ee76ecaca44429fda8a41bff98b00a0f2838151b113f210cc6fe',
  'name': 'jsonschema-specifications',
  'version': '2025.9.1',
  'requires': ['referencing>=0.31.0'],
  'license': 'MIT',
  'license_files': ['jsonschema_specifications-2025.9.1.dist-info/licenses/COPYING'],
  'native': [],
  'pth': [],
  'scripts': [],
  'url': 'https://files.pythonhosted.org/packages/41/45/1a4ed80516f02155c51f51e8cedb3c1902296743db0bbc66608a0db2814f/jsonschema_specifications-2025.9.1-py3-none-any.whl'},
 {'filename': 'pyyaml-6.0.3-cp312-cp312-macosx_10_13_x86_64.whl',
  'sha256': '7f047e29dcae44602496db43be01ad42fc6f1cc0d8cd6c83d342306c32270196',
  'name': 'PyYAML',
  'version': '6.0.3',
  'requires': [],
  'license': 'MIT',
  'license_files': ['pyyaml-6.0.3.dist-info/licenses/', 'pyyaml-6.0.3.dist-info/licenses/LICENSE'],
  'native': ['yaml/_yaml.cpython-312-darwin.so'],
  'pth': [],
  'scripts': [],
  'url': 'https://files.pythonhosted.org/packages/d1/33/422b98d2195232ca1826284a76852ad5a86fe23e31b009c9886b2d0fb8b2/pyyaml-6.0.3-cp312-cp312-macosx_10_13_x86_64.whl'},
 {'filename': 'referencing-0.37.0-py3-none-any.whl',
  'sha256': '381329a9f99628c9069361716891d34ad94af76e461dcb0335825aecc7692231',
  'name': 'referencing',
  'version': '0.37.0',
  'requires': ['attrs>=22.2.0',
               'rpds-py>=0.7.0',
               "typing-extensions>=4.4.0; python_version < '3.13'"],
  'license': 'MIT',
  'license_files': ['referencing-0.37.0.dist-info/licenses/COPYING'],
  'native': [],
  'pth': [],
  'scripts': [],
  'url': 'https://files.pythonhosted.org/packages/2c/58/ca301544e1fa93ed4f80d724bf5b194f6e4b945841c5bfd555878eea9fcb/referencing-0.37.0-py3-none-any.whl'},
 {'filename': 'rpds_py-0.30.0-cp312-cp312-macosx_10_12_x86_64.whl',
  'sha256': 'a161f20d9a43006833cd7068375a94d035714d73a172b681d8881820600abfad',
  'name': 'rpds-py',
  'version': '0.30.0',
  'requires': [],
  'license': 'MIT',
  'license_files': ['rpds_py-0.30.0.dist-info/licenses/LICENSE'],
  'native': ['rpds/rpds.cpython-312-darwin.so'],
  'pth': [],
  'scripts': [],
  'url': 'https://files.pythonhosted.org/packages/03/e7/98a2f4ac921d82f33e03f3835f5bf3a4a40aa1bfdc57975e74a97b2b4bdd/rpds_py-0.30.0-cp312-cp312-macosx_10_12_x86_64.whl'},
 {'filename': 'sortedcontainers-2.4.0-py2.py3-none-any.whl',
  'sha256': 'a163dcaede0f1c021485e957a39245190e74249897e2ae4b2aa38595db237ee0',
  'name': 'sortedcontainers',
  'version': '2.4.0',
  'requires': [],
  'license': 'Apache 2.0',
  'license_files': ['sortedcontainers-2.4.0.dist-info/LICENSE'],
  'native': [],
  'pth': [],
  'scripts': [],
  'url': 'https://files.pythonhosted.org/packages/32/46/9cb0e58b2deb7f82b84065f37f3bffeb12413f947f9388e4cac22c4621ce/sortedcontainers-2.4.0-py2.py3-none-any.whl'},
 {'filename': 'typing_extensions-4.15.0-py3-none-any.whl',
  'sha256': 'f0fa19c6845758ab08074a0cfa8b7aecb71c999ca73d62883bc25cc018c4e548',
  'name': 'typing_extensions',
  'version': '4.15.0',
  'requires': [],
  'license': 'PSF-2.0',
  'license_files': ['typing_extensions-4.15.0.dist-info/licenses/LICENSE'],
  'native': [],
  'pth': [],
  'scripts': [],
  'url': 'https://files.pythonhosted.org/packages/18/67/36e9267722cc04a6b9f15c7f3441c2363321a3ea07da7ae0c0707beb2a9c/typing_extensions-4.15.0-py3-none-any.whl'}]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inspect_wheel(path, expected):
    """Check identities and archive boundaries without importing wheel code."""
    path = Path(path)
    if path.is_symlink() or not path.is_file() or sha(path) != expected['sha256']:
        raise ValueError('reviewed wheel missing or changed: ' + expected['filename'])
    with zipfile.ZipFile(path) as archive:
        if sum(item.file_size for item in archive.infolist()) > 20_000_000:
            raise ValueError('wheel exceeds inspection size boundary')
        for item in archive.infolist():
            parts = item.filename.split('/')
            if item.filename.startswith('/') or '..' in parts or '\\' in item.filename:
                raise ValueError('escaping wheel archive member')
            if stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('wheel symlink is not approved')
            if item.filename.endswith('.pth') or '.data/scripts/' in item.filename:
                raise ValueError('startup hooks or script installation are not approved')
        name = next(n for n in archive.namelist() if n.endswith('.dist-info/METADATA'))
        metadata = email.message_from_bytes(archive.read(name))
        if metadata['Name'] != expected['name'] or metadata['Version'] != expected['version']:
            raise ValueError('wheel package identity differs from pin')
        return {'filename': expected['filename'], 'sha256': expected['sha256'],
                'name': metadata['Name'], 'version': metadata['Version'],
                'requires': metadata.get_all('Requires-Dist', []),
                'license': expected['license'], 'license_files': expected['license_files'],
                'native': expected['native'], 'entrypoint_metadata': expected['scripts'],
                'executed': False}


def verified(cache):
    cache = Path(cache).resolve()
    return [inspect_wheel(cache/entry['filename'], entry) for entry in WHEELS]


def extract(cache, destination):
    """Only verified archive bytes are expanded; no installer or hook runs."""
    reports = verified(cache)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    for entry in WHEELS:
        with zipfile.ZipFile(Path(cache)/entry['filename']) as archive:
            for item in archive.infolist():
                target = destination/item.filename
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as output:
                    output.write(archive.read(item))
    return reports


def prepare(cache):
    """Explicit acquisition, separate from trial execution; no runtime dependency."""
    cache = Path(cache)
    if cache.is_symlink():
        raise ValueError('wheel cache must not be a symlink')
    cache = cache.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    missing = []
    for entry in WHEELS:
        target = cache/entry['filename']
        if target.exists():
            inspect_wheel(target, entry)
        else:
            missing.append(entry)
    started = time.monotonic()
    command = None
    attempt = None
    if missing:
        attempt = Path(tempfile.mkdtemp(prefix='acquisition-', dir=cache))
        requirements = attempt/'requirements.txt'
        with requirements.open('x') as handle:
            handle.write('\n'.join(entry['url']+' --hash=sha256:'+entry['sha256'] for entry in missing)+'\n')
        home = attempt/'home'
        home.mkdir(exist_ok=True)
        tmp = attempt/'tmp'
        tmp.mkdir(exist_ok=True)
        command = [sys.executable, '-I', '-m', 'pip', '--isolated', '--disable-pip-version-check',
                   '--no-cache-dir', 'download', '--only-binary=:all:', '--no-deps', '--no-index',
                   '--require-hashes', '--dest', str(cache), '-r', str(requirements)]
        with (attempt/'acquisition.log').open('x') as log:
            run = subprocess.run(command, env={'HOME': str(home), 'TMPDIR': str(tmp),
                                              'PATH': '/usr/bin:/bin'},
                                 stdout=log, stderr=subprocess.STDOUT, timeout=60)
        if run.returncode:
            raise ValueError('wheel acquisition failed; inspect '+str(attempt/'acquisition.log')+'; no candidate executed')
    report = {'operation': 'acquisition-only', 'executed_candidate': False,
              'command': command, 'attempt': str(attempt) if attempt else None,
              'elapsed_seconds': round(time.monotonic()-started, 6),
              'network': 'explicit official PyPI wheel acquisition', 'packages': verified(cache),
              'limitations': ['Exact macOS CPython 3.12 x86_64 wheel set.',
                              'Native extension contents are pinned, not independently audited.',
                              'CLI and pytest entrypoint metadata are retained but never activated.',
                              'Hypothesis plugins disabled and database=None in execution recipe.']}
    path = cache/'acquisition.json'
    if not path.exists():
        with path.open('x') as handle:
            handle.write(json.dumps(report, indent=2)+'\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.cache)
    print(json.dumps({'operation': result['operation'], 'executed_candidate': False,
                      'wheel_count': len(result['packages']), 'cache': str(args.cache.resolve()),
                      'elapsed_seconds': result['elapsed_seconds']}))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)

# Official PyPI artifact identities reviewed 2026-10-08. This trial set is
# deliberately platform-specific; other hosts remain blocked until reviewed.
