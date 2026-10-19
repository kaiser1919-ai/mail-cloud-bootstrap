#!/usr/bin/env python3
"""Opt-in TEST VPS WebDAV/auth/privacy acceptance; only own UUID fixtures.
Run as root after cloud installation. Requires two generated test users.
No password/cookie appears in argv, output or fixture files. TLS stays verified.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import ssl
import stat
import urllib.error
import urllib.parse
import urllib.request
import uuid


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward an Authorization header to another origin.


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--confirm-test-vps', action='store_true', required=True)
    ap.parse_args()
    if os.geteuid() != 0:
        raise ValueError('Requires root on the authorised TEST VPS')
    state = Path('/etc/mail-cloud-installer/config.json')
    info = state.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
        raise ValueError('Unsafe installer state permissions')
    cfg = json.loads(state.read_text())
    c = cfg['parameters']
    if len(c['users']) < 2:
        raise ValueError('Use at least two test users for cross-account privacy acceptance')
    users = c['users'][:2]
    folder = 'Sentinel-acceptance-' + uuid.uuid4().hex
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))

    def request(actor, target, method='GET', data=None, password=None, file=False):
        endpoint = 'https://' + c['cloud_host'] + '/remote.php/dav/files/' + urllib.parse.quote(target, safe='') + '/' + folder
        if file:
            endpoint += '/fixture.txt'
        pw = cfg['passwords'][actor] if password is None else password
        auth = base64.b64encode((actor + '@' + c['domain'] + ':' + pw).encode()).decode()
        headers = {'Authorization': 'Basic ' + auth, 'Content-Type': 'application/octet-stream'}
        if method == 'DELETE':
            # Pinned Nextcloud supports per-request skip-trash. Only our freshly
            # created UUID folder is addressed; never empty a user's trash.
            headers['X-NC-Skip-Trashbin'] = 'true'
        req = urllib.request.Request(endpoint, data=data, method=method, headers=headers)
        try:
            with opener.open(req, timeout=60) as response:
                return response.status, response.read(2 * 1024**2)
        except urllib.error.HTTPError as error:
            # Never print an error body, private config or auth header.
            return error.code, b''

    created = []
    cleanup_ok = True
    passed = False
    try:
        for user in users:
            if request(user, user, 'MKCOL')[0] != 201:
                raise RuntimeError('Own fixture creation failed; no pre-existing folder was adopted')
            created.append(user)
            payload = b'Synthetic Sentinel acceptance fixture\n' + os.urandom(1024**2)
            if request(user, user, 'PUT', payload, file=True)[0] != 201:
                raise RuntimeError('Own file upload failed')
            status, actual = request(user, user, file=True)
            if status != 200 or actual != payload:
                raise RuntimeError('Own file readback mismatch')
        for actor, target in (users, list(reversed(users))):
            if request(actor, target, file=True)[0] not in (403, 404):
                raise RuntimeError('Cross-account fixture access was not denied')
        first, second = users
        if request(first, first, password=cfg['passwords'][first] + '-wrong', file=True)[0] != 401:
            raise RuntimeError('Wrong password not rejected')
        if request(second, second, password=cfg['passwords'][first], file=True)[0] != 401:
            raise RuntimeError('Cross-user password not rejected')
        passed = True
    finally:
        for user in created:
            try:
                cleanup_ok &= request(user, user, 'DELETE')[0] == 204
            except Exception:
                cleanup_ok = False
        if not cleanup_ok:
            print('Own test fixture may remain: ' + folder)
    if not cleanup_ok:
        raise RuntimeError('Own fixture cleanup incomplete; inspect only the reported test folder')
    print(json.dumps({'webdav_read_write': passed, 'cross_account_access_denied': passed, 'wrong_and_cross_password_rejected': passed, 'own_fixture_cleanup': cleanup_ok}))


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        # HTTP/SSL exceptions can carry request metadata. No raw exception text.
        print('FAIL cloud acceptance: ' + type(e).__name__ + '; inspect test services locally, no credentials printed.')
        raise SystemExit(1)
