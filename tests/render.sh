#!/usr/bin/env bash
set -Eeuo pipefail
cd -- "$(dirname -- "$0")/.."
mkdir -p .runtime/render
export ANSIBLE_HOME="$PWD/.runtime/ansible-home"
export ANSIBLE_LOCAL_TEMP="$PWD/.runtime/ansible"
python3 - <<'PY'
import json,yaml
from pathlib import Path
v=yaml.safe_load(Path('ansible/site.yml').read_text())[0]['vars']
c=json.loads(Path('example.json').read_text());c.update(cloud_host='disk.example.org',mail_host='mail.example.org')
v.update(parameters=c,secrets={'ldap_mail':'synthetic-only'},ansible_remote_tmp=str(Path('.runtime/remote').resolve()))
Path('.runtime/render-vars.json').write_text(json.dumps(v))
PY
ansible-playbook -i localhost, -c local tests/render.yml -e @.runtime/render-vars.json
