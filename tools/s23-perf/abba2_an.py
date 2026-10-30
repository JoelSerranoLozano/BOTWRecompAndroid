#!/usr/bin/env python3
# abba_an.py: the run_abba.sh series - per run, from 100 s after the open world: fps (stats lines), the GPU profiles'
# totals and G-buffer ms (with its draw count), the GPU temperature; then control vs nopreamble (means of the pairs).
import re, sys, os, glob, statistics, subprocess
S = os.path.dirname(os.path.abspath(__file__))
VK = re.compile(r'\[vk\] t=([\d.]+) frame (\d+) ([\d.]+) fps .*?\((\d+) draws')
res = {}
for path in sorted(glob.glob(f'{S}/logs/{sys.argv[1]}[0-9]_*.logcat')):
    name = os.path.basename(path)[:-7]
    lines = open(path, errors='replace').read().splitlines()
    world, prev, fps = None, None, []
    for l in lines:
        m = VK.search(l)
        if not m: continue
        t, f, r, d = float(m[1]), int(m[2]), float(m[3]), int(m[4])
        if prev and f > prev and d / (f - prev) >= 2000 and world is None: world = t
        if world is not None and t >= world + int(sys.argv[2] if len(sys.argv) > 2 else 100): fps.append(r)
        prev = f
    profs, cur = [], None
    for l in lines:
        mh = re.search(r'\[gpuprof\] \d+ marks, ([\d.]+) ms', l)
        if mh: cur = [float(mh[1]), 0.0, 0]; profs.append(cur); continue
        mr = re.search(r'\[gpuprof\]\s+([\d.]+) ms\s+[\d.]+%\s+pass: 6 color 1600x900.*?, (\d+) draws', l)
        if mr and cur: cur[1] += float(mr[1]); cur[2] += int(mr[2])
    temps = [int(l.split()[4]) / 1000 for l in open(f'{S}/logs/{name}.gpu') if len(l.split()) >= 5]
    t_avg = statistics.mean(temps[len(temps) // 3:]) if temps else 0
    f_med = statistics.median(fps) if fps else 0
    res[name] = (f_med, profs, t_avg)
    print(f'{name:12} fps {f_med:5.2f} ({len(fps)} stats lines)  gpu temp {t_avg:4.1f} C  profiles: ' +
          ', '.join(f'{p[0]:.1f} ms (G-buffer {p[1]:.1f} ms / {p[2]} draws)' for p in profs))
for v in ('_a', '_b'):
    runs = [r for n, r in res.items() if n.endswith(v)]
    if runs:
        f = statistics.mean(r[0] for r in runs)
        tot = [p[0] for r in runs for p in r[1]]; gb = [p[1] for r in runs for p in r[1]]
        print(f'{v:6} mean fps {f:5.2f}; profiles median {statistics.median(tot) if tot else 0:.1f} ms, '
              f'G-buffer median {statistics.median(gb) if gb else 0:.1f} ms ({len(tot)} profiles)')
