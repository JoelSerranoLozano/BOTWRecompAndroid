#!/usr/bin/env python3
# busab_an.py NAME: logs/NAME.logcat + logs/NAME.busab (busab.sh's switch times) - the [pace] frames of each "normal"
# / "boost" half (5 s after each switch dropped): median period, fps, GPU ms; and the GPU profiles asked for in each
# half: total and G-buffer ms.
import re, sys, statistics, os
S = os.path.dirname(os.path.abspath(__file__))
name = sys.argv[1]
L = open(f'{S}/logs/{name}.logcat', errors='replace').read().splitlines()
sw = []
for l in open(f'{S}/logs/{name}.busab'):
    p = l.split()
    if len(p) >= 2:
        h, m, s = map(int, p[0].split(':')); sw.append((h * 3600 + m * 60 + s, p[1]))
STAMP = re.compile(r'(\d\d):(\d\d):(\d\d)\.(\d+) ')
def secs(l):
    m = STAMP.search(l)
    return int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) + float('0.' + m[4]) if m else None
def mode_at(t):
    cur = None
    for ts, md in sw:
        if t >= ts: cur = (ts, md)
    return cur
PACE = re.compile(r'\[pace\] period ([\d.]+) .* gpu ([-\d.]+) ab')
per = {'normal': [], 'boost': []}
prof = {'normal': [], 'boost': []}
pending = None
for l in L:
    t = secs(l)
    if t is None: continue
    m = PACE.search(l)
    if m:
        c = mode_at(t)
        if c and c[1] in per and t - c[0] >= 5: per[c[1]].append((float(m[1]), float(m[2])))
        continue
    if 'asked for: frame' in l and '[gpuprof]' in l:
        c = mode_at(t); pending = {'mode': c[1] if c else None, 'total': 0, 'gb': 0.0}
        continue
    mh = re.search(r'\[gpuprof\] \d+ marks, ([\d.]+) ms', l)
    if mh and pending:
        pending['total'] = float(mh[1]); prof.setdefault(pending['mode'], []).append(pending); continue
    mr = re.search(r'\[gpuprof\]\s+([\d.]+) ms\s+[\d.]+%\s+pass: 6 color 1600x900', l)
    if mr and pending: pending['gb'] += float(mr[1])
for md in ('normal', 'boost'):
    v = per[md]
    if v:
        p = statistics.median(x[0] for x in v); g = statistics.median(x[1] for x in v)
        print(f'{md:7} {len(v):5} frames  period {p:6.2f} ms  {1000 / p:5.1f} fps  gpu {g:6.2f} ms')
    for q in prof.get(md, []):
        print(f'        profile: {q["total"]:6.1f} ms, G-buffer {q["gb"]:5.1f} ms')
