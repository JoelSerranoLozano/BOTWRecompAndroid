#!/usr/bin/env python3
# perdraw.py LOG [PASS_PREFIX]: LARECOMP_GPUPROF_DRAWS profiles - each draw's GPU time (a row runs from its mark to
# the next, and a draw's mark comes after it: a draw costs the row before its own), for the passes whose label starts
# with PASS_PREFIX (default the G-buffer, "pass: 6 color 1600x900"): totals, a fit time = fixed + per vertex, the
# costliest draws and shader pairs, and the spread.
import re, sys, statistics
from collections import defaultdict

path = sys.argv[1]
prefix = sys.argv[2] if len(sys.argv) > 2 else 'pass: 6 color 1600x900'
HEAD = re.compile(r'\[gpuprof\] (\d+) marks, ([\d.]+) ms')
ROW = re.compile(r'\[gpuprof\]\s+([\d.]+) ms\s+[\d.]+%\s+(.*?)(?:, \d+ draws)?\s*$')
DRAW = re.compile(r'draw vs ([0-9a-f]+) fs ([0-9a-f]+) n (\d+) inst (\d+)( idx)?')

frames, cur = [], None
for line in open(path, errors='replace'):
    m = HEAD.search(line)
    if m:
        cur = {'total': float(m[2]), 'rows': []}; frames.append(cur); continue
    m = ROW.search(line)
    if m and cur is not None and 'last mark' not in line:
        cur['rows'].append((float(m[1]), m[2].strip()))
if not frames:
    sys.exit('no profiles')

for fi, f in enumerate(frames):
    rows = f['rows']
    draws = []  # (ms, vs, fs, verts, pass label)
    passes = defaultdict(lambda: [0, 0.0, 0.0])  # label kind -> draws, draw ms, overhead ms (setup + end)
    cur_pass = None
    for i, (ms, lab) in enumerate(rows):
        if lab.startswith('pass:'):
            cur_pass = re.sub(r', first fs [0-9a-f]+', '', lab)
        nxt = rows[i + 1][1] if i + 1 < len(rows) else ''
        dm = DRAW.match(nxt)
        if dm and cur_pass:  # this row is the next draw's time
            verts = int(dm[3]) * max(int(dm[4]), 1)
            draws.append((ms, dm[1], dm[2], verts, cur_pass))
            passes[cur_pass][0] += 1; passes[cur_pass][1] += ms
        elif cur_pass:
            passes[cur_pass][2] += ms  # (the pass's start or end, the barrier, between draws of nothing)
    sel = [d for d in draws if d[4].startswith(prefix)]
    print(f'== profile {fi + 1}: {f["total"]:.1f} ms first to last (inflated: a timestamp after every draw), {len(draws)} draws')
    tot_draw = sum(d[0] for d in draws)
    print(f'   all draws {tot_draw:.1f} ms, the rest (pass starts / ends, dispatches, copies) {f["total"] - tot_draw:.1f} ms')
    if not sel:
        print('   no draws in', prefix); continue
    ms = [d[0] for d in sel]
    print(f'   {prefix}*: {len(sel)} draws, {sum(ms):.1f} ms; per draw median {statistics.median(ms) * 1000:.1f} us, '
          f'mean {statistics.mean(ms) * 1000:.1f} us; p10 {sorted(ms)[len(ms) // 10] * 1000:.1f} us, '
          f'p90 {sorted(ms)[9 * len(ms) // 10] * 1000:.1f} us')
    # fit ms = a + b * verts (least squares)
    xs = [d[3] for d in sel]
    mx, my = statistics.mean(xs), statistics.mean(ms)
    vx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ms)) / vx if vx else 0
    a = my - b * mx
    print(f'   fit: {a * 1000:.1f} us a draw + {b * 1e6:.2f} ns a vertex (verts: median {statistics.median(xs):.0f}, '
          f'total {sum(xs) / 1e6:.2f} M) -> fixed part {a * len(sel):.1f} ms, per-vertex part {b * sum(xs):.1f} ms')
    small = [d for d in sel if d[3] <= 300]
    if small:
        print(f'   draws of <= 300 vertices: {len(small)}, median {statistics.median(d[0] for d in small) * 1000:.1f} us, '
              f'{sum(d[0] for d in small):.1f} ms in all')
    print('   costliest draws:')
    for d in sorted(sel, key=lambda d: -d[0])[:10]:
        print(f'     {d[0] * 1000:7.1f} us  verts {d[3]:7d}  vs {d[1]} fs {d[2]}')
    pairs = defaultdict(lambda: [0, 0.0, 0])
    for d in sel:
        p = pairs[(d[1], d[2])]; p[0] += 1; p[1] += d[0]; p[2] += d[3]
    print('   shader pairs by time:')
    for (vs, fs), (n, t, v) in sorted(pairs.items(), key=lambda kv: -kv[1][1])[:10]:
        print(f'     {t:6.2f} ms  {n:4d} draws  {t / n * 1000:6.1f} us/draw  {v / n:7.0f} verts/draw  vs {vs} fs {fs}')
    print('   passes (draws, draw ms, start/end ms):')
    for lab, (n, t, o) in sorted(passes.items(), key=lambda kv: -(kv[1][1] + kv[1][2]))[:8]:
        print(f'     {t + o:6.2f} ms  {n:5d} draws {t:6.2f}  start/end {o:5.2f}  {lab}')
