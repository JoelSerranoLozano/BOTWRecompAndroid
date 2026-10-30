#!/usr/bin/env python3
# pace_ab.py LOG [SKIP]: LARECOMP_AB runs with LARECOMP_LOG_PACE - the open world's [pace] frames (from the first
# stats line with >= 2000 draws a frame to the last one) by A/B phase: median frame period, fps from it, median GPU
# busy ms, render-thread and game busy ms. SKIP: frames dropped after each phase change (default 10).
import re, sys, statistics

path = sys.argv[1]
skip = int(sys.argv[2]) if len(sys.argv) > 2 else 10
STAMP = re.compile(r'(\d\d):(\d\d):(\d\d)\.(\d+) ')
VK = re.compile(r'\[vk\] t=[\d.]+ frame (\d+) .*?\((\d+) draws')
PACE = re.compile(r'\[pace\] period ([\d.]+) blocked ([\d.]+) busy ([\d.]+) ms .* game ([\d.]+) render ([\d.]+) gpu ([-\d.]+) ab (-?\d+)')

def secs(line):
    m = STAMP.search(line)
    return int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) + float('0.' + m[4]) if m else None

lines = open(path, errors='replace').read().splitlines()
world, prev = [], None
for l in lines:
    m = VK.search(l)
    if not m:
        continue
    f = int(m[1])
    if prev is not None and f > prev and int(m[2]) / (f - prev) >= 2000:
        world.append(secs(l))
    prev = f
if not world:
    sys.exit('no open-world stats lines')
lo, hi = world[0] - 2, world[-1]
frames, last_ab, since = {}, None, 0
for l in lines:
    m = PACE.search(l)
    if not m:
        continue
    t = secs(l)
    if t is None or t < lo or t > hi:
        continue
    ab = int(m[7])
    if ab != last_ab:
        last_ab, since = ab, 0
    since += 1
    if since <= skip:
        continue
    frames.setdefault(ab, []).append(tuple(float(x) for x in m.groups()[:6]))
print(f'open world {hi - lo:.0f} s, {skip} frames skipped after each switch')
names = sys.argv[3].split('+') if len(sys.argv) > 3 else []
def label(ab):
    if not names: return str(ab)
    on = [n for k, n in enumerate(names) if ab >= 0 and (ab >> k) & 1]
    return '+'.join(on) if on else 'base'
print(f'{"ab":>3} {"frames":>6} {"period ms":>9} {"fps":>5} {"gpu ms":>7} {"render ms":>9} {"game ms":>8}')
for ab in sorted(frames):
    v = frames[ab]
    med = lambda i: statistics.median(x[i] for x in v)
    print(f'{ab:>3} {len(v):>6} {med(0):9.2f} {1000 / med(0):5.1f} {med(5):7.2f} {med(4):9.2f} {med(3):8.2f}  {label(ab)}')
