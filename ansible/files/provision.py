#!/usr/bin/python3
import json
from mc_runtime import php_binary
import os
from pathlib import Path
import pwd
import subprocess

c = json.loads(Path('/etc/mail-cloud-installer/config.json').read_text())['parameters']
# No passwords; native Mail login middleware captures only the logged-in user's credential.
code = r'''define('OC_CONSOLE',true);require '/srv/mail-cloud/nextcloud/lib/base.php';
$x=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);
$a=\OCP\Server::get(\OCP\App\IAppManager::class);$a->loadApps(['authentication']);$a->loadApp('mail');
$pm=\OCP\Server::get(\OCA\Mail\Service\Provisioning\Manager::class);
if(count($pm->getConfigs())===0){
$pm->newProvisioning(['provisioningDomain'=>$x['domain'],'emailTemplate'=>'%LDAP:mail%','imapUser'=>'%LDAP:mail%','imapHost'=>$x['mail_host'],'imapPort'=>993,'imapSslMode'=>'ssl','smtpUser'=>'%LDAP:mail%','smtpHost'=>$x['mail_host'],'smtpPort'=>587,'smtpSslMode'=>'tls','masterPasswordEnabled'=>false,'masterPassword'=>'','masterUser'=>'','sieveEnabled'=>false,'ldapAliasesProvisioning'=>false,'ldapAliasesAttribute'=>'']);
}
$um=\OCP\Server::get(\OCP\IUserManager::class);
foreach($x['users'] as $id){$u=$um->get($id);if(!$u || $u->getBackendClassName()!=='LDAP')throw new \RuntimeException('Missing LDAP user');$pm->provisionSingleUser($pm->getConfigs(),$u);}
'''
u = pwd.getpwnam('mailcloud-nextcloud')
def drop():
    os.initgroups(u.pw_name, u.pw_gid); os.setgid(u.pw_gid); os.setuid(u.pw_uid)
subprocess.run([php_binary(), '-d', 'apc.enable_cli=1', '-r', code], input=json.dumps(c).encode(), preexec_fn=drop, check=True, cwd='/srv/mail-cloud/nextcloud')
