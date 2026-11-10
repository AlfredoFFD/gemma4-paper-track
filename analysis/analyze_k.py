"""Analysis of experiment E (navigation horizon), as drafted in prereg/06-navigation-horizon.md (DRAFT, NOT FROZEN).

Inputs: <run_dir>/results_k.jsonl (one line per replay, from analysis/modal_k/forks_k_runner.py),
analysis/fork_states_k/population.json and analysis/fork_states_d/states.jsonl.
Usage: py -I -X utf8 analysis/analyze_k.py <run_dir> [--rows <out.jsonl>]

Scoring (re-derived here from the raw calls; the runner stores no outcome):
- usable replay: no error, and the first model response has a call that the frozen failure rule accepts
  (gates_c.failure applied to the first call: no_call, unknown_tool, malformed_args are interface failures);
- target files: the gold patch's modified files that were not opened at the pause (`unopened_gold_files`);
- Yfile: an executed read_file with status ok on a target file; an executed run_command whose output is not empty and
  which the frozen scorer (fork_states.touches, i.e. shell_view_range with the 5,000-character cap) treats as a view of
  a target file; or the stopping call, if it is an edit_file or write_file on a target file;
- Yline: an executed read_file with status ok on a target file whose returned start_line..end_line overlaps a changed
  region; or an executed single-file run_command view (one file argument) whose frozen-scorer range overlaps a changed
  region. Recursive and multi-file commands count for Yfile only. The frozen scorer's grep rule needs a node name;
  file targets have none, so a sentinel that never matches is passed and a grep stage never counts as a view;
- complete state: every arm and every seed of the state's population usable.
Every interval is a 95% bootstrap clustered by state (2,000 resamples, seed 0: analyze_forks.boot_ci / diff_ci).
"""
import argparse
import collections
import json
import shlex
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze_forks import GRAPH_TOOLS, boot_ci, diff_ci  # noqa: E402
from fork_states import VIEW_CMDS, norm_path, touches  # noqa: E402
from gates_c import _ll, failure, load_states, skey, touch_map  # noqa: E402

ARMS = ('A', 'H', 'E', 'RE')
CONTRASTS = (('E', 'H'), ('E', 'A'), ('H', 'A'), ('RE', 'A'))
RULES = {('R', 'Yline', 'E', 'H'): 'K1', ('U', 'Yfile', 'E', 'A'): 'K2'}
SENTINEL = '\x00'  # node id whose short name never occurs in a command


def _overlap(a, b, regions):
    return any(not (b < s or a > e) for s, e in regions)


def _stdout(res):
    res = res or {}
    return res.get('stdout') or (res.get('details') or {}).get('stdout') or ''


def _single_file(cmd, path):
    """True if the stage that names `path` names no other file argument."""
    for st in (s.strip() for s in cmd.split('|')):
        try:
            toks = shlex.split(st)
        except ValueError:
            toks = st.split()
        if not toks or toks[0] not in VIEW_CMDS or not any(norm_path(t) == path for t in toks[1:]):
            continue
        args = [t for t in toks[1:] if not t.startswith('-')]
        if toks[0] in ('grep', 'rg', 'sed', 'awk') and not any(t in ('-e', '-f') for t in toks[1:]):
            args = args[1:]  # the pattern or script
        return len(args) == 1
    return False


def score(state, gold, r):
    """Outcomes of one replay, plus per-call details for the rows file."""
    task = state['task']
    targets = {f: gold['gold_files'][f] for f in gold['unopened_gold_files']}
    unshown = set(state.get('unshown_true_neighbors', state['true_neighbors']))
    true_names = [n for n in state['true_neighbors'] if n in unshown]
    out = {'Yfile': 0, 'Yline': 0, 'first_Yfile': None, 'first_Yline': None, 'calls': []}
    stop_counted = False
    for si, step in enumerate(r.get('steps') or [], 1):
        for c in step['calls']:
            call = {'function_name': c['function_name'], 'arguments': c['arguments']}
            res = c.get('result') or {}
            yf = yl = False
            name = c['function_name']
            if c['executed'] and name == 'read_file' and res.get('status') == 'ok':
                f = norm_path(c['arguments'].get('filepath'))
                if f in targets:
                    yf = True
                    a, b = res.get('start_line'), res.get('end_line')
                    if isinstance(a, int) and isinstance(b, int) and b >= a:
                        yl = _overlap(a, b, targets[f])
            elif c['executed'] and name == 'run_command' and _stdout(res):
                cmd = str(c['arguments'].get('command', ''))
                for f, regions in targets.items():
                    ll = _ll(task, f)
                    if touches(call, {'path': f, 'start': 1, 'end': None}, SENTINEL, line_lengths=ll) == 'read':
                        yf = True
                        if _single_file(cmd, f) and any(
                                touches(call, {'path': f, 'start': s, 'end': e}, SENTINEL, line_lengths=ll) == 'read'
                                for s, e in regions):
                            yl = True
            elif not c['executed'] and not stop_counted:
                stop_counted = True  # only the stopping call itself, never the calls after it in the same response
                if name in ('edit_file', 'write_file') and any(
                        touches(call, {'path': f, 'start': 1, 'end': None}, SENTINEL) == 'edit' for f in targets):
                    yf = True
            tt = touch_map(state, call, true_names, state['neighbor_spans'])
            tr = touch_map(state, call, state.get('rewired_entries', []), state.get('rewired_spans', {}))
            out['calls'].append({'step': si, 'function_name': name, 'executed': c['executed'], 'Yfile': yf, 'Yline': yl,
                                 'touch_true': any(bool(v) and v != 'graph' for v in tt.values()),
                                 'touch_rewired': any(bool(v) and v != 'graph' for v in tr.values()),
                                 'prompt_tokens': step.get('prompt_tokens')})
            if yf and out['first_Yfile'] is None:
                out['first_Yfile'] = si
            if yl and out['first_Yline'] is None:
                out['first_Yline'] = si
            out['Yfile'] |= int(yf)
            out['Yline'] |= int(yl)
    out['executed_calls'] = sum(1 for c in out['calls'] if c['executed'])
    out['stop'] = r.get('stop')
    return out


