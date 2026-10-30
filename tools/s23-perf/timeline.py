#!/usr/bin/env python3
# timeline.py LOG [MS_PER_CHAR]: LARECOMP_FRAME_TIMELINE's dump - three lanes (game waiting in SyncWait, render thread
# translating / presenting, GPU running a submission), the share of time each is busy, the GPU's idle gaps and what
# the other two did meanwhile, and the game's waits.
import re, sys

path = sys.argv[1]
res = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
EV = re.compile(r'\[timeline\]\s+([\d.]+) (.*?) (\d+) (\d+)\s*$')
ev = []
for line in open(path, errors='replace'):
    if '[timeline]' in line and 'events' not in line:
        m = EV.search(line)
        if m:
            ev.append((float(m[1]), m[2], int(m[3]), int(m[4])))
if not ev:
    sys.exit('no timeline')

def intervals(start, end, key=lambda e: e[2]):
    out, open_ = [], {}
    for t, what, a, b in ev:
        if what == start:
            open_[key((t, what, a, b))] = t
        elif what == end and key((t, what, a, b)) in open_:
            out.append((open_.pop(key((t, what, a, b))), t))
    return out

gpu = intervals('gpu: start of submission', 'gpu: end of submission')
# (the completion watcher's events: a submission runs from when it was submitted or the previous one was done,
# whichever is later, until it was seen done - the GPU's busy time, to the watcher's wake-up)
sub_t = {a: t for t, what, a, b in ev if what.startswith('render: submitted')}
done_t = {a: t for t, what, a, b in ev if what == 'gpu: done (watcher)'}
present_seqs = {a for t, what, a, b in ev if what == 'render: submitted (present)'}
if done_t:
    gpu = []
    for s in sorted(done_t):
        if s in sub_t:
            st = max(sub_t[s], done_t.get(s - 1, sub_t[s]))
            if done_t[s] > st:
                gpu.append((st, done_t[s]))
    print('GPU lane from the completion watcher: submissions\' start = max(submitted, previous done)')
    print('per submission (ms from the first event): submitted, done, ran (after the previous one), waited for work')
    for s in sorted(done_t):
        if s in sub_t:
            prev = done_t.get(s - 1)
            ran = done_t[s] - max(sub_t[s], prev if prev else sub_t[s])
            idle = sub_t[s] - prev if prev and sub_t[s] > prev else 0
            print(f'  {s}{" P" if s in present_seqs else "  "} submitted {sub_t[s]:8.2f} done {done_t[s]:8.2f}  ran {ran:6.2f}  gpu idle before {idle:6.2f}')
rend = intervals('render: list start', 'render: list end') + intervals('render: present start', 'render: present end')
wait = []
o = None
for t, what, a, b in ev:
    if what.startswith('game: SyncWait begin'):
        o = t
    elif what == 'game: SyncWait end' and o is not None:
        wait.append((o, t)); o = None
presents = [t for t, what, a, b in ev if what == 'game: present sent']
t0 = presents[0] if presents else ev[0][0]
t1 = presents[-1] if len(presents) > 1 else ev[-1][0]
span = t1 - t0

def busy(iv, lo, hi):
    pts = sorted((max(a, lo), min(b, hi)) for a, b in iv if b > lo and a < hi)
    tot, cur = 0.0, None
    for a, b in pts:
        if cur is None or a > cur[1]:
            if cur: tot += cur[1] - cur[0]
            cur = [a, b]
        else:
            cur[1] = max(cur[1], b)
    if cur: tot += cur[1] - cur[0]
    return tot

nfr = max(len(presents) - 1, 1)
print(f'{len(ev)} events; {nfr} frames between the game\'s presents: {span:.1f} ms, {span / nfr:.1f} ms a frame')
for name, iv in (('GPU busy', gpu), ('render thread busy', rend), ('game in SyncWait', wait)):
    b = busy(iv, t0, t1)
    print(f'  {name:20} {b:7.1f} ms  {100 * b / span:5.1f}%  ({b / nfr:.1f} ms a frame)')

# lanes
n = int(span / res) + 1
lanes = {'game wait': wait, 'render   ': rend, 'gpu      ': gpu}
print(f'\nlanes, {res:g} ms a character (| = the game sends a present):')
for name, iv in lanes.items():
    row = []
    for i in range(n):
        lo, hi = t0 + i * res, t0 + (i + 1) * res
        f = busy(iv, lo, hi) / res
        row.append('#' if f > 0.66 else '+' if f > 0.33 else '.' if f > 0 else ' ')
    for p in presents:
        i = int((p - t0) / res)
        if 0 <= i < n and row[i] == ' ':
            row[i] = '|'
    s = ''.join(row)
    for k in range(0, len(s), 120):
        print(f'{name if k == 0 else " " * 9} {s[k:k + 120]}')

# GPU idle gaps
gp = sorted(gpu)
merged = []
for a, b in gp:
    if merged and a <= merged[-1][1]:
        merged[-1][1] = max(merged[-1][1], b)
    else:
        merged.append([a, b])
print('\nGPU idle gaps over 0.5 ms (what the render thread and the game did meanwhile):')
gaps = 0.0
for (a0, b0), (a1, b1) in zip(merged, merged[1:]):
    g = a1 - b0
    if g < 0.5 or b0 < t0 or a1 > t1:
        continue
    gaps += g
    r = busy(rend, b0, a1)
    w = busy(wait, b0, a1)
    print(f'  at {b0 - t0:7.1f} ms: {g:6.2f} ms idle - render busy {r:5.2f} ms, game waiting {w:5.2f} ms')
print(f'  total {gaps:.1f} ms ({gaps / nfr:.1f} ms a frame)')
print('\nthe game\'s waits:')
for a, b in wait:
    if a >= t0 - 1 and b <= t1 + 1:
        print(f'  at {a - t0:7.1f} ms: {b - a:6.2f} ms')
