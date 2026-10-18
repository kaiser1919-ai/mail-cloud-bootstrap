"""Root-owned, non-secret runtime selection. No arbitrary binary paths from JSON."""
import json
from pathlib import Path
import stat


def php_binary(path=Path('/usr/local/lib/mail-cloud/platform.json')):
    s = path.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_uid != 0 or s.st_mode & 0o022:
        raise ValueError('Unsafe installed runtime profile')
    profile = json.loads(path.read_text())
    expected = {('ubuntu', '24.04'): '8.3', ('debian', '13'): '8.4'}
    version = expected.get((profile.get('os_id'), profile.get('version')))
    if version is None or profile.get('php_version') != version:
        raise ValueError('Unsupported installed runtime profile')
    return '/usr/bin/php' + version
