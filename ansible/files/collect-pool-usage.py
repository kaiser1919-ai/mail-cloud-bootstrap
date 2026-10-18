#!/usr/bin/python3
"""Read only one bounded shared filesystem; publish no paths, users or filenames."""
import json, os, tempfile, time
from pathlib import Path
DATA=Path('/srv/mail-cloud/data')
OUT=Path('/run/mail-cloud-pool-usage/usage.json')
def measure(path=DATA, mountinfo=Path('/proc/self/mountinfo')):
    matches=[]
    for row in mountinfo.read_text().splitlines():
        left,right=row.split(' - ',1)
        if left.split()[4] == str(path):matches.append(right.split()[0])
    if not matches or matches[-1]!='ext4' or path.stat().st_dev==path.parent.stat().st_dev:
        raise RuntimeError('shared mount unavailable')
    st=os.statvfs(path);unit=st.f_frsize
    total=st.f_blocks*unit;used=(st.f_blocks-st.f_bfree)*unit
    available=st.f_bavail*unit;reserved=(st.f_bfree-st.f_bavail)*unit
    if min(total,used,available,reserved)<0 or total<=0 or used+available+reserved!=total:
        raise RuntimeError('invalid filesystem statistics')
    return {'status':'ok','total_bytes':total,'used_bytes':used,'available_bytes':available,
            'reserved_bytes':reserved,'measured_at':int(time.time()),'refresh_seconds':30,'max_delay_seconds':70}
def publish():
    if os.geteuid()==0:raise RuntimeError('collector must run as unprivileged cloud service account')
    os.umask(0o077)
    try:row=measure()
    except Exception:row={'status':'unavailable','measured_at':int(time.time())}
    fd,name=tempfile.mkstemp(prefix='.usage-',dir=OUT.parent)
    try:
        with os.fdopen(fd,'w') as f:json.dump(row,f);f.write('\n');f.flush();os.fsync(f.fileno())
        os.replace(name,OUT)
    finally:
        if os.path.exists(name):os.unlink(name)
if __name__=='__main__':publish()
