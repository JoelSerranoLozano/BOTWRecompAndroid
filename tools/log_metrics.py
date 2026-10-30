#!/usr/bin/env python3
"""Open-world numbers from a runtime log (botwrecomp-log.txt, or logcat with the BOTWRecompAndroid tag), to compare
one change against another on the same save.

Reads the `[vk] t=...` lines (one every ~2 s, counts summed over the frames since the previous one), the
`[kernel] core 0, last 30 s: ... held N%` lines and the memory lines ([android] ... rss, low memory kills, gpu mem).

Open world: the stats lines from --from seconds on (the `t=` clock) whose frames carry at least --min-draws draws each
(menus and loading screens draw far less). Prints medians:
  fps, ms per frame, draws per frame, ms per 1000 draws, MB uploaded per frame, core 0 held %, gpu mem, last rss.

  log_metrics.py LOG [LOG ...] [--from 120] [--to 400] [--min-draws 2000] [--csv]
"""
import argparse
import re
import statistics as st
import sys
from pathlib import Path

VK = re.compile(r'\[vk\] t=([\d.]+) frame (\d+) ([\d.]+) fps max (\d+)ms .*?\((\d+) draws, (\d+) skipped, (\d+) passes, '
                r'(\d+) dispatches.*?upload ([\d.]+)MB.*?gpu mem (\d+)MB')
CORE0 = re.compile(r'(\d\d):(\d\d):(\d\d)\.\d+ .*?\[kernel\] core 0, last \d+ s: (\d+) takes, waited (\d+) ms.*held (\d+)%')
STAMP = re.compile(r'(\d\d):(\d\d):(\d\d)\.\d+ ')
RSS = re.compile(r'rss (\d+) MB')
LMK = re.compile(r'low memory|lowmemorykiller|reason 3', re.I)


def secs(m):
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))


def med(xs):
    return st.median(xs) if xs else float('nan')


def analyse(path, a):
    rows, core0, rss, lmk = [], [], [], []
    prev_frame = None
    t0_wall = None  # wall clock of t=0, to place the core 0 lines on the t= axis
    for line in path.read_text(errors='replace').splitlines():
        m = VK.search(line)
        if m:
            t, frame, fps = float(m.group(1)), int(m.group(2)), float(m.group(3))
            draws, upload, gmem = int(m.group(5)), float(m.group(9)), int(m.group(10))
            s = STAMP.search(line)
            if s and t0_wall is None:
                t0_wall = secs(s) - t
            frames = frame - prev_frame if prev_frame is not None else 0
            prev_frame = frame
            if frames <= 0 or fps <= 0:
                continue
            dpf = draws / frames
            rows.append(dict(t=t, fps=fps, ms=1000 / fps, dpf=dpf, ms_kdraw=1000 / fps / dpf * 1000,
                             mb=upload / frames, gmem=gmem))
            continue
        m = CORE0.search(line)
        if m:
            core0.append((secs(m), int(m.group(6)), int(m.group(4)), int(m.group(5))))
            continue
        m = RSS.search(line)
        if m:
            rss.append(line.strip())
        if LMK.search(line):
            lmk.append(line.strip())

    ow = [r for r in rows if r['t'] >= a.from_ and (a.to is None or r['t'] <= a.to) and r['dpf'] >= a.min_draws]
    held = []
    if ow and t0_wall is not None:
        lo, hi = ow[0]['t'] + t0_wall, ow[-1]['t'] + t0_wall + 30  # (a core 0 line covers the 30 s before it)
        held = [h for w, h, _, _ in core0 if lo <= w <= hi]
    return dict(name=path.name, n=len(ow), span=(ow[0]['t'], ow[-1]['t']) if ow else None,
                fps=med([r['fps'] for r in ow]), ms=med([r['ms'] for r in ow]), dpf=med([r['dpf'] for r in ow]),
                ms_kdraw=med([r['ms_kdraw'] for r in ow]), mb=med([r['mb'] for r in ow]),
                held=med(held), nheld=len(held), gmem=max((r['gmem'] for r in ow), default=0),
                rss=rss[-3:], lmk=lmk[-3:])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('logs', nargs='+', type=Path)
    p.add_argument('--from', dest='from_', type=float, default=0, help='open world from this t= second on')
    p.add_argument('--to', type=float, help='... up to this one')
    p.add_argument('--min-draws', type=float, default=2000, help='draws per frame that count as open world')
    p.add_argument('--csv', action='store_true')
    a = p.parse_args()
    res = [analyse(x, a) for x in a.logs]
    cols = ['name', 'n', 'fps', 'ms', 'dpf', 'ms_kdraw', 'mb', 'held', 'gmem']
    if a.csv:
        print(','.join(cols))
        for r in res:
            print(','.join(str(r[c]) for c in cols))
        return
    print(f"{'log':34} {'lines':>5} {'fps':>5} {'ms/fr':>6} {'draws/fr':>8} {'ms/1k dr':>8} {'MB/fr':>6} {'held%':>6} "
          f"{'gpuMB':>6}")
    for r in res:
        print(f"{r['name'][:34]:34} {r['n']:5} {r['fps']:5.1f} {r['ms']:6.1f} {r['dpf']:8.0f} {r['ms_kdraw']:8.1f} "
              f"{r['mb']:6.1f} {r['held']:6.0f} {r['gmem']:6}")
        if r['span']:
            print(f"    open world t={r['span'][0]:.0f}-{r['span'][1]:.0f} s, {r['nheld']} core 0 lines")
        for l in r['rss'] + r['lmk']:
            print('    ' + l[:160])


if __name__ == '__main__':
    sys.exit(main())
