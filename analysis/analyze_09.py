"""Analysis of pre-registration 09: fresh episodes, the graph tools' answers as shipped or with addresses.

Usage: py -I -X utf8 analysis/analyze_09.py <run_dir>      (results_09.jsonl from analysis/modal_g/forks_09_runner.py)

Arms, same tasks and seeds (1 to 3), up to 8 model calls from the task prompt, newest harness wheels:
  N    everything as shipped
  NA   the graph tools' answers carry file and line range for every entity that resolves
  NAF  NA, and a mangled line-bound name of read_file is restored before the call runs

N1 (pre-registration 08)  arm N: share of executed ranged read_file calls with a mangled bound name; "the defect occurs
    in fresh episodes" if the lower 95% bound, clustered by task, is above 2.1%.
A1  NA minus N on Ynext, all episodes of complete tasks, clustered by task. Ynext: the episode has a first graph answer
    that returns at least one entity with a line range in a file the episode has not read, and the first call of the
    next model response reads that entity (the frozen scorer fork_states.touches: a read_file whose range overlaps the
    entity's lines within the harness's caps, an edit of its file, or a shell view of those lines or its name). An
    episode without such an answer scores 0. "Addresses in the graph tools' own answers bring the next call to a
    returned entity's code" if the lower 95% bound is above 0.
A2  NAF minus N on Yline (the agent is shown a line the gold patch changes within the eight calls; analyze_k.score with
    every file the gold patch modifies as a target), tasks whose gold patch modifies a file, clustered by task. "The
    patched harness brings the agent to the fix's lines within eight calls of a fresh start" if the lower 95% bound is
    above 0; otherwise no detectable gain.
Everything else printed here is descriptive.
"""
import collections
import json
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nodes as N  # noqa: E402
from analyze_forks import boot_ci, diff_ci  # noqa: E402
from analyze_g import error_kind, is_mangled, part_fresh, ranged_reads  # noqa: E402
from analyze_k import score, stop_group  # noqa: E402
from fork_states import norm_path, touches  # noqa: E402
from gates_c import _ll  # noqa: E402
from mangled_sensitivity import intended  # noqa: E402

ARMS = ('N', 'NA', 'NAF')
SEEDS = (1, 2, 3)
K = 8
GRAPH_TOOLS = ('get_code_neighbors', 'search_similar_code', 'get_code_subgraph')
HONORED = ('NAF',)


def pct(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:.2f} [{100 * t[1]:.2f}, {100 * t[2]:.2f}]'


def dpt(t):
    return 'n/a' if t[0] is None else f'{100 * t[0]:+.2f} [{100 * t[1]:+.2f}, {100 * t[2]:+.2f}]'


def raw(tab):
    vals = [v for vs in tab.values() for v in vs]
    return f'{sum(vals)}/{len(vals)}'


def plain(name):
    name = str(name)
    return name.split(';', 1)[1] if ';' in name else name


def returned_entities(tool, result):
    """Names a graph tool's answer returns (the plain names, whether or not the answer carries addresses)."""
    if not isinstance(result, dict) or result.get('status') != 'ok':
        return []
    items = result.get({'get_code_neighbors': 'neighbors', 'get_code_subgraph': 'nodes',
                        'search_similar_code': 'results'}[tool]) or []
    out = []
    for it in items:
        if isinstance(it, dict):
            name = it.get('name') or it.get('node_name')
        else:
            name = it
        if name:
            out.append(plain(name))
    return out


def printed_addresses(tool, result):
    """(name, file, lines) for the entities of an answer that carry an address."""
    if not isinstance(result, dict):
        return []
    items = result.get({'get_code_neighbors': 'neighbors', 'get_code_subgraph': 'nodes',
                        'search_similar_code': 'results'}[tool]) or []
    return [(plain(it.get('name') or it.get('node_name')), it.get('file'), it.get('lines'))
            for it in items if isinstance(it, dict) and it.get('file')]


def call_as_executed(arm, c):
    call = {'function_name': c['function_name'], 'arguments': c['arguments'] if isinstance(c['arguments'], dict) else {}}
    if arm in HONORED and is_mangled(call['arguments']):
        return intended(call)
    return call


