#!/usr/bin/python3
"""Drop privilege before running occ. JSON stdin option keeps secrets out of argv."""
import json
from mc_runtime import php_binary
import os
import pwd
import subprocess
import sys

args = sys.argv[1:]
if args == ['--json-stdin']:
    args = json.load(sys.stdin)
if not isinstance(args, list) or not all(isinstance(x, str) for x in args):
    raise SystemExit('Invalid arguments')
u = pwd.getpwnam('mailcloud-nextcloud')
code = r'''$argv=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);array_unshift($argv,'occ');$_SERVER['argv']=$argv;$_SERVER['argc']=count($argv);require '/srv/mail-cloud/nextcloud/console.php';'''
# Standard runtime commands may need DB/Redis sockets and staging, not the root state file.
def drop():
    os.initgroups(u.pw_name, u.pw_gid)
    os.setgid(u.pw_gid)
    os.setuid(u.pw_uid)
result = subprocess.run([php_binary(), '-d', 'apc.enable_cli=1', '-d', 'memory_limit=512M', '-d', 'sys_temp_dir=/srv/mail-cloud/staging/nextcloud', '-r', code],
                        input=json.dumps(args).encode(), preexec_fn=drop if os.geteuid() == 0 else None,
                        cwd='/srv/mail-cloud/nextcloud', env={'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent'})
sys.exit(result.returncode)
