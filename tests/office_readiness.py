#!/usr/bin/env python3
"""Unprivileged isolated TLS fixture: execute the actual Office readiness task."""
import copy
import http.server
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile
import threading
import yaml

ROOT=Path(__file__).resolve().parents[1]


def main():
    runtime=ROOT/'.runtime';runtime.mkdir(mode=0o700,exist_ok=True)
    task=next(t for t in yaml.safe_load((ROOT/'ansible/tasks/office.yml').read_text()) if 'ansible.builtin.uri' in t)
    assert task['ansible.builtin.uri']['validate_certs'] is True
    with tempfile.TemporaryDirectory(prefix='office-readiness-',dir=runtime) as tmp:
        base=Path(tmp);cert=base/'cert.pem';key=base/'key.pem'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=readiness-fixture','-addext','subjectAltName=IP:127.0.0.1','-keyout',str(key),'-out',str(cert)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        class Endpoint(http.server.BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                assert self.path=='/hosting/discovery'
                self.server.attempts+=1
                count=self.server.attempts
                body=b'Warming up' if count<=2 else b'<wopi-discovery><net-zone/></wopi-discovery>'
                self.send_response(503 if count==1 else 200)
                self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Endpoint)
        server.attempts=0
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(cert,key)
        server.socket=context.wrap_socket(server.socket,server_side=True)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            runner=shutil.which('ansible-playbook')
            if not runner:raise RuntimeError('Install ansible-core before this test')
            uri=task['ansible.builtin.uri'];uri['ca_path']=str(cert)
            # Only fixture address/CA injected; validation, until, retry and timeout
            # are the unmodified real task. No production hostname/CA is changed.
            play={'hosts':'all','gather_facts':False,'vars':{'c':{'cloud_host':f'127.0.0.1:{server.server_port}'},'ansible_remote_tmp':str(base/'remote')},'tasks':[task]}
            path=base/'play.yml';path.write_text(yaml.safe_dump([play]))
            env={**os.environ,'ANSIBLE_HOME':str(base/'ansible-home'),'ANSIBLE_LOCAL_TEMP':str(base/'ansible-local'),'ANSIBLE_CONFIG':str(ROOT/'ansible.cfg'),'ANSIBLE_LOG_PATH':'/dev/null'}
            result=subprocess.run([runner,'-i','localhost,','-c','local',str(path)],cwd=ROOT,env=env,capture_output=True,text=True,timeout=180)
            if result.returncode:
                print(result.stdout[-3000:]);print(result.stderr[-1500:]);raise RuntimeError('Actual readiness task failed')
            assert server.attempts==3,'Must reject503 and200 without XML, then accept discovery'
            # Without the private fixture CA, actual URI TLS validation must fail.
            negative=copy.deepcopy(task);negative['ansible.builtin.uri'].pop('ca_path')
            negative['retries']=1;negative['delay']=0
            play['tasks']=[negative];path.write_text(yaml.safe_dump([play]));before=server.attempts
            result=subprocess.run([runner,'-i','localhost,','-c','local',str(path)],cwd=ROOT,env=env,capture_output=True,text=True,timeout=60)
            assert result.returncode!=0 and server.attempts==before,'Untrusted TLS must fail before HTTP'
            print(json.dumps({'actual_ansible_uri_cold503_and_nonxml_retried':True,'valid_xml_accepted':True,'untrusted_tls_rejected':True,'production_paths_modified':False}))
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5)


if __name__=='__main__':main()
