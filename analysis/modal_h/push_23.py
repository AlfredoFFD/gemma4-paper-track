"""Experiment 23: what arm PE pushes at the agent after a file read. One module, used by the runner (in the container),
by analysis/explore_push_23.py (the offline exposure count) and by analysis/analyze_23.py.

neighbor_sets(graph)  {node: set of neighbors} of a task's code graph, built as analysis/fork_states.py graph_for builds
                      `nbr` (every edge both ways; self-loops kept)
harness_neighbors     what get_code_neighbors returns: the sorted neighbors, the first 50 (fork_states.harness_neighbors)
Pusher(nbr, spans)    the state of one session; spans is the address table of the task ({node: {"file", "lines"}},
                      analysis/make_spans_g.py and make_spans_h.py, as `spans_of` of the runner of 14 reads it).
  .on_read(path, first, last)   called after every read_file answer of status ok with the lines it returned; returns
                      the value of the key `code_graph` or None. The rules:
      SHOWN NODE   a node whose span ("lines") lies in the file read and overlaps the returned lines
      sources      the shown nodes of this read not yet used as a source, largest overlap first (ties by name), at most 2
      neighbors    per source, harness_neighbors without nodes shown by an earlier or this read, without nodes listed by
                   an earlier push, without nodes that have no line range; the first 8 in that order, 4 per source when
                   there are two sources; a source with none is left out of the value (it still counts as used)
      value        [{"node": <source>, "neighbors": [{"name": <node>, "file": <path>, "lines": "<s>-<e>"}, ...]}, ...]
      at most MAX_PUSHES reads per session get the key (the first that qualify); a read with nothing to list gets none
as_shown(value, arm)  what the agent receives: arm PE the value unchanged; arm PH (pushed names) the same value with
                      each neighbor entry reduced to {"name": <node>} (same reads, sources, neighbors, order and caps;
                      the Pusher's state and rules do not depend on the arm)
"""
import collections

MAX_NEIGHBORS = 50
MAX_SOURCES = 2
MAX_ENTRIES = 8
MAX_PUSHES = 10
KEY = 'code_graph'
ARMS = ('PH', 'PE')  # pushed names, pushed with addresses


def as_shown(value, arm):
    """The value of the key as the agent of `arm` receives it (a new object; `value` is not changed)."""
    if arm == 'PE':
        return [{'node': v['node'], 'neighbors': [dict(n) for n in v['neighbors']]} for v in value]
    if arm == 'PH':
        return [{'node': v['node'], 'neighbors': [{'name': n['name']} for n in v['neighbors']]} for v in value]
    raise ValueError(f'not a push arm: {arm}')


def neighbor_sets(graph):
    nbr = collections.defaultdict(set)
    for e in graph['edges']:
        nbr[e['source']].add(e['target'])
        nbr[e['target']].add(e['source'])
    return nbr


def harness_neighbors(nbr, node):
    return sorted(nbr.get(node, set()))[:MAX_NEIGHBORS]


def span(entry):
    """(start, end) of an address entry, or None."""
    try:
        s, e = str(entry.get('lines') or '').split('-')
        return int(s), int(e)
    except (ValueError, AttributeError):
        return None


def norm(path):
    p = str(path or '').strip()
    for pre in ('/workspace/', 'workspace/', './'):
        while p.startswith(pre):
            p = p[len(pre):]
    return p


def shown_range(response):
    """(first, last) line a read_file answer of status ok returned; a read cut by the character limit ends where its
    content ends. None for anything else."""
    if not isinstance(response, dict) or response.get('status') != 'ok':
        return None
    s, e = response.get('start_line'), response.get('end_line')
    if not isinstance(s, int) or not isinstance(e, int) or e < s:
        return None
    content = response.get('content') or ''
    if response.get('is_truncated') and content:
        e = min(e, s + content.count('\n'))
    return s, e


class Pusher:
    def __init__(self, nbr, spans):
        self.nbr = nbr
        self.spans = spans
        self.by_file = collections.defaultdict(list)
        for name, entry in spans.items():
            r = span(entry)
            if r is not None:
                self.by_file[norm(entry.get('file'))].append((name, r[0], r[1]))
        self.shown, self.sources, self.listed = set(), set(), set()
        self.pushes = 0

    def shown_by(self, path, first, last):
        """[(node, overlap)] of the nodes a read of `path`, lines first..last, shows."""
        out = []
        for name, s, e in self.by_file.get(norm(path), []):
            o = min(e, last) - max(s, first) + 1
            if o > 0:
                out.append((name, o))
        return out

    def on_read(self, path, first, last):
        shown = self.shown_by(path, first, last)
        self.shown.update(n for n, _o in shown)
        if self.pushes >= MAX_PUSHES:
            return None
        cands = sorted(((n, o) for n, o in shown if n not in self.sources), key=lambda x: (-x[1], x[0]))[:MAX_SOURCES]
        if not cands:
            return None
        cap = MAX_ENTRIES if len(cands) == 1 else MAX_ENTRIES // MAX_SOURCES
        value = []
        for node, _o in cands:
            self.sources.add(node)
            keep = []
            for m in harness_neighbors(self.nbr, node):
                if m in self.shown or m in self.listed or span(self.spans.get(m) or {}) is None:
                    continue
                keep.append(m)
                if len(keep) == cap:
                    break
            if keep:
                self.listed.update(keep)
                value.append({'node': node, 'neighbors': [{'name': m, 'file': self.spans[m]['file'],
                                                           'lines': self.spans[m]['lines']} for m in keep]})
        if not value:
            return None
        self.pushes += 1
        return value
