#!/usr/bin/python3
"""Bootstrap acceptance: real LDAP cloud password and cross-password rejection."""
import json
from mc_runtime import php_binary
import os
from pathlib import Path
import pwd
import subprocess

cfg = json.loads(Path('/etc/mail-cloud-installer/config.json').read_text())
c = cfg['parameters']
users = [{'uid':u,'email':u+'@'+c['domain'],'password':cfg['passwords'][u]} for u in c['users']]
code = r'''define('OC_CONSOLE',true);$users=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);require '/srv/mail-cloud/nextcloud/lib/base.php';
\OCP\Server::get(\OCP\App\IAppManager::class)->loadApps(['authentication']);
$m=\OCP\Server::get(\OCP\IUserManager::class);
foreach($users as $i=>$item){$u=$m->checkPassword($item['email'],$item['password']);
if(!$u || $u->getUID()!==$item['uid'] || $u->getEMailAddress()!==$item['email'])exit(1);
if($m->checkPassword($item['email'],$item['password'].'-wrong')!==false)exit(2);
if(count($users)>1 && $m->checkPassword($item['email'],$users[($i+1)%count($users)]['password'])!==false)exit(3);
}echo "PASS cloud LDAP correct/wrong/cross passwords\n";'''
u = pwd.getpwnam('mailcloud-nextcloud')
def drop():
    os.initgroups(u.pw_name,u.pw_gid);os.setgid(u.pw_gid);os.setuid(u.pw_uid)
subprocess.run([php_binary(),'-d','apc.enable_cli=1','-r',code], input=json.dumps(users).encode(),preexec_fn=drop,check=True,cwd='/srv/mail-cloud/nextcloud')
