#!/usr/bin/env python3
# gpuprof_ab.py LOG N [MARGIN]: GPU profiles asked for with prof_gpu ("[gpuprof] asked for: frame F") during a
# LARECOMP_AB=N:<one switch> run, split by stretch ((F // N) & 1; profiles within MARGIN frames of a switch dropped):
# per kind of work the median ms in each stretch and the ratio of the odd stretch (switch on) to the even one.
import re, sys, statistics
from collections import defaultdict
sys.path.insert(0, __file__.rsplit('/', 1)[0])

path, n = sys.argv[1], int(sys.argv[2])
margin = int(sys.argv[3]) if len(sys.argv) > 3 else 4
ASK = re.compile(r'\[gpuprof\] asked for: frame (\d+)')
HEAD = re.compile(r'\[gpuprof\] (\d+) marks, ([\d.]+) ms')
ROW = re.compile(r'\[gpuprof\]\s+([\d.]+) ms\s+([\d.]+)%\s+(.*)$')

def kind(label):
    m = re.match(r'pass: (\d+) color (\d+)x(\d+) fmt (\S+), depth (yes|no)', label)
    if m:
        return f'pass {m[2]}x{m[3]} ({m[1]} color, depth {m[5]})'
    for k in ('dispatch', '(submission start', 'copy texture', 'feedback snapshot', 'present', 'scene upscale'):
        if label.startswith(k):
            return k
    return label[:40]

frames, asked, cur = [], None, None
for line in open(path, errors='replace'):
    m = ASK.search(line)
    if m:
        asked = int(m[1]); continue
    m = HEAD.search(line)
    if m:
        cur = None
        if asked is not None:
            off = asked % n
            if margin <= off <= n - margin:
                cur = {'phase': (asked // n) & 1, 'total': float(m[2]), 'by': defaultdict(float), 'frame': asked}
                frames.append(cur)
        asked = None
        continue
    m = ROW.search(line)
    if m and cur is not None:
        cur['by'][kind(m[3].strip())] += float(m[1])

by_phase = {0: [f for f in frames if f['phase'] == 0], 1: [f for f in frames if f['phase'] == 1]}
print('profiles: ' + ', '.join(f"frame {f['frame']} ab {f['phase']} {f['total']:.1f} ms" for f in frames))
if not by_phase[0] or not by_phase[1]:
    sys.exit('need profiles in both stretches')
med = lambda fs, k: statistics.median(f['by'].get(k, 0.0) for f in fs)
tot0 = statistics.median(f['total'] for f in by_phase[0]); tot1 = statistics.median(f['total'] for f in by_phase[1])
print(f'\n{len(by_phase[0])} profiles in ab 0, {len(by_phase[1])} in ab 1; total {tot0:.1f} -> {tot1:.1f} ms ({tot1 / tot0:.2f})')
keys = sorted({k for f in frames for k in f['by']}, key=lambda k: -med(by_phase[0], k))
print(f'\n{"kind":50} {"ab 0 ms":>8} {"ab 1 ms":>8} {"ratio":>6} {"saved":>6}')
for k in keys:
    a, b = med(by_phase[0], k), med(by_phase[1], k)
    if a < 0.15 and b < 0.15:
        continue
    print(f'{k:50} {a:8.2f} {b:8.2f} {b / a if a else 0:6.2f} {a - b:6.2f}')
