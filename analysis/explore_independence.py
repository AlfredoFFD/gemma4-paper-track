"""EXPLORATORY. Is the fall of "shown every changed region" with the number of regions only what a constant rate
per region predicts?

The objection this answers. A fix with one changed region is shown to the agent in about four runs of five. If
every region of every fix were shown with that probability, independently of the others, a fix with k regions would
be shown whole in that probability to the power k, which is near what the runs give. Then a fix with several places
is not harder to find than a fix with one; it only has more places.

That reading has two premises the runs can check, and this script counts both:
  (1) a region of a fix with several is shown as often as the region of a fix with one;
  (2) within a run, the regions of one fix are shown independently of each other.

Terms (as in analysis/explore_read_starts.py, whose reading of the traces this script uses unchanged):
  CHANGED REGION   a hunk of the reference patch in a file that exists before the fix
  SHOWN            a file read of the run returned a line of the region (the 10-line margin of that script)
For each set of runs and each class of tasks by the number of CHANGED REGIONS of the fix it prints:
  - the share of regions SHOWN, pooled over regions and as the mean over runs of the run's own share, with a
    95% interval over tasks;
  - runs SHOWN at least one region, and runs SHOWN every region;
  - the number of runs that would be SHOWN every region under two models of independence:
      CONSTANT RATE   every region is shown with the probability of the lone region of a one-region fix
      OWN RATES       every region is shown with its own frequency over the runs of its task (the product of
                      those frequencies; unbiased for the expected count if regions are shown independently)
  - THE OTHERS: in runs SHOWN at least one region of a fix with several, the share of the remaining regions that
    is SHOWN, against what CONSTANT RATE predicts for it, and split by whether the region lies in the file of the
    region that was shown first (for a region in another file: whether the run read that file at all).
and, per set: the difference between the lone region of a one-region fix and the regions of a fix with several, by
task; the same classes of fixes split by whether all their regions lie in one file; and, for fixes whose regions
lie in several files, how many of the fix's files the run read.
OWN RATES needs several runs per task: with one run per task (our whole runs) it equals the observed count and is
not printed. Where a set records the outcome of its runs, the resolved runs of each group are printed too.
Counts only; no rule; nothing here is a test of a registered hypothesis.

Usage:
    python analysis/explore_independence.py
Output is stored in analysis/results/explore_independence.txt.
"""
import collections
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import explore_read_starts as R  # noqa: E402
from analyze_forks import boot_ci, diff_ci  # noqa: E402

SETS = ('starter agent, public runs of September (GraphLoc base arm)',
        'the same agent with a graph skill, public runs (GraphLoc skill arm)',
        'our whole runs of pre-registration 14, condition N',
        'our whole runs of pre-registration 14, condition NAF')
CLASSES = (('1', lambda k: k == 1), ('2 or 3', lambda k: 2 <= k <= 3), ('4 to 9', lambda k: 4 <= k <= 9),
           ('10 or more', lambda k: k >= 10), ('2 or more', lambda k: k >= 2))


def pct(k, n):
    return f'{k} of {n} ({100.0 * k / n:.1f}%)' if n else f'{k} of {n}'


def ci(by):
    p, lo, hi = boot_ci(by)
    return 'none' if p is None else f'{100 * p:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]'


def resolved_of(sel):
    """Resolved among the runs whose outcome is known, and among those of them shown every region."""
    known = [r for r in sel if r['resolved'] is not None]
    if not known:
        return ''
    full = [r for r in known if all(x['seen'] for x in r['regs'])]
    return (f'; resolved {pct(sum(bool(r["resolved"]) for r in known), len(known))}, of the runs SHOWN every region '
            f'{pct(sum(bool(r["resolved"]) for r in full), len(full))}')


def others_given_one(p, k):
    """Expected number of further regions shown, given at least one of k is shown, each with probability p."""
    some = 1 - (1 - p) ** k
    return (k * p - some) / some if some > 0 else 0.0


def runs_of(label, srcs, gold, texts):
    out = []
    for r in srcs[label]:
        g = gold.get(r['task'], {})
        if not g:
            continue
        regs = R.analyse(r['load'](), g, texts.get(r['task'], ''), r.get('places'), r.get('arm'))[1]
        if regs:
            out.append({'task': r['task'], 'resolved': r['resolved'],
                        'regs': sorted(regs, key=lambda x: (x['f'], x['a']))})
    return out


