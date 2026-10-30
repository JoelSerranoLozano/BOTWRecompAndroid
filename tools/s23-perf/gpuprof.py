#!/usr/bin/env python3
# gpuprof.py LOG [N]: the [gpuprof] frames of a logcat / app log - per frame the total, by kind (pass by target size,
# dispatch, copy, feedback snapshot, submission start = GPU idle before it, present), and the N costliest rows of the
# median frame
import re, sys, statistics
from collections import defaultdict

path = sys.argv[1]
top = int(sys.argv[2]) if len(sys.argv) > 2 else 25
frames, cur = [], None
row = re.compile(r'\[gpuprof\]\s+([\d.]+) ms\s+([\d.]+)%\s+(.*)$')
for line in open(path, errors='replace'):
    if '[gpuprof]' not in line:
        continue
    if 'marks,' in line:
        cur = {'total': float(re.search(r'([\d.]+) ms first to last', line).group(1)), 'rows': []}
        frames.append(cur)
        continue
    m = row.search(line)
    if m and cur is not None:
        cur['rows'].append((float(m.group(1)), m.group(3).strip()))

def kind(label):
    if label.startswith('pass:'):
        m = re.match(r'pass: (\d+) color (\d+)x(\d+) fmt (\S+), depth (\S+)', label)
        if m:
            n, w, h, f, d = m.groups()
            return f'pass {w}x{h} ({n} color, depth {d.rstrip(",")})'
        return 'pass ?'
    if label.startswith('dispatch'):
        return 'dispatch'
    if label.startswith('(submission start'):
        return 'submission start (incl. GPU idle)'
    for k in ('copy texture (deferred', 'copy texture', 'feedback snapshot', 'present', 'scene upscale'):
        if label.startswith(k):
            return k
    return label[:40]

print(f'{len(frames)} frames: totals ' + ', '.join(f"{f['total']:.1f}" for f in frames) + ' ms')
agg = defaultdict(list)
for f in frames:
    by = defaultdict(float)
    cnt = defaultdict(int)
    for ms, lab in f['rows']:
        by[kind(lab)] += ms
        cnt[kind(lab)] += 1
    for k in set(by) | set(agg):
        agg[k].append((by.get(k, 0.0), cnt.get(k, 0)))
print(f'\n{"kind":58} {"median ms":>9} {"share":>6} {"rows":>5}')
tot = statistics.median(f['total'] for f in frames)
for k, v in sorted(agg.items(), key=lambda kv: -statistics.median(x[0] for x in kv[1])):
    med = statistics.median(x[0] for x in v)
    if med < 0.05:
        continue
    print(f'{k:58} {med:9.2f} {100 * med / tot:5.1f}% {statistics.median(x[1] for x in v):5.0f}')
mid = sorted(frames, key=lambda f: f['total'])[len(frames) // 2]
print(f'\nthe {top} costliest rows of the median frame ({mid["total"]:.1f} ms):')
for i, (ms, lab) in enumerate(sorted(mid['rows'], key=lambda r: -r[0])[:top]):
    print(f'{ms:7.3f} ms  {lab[:150]}')
