#!/usr/bin/python3
"""Read-only pressure guard for explicitly enabled low-headroom test mode."""
from pathlib import Path
import shutil

GIB = 1024**3

def check(root='/srv', meminfo=None, free=None):
    free = shutil.disk_usage(root).free if free is None else free
    if meminfo is None:
        meminfo = {r.split(':', 1)[0]: int(r.split()[1]) for r in Path('/proc/meminfo').read_text().splitlines() if ':' in r}
    if free < 2 * GIB:
        raise ValueError('Pressure stop: need 2 GiB free outside data/staging; do not delete user data')
    if meminfo.get('MemAvailable', 0) < 250 * 1024:
        raise ValueError('Pressure stop: MemAvailable below 250 MiB')
    if meminfo.get('SwapFree', 0) < 512 * 1024:
        raise ValueError('Pressure stop: SwapFree below 512 MiB')
    return {'root_free_bytes': free, 'mem_available_kib': meminfo['MemAvailable'], 'swap_free_kib': meminfo['SwapFree']}

if __name__ == '__main__':
    import json
    try:
        print(json.dumps(check()))
    except ValueError as e:
        raise SystemExit(str(e))