def report(label, runs):
    print(f'{label}: runs of tasks with a CHANGED REGION {len(runs)}, tasks {len({r["task"] for r in runs})}')
    lone = [r for r in runs if len(r['regs']) == 1]
    p1 = sum(r['regs'][0]['seen'] for r in lone) / len(lone) if lone else None
    by_task = collections.defaultdict(list)
    for r in runs:
        by_task[r['task']].append(r)
    for name, test in CLASSES:
        sel = [r for r in runs if test(len(r['regs']))]
        if not sel:
            continue
        tasks = sorted({r['task'] for r in sel})
        n_reg = sum(len(r['regs']) for r in sel)
        n_seen = sum(x['seen'] for r in sel for x in r['regs'])
        share = collections.defaultdict(list)
        for r in sel:
            share[r['task']].append(sum(x['seen'] for x in r['regs']) / len(r['regs']))
        some = [r for r in sel if any(x['seen'] for x in r['regs'])]
        every = sum(all(x['seen'] for x in r['regs']) for r in sel)
        const = sum(p1 ** len(r['regs']) for r in sel) if p1 is not None else None
        own = 0.0
        for t in tasks:
            rs = by_task[t]
            k = len(rs[0]['regs'])
            prod = 1.0
            for j in range(k):
                prod *= sum(r['regs'][j]['seen'] for r in rs) / len(rs)
            own += prod * len(rs)
        print(f'   fixes with {name} CHANGED REGIONS: tasks {len(tasks)}, runs {len(sel)}')
        print(f'      regions SHOWN, pooled {pct(n_seen, n_reg)}; mean over runs of the run\'s share {ci(share)}')
        print(f'      runs SHOWN at least one region {pct(len(some), len(sel))}; SHOWN every region {pct(every, len(sel))}')
        if name != '1':
            several = len(sel) > len(tasks)
            print(f'      runs SHOWN every region if regions were independent: CONSTANT RATE '
                  + (f'{const:.1f}' if const is not None else 'none')
                  + (f'; OWN RATES {own:.1f}' if several else '') + f'; observed {every}')
            rest = sum(len(r['regs']) - 1 for r in some)
            got = sum(sum(x['seen'] for x in r['regs']) - 1 for r in some)
            exp = sum(others_given_one(p1, len(r['regs'])) for r in some) if p1 is not None else None
            oth = collections.defaultdict(list)
            same = [0, 0]
            other = [0, 0]
            opened = 0
            same_t, other_t = collections.defaultdict(list), collections.defaultdict(list)
            for r in some:
                oth[r['task']].append((sum(x['seen'] for x in r['regs']) - 1) / (len(r['regs']) - 1))
                first = min((x for x in r['regs'] if x['seen']), key=lambda x: (x['seen_at'], x['f'], x['a']))
                for x in r['regs']:
                    if x is first:
                        continue
                    here = x['f'] == first['f']
                    box = same if here else other
                    box[0] += x['seen']
                    box[1] += 1
                    (same_t if here else other_t)[r['task']].append(int(x['seen']))
                    if not here:
                        opened += x['opened']
            print(f'      THE OTHERS, in the {len(some)} runs SHOWN at least one region: SHOWN {pct(got, rest)}; mean over runs '
                  f'{ci(oth)}; CONSTANT RATE predicts ' + (f'{exp:.1f} of {rest} ({100 * exp / rest:.1f}%)' if exp is not None and rest else 'none'))
            print(f'         in the file of the region shown first {pct(same[0], same[1])}; in another file {pct(other[0], other[1])}'
                  + (f' (the run read that file for {pct(opened, other[1])} of them)' if other[1] else ''))
            dd = diff_ci(same_t, other_t)
            if dd[0] is not None:
                print(f'         same file minus another file, by task: {100 * dd[0]:+.1f} points [{100 * dd[1]:+.1f}, {100 * dd[2]:+.1f}]'
                      f' (tasks with such regions: {len(same_t)} and {len(other_t)})')
    one, more = collections.defaultdict(list), collections.defaultdict(list)
    for r in runs:
        s = sum(x['seen'] for x in r['regs']) / len(r['regs'])
        (one if len(r['regs']) == 1 else more)[r['task']].append(s)
    dd = diff_ci(one, more)
    if dd[0] is not None:
        print(f'   share of regions SHOWN, fixes with one region minus fixes with several, mean over runs, by task: '
              f'{100 * dd[0]:+.1f} points [{100 * dd[1]:+.1f}, {100 * dd[2]:+.1f}]')
    for name, test in CLASSES[1:4]:
        sub = {t: v for t, v in more.items() if test(len(by_task[t][0]['regs']))}
        dd = diff_ci(one, sub)
        if dd[0] is not None:
            print(f'      against fixes with {name}: {100 * dd[0]:+.1f} points [{100 * dd[1]:+.1f}, {100 * dd[2]:+.1f}]')
    print('   fixes with several CHANGED REGIONS, by whether all of them lie in one file')
    for name, test in CLASSES[1:]:
        for where, pick in (('one file', lambda r: len({x['f'] for x in r['regs']}) == 1),
                            ('several files', lambda r: len({x['f'] for x in r['regs']}) > 1)):
            sel = [r for r in runs if test(len(r['regs'])) and pick(r)]
            if not sel:
                continue
            n_reg = sum(len(r['regs']) for r in sel)
            n_seen = sum(x['seen'] for r in sel for x in r['regs'])
            every = sum(all(x['seen'] for x in r['regs']) for r in sel)
            const = sum(p1 ** len(r['regs']) for r in sel) if p1 is not None else None
            print(f'      {name} regions, {where}: tasks {len({r["task"] for r in sel})}, runs {len(sel)}; regions SHOWN '
                  f'{pct(n_seen, n_reg)}; runs SHOWN every region {pct(every, len(sel))}'
                  + (f' (CONSTANT RATE {const:.1f})' if const is not None else '') + resolved_of(sel))
    multi = [r for r in runs if len({x['f'] for x in r['regs']}) > 1]
    if multi:
        n_files = sum(len({x['f'] for x in r['regs']}) for r in multi)
        read = sum(len({x['f'] for x in r['regs'] if x['opened']}) for r in multi)
        hit = sum(len({x['f'] for x in r['regs'] if x['seen']}) for r in multi)
        allread = sum(all(x['opened'] for x in r['regs']) for r in multi)
        print(f'   fixes whose regions lie in several files: tasks {len({r["task"] for r in multi})}, runs {len(multi)}; files of '
              f'the fix {n_files}; the run read the file {pct(read, n_files)}; was SHOWN a region of it {pct(hit, n_files)}; '
              f'runs that read every file of the fix {pct(allread, len(multi))}')
        by_n = collections.defaultdict(list)
        for r in multi:
            by_n[min(len({x['f'] for x in r['regs']}), 4)].append(r)
        for n in sorted(by_n):
            rs = by_n[n]
            k = sum(len({x['f'] for x in r['regs'] if x['opened']}) for r in rs)
            tot = sum(len({x['f'] for x in r['regs']}) for r in rs)
            print(f'      {n}{" or more" if n == 4 else ""} files: runs {len(rs)}; files read {pct(k, tot)}; runs that read every file '
                  f'{pct(sum(all(x["opened"] for x in r["regs"]) for r in rs), len(rs))}; SHOWN every region '
                  f'{pct(sum(all(x["seen"] for x in r["regs"]) for r in rs), len(rs))}' + resolved_of(rs))
    single = [r for r in runs if len({x['f'] for x in r['regs']}) == 1]
    if single:
        print(f'   fixes whose regions lie in one file: tasks {len({r["task"] for r in single})}, runs {len(single)}; the run read '
              f'the file {pct(sum(r["regs"][0]["opened"] for r in single), len(single))}; SHOWN every region '
              f'{pct(sum(all(x["seen"] for x in r["regs"]) for r in single), len(single))}' + resolved_of(single))
        print('      of them, fixes with one CHANGED REGION: runs ' + str(len(lone)) + resolved_of(lone))
    print()


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    gold = R.gold_regions()
    texts = R.task_texts()
    srcs = R.all_sources()
    print('IS A FIX WITH SEVERAL PLACES ONLY A FIX WITH MORE PLACES? THE SHARE OF REGIONS SHOWN, AND WHETHER THE REGIONS OF')
    print('ONE FIX ARE SHOWN INDEPENDENTLY (EXPLORATORY)')
    print()
    for label in SETS:
        if label in srcs:
            report(label, runs_of(label, srcs, gold, texts))


if __name__ == '__main__':
    main()