def stop_group(stop):
    if not stop or not stop.startswith('stop_call:'):
        return stop or 'none'
    name = stop.split(':', 1)[1]
    if name in GRAPH_TOOLS:
        return 'stop:graph_tool'
    if name in ('edit_file', 'write_file', 'submit_patch', 'get_status', 'run_command'):
        return f'stop:{name}'
    return 'stop:other'


def first_call_failure(r):
    steps = r.get('steps') or []
    first = steps[0]['calls'][0] if steps and steps[0]['calls'] else None
    return failure({'error': r.get('error'),
                    'next_call': {'function_name': first['function_name'], 'arguments': first['arguments']} if first else None})


def pct(trip):
    p, lo, hi = trip
    return 'n/a' if p is None else f'{100 * p:.2f} [{100 * lo:.2f}, {100 * hi:.2f}]'


def dpt(trip):
    p, lo, hi = trip
    return 'n/a' if p is None else f'{100 * p:+.2f} [{100 * lo:+.2f}, {100 * hi:+.2f}]'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run_dir')
    ap.add_argument('--population', default=str(HERE / 'fork_states_k' / 'population.json'))
    ap.add_argument('--states', default=str(HERE / 'fork_states_d' / 'states.jsonl'))
    ap.add_argument('--rows', default=None, help='optional: write per-replay outcomes here (nothing more is printed)')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    states = load_states(args.states)
    pop = json.load(open(args.population, encoding='utf-8'))
    member = {tuple(g['key']): (p, g) for p in ('R', 'U') for g in pop[p]}
    rows = [json.loads(l) for l in open(Path(args.run_dir) / 'results_k.jsonl', encoding='utf-8') if l.strip()]
    usable = collections.defaultdict(dict)
    for r in rows:
        k = skey(r)
        if k in member and r['arm'] in ARMS and r['seed'] in member[k][1]['seeds'] and not first_call_failure(r):
            usable[k][(r['arm'], r['seed'])] = r
    complete = {p: sorted(k for k, (pp, g) in member.items() if pp == p
                          and {(a, s) for a in ARMS for s in g['seeds']} <= set(usable.get(k, {})))
                for p in ('R', 'U')}
    scored = {}
    for p in ('R', 'U'):
        for k in complete[p]:
            for key, r in usable[k].items():
                scored[(k, key)] = score(states[k], member[k][1], r)
    if args.rows:
        with open(args.rows, 'w', encoding='utf-8') as f:
            for (k, (arm, seed)), s in sorted(scored.items()):
                f.write(json.dumps({'task': k[0], 'run': k[1], 'fork': k[2], 'arm': arm, 'seed': seed,
                                    'population': member[k][0], **s}) + '\n')

    print(f'complete states: R {len(complete["R"])} of {len(pop["R"])}, U {len(complete["U"])} of {len(pop["U"])}')
    for p in ('R', 'U'):
        if not complete[p]:
            continue
        seeds = pop['seeds'][p]
        tab = {y: {a: {k: [scored[(k, (a, s))][y] for s in seeds] for k in complete[p]} for a in ARMS}
               for y in ('Yline', 'Yfile')}
        print(f'\npopulation {p} ({len(complete[p])} states x {len(seeds)} seeds per arm):')
        for y in ('Yline', 'Yfile'):
            for a in ARMS:
                vals = [v for vs in tab[y][a].values() for v in vs]
                print(f'  {y} {a:2s}: {pct(boot_ci(tab[y][a]))} | {sum(vals)}/{len(vals)}')
            for a, b in CONTRASTS:
                tag = RULES.get((p, y, a, b))
                print(f'  {y} {a} - {b}: {dpt(diff_ci(tab[y][a], tab[y][b]))}' + (f'  ({tag})' if tag else ''))
    print('\nstop reasons and executed calls per arm (complete states of R and U):')
    for a in ARMS:
        ss = [s for (k, (arm, _seed)), s in scored.items() if arm == a]
        if not ss:
            continue
        c = collections.Counter(stop_group(s['stop']) for s in ss)
        shares = ', '.join(f'{g} {100 * n / len(ss):.1f}%' for g, n in sorted(c.items(), key=lambda x: (-x[1], x[0])))
        print(f'  {a:2s}: n {len(ss)}; {shares}; mean executed calls {statistics.mean(s["executed_calls"] for s in ss):.2f}')


if __name__ == '__main__':
    main()
