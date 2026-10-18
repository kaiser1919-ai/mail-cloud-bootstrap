#!/usr/bin/env bash
set -Eeuo pipefail
cd -- "$(dirname -- "$0")/.."
export ANSIBLE_HOME="$PWD/.runtime/ansible-home"
export ANSIBLE_LOCAL_TEMP="$PWD/.runtime/ansible"
for profile in ubuntu-24.04 debian-13; do
  mkdir -p ".runtime/render/$profile"
  python3 - "$profile" <<'PY'
import json,sys,yaml
from pathlib import Path
key=sys.argv[1]
profiles=json.loads(Path('platforms.json').read_text())['os_profiles']; p=profiles[key]
v=yaml.safe_load(Path('ansible/site.yml').read_text())[0]['vars']
c=json.loads(Path('example.json').read_text()); c.update(cloud_host='disk.example.org',mail_host='mail.example.org')
v.update(os_profiles=profiles,parameters=c,secrets={'ldap_mail':'synthetic-only'},platform={'key':key,**p},
         ansible_distribution=p['distribution'],ansible_distribution_version=p['version'],ansible_distribution_major_version=p['version'].split('.')[0],
         ansible_remote_tmp=str(Path('.runtime/remote').resolve()),render_dir=str(Path('.runtime/render',key).resolve()))
Path('.runtime/render-vars-'+key+'.json').write_text(json.dumps(v))
PY
  ansible-playbook -i localhost, -c local tests/render.yml -e "@.runtime/render-vars-$profile.json"
done
