#!/usr/bin/python3
import re
import subprocess
import sys


def enabled(text):
    # Fail closed on an unknown/translated CLI output format.
    m = re.search(r'^Enabled providers:\s*\n(.*?)(?=^Disabled providers:|\Z)', text, re.M | re.S)
    return set(re.findall(r'^\s*-\s*([a-z_]+)\s*$', m.group(1), re.M)) if m else set()


if __name__ == '__main__':
    text = subprocess.check_output(['/usr/local/lib/mail-cloud/occ', 'twofactorauth:state', 'recovery_admin'], text=True)
    if not {'totp', 'backup_codes'} <= enabled(text):
        sys.exit('STOP: enable recovery_admin TOTP and generate backup codes first. Portal stays closed.')
    print('Recovery MFA enabled; this does not replace a real recovery-code login test.')