def episode(task, arm, r):
    """Outcome Ynext and its parts for one episode."""
    steps = r.get('steps') or []
    read_files = set()
    out = {'graph_calls': collections.Counter(), 'first_graph_step': None, 'qualifying': False, 'Ynext': 0,
           'entities': 0, 'next_tool': None, 'next_locates': 0, 'later_touch': 0}
    for i, step in enumerate(steps):
        for c in step['calls']:
            name = c['function_name']
            if name in GRAPH_TOOLS and c['executed']:
                out['graph_calls'][name] += 1
                if out['first_graph_step'] is None:
                    out['first_graph_step'] = i + 1
                if not out['qualifying']:
                    spans = {}
                    for n in returned_entities(name, c.get('result')):
                        sp = N.span(task, n)
                        if sp and sp['end'] is not None and sp['path'] not in read_files:
                            spans[n] = sp
                    if spans:
                        out['qualifying'] = True
                        out['entities'] = len(spans)
                        later = steps[i + 1:]
                        if later and later[0]['calls']:
                            nxt = later[0]['calls'][0]
                            call = call_as_executed(arm, nxt)
                            out['next_tool'] = nxt['function_name']
                            hit = any((t := touches(call, sp, n, line_lengths=_ll(task, sp['path']))) and t != 'graph'
                                      for n, sp in spans.items())
                            out['Ynext'] = int(hit)
                            if nxt['function_name'] == 'run_command' and not hit:
                                cmd = str(call['arguments'].get('command', ''))
                                out['next_locates'] = int(any(n.split('.')[-1] in cmd or sp['path'] in cmd
                                                              for n, sp in spans.items()))
                        for st_ in later:
                            for c2 in st_['calls']:
                                call = call_as_executed(arm, c2)
                                if any((t := touches(call, sp, n, line_lengths=_ll(task, sp['path']))) and t != 'graph'
                                       for n, sp in spans.items()):
                                    out['later_touch'] = 1
            if name == 'read_file' and c['executed'] and (c.get('result') or {}).get('status') == 'ok':
                read_files.add(norm_path(c['arguments'].get('filepath')))
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    run_dir = Path(sys.argv[1])
    fresh = {s['task']: s for s in (json.loads(l) for l in open(HERE / 'fork_states_g' / 'fresh_states.jsonl', encoding='utf-8'))}
    rows = [json.loads(l) for l in open(run_dir / 'results_09.jsonl', encoding='utf-8') if l.strip()]
    vp = run_dir / 'versions_09.json'
    if vp.exists():
        v = json.load(open(vp, encoding='utf-8'))
        print(f'run: harness variant {v.get("harness_variant")}; arms {v.get("arms", {}).get("FRESH")}; seeds {v.get("seeds", {}).get("FRESH")}')
    design = [r for r in rows if r.get('population') == 'FRESH' and r['arm'] in ARMS and r['seed'] in SEEDS and r['task'] in fresh]
    keys = collections.Counter((r['task'], r['arm'], r['seed']) for r in design)
    print(f'episodes in the file: {len(design)} of {len(fresh) * len(ARMS) * len(SEEDS)} expected; repeated keys: '
          f'{sum(1 for v in keys.values() if v > 1)}')

    part_fresh(design, fresh)   # N1 of pre-registration 08, on arm N

    print('\nPRE-REGISTRATION 09: N as shipped, NA addresses in the graph tools\' answers, NAF addresses and bounds honored')
    usable = collections.defaultdict(dict)
    errs = collections.Counter()
    for r in design:
        if r.get('error'):
            errs[(r['arm'], error_kind(r))] += 1
        else:
            usable[r['task']][(r['arm'], r['seed'])] = r
    for a in ARMS:
        kinds = {k: v for (arm, k), v in sorted(errs.items()) if arm == a}
        print(f'  episodes that ended in an error, arm {a}: {sum(kinds.values())} {kinds} (excluded)')
    need = {(a, s) for a in ARMS for s in SEEDS}
    complete = sorted(t for t in fresh if need <= set(usable.get(t, {})))
    print(f'  complete tasks: {len(complete)} of {len(fresh)}')
    if not complete:
        return
    ep = {(t, a, s): episode(t, a, usable[t][(a, s)]) for t in complete for a in ARMS for s in SEEDS}

    print('  graph tools in the episodes (complete tasks):')
    for a in ARMS:
        es = [ep[(t, a, s)] for t in complete for s in SEEDS]
        with_call = sum(1 for e in es if e['first_graph_step'] is not None)
        qual = sum(1 for e in es if e['qualifying'])
        tools = collections.Counter()
        for e in es:
            tools.update(e['graph_calls'])
        firsts = [e['first_graph_step'] for e in es if e['first_graph_step'] is not None]
        print(f'    {a:3s}: episodes with an executed graph call {with_call} of {len(es)}; with a qualifying answer {qual}; '
              f'calls by tool {dict(tools)}; median model call of the first graph call {st.median(firsts) if firsts else "n/a"}')

    tab = {a: {t: [ep[(t, a, s)]['Ynext'] for s in SEEDS] for t in complete} for a in ARMS}
    for a in ARMS:
        print(f'  Ynext {a:3s}: {pct(boot_ci(tab[a]))} | {raw(tab[a])}')
    a1 = diff_ci(tab['NA'], tab['N'])
    print(f'  A1 NA - N on Ynext, clustered by task ({len(complete)} tasks): {dpt(a1)}')
    if a1[0] is not None:
        print('  A1 verdict: ' + ('addresses in the graph tools\' own answers bring the next call to a returned entity\'s code'
                                  if a1[1] > 0 else 'no detectable difference'))
    print(f'  descriptive NAF - N on Ynext: {dpt(diff_ci(tab["NAF"], tab["N"]))}')
    print('  descriptive, among episodes with a qualifying graph answer:')
    for a in ARMS:
        es = [ep[(t, a, s)] for t in complete for s in SEEDS if ep[(t, a, s)]['qualifying']]
        if not es:
            continue
        nt = collections.Counter(e['next_tool'] for e in es)
        print(f'    {a:3s}: n {len(es)}; next call reads a returned entity {sum(e["Ynext"] for e in es)} '
              f'({100 * sum(e["Ynext"] for e in es) / len(es):.1f}%); next call is a shell command naming a returned entity '
              f'or its file {sum(e["next_locates"] for e in es)} ({100 * sum(e["next_locates"] for e in es) / len(es):.1f}%); '
              f'a returned entity is read at some later call {sum(e["later_touch"] for e in es)} '
              f'({100 * sum(e["later_touch"] for e in es) / len(es):.1f}%); next tool {dict(nt)}')

    with_gold = [t for t in complete if fresh[t]['gold_files']]
    scored = {}
    for t in with_gold:
        state = {'task': t, 'true_neighbors': [], 'neighbor_spans': {}}
        gold = {'gold_files': fresh[t]['gold_files'], 'unopened_gold_files': sorted(fresh[t]['gold_files'])}
        for a in ARMS:
            for s in SEEDS:
                scored[(t, a, s)] = score(state, gold, usable[t][(a, s)])
    print(f'\n  reaching the fix within eight calls (tasks whose gold patch modifies a file: {len(with_gold)}):')
    for y in ('Yline', 'Yfile'):
        t_ = {a: {t: [scored[(t, a, s)][y] for s in SEEDS] for t in with_gold} for a in ARMS}
        for a in ARMS:
            print(f'    {y} {a:3s}: {pct(boot_ci(t_[a]))} | {raw(t_[a])}')
        if y == 'Yline':
            a2 = diff_ci(t_['NAF'], t_['N'])
            print(f'    A2 NAF - N on Yline, clustered by task: {dpt(a2)}')
            if a2[0] is not None:
                print('    A2 verdict: ' + ('the patched harness brings the agent to the fix\'s lines within eight calls of a fresh start'
                                            if a2[1] > 0 else 'no detectable gain'))
        print(f'    descriptive {y}: NA - N {dpt(diff_ci(t_["NA"], t_["N"]))}; NAF - NA {dpt(diff_ci(t_["NAF"], t_["NA"]))}')
    print('  descriptive, shown a changed line by the end of each model call (percent of episodes):')
    for a in ARMS:
        firsts = [scored[(t, a, s)]['first_Yline'] for t in with_gold for s in SEEDS]
        cum = [100 * sum(1 for f in firsts if f is not None and f <= c) / len(firsts) for c in range(1, K + 1)]
        print(f'    {a:3s}: ' + ', '.join(f'{c}: {v:.1f}' for c, v in enumerate(cum, 1))
              + f'; mean calls to the first changed line, never counted as {K + 1}: {st.mean(f if f is not None else K + 1 for f in firsts):.2f}')

    print('\n  descriptive, executed read_file calls with a line bound, by arm (complete tasks):')
    for a in ARMS:
        n_r = n_m = n_l1 = 0
        for t in complete:
            for s in SEEDS:
                for _i, m, start in ranged_reads(usable[t][(a, s)]):
                    n_r += 1
                    n_m += m
                    n_l1 += int(bool(m) and start == 1)
        print(f'    {a:3s}: {n_r} reads, mangled {n_m} ({100 * n_m / n_r:.1f}%); mangled reads that returned the file from line 1: {n_l1}'
              if n_r else f'    {a:3s}: no ranged read')
    print('  descriptive, stop reasons and calls:')
    for a in ARMS:
        rs = [usable[t][(a, s)] for t in complete for s in SEEDS]
        c = collections.Counter(stop_group(r.get('stop')) for r in rs)
        shares = ', '.join(f'{g} {100 * v / len(rs):.1f}%' for g, v in sorted(c.items(), key=lambda x: (-x[1], x[0])))
        print(f'    {a:3s}: n {len(rs)}; {shares}; mean model calls {st.mean(len(r.get("steps") or []) for r in rs):.2f}; '
              f'mean executed calls {st.mean(r.get("executed_calls", 0) for r in rs):.2f}')

    n_addr = n_diff = 0
    for t in complete:
        for a in ('NA', 'NAF'):
            for s in SEEDS:
                for step in usable[t][(a, s)].get('steps') or []:
                    for c in step['calls']:
                        if c['function_name'] in GRAPH_TOOLS and c['executed']:
                            for name, f, lines in printed_addresses(c['function_name'], c.get('result')):
                                sp = N.span(t, name)
                                want = (sp['path'], f"{sp['start']}-{sp['end']}" if sp and sp['end'] is not None else None) if sp else (None, None)
                                n_addr += 1
                                n_diff += int((f, lines) != want)
    print(f'\n  check: addresses printed in the answers of NA and NAF that differ from the resolver: {n_diff} of {n_addr}')


if __name__ == '__main__':
    main()
